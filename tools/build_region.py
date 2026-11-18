"""Build the Kyiv agglomeration layer (outside the city) from an OpenStreetMap extract.

usage: python3 tools/build_region.py <region.osm.pbf> <out dir, e.g. region>

Writes, in the city model's projection (metres from 50.45N 30.52E, x east, z south):
  manifest.json   tiles, town labels, area outline
  base.bin        ground, water, forests/parks, main roads and railways for the whole area
  t_<i>_<j>.bin   buildings (and local streets) per 8 km tile, loaded by the page on demand
  addr.json       addresses for the "Мій дім" search
Binary files: uint32 header length, JSON header, padding to 4 bytes, then the arrays it lists as
[offset, length] (offsets from the start of the arrays). Coordinates are int16: base.bin in units of
2 m from the centre, tiles in metres from the tile origin (header "origin").
Buildings carry no power data: Kyiv region outages come from DTEK KREM, which has no open feed.
"""
import json, math, os, re, struct, sys, collections
import osmium
import shapely
from shapely import wkb as shwkb
from shapely.geometry import shape, box, Polygon, MultiPolygon, LineString
from shapely.ops import unary_union, transform
from shapely.prepared import prep

PBF, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
LAT0, LON0 = 50.45, 30.52
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110570
BBOX = (29.95, 50.05, 31.05, 50.72)           # lon/lat: Irpin–Bucha to Brovary–Boryspil, Vyshhorod to Obukhiv
TILE = 8000.0

def P(lon, lat): return ((lon - LON0) * KX, -(lat - LAT0) * KY)
def proj(g): return transform(lambda x, y, z=None: P(x, y), g)

adm = json.load(open(os.path.join(HERE, "adm1.geojson")))
by = {f["properties"]["shapeName"]: shape(f["geometry"]) for f in adm["features"]}
city_ll = by["Kyiv"].buffer(0)
area_ll = by["Kyiv Oblast"].buffer(0).intersection(box(*BBOX)).difference(city_ll)
city_m, area_m = proj(city_ll), proj(area_ll)
area_p, city_p = prep(area_ll), prep(city_ll)
fab = osmium.geom.WKBFactory()

def num(v):
    if not v: return None
    m = re.match(r"\s*([0-9]+(?:[.,][0-9]+)?)", v)
    return float(m.group(1).replace(",", ".")) if m else None

def bheight(h, lv, bt):
    if h and 2 <= h <= 400: return h
    if lv and 1 <= lv <= 120: return lv * 3.0 + 1.5
    return {"house": 7, "detached": 7, "semidetached_house": 7, "garages": 3, "garage": 3, "shed": 3, "roof": 4, "kiosk": 3,
            "apartments": 16, "residential": 10, "dormitory": 16, "hotel": 20, "office": 16, "commercial": 9, "retail": 7,
            "industrial": 9, "warehouse": 8, "service": 4, "church": 18, "school": 12, "university": 14, "hospital": 15,
            "kindergarten": 8, "construction": 6, "farm_auxiliary": 4, "greenhouse": 3}.get(bt, 6)

ROAD_RANK = {"motorway": 0, "trunk": 0, "primary": 1, "secondary": 1, "tertiary": 2, "motorway_link": 1, "trunk_link": 1,
             "primary_link": 2, "secondary_link": 2, "tertiary_link": 2, "residential": 3, "unclassified": 3, "living_street": 3}
PLACE = {"city", "town", "village", "suburb"}

class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.b = []; s.w = []; s.p = []; s.r = []; s.places = []
    def node(s, n):
        t = n.tags
        if t.get("place") in PLACE and ("name:uk" in t or "name" in t):
            if not area_p.contains(shapely.Point(n.location.lon, n.location.lat)): return
            pop = num(t.get("population")) or 0
            s.places.append((t.get("name:uk") or t.get("name"), t.get("place"), pop, n.location.lon, n.location.lat))
    def area(s, a):
        t = a.tags
        try:
            if "building" in t and t.get("building") != "no":
                g = shwkb.loads(fab.create_multipolygon(a), hex=True)
                c = g.representative_point()
                if not area_p.contains(c): return
                s.b.append((g, num(t.get("height")), num(t.get("building:levels")), t.get("building"),
                            t.get("addr:street", ""), t.get("addr:housenumber", ""), t.get("addr:city", "")))
            elif t.get("natural") == "water" or t.get("waterway") == "riverbank" or t.get("landuse") in ("reservoir", "basin"):
                g = shwkb.loads(fab.create_multipolygon(a), hex=True)
                if g.area > 2.5e-6: s.w.append(g)
            elif t.get("landuse") in ("forest",) or t.get("natural") == "wood" or t.get("leisure") in ("park", "nature_reserve"):
                g = shwkb.loads(fab.create_multipolygon(a), hex=True)
                if g.area > 6e-6: s.p.append(g)
        except Exception:
            pass
    def way(s, w):
        t = w.tags; hw = t.get("highway")
        try:
            if hw in ROAD_RANK or (t.get("railway") == "rail" and t.get("service") is None):
                pts = [(n.lon, n.lat) for n in w.nodes]
                if len(pts) < 2: return
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                if max(xs) < BBOX[0] or min(xs) > BBOX[2] or max(ys) < BBOX[1] or min(ys) > BBOX[3]: return
                s.r.append((9 if hw is None else ROAD_RANK[hw], pts))
        except Exception:
            pass

h = H(); h.apply_file(PBF, locations=True, idx="flex_mem")
print(f"read: {len(h.b)} buildings, {len(h.w)} water, {len(h.p)} green, {len(h.r)} roads/rail, {len(h.places)} places", flush=True)
os.makedirs(OUT, exist_ok=True)

def pack(path, header, arrays):
    body, offs = b"", {}
    for name, data in arrays:
        body += b"\0" * ((-len(body)) % 4); offs[name] = [len(body), len(data)]; body += data
    header = dict(header, arrays=offs)
    hj = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode()
    hj += b" " * ((-len(hj) - 4) % 4)
    open(path, "wb").write(struct.pack("<I", len(hj)) + hj + body)
    return 4 + len(hj) + len(body)

def i16(vals, scale=1.0):
    out = []
    for v in vals:
        q = int(round(v / scale)); out.append(max(-32767, min(32767, q)))
    return struct.pack(f"<{len(out)}h", *out)

def tris(geom, tol, min_area):
    out = []
    g = geom.simplify(tol)
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        if p.geom_type != "Polygon" or p.area < min_area: continue
        for t in shapely.constrained_delaunay_triangles(p).geoms:
            for x, z in list(t.exterior.coords)[:3]: out += [x, z]
    return out

# ---- base layer
area_s = area_m.simplify(40)
ground = tris(area_s, 0, 1)
water_m = proj(unary_union([g.buffer(0) for g in h.w])).intersection(area_m) if h.w else Polygon()
green_m = proj(unary_union([g.buffer(0) for g in h.p])).intersection(area_m).difference(water_m) if h.p else Polygon()
water = tris(water_m, 15, 20000)
green = tris(green_m, 25, 60000)
rank, rlen, rco = [], [], []
tile_streets = collections.defaultdict(list)
for rk, pts in h.r:
    ls = proj(LineString(pts)).simplify(4 if rk >= 3 else 2).difference(city_m)
    for part in (ls.geoms if hasattr(ls, "geoms") else [ls]):
        if part.geom_type != "LineString" or len(part.coords) < 2: continue
        c = list(part.coords)
        if rk == 3:                                  # local streets go with the tile they start in
            tx, tz = math.floor(c[0][0] / TILE), math.floor(c[0][1] / TILE); tile_streets[(tx, tz)].append(c)
            continue
        rank.append(rk); rlen.append(len(c)); rco += [v for q in c for v in q]
outline = list(area_s.exterior.coords) if area_s.geom_type == "Polygon" else list(max(area_s.geoms, key=lambda q: q.area).exterior.coords)
base_size = pack(os.path.join(OUT, "base.bin"), {"v": 1, "scale": 2},
                 [("ground", i16(ground, 2)), ("water", i16(water, 2)), ("green", i16(green, 2)),
                  ("roadRank", struct.pack(f"<{len(rank)}B", *rank)), ("roadLen", struct.pack(f"<{len(rlen)}H", *rlen)),
                  ("roadCoords", i16(rco, 2))])

# ---- buildings by tile
tiles = collections.defaultdict(list)
addrs = []
for g, hh, lv, bt, st, hn, ac in h.b:
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    height = bheight(hh, lv, bt)
    first = True
    for p in polys:
        if p.is_empty: continue
        pp = Polygon([P(x, y) for x, y in p.exterior.coords], [[P(x, y) for x, y in r.coords] for r in p.interiors]).simplify(0.6, preserve_topology=True)
        if pp.is_empty or pp.area < 8 or pp.geom_type != "Polygon": continue
        rings = [list(pp.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in list(pp.interiors)[:6]]
        rings = [r for r in rings if len(r) >= 3]
        if not rings: continue
        c = pp.representative_point()
        key = (math.floor(c.x / TILE), math.floor(c.y / TILE))
        tiles[key].append((height, rings))
        if first and st and hn:
            addrs.append((ac, st, hn, round(c.x), round(c.y))); first = False

manifest_tiles = []
for (tx, tz), items in sorted(tiles.items()):
    ox, oz = (tx + 0.5) * TILE, (tz + 0.5) * TILE
    hs, rc, rl, co = [], [], [], []
    for height, rings in items:
        hs.append(min(65535, int(round(height * 10)))); rc.append(len(rings))
        for r in rings:
            rl.append(len(r)); co += [v for q in r for v in (q[0] - ox, q[1] - oz)]
    sr, sl = [], []
    for c in tile_streets.get((tx, tz), []):
        sl.append(len(c)); sr += [v for q in c for v in (q[0] - ox, q[1] - oz)]
    name = f"t_{tx}_{tz}.bin"
    size = pack(os.path.join(OUT, name), {"v": 1, "origin": [ox, oz], "n": len(items)},
                [("height", struct.pack(f"<{len(hs)}H", *hs)), ("ringCount", struct.pack(f"<{len(rc)}B", *rc)),
                 ("ringLen", struct.pack(f"<{len(rl)}H", *rl)), ("coords", i16(co)),
                 ("streetLen", struct.pack(f"<{len(sl)}H", *sl)), ("streetCoords", i16(sr))])
    manifest_tiles.append({"f": name, "x": ox, "z": oz, "n": len(items), "kb": round(size / 1024)})

# ---- town labels: cities and towns, plus big villages
towns = []
for name, kind, pop, lon, lat in h.places:
    if kind in ("city", "town") or (kind == "village" and pop >= 5000):
        x, z = P(lon, lat); towns.append({"n": name, "x": round(x), "z": round(z), "p": int(pop), "k": kind})
towns.sort(key=lambda t: -t["p"])

# ---- addresses: settlement from addr:city, else the nearest named place
pl = [(n, P(lon, lat)) for n, kind, pop, lon, lat in h.places if kind in ("city", "town", "village")]
def settle(ac, x, z):
    if ac: return ac
    best, bd = "", 4000.0 ** 2
    for n, (px, pz) in pl:
        d = (px - x) ** 2 + (pz - z) ** 2
        if d < bd: best, bd = n, d
    return best
places, streets, rows, pidx, sidx, seen = [], [], [], {}, {}, set()
for ac, st, hn, x, z in addrs:
    s = settle(ac.strip(), x, z); key = (s, st.strip(), hn.strip())
    if key in seen: continue
    seen.add(key)
    pi = pidx.setdefault(s, len(places)); places.append(s) if pi == len(places) else None
    si = sidx.setdefault(st.strip(), len(streets)); streets.append(st.strip()) if si == len(streets) else None
    rows.append([pi, si, hn.strip(), x, z])
json.dump({"v": 1, "places": places, "streets": streets, "a": rows}, open(os.path.join(OUT, "addr.json"), "w"),
          ensure_ascii=False, separators=(",", ":"))

bx0, bz0 = P(BBOX[0], BBOX[3]); bx1, bz1 = P(BBOX[2], BBOX[1])
json.dump({"v": 1, "tile": TILE, "bbox": [round(bx0), round(bz0), round(bx1), round(bz1)], "tiles": manifest_tiles,
           "towns": towns, "outline": [[round(x), round(z)] for x, z in outline[::max(1, len(outline) // 400)]],
           "buildings": sum(t["n"] for t in manifest_tiles), "addresses": len(rows)},
          open(os.path.join(OUT, "manifest.json"), "w"), ensure_ascii=False, separators=(",", ":"))
total = sum(t["kb"] for t in manifest_tiles)
print(f"region: {len(manifest_tiles)} tiles, {sum(t['n'] for t in manifest_tiles)} buildings ({total} KB), base {base_size//1024} KB, "
      f"{len(towns)} towns, {len(rows)} addresses")
