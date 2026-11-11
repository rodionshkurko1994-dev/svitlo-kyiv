"""Turn the Kyivpastrans GTFS timetable into a compact file for the map (transit.bin).

usage: python3 scripts/build_transit.py <gtfs.zip> <out transit.bin>
       python3 scripts/build_transit.py --same new.bin old.bin   (exit 0 when only the build time differs)

The feed's own route lines are often just a few points, so each one is replaced by the
matching OpenStreetMap route (data/osm_routes.json, same number and type, closest trace),
cut between the trip's first and last stop. Lines with no OSM match are routed through
their points along the street / tram-track graph (data/road_graph.npz, shortest path).

Layout (little-endian):
  uint32 header length N, then N bytes of JSON header, padded to 4 bytes, then the arrays
  the header lists as [byte offset, byte length] (offsets from the start of the arrays):
    shapeLen  uint16[shapes]        points per shape
    shapeXZ   int16[2*points]       x east, z south in metres, same projection as the city model
    tripShape uint16[trips]         shape index
    tripRoute uint16[trips]         route index (header.routes)
    tripStart uint16[trips]         departure from the first stop, minutes after service-day midnight
    tripEnd   uint16[trips]         arrival at the last stop, minutes (can exceed 1440)
    tripDays  uint8[trips]          bit 0 = Monday … bit 6 = Sunday
  header.routes = [[short name, long name, kind]], kind 0 tram, 1 trolleybus, 2 bus
Trips are sorted by start time. Vehicles move at even speed along the shape between the first
and last stop: the feed gives times for the terminals, not for every stop.
"""
import csv, io, json, math, os, re, sys, zipfile, datetime, collections, struct
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree

LAT0, LON0 = 50.45, 30.52
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110570
def P(lon, lat):
    return ((lon - LON0) * KX, -(lat - LAT0) * KY)

KIND = {"0": 0, "11": 1, "3": 2}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def _content(path):
    """everything but the build time, to tell whether a rebuilt file really changed"""
    b = open(path, "rb").read(); n = struct.unpack("<I", b[:4])[0]
    h = json.loads(b[4:4 + n]); h.pop("built", None); h.pop("feedVersion", None)
    return json.dumps(h, sort_keys=True).encode() + b[4 + n:]
if sys.argv[1] == "--same":              # build_transit.py --same new.bin old.bin → exit 0 if equal
    try:
        sys.exit(0 if _content(sys.argv[2]) == _content(sys.argv[3]) else 1)
    except Exception:
        sys.exit(1)

src, out = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(src)
def rows(name):
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))
def minutes(t):
    h, m, s = (int(x) for x in t.split(":"))
    return h * 60 + m + (1 if s >= 30 else 0)

routes = {}
for r in rows("routes.txt"):
    if r["route_type"] in KIND:
        routes[r["route_id"]] = [r["route_short_name"].strip(), (r.get("route_long_name") or "").strip(), KIND[r["route_type"]]]

masks = {}
for c in rows("calendar.txt"):
    masks[c["service_id"]] = sum(1 << i for i, d in enumerate(DAYS) if c[d] == "1")

# shapes, simplified (Douglas-Peucker, 3 m)
pts = collections.defaultdict(list)
for s in rows("shapes.txt"):
    pts[s["shape_id"]].append((int(s["shape_pt_sequence"]), float(s["shape_pt_lon"]), float(s["shape_pt_lat"])))
def simplify(p, tol=3.0):
    if len(p) < 3:
        return p
    keep = [False] * len(p); keep[0] = keep[-1] = True
    stack = [(0, len(p) - 1)]
    while stack:
        a, b = stack.pop()
        ax, az = p[a]; bx, bz = p[b]; dx, dz = bx - ax, bz - az; L = math.hypot(dx, dz) or 1e-9
        best, bi = 0, -1
        for i in range(a + 1, b):
            d = abs((p[i][0] - ax) * dz - (p[i][1] - az) * dx) / L
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True; stack += [(a, bi), (bi, b)]
    return [q for q, k in zip(p, keep) if k]
shape_xz = {}
for sid, lst in pts.items():
    lst.sort()
    xz = [P(lon, lat) for _, lon, lat in lst]
    shape_xz[sid] = simplify(xz)

# stops, to check each trip runs the same way as its shape
stops = {s["stop_id"]: P(float(s["stop_lon"]), float(s["stop_lat"])) for s in rows("stops.txt")}
first_last = {}
for s in rows("stop_times.txt"):
    tid, seq = s["trip_id"], int(s["stop_sequence"])
    t = s["departure_time"] or s["arrival_time"]
    if not t:
        continue
    fl = first_last.get(tid)
    rec = (seq, minutes(s["departure_time"] or t), minutes(s["arrival_time"] or t), s["stop_id"])
    if fl is None:
        first_last[tid] = [rec, rec]
    else:
        if seq < fl[0][0]: fl[0] = rec
        if seq > fl[1][0]: fl[1] = rec

# ---- OSM route geometry
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OSM = json.load(open(os.path.join(DATA, "osm_routes.json")))
LOOK = str.maketrans("ABCEHKMOPTXaceopx", "АВСЕНКМОРТХасеорх")
def norm_ref(r):
    r = r.translate(LOOK).upper().replace(" ", "")
    return re.sub(r"^(ТР|ТРОЛ|Т|А)(?=\d)", "", r)
osm_by = collections.defaultdict(list)
for o in OSM:
    a = np.array(o["xz"], dtype=float)
    seg = np.diff(a, axis=0); L = np.hypot(seg[:, 0], seg[:, 1])
    o["a"], o["cum"] = a, np.concatenate([[0], np.cumsum(L)])
    osm_by[(o["kind"], norm_ref(o["ref"]))].append(o)

def project(o, pts):
    """distance from each point to the OSM line and its position along it (metres)"""
    a, cum = o["a"], o["cum"]
    p0, d = a[:-1], np.diff(a, axis=0); dd = (d * d).sum(1) + 1e-9
    P_ = np.asarray(pts, dtype=float)[:, None, :]
    t = np.clip(((P_ - p0) * d).sum(2) / dd, 0, 1)
    q = p0 + t[..., None] * d
    dist = np.hypot(*(P_ - q).transpose(2, 0, 1))
    k = dist.argmin(1); i = np.arange(len(pts))
    return dist[i, k], cum[k] + t[i, k] * np.sqrt(dd[k])

def cut(o, s0, s1):
    a, cum = o["a"], o["cum"]
    def at(s):
        k = min(max(int(np.searchsorted(cum, s) - 1), 0), len(a) - 2)
        f = (s - cum[k]) / max(cum[k + 1] - cum[k], 1e-9)
        return a[k] + f * (a[k + 1] - a[k]), k
    pa, ka = at(s0); pb, kb = at(s1)
    return [tuple(pa)] + [tuple(x) for x in a[ka + 1:kb + 1]] + [tuple(pb)]

def densify(p, step=40):
    out = [p[0]]
    for a, b in zip(p, p[1:]):
        n = int(math.dist(a, b) // step)
        out += [(a[0] + (b[0] - a[0]) * i / (n + 1), a[1] + (b[1] - a[1]) * i / (n + 1)) for i in range(1, n + 1)] + [b]
    return out

# ---- street graph routing
_G = np.load(os.path.join(DATA, "road_graph.npz"))
GXY, GE, GNET, GLEN = _G["xy"].astype(float), _G["edges"], _G["net"], _G["length"].astype(float)
NETS = {}
COST = {1: 1.0, 3: 1.15, 4: 1.8, 5: 3.0, 2: 1.0}   # prefer main roads: transit keeps to them
def net_for(kind):
    n = 2 if kind == 0 else 1
    if n not in NETS:
        m = (GNET == 2) if n == 2 else (GNET != 2)
        e = GE[m]; w = np.maximum(GLEN[m], 0.01) * np.vectorize(COST.get)(GNET[m]); N = len(GXY)
        g = csr_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(N, N))
        nodes = np.unique(e)
        # snap only to sizeable connected pieces (the road network is one piece; Kyiv's tram
        # network is a few), never to an isolated driveway or depot siding
        _, lab = connected_components(g, directed=False)
        size = np.bincount(lab[nodes])
        nodes = nodes[size[lab[nodes]] >= (300 if n == 2 else 5000)]
        if n == 1:   # snap to streets, not to yards and parking lanes
            on_street = np.zeros(N, bool); on_street[GE[(GNET != 2) & (GNET != 5)].ravel()] = True
            nodes = nodes[on_street[nodes]]
        NETS[n] = (g, nodes, cKDTree(GXY[nodes]))
    return NETS[n]
path_cache = {}
def route_path(kind, a, b):
    """cheapest path a→b (node ids) on the network, or None if missing or a long detour"""
    g, nodes, tree = net_for(kind)
    key = (kind, a, b)
    if key not in path_cache:
        straight = math.dist(GXY[a], GXY[b])
        dist, pred = dijkstra(g, indices=a, return_predecessors=True, limit=3.5 * straight + 1000)
        if not np.isfinite(dist[b]):
            path_cache[key] = None
        else:
            seq = [b]
            while seq[-1] != a:
                seq.append(int(pred[seq[-1]]))
            path_cache[key] = seq[::-1]
    return path_cache[key]
def drop_loops(seq):
    """remove out-and-back spurs and loops: when a node comes up again, cut back to it"""
    out, pos = [], {}
    for n in seq:
        if n in pos:
            for m in out[pos[n] + 1:]:
                pos.pop(m, None)
            del out[pos[n] + 1:]
        else:
            pos[n] = len(out); out.append(n)
    return out
def route_on_streets(kind, p):
    """Follow the network through the line's own points; a point that only connects by a long
    detour (e.g. it snapped to the opposite tram track) is skipped."""
    g, nodes, tree = net_for(kind)
    d, k = tree.query(np.array(p))
    way = []
    for dd, j in zip(d, k):
        if dd < (400 if kind == 0 else 250):
            n = int(nodes[j])
            if not way or math.dist(GXY[way[-1]], GXY[n]) > 60:
                way.append(n)
    if len(way) < 2:
        return None
    seq, i = [], 0
    while i < len(way) - 1:
        for j in range(i + 1, min(i + 5, len(way))):
            seg = route_path(kind, way[i], way[j])
            if seg is not None:
                break
        else:
            return None
        seq += seg[1:] if seq else seg
        i = j
    return [tuple(GXY[n]) for n in drop_loops(seq)]

match_cache, how = {}, collections.Counter()
def street_line(sid, kind, ref, s0, s1):
    """Route line on the streets for a trip: OSM geometry when it fits, else the feed's own line."""
    key = (sid, s0, s1)
    if key in match_cache:
        return match_cache[key]
    p = shape_xz_raw[sid]
    if s0 and s1 and math.dist(s0, p[-1]) + math.dist(s1, p[0]) < math.dist(s0, p[0]) + math.dist(s1, p[-1]):
        p = p[::-1]
    ref_pts = densify(p, 150)
    best = None
    for o in osm_by.get((kind, norm_ref(ref)), []):
        dist, along = project(o, ref_pts)
        if along[-1] - along[0] < 0.5 * sum(math.dist(a, b) for a, b in zip(p, p[1:])):
            continue                                   # runs the other way, or covers only part
        score = float(np.median(dist))
        if best is None or score < best[0]:
            best = (score, o, along[0], along[-1])
    line = None
    if best and best[0] < 60:
        line, h = cut(best[1], best[2], best[3]), "osm"
    else:
        line, h = route_on_streets(kind, p), "streets"
        if line is None:
            h = "dropped"
    how[h] += 1
    match_cache[key] = line
    return line

shape_xz_raw = {sid: [P(lon, lat) for _, lon, lat in lst] for sid, lst in pts.items()}
shape_index, shape_list = {}, []
def shape_for(line):
    key = tuple((round(x), round(z)) for x, z in line)
    if key not in shape_index:
        shape_index[key] = len(shape_list); shape_list.append(simplify(list(line), 2.0))
    return shape_index[key]

route_ids = list(routes); route_idx = {r: i for i, r in enumerate(route_ids)}
trips, skipped = [], collections.Counter()
for t in rows("trips.txt"):
    rid, sid, tid = t["route_id"], t.get("shape_id"), t["trip_id"]
    if rid not in routes: skipped["route_type"] += 1; continue
    if sid not in shape_xz or len(shape_xz[sid]) < 2: skipped["no_shape"] += 1; continue
    if tid not in first_last: skipped["no_times"] += 1; continue
    m = masks.get(t["service_id"], 0)
    if not m: skipped["no_days"] += 1; continue
    a, b = first_last[tid]
    start, end = a[1], b[2]
    if end <= start or end - start > 300: skipped["bad_times"] += 1; continue
    line = street_line(sid, routes[rid][2], routes[rid][0], stops.get(a[3]), stops.get(b[3]))
    if line is None: skipped["no_street_line"] += 1; continue
    trips.append((start, end, shape_for(line), route_idx[rid], m))
trips.sort()

xs = [c for p in shape_list for q in p for c in q]
span = max(abs(v) for v in xs)
assert span < 32000, f"coordinates out of int16 range: {span:.0f} m"

arrays = [
    ("shapeLen", struct.pack(f"<{len(shape_list)}H", *[len(p) for p in shape_list])),
    ("shapeXZ", struct.pack(f"<{len(xs)}h", *[int(round(v)) for v in xs])),
    ("tripShape", struct.pack(f"<{len(trips)}H", *[t[2] for t in trips])),
    ("tripRoute", struct.pack(f"<{len(trips)}H", *[t[3] for t in trips])),
    ("tripStart", struct.pack(f"<{len(trips)}H", *[t[0] for t in trips])),
    ("tripEnd", struct.pack(f"<{len(trips)}H", *[t[1] for t in trips])),
    ("tripDays", struct.pack(f"<{len(trips)}B", *[t[4] for t in trips])),
]
body, offsets = b"", {}
for name, data in arrays:
    body += b"\0" * ((-len(body)) % 4)
    offsets[name] = [len(body), len(data)]
    body += data
feed = next(rows("feed_info.txt"), {})
header = {"version": 1, "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "feedVersion": feed.get("feed_version", ""), "source": "КП «Київпастранс», GTFS, CC BY 4.0",
          "routes": [routes[r] for r in route_ids], "shapes": len(shape_list), "trips": len(trips), "arrays": offsets}
hj = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode()
hj += b" " * ((-len(hj) - 4) % 4)
open(out, "wb").write(struct.pack("<I", len(hj)) + hj + body)
print(f"transit: {len(route_ids)} routes, {len(trips)} trips, {len(shape_list)} shapes, "
      f"{len(xs)//2} points, {4 + len(hj) + len(body)} bytes, skipped {dict(skipped)}, route lines {dict(how)}")
