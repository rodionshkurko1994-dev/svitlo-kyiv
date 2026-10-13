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
    raise SystemExit(f"fetch failed: {last}")

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
    raise SystemExit(f"unexpected data: {err}")

old = {}
if OUT.exists():
    try:
        old = json.loads(OUT.read_text()).get("raw", {})
    except Exception:
        old = {}
if old == raw:
    print("unchanged")
    sys.exit(0)

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
OUT.write_text(json.dumps({"fetchedAt": now, "raw": raw}, ensure_ascii=False, separators=(",", ":")))
print("changed")
