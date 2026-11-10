"""Finish the published copy of the site in _site/ for search engines.

- fills the per-group schedule table (today and tomorrow) into _site/index.html,
  so the current schedule is plain indexable text;
- stamps dateModified in the structured data;
- writes sitemap.xml with the schedule's fetch time as lastmod.

usage: python3 scripts/build_site.py _site
"""
import json, re, sys, html, pathlib, datetime
from zoneinfo import ZoneInfo

site = pathlib.Path(sys.argv[1])
root = pathlib.Path(__file__).resolve().parent.parent
d = json.loads((root / "schedule.json").read_text())
raw, known = d.get("raw", {}), d.get("lastKnown", {})
fetched = d.get("fetchedAt") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
def day_name(iso):
    y, m, dd = map(int, iso.split("-"))
    return f"{dd} {MONTHS[m - 1]}"

def hhmm(m):
    return "24:00" if m >= 1440 else f"{m // 60:02d}:{m % 60:02d}"

def off_ranges(slots):
    out = []
    for sl in slots:
        if sl.get("type") == "Definite":
            if out and out[-1][1] == sl["start"]:
                out[-1][1] = sl["end"]
            else:
                out.append([sl["start"], sl["end"]])
    return ", ".join(f"{hhmm(a)}–{hhmm(b)}" for a, b in out) or "без відключень"

def cell(group, entry):
    if not entry:
        return "—", False
    st, date = entry.get("status", ""), (entry.get("date") or "")[:10]
    if "Emergency" in st:
        lk = known.get(group, {})
        past = sorted(x for x in lk if x <= date) or sorted(lk)
        if past:
            return off_ranges(lk[past[-1]]), True
        return "екстрені відключення, графік не діє", True
    if st == "WaitingForSchedule" or not entry.get("slots"):
        return "графік ще не опубліковано", False
    return off_ranges(entry["slots"]), False

groups = sorted(raw, key=lambda k: [int(x) for x in re.findall(r"\d+", k)])
first = raw[groups[0]] if groups else {}
dates = [((first.get(k) or {}).get("date") or "")[:10] for k in ("today", "tomorrow")]
rows, emergency = [], False
for g in groups:
    t, e1 = cell(g, raw[g].get("today"))
    m, e2 = cell(g, raw[g].get("tomorrow"))
    emergency |= e1 or e2
    rows.append(f"<tr><td>{html.escape(g)}</td><td>{html.escape(t)}</td><td>{html.escape(m)}</td></tr>")

kyiv = datetime.datetime.fromisoformat(fetched.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Kyiv"))
h_today = f"Сьогодні, {day_name(dates[0])}" if dates[0] else "Сьогодні"
h_tom = f"Завтра, {day_name(dates[1])}" if dates[1] else "Завтра"
table = (
    f'<h2 class="seo-h">Графік відключень світла в Києві на {day_name(dates[0]) if dates[0] else "сьогодні"} по групах YASNO</h2>'
    f'<p class="note">Години без світла за графіком ДТЕК для кожної з {len(groups)} груп. Дані YASNO отримано '
    f'{kyiv.day} {MONTHS[kyiv.month - 1]} о {kyiv:%H:%M}. Свою групу дізнайтеся, натиснувши на будинок на карті.'
    + (" Зараз діють екстрені відключення: у таблиці останній відомий графік, але світла може не бути й поза ним." if emergency else "")
    + "</p>"
    f'<table class="gt"><thead><tr><th>Група</th><th>{h_today}</th><th>{h_tom}</th></tr></thead><tbody>'
    + "".join(rows) + "</tbody></table>"
)

idx = site / "index.html"
page = idx.read_text()
page = re.sub(r"<!--GROUPS-->.*?<!--/GROUPS-->", lambda _: "<!--GROUPS-->" + table + "<!--/GROUPS-->", page, count=1, flags=re.S)
page = page.replace("__MODIFIED__", fetched)
idx.write_text(page)

(site / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"  <url><loc>https://svitlo-kyiv.online/</loc><lastmod>{fetched}</lastmod><changefreq>hourly</changefreq><priority>1.0</priority></url>\n"
    "</urlset>\n")
print(f"site built: {len(groups)} groups, emergency={emergency}, lastmod={fetched}")
