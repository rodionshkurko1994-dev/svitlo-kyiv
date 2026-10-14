"""Fetch the Kyiv planned-outage schedule from YASNO and write schedule.json.

Exit code 0 with "changed" / "unchanged" on stdout; non-zero if the data
could not be fetched or looks wrong (so the failure is visible in Actions).
"""
import json, sys, urllib.request, datetime, pathlib

URL = "https://app.yasno.ua/api/blackout-service/public/shutdowns/regions/25/dsos/902/planned-outages"
OUT = pathlib.Path(__file__).resolve().parent.parent / "schedule.json"

def fetch():
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (svitlo-kyiv map; +https://github.com/rodionshkurko1994-dev/svitlo-kyiv)",
        "Accept": "application/json",
    })
    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # network hiccup, retry
            last = e
    detail = ""
    if hasattr(last, "code"):
        try: detail = f" (HTTP {last.code}: {last.read()[:200]!r})"
        except Exception: detail = f" (HTTP {last.code})"
    print(f"::error::YASNO fetch failed: {last!r}{detail}")
    raise SystemExit(1)

def valid(raw):
    if not isinstance(raw, dict) or len([k for k in raw if k.endswith(".1")]) < 60:
        return "fewer than 60 groups"
    for k, g in raw.items():
        for day in ("today", "tomorrow"):
            d = g.get(day) or {}
            s = d.get("slots") or []
            if s and (s[0]["start"] != 0 or s[-1]["end"] != 1440 or any(a["end"] != b["start"] for a, b in zip(s, s[1:]))):
                if d.get("status") != "WaitingForSchedule":
                    return f"bad slots in {k} {day}"
    return None

raw = fetch()
err = valid(raw)
if err:
    print(f"::error::YASNO data rejected: {err}")
    raise SystemExit(1)

def remember(known, raw):
    """Keep each group's latest real schedules (by date) so the map can fall back
    to them while YASNO shows emergency outages instead of a schedule."""
    for k, g in raw.items():
        for day in ("today", "tomorrow"):
            d = g.get(day) or {}
            if d.get("status") == "ScheduleApplies" and d.get("slots") and d.get("date"):
                known.setdefault(k, {})[d["date"][:10]] = d["slots"]
    for k in known:  # keep the 3 most recent dates
        for date in sorted(known[k])[:-3]:
            del known[k][date]
    return known

old, known = {}, {}
if OUT.exists():
    try:
        prev = json.loads(OUT.read_text())
        old, known = prev.get("raw", {}), prev.get("lastKnown", {})
    except Exception:
        pass
known_before = json.dumps(known, sort_keys=True)
known = remember(remember(known, old), raw)
if old == raw and json.dumps(known, sort_keys=True) == known_before:
    print("unchanged")
    sys.exit(0)

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
OUT.write_text(json.dumps({"fetchedAt": now, "raw": raw, "lastKnown": known}, ensure_ascii=False, separators=(",", ":")))
print("changed")
