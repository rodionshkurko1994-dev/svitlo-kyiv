import pickle, math, json, re, struct
import numpy as np
from shapely import wkb
from shapely.geometry import shape, Polygon, MultiPolygon, box
from shapely.ops import unary_union
import shapely

OSM = '/home/claude/kyiv/osm/'
LAT0, LON0 = 50.45, 30.52
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110570
def P(lon, lat): return ((lon - LON0) * KX, -(lat - LAT0) * KY)   # x east, z south (three.js)

d = pickle.load(open(OSM + 'extract.pkl', 'rb'))

# ---------- YASNO groups per address (from the GitHub crawl) ----------
import glob, sys
GROUP_DIR = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/svitlo-kyiv/data'
found = {}
for f in sorted(glob.glob(GROUP_DIR + '/full/groups_*.json')) + sorted(glob.glob(GROUP_DIR + '/test_groups*.json')):
    for r in json.load(open(f))['results']:
        if r.get('status') == 'ok':
            found.setdefault((r['street'].strip(), r['house'].strip()), (int(r['group']), bool(r.get('exact', True))))
print('addresses with group', len(found))
NEIGH = 150.0   # metres: buildings without their own address take the nearest crawled building within this radius
# ---------- buildings ----------
def bheight(h, lv, bt):
    if h and 2 <= h <= 400: return h
    if lv and 1 <= lv <= 120: return lv * 3.0 + 1.5
    return {'house': 7, 'detached': 7, 'garages': 3, 'garage': 3, 'shed': 3, 'roof': 4, 'kiosk': 3,
            'apartments': 16, 'residential': 13, 'dormitory': 16, 'hotel': 20, 'office': 16, 'commercial': 9,
            'retail': 7, 'industrial': 9, 'warehouse': 8, 'service': 4, 'church': 18, 'school': 12,
            'university': 14, 'hospital': 15, 'kindergarten': 8, 'construction': 6}.get(bt, 8)

zones, srcs, heights, ring_counts, ring_lens, coords, cent = [], [], [], [], [], [], []
for g_wkb, h, lv, bt, nm, st, hn in d['b']:
    own = found.get(((st or '').strip(), (hn or '').strip())) if st and hn else None
    g = wkb.loads(g_wkb)
    polys = list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]
    hh = bheight(h, lv, bt)
    for p in polys:
        if p.is_empty or p.area < 1e-10: continue
        ext = [P(x, y) for x, y in p.exterior.coords]
        pp = Polygon(ext, [[P(x, y) for x, y in r.coords] for r in p.interiors]).simplify(0.6, preserve_topology=True)
        if pp.is_empty or pp.area < 6 or pp.geom_type != 'Polygon': continue
        rings = [pp.exterior] + list(pp.interiors)[:8]
        rr = []
        for r in rings:
            c = list(r.coords)[:-1]
            if len(c) < 3: continue
            rr.append(c)
        if not rr: continue
        c = pp.representative_point()
        cent.append((c.x, c.y))
        if own:
            zones.append(own[0]); srcs.append(1 if own[1] else 2)
        else:
            zones.append(0); srcs.append(0)
        heights.append(min(65535, int(round(hh * 10))))
        ring_counts.append(len(rr))
        for c in rr:
            ring_lens.append(len(c))
            for x, y in c: coords += [int(round(x)), int(round(y))]
# neighbours: nearest building that has its own group
from scipy.spatial import cKDTree
C = np.array(cent); Z = np.array(zones); SRC = np.array(srcs)
known = np.where(SRC > 0)[0]
tree = cKDTree(C[known])
miss = np.where(SRC == 0)[0]
dist, idx = tree.query(C[miss], distance_upper_bound=NEIGH)
okm = np.isfinite(dist)
Z[miss[okm]] = Z[known[idx[okm]]]; SRC[miss[okm]] = 3
zones, srcs = Z.tolist(), SRC.tolist()
def zone_at(x, y, r=NEIGH):
    dd, ii = tree.query([x, y], distance_upper_bound=r)
    return int(Z[known[ii]]) if np.isfinite(dd) else 0
from collections import Counter
print('building parts', len(zones), 'pts', len(coords) // 2, 'by source', Counter(srcs))

VIEW = box(-24000, -24000, 24000, 24000)
# ---------- roads ----------
road_rank, road_lens, road_coords, road_zone = [], [], [], []
for rank, pts, name in d['r']:
    if rank > 3 or len(pts) < 2: continue
    ls = shapely.LineString([P(*q) for q in pts]).simplify(1.5).intersection(VIEW)
    for part in (ls.geoms if hasattr(ls, 'geoms') else [ls]):
        if part.geom_type != 'LineString': continue
        c = list(part.coords)
        if len(c) < 2: continue
        road_rank.append(rank); road_lens.append(len(c))
        for x, y in c: road_coords += [int(round(x)), int(round(y))]; road_zone.append(zone_at(x, y, 250))
for pts in d['rail']:
    ls = shapely.LineString([P(*q) for q in pts]).simplify(2).intersection(VIEW)
    for part in (ls.geoms if hasattr(ls, 'geoms') else [ls]):
        if part.geom_type != 'LineString': continue
        c = list(part.coords)
        if len(c) < 2: continue
        road_rank.append(9); road_lens.append(len(c))
        for x, y in c: road_coords += [int(round(x)), int(round(y))]; road_zone.append(0)
print('road lines', len(road_lens), 'pts', len(road_coords) // 2)

# ---------- area polygons -> triangles ----------
VIEW = box(-24000, -24000, 24000, 24000)
def tris_of(geoms, simplify, min_area):
    out = []
    u = unary_union([shapely.ops.transform(lambda x, y, z=None: P(x, y), g).buffer(0) for g in geoms])
    u = u.intersection(VIEW).simplify(simplify)
    for p in (u.geoms if hasattr(u, 'geoms') else [u]):
        if p.geom_type != 'Polygon' or p.area < min_area: continue
        t = shapely.constrained_delaunay_triangles(p)
        for tri in t.geoms:
            cs = list(tri.exterior.coords)[:3]
            for x, y in cs: out += [int(round(x)), int(round(y))]
    return out
water = tris_of([wkb.loads(w) for w in d['w']], 3, 800)
parks = tris_of([wkb.loads(w) for w in d['p']], 4, 3000)
adm = json.load(open('/home/claude/kyiv/raw/adm1.geojson'))
city = shape([f for f in adm['features'] if f['properties']['shapeName'] == 'Kyiv'][0]['geometry'])
ground = tris_of([city], 20, 1)
city_ring = [[int(round(x)), int(round(y))] for x, y in shapely.ops.transform(lambda x, y, z=None: P(x, y), city).simplify(25).exterior.coords]
print('water tris', len(water) // 6, 'park tris', len(parks) // 6, 'ground tris', len(ground) // 6)

# ---------- write binary ----------
def arr(a, t): return np.asarray(a, dtype=t).tobytes()
parts = [
    ('zone', arr(zones, np.uint8)), ('src', arr(srcs, np.uint8)), ('height', arr(heights, np.uint16)), ('ringCount', arr(ring_counts, np.uint8)),
    ('ringLen', arr(ring_lens, np.uint16)), ('coords', arr(coords, np.int16)),
    ('roadRank', arr(road_rank, np.uint8)), ('roadLen', arr(road_lens, np.uint16)), ('roadCoords', arr(road_coords, np.int16)), ('roadZone', arr(road_zone, np.uint8)),
    ('water', arr(water, np.int16)), ('parks', arr(parks, np.int16)), ('ground', arr(ground, np.int16)),
]
header = {}
blob = b''
for name, b in parts:
    pad = (-len(blob)) % 4
    blob += b'\0' * pad
    header[name] = [len(blob), len(b)]
    blob += b
open(OSM + 'kyiv3d_v2.bin', 'wb').write(blob)
cnt = Counter(srcs)
meta = {'header': header, 'city': city_ring, 'v': 2,
        'stats': {'buildings': len(srcs), 'byAddress': cnt[1], 'byAddressNear': cnt[2], 'byNeighbour': cnt[3], 'noData': cnt[0], 'addresses': len(found)}}
json.dump(meta, open(OSM + 'meta_v2.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('bin bytes', len(blob))
