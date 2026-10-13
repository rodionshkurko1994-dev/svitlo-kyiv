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

# ---------- address index for geocoding sample addresses ----------
TYPES = r'\b(вулиця|вул\.?|проспект|просп\.?|провулок|пров\.?|бульвар|бульв\.?|набережна|наб\.?|шосе|площа|узвіз|дорога|академіка)\b'
def norm_street(s):
    s = s.lower().replace('’', "'").replace('ʼ', "'").replace('`', "'")
    s = re.sub(TYPES, ' ', s)
    toks = sorted(t for t in re.split(r"[\s,\.]+", s) if t)
    return ' '.join(toks)
def norm_num(n): return re.sub(r'[\s\-]', '', n.lower())
addr = {}
for g_wkb, h, lv, bt, nm, st, hn in d['b']:
    if st and hn:
        addr.setdefault((norm_street(st), norm_num(hn)), g_wkb)

samples = []
miss = []
for l in open('/home/claude/kyiv/work/samples_final.tsv'):
    i, a, lat, lon, area, grp = l.rstrip('\n').split('\t')
    st, hn = a.rsplit(', ', 1)
    key = (norm_street(st), norm_num(hn))
    g = addr.get(key)
    if g is None:   # try without the first name token (e.g. "Степана Бандери" vs "Бандери")
        for (s2, n2), gg in addr.items():
            if n2 == key[1] and set(key[0].split()) <= set(s2.split()) | set(key[0].split()) and set(s2.split()) & set(key[0].split()) and len(set(s2.split()) & set(key[0].split())) >= max(1, len(key[0].split()) - 1):
                g = gg; break
    if g is not None:
        c = wkb.loads(g).centroid; lon, lat = c.x, c.y
    else:
        miss.append(a); lat, lon = float(lat), float(lon)
    ox, oz = P(float(l.split('\t')[3]), float(l.split('\t')[2])); nx, nz = P(lon, lat)
    print('  shift', a, round(math.hypot(nx-ox, nz-oz)))
    samples.append({'addr': a, 'area': area, 'group': int(grp), 'lat': lat, 'lon': lon})
NEW = {r.split('\t')[0]: r.rstrip('\n').split('\t') for r in open(OSM + 'new_samples.tsv')}
GROUPS = {'101':8,'102':34,'104':35,'105':44,'107':44,'108':12,'109':49,'111':4,'113':37,'114':44,'115':49,'116':2,'117':6,'119':4,'120':6,'121':2,'122':4,'123':34,'125':45,'127':49,'128':1,'129':28,'131':4,'134':24,'136':34}
for k, grp in GROUPS.items():
    r = NEW[k]
    samples.append({'addr': f"{r[1]}, {r[3]}", 'area': r[6], 'group': grp, 'lat': float(r[4]), 'lon': float(r[5])})
print('samples', len(samples), 'geocode misses', miss)
S = np.array([P(s['lon'], s['lat']) for s in samples])
for s, (x, z) in zip(samples, S): s['x'] = round(float(x)); s['z'] = round(float(z))
MAXD = 2600.0
NOZONE = 255

def zone_of(x, z):
    dd = np.hypot(S[:, 0] - x, S[:, 1] - z); k = int(dd.argmin())
    return (k if dd[k] <= MAXD else NOZONE), float(dd[k])

# ---------- buildings ----------
def bheight(h, lv, bt):
    if h and 2 <= h <= 400: return h
    if lv and 1 <= lv <= 120: return lv * 3.0 + 1.5
    return {'house': 7, 'detached': 7, 'garages': 3, 'garage': 3, 'shed': 3, 'roof': 4, 'kiosk': 3,
            'apartments': 16, 'residential': 13, 'dormitory': 16, 'hotel': 20, 'office': 16, 'commercial': 9,
            'retail': 7, 'industrial': 9, 'warehouse': 8, 'service': 4, 'church': 18, 'school': 12,
            'university': 14, 'hospital': 15, 'kindergarten': 8, 'construction': 6}.get(bt, 8)

zones, heights, ring_counts, ring_lens, coords = [], [], [], [], []
zone_counts = {}
for g_wkb, h, lv, bt, nm, st, hn in d['b']:
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
        z, _ = zone_of(c.x, c.y)
        zone_counts[z] = zone_counts.get(z, 0) + 1
        zones.append(z); heights.append(min(65535, int(round(hh * 10))))
        ring_counts.append(len(rr))
        for c in rr:
            ring_lens.append(len(c))
            for x, y in c: coords += [int(round(x)), int(round(y))]
print('building parts', len(zones), 'rings', len(ring_lens), 'pts', len(coords) // 2,
      'no-zone', zone_counts.get(NOZONE, 0))

VIEW = box(-24000, -24000, 24000, 24000)
# ---------- roads ----------
road_rank, road_lens, road_coords = [], [], []
for rank, pts, name in d['r']:
    if rank > 3 or len(pts) < 2: continue
    ls = shapely.LineString([P(*q) for q in pts]).simplify(1.5).intersection(VIEW)
    for part in (ls.geoms if hasattr(ls, 'geoms') else [ls]):
        if part.geom_type != 'LineString': continue
        c = list(part.coords)
        if len(c) < 2: continue
        road_rank.append(rank); road_lens.append(len(c))
        for x, y in c: road_coords += [int(round(x)), int(round(y))]
for pts in d['rail']:
    ls = shapely.LineString([P(*q) for q in pts]).simplify(2).intersection(VIEW)
    for part in (ls.geoms if hasattr(ls, 'geoms') else [ls]):
        if part.geom_type != 'LineString': continue
        c = list(part.coords)
        if len(c) < 2: continue
        road_rank.append(9); road_lens.append(len(c))
        for x, y in c: road_coords += [int(round(x)), int(round(y))]
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
    ('zone', arr(zones, np.uint8)), ('height', arr(heights, np.uint16)), ('ringCount', arr(ring_counts, np.uint8)),
    ('ringLen', arr(ring_lens, np.uint16)), ('coords', arr(coords, np.int16)),
    ('roadRank', arr(road_rank, np.uint8)), ('roadLen', arr(road_lens, np.uint16)), ('roadCoords', arr(road_coords, np.int16)),
    ('water', arr(water, np.int16)), ('parks', arr(parks, np.int16)), ('ground', arr(ground, np.int16)),
]
header = {}
blob = b''
for name, b in parts:
    pad = (-len(blob)) % 4
    blob += b'\0' * pad
    header[name] = [len(blob), len(b)]
    blob += b
open(OSM + 'kyiv3d.bin', 'wb').write(blob)
meta = {'header': header, 'samples': samples, 'maxd': MAXD, 'nozone': NOZONE, 'city': city_ring}
json.dump(meta, open(OSM + 'meta.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('bin bytes', len(blob))
