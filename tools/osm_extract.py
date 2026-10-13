import osmium, json, math, sys, re
from shapely.geometry import shape, Polygon, MultiPolygon, LineString, Point
from shapely.prepared import prep
from shapely import wkb as shwkb

PBF = sys.argv[1]
OUT = '/home/claude/kyiv/osm/'
LAT0, LON0 = 50.45, 30.52
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110570

adm = json.load(open('/home/claude/kyiv/raw/adm1.geojson'))
city = shape([f for f in adm['features'] if f['properties']['shapeName'] == 'Kyiv'][0]['geometry']).buffer(0.003)
cityp = prep(city)
fab = osmium.geom.WKBFactory()

def num(v):
    if not v: return None
    m = re.match(r'\s*([0-9]+(?:[.,][0-9]+)?)', v)
    return float(m.group(1).replace(',', '.')) if m else None

ROAD_RANK = {'motorway': 0, 'trunk': 0, 'primary': 1, 'secondary': 1, 'tertiary': 2,
             'motorway_link': 1, 'trunk_link': 1, 'primary_link': 2, 'secondary_link': 2, 'tertiary_link': 2,
             'residential': 3, 'unclassified': 3, 'living_street': 3, 'service': 4}

class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__()
        s.b = []; s.w = []; s.r = []; s.p = []; s.rail = []
    def area(s, a):
        t = a.tags
        try:
            if 'building' in t or 'building:part' in t and False:
                if t.get('building') in ('no',): return
                g = shwkb.loads(fab.create_multipolygon(a), hex=True)
                c = g.representative_point()
                if not cityp.contains(c): return
                h = num(t.get('height'))
                lv = num(t.get('building:levels'))
                s.b.append((g, h, lv, t.get('building'), t.get('name', ''), t.get('addr:street', ''), t.get('addr:housenumber', '')))
            elif t.get('natural') == 'water' or t.get('waterway') == 'riverbank' or t.get('landuse') in ('reservoir', 'basin'):
                g = shwkb.loads(fab.create_multipolygon(a), hex=True)
                if g.area < 2e-7: return
                s.w.append(g)
            elif t.get('leisure') in ('park', 'garden') or t.get('landuse') in ('forest', 'grass', 'recreation_ground') or t.get('natural') == 'wood':
                g = shwkb.loads(fab.create_multipolygon(a), hex=True)
                if g.area < 4e-7: return
                s.p.append(g)
        except Exception:
            pass
    def way(s, w):
        t = w.tags
        hw = t.get('highway')
        try:
            if hw in ROAD_RANK:
                pts = [(n.lon, n.lat) for n in w.nodes]
                s.r.append((ROAD_RANK[hw], pts, t.get('name', '')))
            elif t.get('railway') in ('rail',) and t.get('service') is None:
                s.rail.append([(n.lon, n.lat) for n in w.nodes])
        except Exception:
            pass

h = H()
h.apply_file(PBF, locations=True, idx='flex_mem')
print('buildings', len(h.b), 'water', len(h.w), 'parks', len(h.p), 'roads', len(h.r), 'rail', len(h.rail))

import pickle
pickle.dump({'b': [(g.wkb, hh, lv, bt, nm, st, hn) for g, hh, lv, bt, nm, st, hn in h.b],
             'w': [g.wkb for g in h.w], 'p': [g.wkb for g in h.p], 'r': h.r, 'rail': h.rail},
            open(OUT + 'extract.pkl', 'wb'))
