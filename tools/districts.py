import osmium, json, math
from shapely import wkb
LAT0, LON0 = 50.45, 30.52
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110570
fab = osmium.geom.WKBFactory()
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.out=[]
    def area(s, a):
        t=a.tags
        if t.get('boundary')=='administrative' and t.get('name','').endswith('район') and not a.from_way():
            try:
                g=wkb.loads(fab.create_multipolygon(a), hex=True)
                s.out.append((t.get('name'), t.get('admin_level'), g))
            except Exception as e: print('err', t.get('name'), e)
h=H(); h.apply_file("/mnt/user-data/uploads/Downloads/planet_30.23,50.21_30.83,50.59.osm.pbf", locations=True, idx='flex_mem')
res=[]
for n,l,g in h.out:
    p=g.representative_point() if g.geom_type!='Polygon' else g.centroid
    if not g.contains(p): p=g.representative_point()
    # pole of inaccessibility-ish: use shapely's maximum_inscribed_circle center if available
    try:
        import shapely; c=shapely.maximum_inscribed_circle(g, 0.0005).coords[0]; p=shapely.Point(c)
    except Exception: pass
    x=(p.x-LON0)*KX; z=-(p.y-LAT0)*KY
    print(n,l,round(g.area*1e4,1),round(x),round(z))
    res.append({'name':n.replace(' район',''),'lvl':l,'x':round(x),'z':round(z),'a':g.area})
json.dump(res,open('districts.json','w'),ensure_ascii=False)
