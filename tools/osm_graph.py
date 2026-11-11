"""Road and tram-track graph of Kyiv from an OpenStreetMap .pbf, for routing transit trips along
real streets when no OSM route relation matches (scripts/build_transit.py).

Output data/road_graph.npz: xy (float32 [n,2], metres, city-model projection), edges (int32 [m,2]),
net (uint8 [m]: 1 major road, 2 tram track, 3 tertiary, 4 residential, 5 service), length (float32 [m]). Ways are kept whole (every node),
so paths follow the street shape.

usage: python3 tools/osm_graph.py <kyiv.osm.pbf> data/road_graph.npz
"""
import math, sys
import numpy as np
import osmium

LAT0, LON0 = 50.45, 30.52
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110570
ROADS = {"motorway": 1, "trunk": 1, "primary": 1, "secondary": 1, "motorway_link": 1, "trunk_link": 1,
         "primary_link": 1, "secondary_link": 1, "tertiary": 3, "tertiary_link": 3, "busway": 3,
         "unclassified": 4, "residential": 4, "service": 5}
BOX = 30000   # metres from the centre

class G(osmium.SimpleHandler):
    def __init__(self):
        super().__init__(); self.idx = {}; self.xy = []; self.e = []; self.net = []
    def node_id(self, n):
        i = self.idx.get(n.ref)
        if i is None:
            x, z = (n.lon - LON0) * KX, -(n.lat - LAT0) * KY
            i = self.idx[n.ref] = len(self.xy); self.xy.append((x, z))
        return i
    def way(self, w):
        t = w.tags
        hw, rw = t.get("highway"), t.get("railway")
        if rw == "tram":
            net = 2
        elif hw in ROADS and t.get("access") not in ("no", "private") and t.get("service") not in ("parking_aisle", "driveway"):
            net = ROADS[hw]
        else:
            return
        try:
            ids = [self.node_id(n) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        for a, b in zip(ids, ids[1:]):
            if a != b:
                self.e.append((a, b)); self.net.append(net)

g = G(); g.apply_file(sys.argv[1], locations=True, idx="flex_mem")
xy = np.array(g.xy, dtype=np.float64); e = np.array(g.e, dtype=np.int64); net = np.array(g.net, dtype=np.uint8)
keep = (np.abs(xy[e[:, 0]]).max(1) < BOX) & (np.abs(xy[e[:, 1]]).max(1) < BOX)
e, net = e[keep], net[keep]
used = np.unique(e); remap = -np.ones(len(xy), dtype=np.int64); remap[used] = np.arange(len(used))
xy = xy[used]; e = remap[e]
length = np.hypot(*(xy[e[:, 0]] - xy[e[:, 1]]).T)
np.savez_compressed(sys.argv[2], xy=xy.astype(np.float32), edges=e.astype(np.int32), net=net, length=length.astype(np.float32))
print(f"graph: {len(xy)} nodes, {len(e)} edges (roads {int((net != 2).sum())}, tram {int((net == 2).sum())})")
