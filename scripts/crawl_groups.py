"""Look up the YASNO schedule group for a list of Kyiv addresses (OSM names).

Usage: python3 scripts/crawl_groups.py data/test_addresses.json data/test_groups.json

For every address: find the YASNO street id (street search), then the house id
(house search), then the group. Requests are spaced out so YASNO is not
hammered. Results and a summary (match rate, agreement with the map's current
guess) are written to the output file; the summary is also printed for the
Actions log.
"""
import json, re, sys, time, urllib.parse, urllib.request, collections

BASE = "https://app.yasno.ua/api/blackout-service/public/shutdowns/addresses/v2/"
COMMON = {"regionId": "25", "dsoId": "902"}
DELAY = 0.8  # seconds between requests
UA = "Mozilla/5.0 (svitlo-kyiv map; +https://svitlo-kyiv.online)"

stats = collections.Counter()
DEBUG = "--debug" in sys.argv
debug_log = {}

def get(path, **params):
    q = urllib.parse.urlencode({**COMMON, **params})
    req = urllib.request.Request(BASE + path + "?" + q, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(4):
        time.sleep(DELAY if attempt == 0 else DELAY * 4 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                stats["requests"] += 1
                return json.load(r)
        except urllib.error.HTTPError as e:
            stats[f"http_{e.code}"] += 1
            if e.code in (400, 404):
                return None
        except Exception:
            stats["net_errors"] += 1
    return None

TYPES = [
    (r"\bвулиця\b|\bвул\b", "вул"), (r"\bпроспект\b|\bпросп\b|\bпр-т\b", "просп"),
    (r"\bпровулок\b|\bпров\b", "пров"), (r"\bбульвар\b|\bбульв\b|\bб-р\b", "бульв"),
    (r"\bплоща\b|\bпл\b", "пл"), (r"\bнабережна\b|\bнаб\b", "наб"), (r"\bшосе\b", "шосе"),
    (r"\bузвіз\b", "узвіз"), (r"\bтупик\b", "тупик"), (r"\bалея\b", "алея"), (r"\bдорога\b", "дорога"),
    (r"\bпроїзд\b", "проїзд"), (r"\bмайдан\b", "майдан"), (r"\bлінія\b", "лінія"),
]
DROP = {"академіка", "генерала", "гетьмана", "маршала", "професора", "отамана", "князя", "святого"}

def norm_street(s):
    s = s.lower().replace("’", "'").replace("ʼ", "'").replace("`", "'").replace("ё", "е")
    s = re.sub(r"\(.*?\)", " ", s)
    kind = None
    for pat, canon in TYPES:
        if re.search(pat, s):
            kind = kind or canon
            s = re.sub(pat, " ", s)
    toks = [t for t in re.split(r"[\s,.\-]+", s) if t and t not in DROP]
    return kind, frozenset(toks)

def norm_house(h):
    h = h.upper().replace(" ", "").replace("-", "").replace("“", "").replace("”", "").replace('"', "")
    h = h.replace("A", "А").replace("B", "В").replace("E", "Е").replace("K", "К").replace("C", "С")
    h = re.sub(r"ВВОД\d*$", "", h)
    h = re.sub(r",?КОРП(УС)?\.?", "К", h).replace(",К", "К")
    h = re.sub(r"/(?=[А-ЯІЇЄҐ])", "", h)      # 28/Б -> 28Б
    h = re.sub(r"К\.?(\d+)$", r"К\1", h)     # 60К.5 -> 60К5
    return h

def house_variants(h):
    """Spellings to try for an OSM number, most exact first."""
    w = norm_house(h)
    out = [w]
    m = re.match(r"^(\d+[А-ЯІЇЄҐ]?)К(\d+)$", w)       # 1К1 / 60К5 -> 1/К1, 60/5
    if m:
        out += [f"{m.group(1)}/К{m.group(2)}", f"{m.group(1)}/{m.group(2)}", m.group(1)]
    return out

street_cache = {}

def compatible(a, b):
    """Same words up to shortened first names: every word has a partner sharing its first 4+ letters."""
    if len(a) != len(b) or not a:
        return False
    def has(x, ys):
        return any(x == y or (len(x) >= 4 and len(y) >= 4 and (x.startswith(y[:4]) and y.startswith(x[:4]))) for y in ys)
    return all(has(x, b) for x in a) and all(has(y, a) for y in b)

def street_id(osm_name):
    if osm_name in street_cache:
        return street_cache[osm_name]
    kind, toks = norm_street(osm_name)
    sid = None
    if toks:
        key = max(toks, key=len)  # the longest word is usually the distinctive one
        res = get("streets", query=key) or []
        if DEBUG:
            debug_log.setdefault(osm_name, {})["streets"] = res[:15]
        best = None
        for r in res:
            k2, t2 = norm_street(r.get("value", ""))
            if "(" in r.get("value", "") or "р-н" in r.get("value", ""):
                score_pen = 1
            else:
                score_pen = 0
            if t2 == toks or compatible(toks, t2):
                score = 3 if (k2 == kind or kind is None or k2 is None) else 1
            elif toks <= t2 or t2 <= toks:
                score = 2 if (k2 == kind or kind is None or k2 is None) else 0
            else:
                continue
            score -= score_pen
            if score > 0 and (best is None or score > best[0]):
                best = (score, r["id"])
        sid = best[1] if best else None
    street_cache[osm_name] = sid
    return sid

house_cache = {}

def houses_for(sid, number):
    key = (sid, number)
    if key not in house_cache:
        house_cache[key] = get("houses", streetId=sid, query=number) or []
    return house_cache[key]

def house_id(sid, house):
    """Return (houseId, exact) or (None, None)."""
    variants = house_variants(house)
    m = re.match(r"\d+", variants[0])
    if not m:
        return None, None
    res = houses_for(sid, m.group(0))
    if DEBUG:
        debug_log.setdefault(f"{sid}|{house}", {})["houses"] = res[:20]
    norm = [(norm_house(r.get("value", "")), r["id"]) for r in res]
    for v in variants:
        for n, i in norm:
            if n == v:
                return i, True
    # same base number with a different letter/corpus (e.g. 39 vs 39В): likely the same complex
    base = m.group(0)
    for n, i in norm:
        if re.match(rf"^{base}(?!\d)", n):
            return i, False
    return None, None

def load_cache(path):
    if path:
        try:
            c = json.load(open(path))
            street_cache.update({k: v for k, v in c.items()})
        except FileNotFoundError:
            pass

def save_cache(path):
    if path:
        json.dump(street_cache, open(path, "w"), ensure_ascii=False, indent=0, sort_keys=True)

def main(inp, outp, cache=None):
    load_cache(cache)
    rows = json.load(open(inp))
    t0 = time.time()
    out = []
    for i, a in enumerate(rows):
        rec = dict(a)
        sid = street_id(a["street"])
        if sid is None:
            rec["status"] = "street_not_found"
        else:
            hid, exact = house_id(sid, a["house"])
            if hid is None:
                rec["status"] = "house_not_found"
            else:
                g = get("group", streetId=sid, houseId=hid)
                if g and "group" in g:
                    rec.update(status="ok", group=g["group"], subgroup=g.get("subgroup"), streetId=sid, houseId=hid, exact=exact)
                else:
                    rec["status"] = "group_error"
        stats[rec["status"]] += 1
        out.append(rec)
        if (i + 1) % 50 == 0:
            print(f"{i+1}/{len(rows)} done, {dict(stats)}", flush=True)
    ok = [r for r in out if r["status"] == "ok"]
    summary_exact = sum(1 for r in ok if r.get("exact"))
    with_pred = [r for r in ok if r.get("pred") is not None]
    agree = sum(1 for r in with_pred if r["group"] == r["pred"])
    # schedules repeat every 12 groups today; also count agreement of the actual schedule pattern
    agree12 = sum(1 for r in with_pred if (r["group"] - 1) % 12 == (r["pred"] - 1) % 12)
    summary = {
        "addresses": len(rows), "found": len(ok), "minutes": round((time.time() - t0) / 60, 1),
        "stats": dict(stats), "map_guess_checked": len(with_pred),
        "map_guess_same_group": agree, "map_guess_same_schedule_pattern": agree12,
        "distinct_groups": len({r["group"] for r in ok}), "exact_house_match": summary_exact,
    }
    payload = {"summary": summary, "results": out}
    if DEBUG:
        payload["debug"] = debug_log
    json.dump(payload, open(outp, "w"), ensure_ascii=False, indent=0)
    save_cache(cache)
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False))
    print(f"::notice::found {len(ok)}/{len(rows)}; map guess correct {agree}/{len(with_pred)} (same pattern {agree12}); {dict(stats)}")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cache = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--cache=")), None)
    main(args[0], args[1], cache)
