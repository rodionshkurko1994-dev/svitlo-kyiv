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
    return h.replace("A", "А").replace("B", "В").replace("E", "Е").replace("K", "К")

street_cache = {}

def street_id(osm_name):
    if osm_name in street_cache:
        return street_cache[osm_name]
    kind, toks = norm_street(osm_name)
    sid = None
    if toks:
        key = max(toks, key=len)  # the longest word is usually the distinctive one
        res = get("streets", query=key) or []
        best = None
        for r in res:
            k2, t2 = norm_street(r.get("value", ""))
            if "(" in r.get("value", "") or "р-н" in r.get("value", ""):
                score_pen = 1
            else:
                score_pen = 0
            if t2 == toks:
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

def house_id(sid, house):
    want = norm_house(house)
    m = re.match(r"\d+", want)
    if not m:
        return None
    res = get("houses", streetId=sid, query=m.group(0)) or []
    for r in res:
        if norm_house(r.get("value", "")) == want:
            return r["id"]
    # fall back to the plain number (e.g. OSM "12" vs YASNO "12 ввод 1")
    for r in res:
        if norm_house(r.get("value", "")).split("ВВОД")[0] == want:
            return r["id"]
    return None

def main(inp, outp):
    rows = json.load(open(inp))
    t0 = time.time()
    out = []
    for i, a in enumerate(rows):
        rec = dict(a)
        sid = street_id(a["street"])
        if sid is None:
            rec["status"] = "street_not_found"
        else:
            hid = house_id(sid, a["house"])
            if hid is None:
                rec["status"] = "house_not_found"
            else:
                g = get("group", streetId=sid, houseId=hid)
                if g and "group" in g:
                    rec.update(status="ok", group=g["group"], subgroup=g.get("subgroup"), streetId=sid, houseId=hid)
                else:
                    rec["status"] = "group_error"
        stats[rec["status"]] += 1
        out.append(rec)
        if (i + 1) % 50 == 0:
            print(f"{i+1}/{len(rows)} done, {dict(stats)}", flush=True)
    ok = [r for r in out if r["status"] == "ok"]
    with_pred = [r for r in ok if r.get("pred") is not None]
    agree = sum(1 for r in with_pred if r["group"] == r["pred"])
    # schedules repeat every 12 groups today; also count agreement of the actual schedule pattern
    agree12 = sum(1 for r in with_pred if (r["group"] - 1) % 12 == (r["pred"] - 1) % 12)
    summary = {
        "addresses": len(rows), "found": len(ok), "minutes": round((time.time() - t0) / 60, 1),
        "stats": dict(stats), "map_guess_checked": len(with_pred),
        "map_guess_same_group": agree, "map_guess_same_schedule_pattern": agree12,
        "distinct_groups": len({r["group"] for r in ok}),
    }
    json.dump({"summary": summary, "results": out}, open(outp, "w"), ensure_ascii=False, indent=0)
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False))
    print(f"::notice::found {len(ok)}/{len(rows)}; map guess correct {agree}/{len(with_pred)} (same pattern {agree12}); {dict(stats)}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
