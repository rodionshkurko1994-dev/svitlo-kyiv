"""Recolour the city model with fresh YASNO groups, without OpenStreetMap.

Reads the crawl results (data/full/groups_*.json, data/test_groups*.json),
each building's address (data/building_addr.json, same order as the model)
and the model itself (city_v2.txt, base64), then rewrites only the 'zone',
'src' and 'roadZone' arrays in place. Also refreshes the coverage figures
shown on the page (index.html).

usage: python3 tools/apply_groups.py
"""
import base64, glob, json, re, pathlib
import numpy as np
from scipy.spatial import cKDTree

ROOT = pathlib.Path(__file__).resolve().parent.parent
NEIGH, ROAD_R = 150.0, 250.0

header = json.loads((ROOT / "data/city_header.json").read_text())
buf = bytearray(base64.b64decode((ROOT / "city_v2.txt").read_bytes()))

def view(name, dtype):
    off, ln = header[name]
    return np.frombuffer(buf, dtype=dtype, count=ln // np.dtype(dtype).itemsize, offset=off)

def put(name, arr, dtype):
    off, ln = header[name]
    data = np.asarray(arr, dtype=dtype).tobytes()
    assert len(data) == ln, (name, len(data), ln)
    buf[off:off + ln] = data

# --- addresses -> group
found = {}
files = sorted(glob.glob(str(ROOT / "data/full/groups_*.json"))) + sorted(glob.glob(str(ROOT / "data/test_groups*.json")))
for f in files:
    for r in json.load(open(f))["results"]:
        if r.get("status") == "ok":
            found.setdefault((r["street"].strip(), r["house"].strip()), (int(r["group"]), bool(r.get("exact", True))))

keys = json.loads((ROOT / "data/building_addr.json").read_text())
ring_count = view("ringCount", np.uint8); ring_len = view("ringLen", np.uint16); coords = view("coords", np.int16)
n = len(ring_count)
assert n == len(keys), (n, len(keys))

# centroids: mean of each building's outer ring
cx = np.zeros(n); cz = np.zeros(n)
ri = 0; pi = 0
for b in range(n):
    for r in range(int(ring_count[b])):
        L = int(ring_len[ri + r])
        if r == 0:
            seg = coords[pi * 2:(pi + L) * 2].reshape(-1, 2)
            cx[b], cz[b] = seg[:, 0].mean(), seg[:, 1].mean()
        pi += L
    ri += int(ring_count[b])

zone = np.zeros(n, np.uint8); src = np.zeros(n, np.uint8)
for b, k in enumerate(keys):
    if k:
        g = found.get((k[0], k[1]))
        if g:
            zone[b] = g[0]; src[b] = 1 if g[1] else 2

known = np.where(src > 0)[0]
tree = cKDTree(np.c_[cx[known], cz[known]])
miss = np.where(src == 0)[0]
d, i = tree.query(np.c_[cx[miss], cz[miss]], distance_upper_bound=NEIGH)
ok = np.isfinite(d)
zone[miss[ok]] = zone[known[i[ok]]]; src[miss[ok]] = 3

# roads: each point takes the nearest known building within ROAD_R; rail stays 0
road_rank = view("roadRank", np.uint8); road_len = view("roadLen", np.uint16)
rc = view("roadCoords", np.int16).reshape(-1, 2)
d, i = tree.query(rc.astype(float), distance_upper_bound=ROAD_R)
rz = np.where(np.isfinite(d), zone[known[np.minimum(i, len(known) - 1)]], 0).astype(np.uint8)
p = 0
for k in range(len(road_len)):
    if road_rank[k] == 9:
        rz[p:p + int(road_len[k])] = 0
    p += int(road_len[k])

put("zone", zone, np.uint8); put("src", src, np.uint8); put("roadZone", rz, np.uint8)
(ROOT / "city_v2.txt").write_bytes(base64.b64encode(bytes(buf)))

# --- coverage figures on the page
cnt = np.bincount(src, minlength=4)
stats = {"buildings": int(n), "byAddress": int(cnt[1]), "byAddressNear": int(cnt[2]), "byNeighbour": int(cnt[3]),
         "noData": int(cnt[0]), "addresses": len(found)}
html = (ROOT / "index.html").read_text()
html = re.sub(r'"stats":\{[^}]*\}', '"stats":' + json.dumps(stats, separators=(",", ":")), html, count=1)
pct = round(100 * (stats["byAddress"] + stats["byAddressNear"]) / n)
pctN = round(100 * stats["byNeighbour"] / n)
addr = format(stats["addresses"], ",").replace(",", " ")
html = re.sub(r"Я запитав групу для [\d  ]+ адрес з OpenStreetMap: \d+% будинків на карті пофарбовані за власною адресою, ще \d+%",
              f"Я запитав групу для {addr} адрес з OpenStreetMap: {pct}% будинків на карті пофарбовані за власною адресою, ще {pctN}%",
              html, count=1)
(ROOT / "index.html").write_text(html)
print("groups applied:", stats)
