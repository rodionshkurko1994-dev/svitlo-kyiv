"""Extract tram, trolleybus and bus route geometry from an OpenStreetMap .pbf into
data/osm_routes.json, in the city model's projection (metres, x east, z south).

The Kyivpastrans GTFS gives very coarse route lines (often just a few points), so
scripts/build_transit.py replaces them with the matching OSM route where one fits.

usage: python3 tools/osm_routes.py <kyiv.osm.pbf> data/osm_routes.json
"""
import json, math, sys
import osmium

LAT0, LON0 = 50.45, 30.52
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110570
KINDS = {"tram": 0, "trolleybus": 1, "bus": 2}
SKIP_ROLES = {"platform", "stop", "stop_entry_only", "stop_exit_only", "platform_entry_only", "platform_exit_only"}

class Rels(osmium.SimpleHandler):
    def __init__(self):
        super().__init__(); self.rels = []; self.need = set()
    def relation(self, r):
        t = r.tags
        if t.get("type") != "route" or t.get("route") not in KINDS:
            return
        ways = [m.ref for m in r.members if m.type == "w" and m.role not in SKIP_ROLES]
        if not ways:
            return
        self.rels.append({"id": r.id, "kind": KINDS[t["route"]], "ref": t.get("ref", ""), "name": t.get("name", ""),
                          "from": t.get("from", ""), "to": t.get("to", ""), "ways": ways})
        self.need.update(ways)

class Ways(osmium.SimpleHandler):
    def __init__(self, need):
        super().__init__(); self.need = need; self.geo = {}
    def way(self, w):
        if w.id in self.need:
            try:
                self.geo[w.id] = [((n.lon - LON0) * KX, -(n.lat - LAT0) * KY) for n in w.nodes]
            except osmium.InvalidLocationError:
                pass

def chain(parts):
    """Join the member ways in order, flipping each to continue from the previous end.
    Returns the line and the widest jump between consecutive ways."""
    out, gaps = [], 0.0
    for i, p in enumerate(parts):
        if not out:
            if i + 1 < len(parts):   # orient the first way towards the second
                nxt = parts[i + 1]
                d_keep = min(math.dist(p[-1], nxt[0]), math.dist(p[-1], nxt[-1]))
                d_flip = min(math.dist(p[0], nxt[0]), math.dist(p[0], nxt[-1]))
                if d_flip < d_keep:
                    p = p[::-1]
            out = list(p); continue
        if math.dist(out[-1], p[-1]) < math.dist(out[-1], p[0]):
            p = p[::-1]
        j = math.dist(out[-1], p[0])
        gaps = max(gaps, j)
        out += p[1:] if j < 1 else p
    return out, gaps

def simplify(p, tol=2.0):
    if len(p) < 3:
        return p
    keep = [False] * len(p); keep[0] = keep[-1] = True; stack = [(0, len(p) - 1)]
    while stack:
        a, b = stack.pop(); ax, az = p[a]; bx, bz = p[b]; dx, dz = bx - ax, bz - az; L = math.hypot(dx, dz) or 1e-9
        best, bi = 0, -1
        for i in range(a + 1, b):
            d = abs((p[i][0] - ax) * dz - (p[i][1] - az) * dx) / L
            if d > best: best, bi = d, i
        if best > tol:
            keep[bi] = True; stack += [(a, bi), (bi, b)]
    return [q for q, k in zip(p, keep) if k]

pbf, out = sys.argv[1], sys.argv[2]
r = Rels(); r.apply_file(pbf)
w = Ways(r.need); w.apply_file(pbf, locations=True, idx="flex_mem")
res = []
for rel in r.rels:
    parts = [w.geo[i] for i in rel["ways"] if i in w.geo]
    if len(parts) < len(rel["ways"]) * 0.9:
        continue   # relation leaves the extract or is broken
    line, gap = chain(parts)
    line = simplify(line)
    if len(line) < 2 or gap > 80:   # a missing piece would be bridged by a straight line
        continue
    res.append({k: rel[k] for k in ("id", "kind", "ref", "name", "from", "to")} | {"xz": [[round(x, 1), round(z, 1)] for x, z in line]})
json.dump(res, open(out, "w"), ensure_ascii=False, separators=(",", ":"))
by = {}
for x in res: by[x["kind"]] = by.get(x["kind"], 0) + 1
print(f"{len(res)} of {len(r.rels)} route relations kept (by kind {by})")
