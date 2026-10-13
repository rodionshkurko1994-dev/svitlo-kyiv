"""Turn the sample-based page into the per-building-group page (v2).

usage: python3 patch_v2.py <in.html> <out.html> <meta_v2.json> <data file name>
"""
import sys, re, json

src, dst, meta_path, data_name = sys.argv[1:5]
s = open(src).read()
meta = json.load(open(meta_path))
st = meta['stats']

def rep(old, new, count=1):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, count)

# embedded META
i = s.index('const META = ') + len('const META = ')
j = s.index(';\nconst SEED')
s = s[:i] + json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + s[j:]

rep('const SAMPLES = META.samples, MAXD = META.maxd, NZ = 63;',
    'const NZ = 0, MST = META.stats || {};')

# zoneAt -> nearest building lookup (filled once the city is built)
a = s.index('function zoneAt(x, z){')
b = s.index('\n}', s.index('return {zone:', a)) + 2
s = s[:a] + '''let cellIdx = null, bcx = null, bcz = null, srcArr = null;
function buildingAt(x, z){
  if(!cellIdx) return -1;
  const cx=Math.floor(x/200), cz=Math.floor(z/200); let best=-1, bd=45*45;
  for(let dx=-1;dx<=1;dx++) for(let dz=-1;dz<=1;dz++){
    const l=cellIdx.get((cx+dx)*100000+(cz+dz)); if(!l) continue;
    for(const i of l){ const ex=bcx[i]-x, ez=bcz[i]-z, d=ex*ex+ez*ez; if(d<bd){bd=d;best=i;} }
  }
  return best;
}''' + s[b:]

rep('fetch("kyiv3d.txt")', f'fetch("{data_name}")')
rep('const total = 6888940;', 'const total = 7200000;')
rep('''  bCount = zone.length; zoneArr = zone;
  for(let i=0;i<bCount;i++){ const z = zone[i]===255?NZ:zone[i]; zoneBuildings[z]++; }''',
    '''  bCount = zone.length; zoneArr = zone; srcArr = view("src",Uint8Array);
  bcx = new Float32Array(bCount); bcz = new Float32Array(bCount);
  for(let i=0;i<bCount;i++){ const z = zone[i]>60?NZ:zone[i]; zoneBuildings[z]++; }''')
rep('const h = height[b]/10, z = zone[b]===255?NZ:zone[b];',
    'const h = height[b]/10, z = zone[b]>60?NZ:zone[b]; let sx=0, sz=0, sn=0;')
rep('''        ring.push(new THREE.Vector2(x,y)); v+=2;''',
    '''        ring.push(new THREE.Vector2(x,y)); v+=2;
        if(r===0){ sx+=x; sz+=y; sn++; }''')
rep('''    ri+=rc[b];
    // roof''', '''    ri+=rc[b];
    bcx[b]=sx/sn; bcz[b]=sz/sn;
    // roof''')
# spatial index after the building loop
rep('''  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos,3));''', '''  cellIdx = new Map();
  for(let i=0;i<bCount;i++){ const k=Math.floor(bcx[i]/200)*100000+Math.floor(bcz[i]/200); let l=cellIdx.get(k); if(!l){ l=[]; cellIdx.set(k,l); } l.push(i); }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos,3));''')
# roads: per-point zones from the file
rep('''  let p=0, s=0, zc=new Map();
  const zKey=(x,y)=>{ const k=((x>>7)+512)*2048+((y>>7)+512); let zz=zc.get(k); if(zz===undefined){ zz=zoneAt(x,y).zone; zc.set(k,zz);} return zz; };''',
    '''  let p=0, s=0; const rzv = view("roadZone",Uint8Array);''')
rep('rz[s*2]=zKey(x0,y0); rz[s*2+1]=zKey(x1,y1);', 'rz[s*2]=rzv[p+k]; rz[s*2+1]=rzv[p+k+1];')
# apply(): one uniform slot per YASNO group
rep('''  SAMPLES.forEach((s,k)=>{ if(!(s.group in per)) per[s.group]=stateAt(s.group,tMin); const st=per[s.group];
    if(st.emergency) emergency=true;
    target[k] = st.state==="on"?1:st.state==="off"?0:0.5;
    const n = zoneBuildings[k]; st.state==="on"?on+=n:st.state==="off"?off+=n:unk+=n; });''',
    '''  for(let g=1; g<=60; g++){ const st=stateAt(g,tMin); per[g]=st;
    if(st.emergency) emergency=true;
    target[g] = st.state==="on"?1:st.state==="off"?0:0.5;
    const n = zoneBuildings[g]; st.state==="on"?on+=n:st.state==="off"?off+=n:unk+=n; }''')
rep('''const byGroup={}; SAMPLES.forEach((s,k)=>{ byGroup[s.group]=(byGroup[s.group]||0)+(zoneBuildings[k]||1); });''',
    '''const byGroup={}; for(let g=1; g<=60; g++) byGroup[g]=zoneBuildings[g]||1;''')
# tooltip: the building under the cursor
a = s.index('  const {zone, dist} = zoneAt(hit.x, hit.z);')
b = s.index('  tip.innerHTML = html; tip.hidden=false;')
s = s[:a] + '''  const bi = buildingAt(hit.x, hit.z);
  let html;
  if(bi < 0){ tip.hidden=true; return; }
  const grp = zoneArr[bi] > 60 ? 0 : zoneArr[bi], how = srcArr[bi];
  if(!grp){ html = `<div class="st">Немає даних</div><div class="m">Для цього будинку й найближчих сусідів група невідома</div>`; }
  else {
    const st=stateAt(grp,tMin), nx=nextChange(grp,tMin);
    const label = st.state==="on"?"Світло є":st.state==="off"?"Світла немає":"Немає графіка";
    const src = how===1 ? "група за адресою будинку" : how===2 ? "група за сусіднім корпусом того ж номера" : "група оцінена за найближчим будинком";
    html = `<div class="st ${st.state}">${label}</div><div>Група ${grp}</div>`+
      (nx?`<div class="m">${nx.to==="on"?"Увімкнуть":nx.to==="off"?"Вимкнуть":"Далі немає графіка"} о ${hhmm(nx.at%1440)}${nx.at>=1440?" завтра":""}</div>`:"")+
      `<div class="m">${src}</div>`;
  }
''' + s[b:]
rep('$("nSamples").textContent = SAMPLES.length;', '')
# explanation text
a = s.index('<p class="note">З 12–13 жовтня 2026 року')
b = s.index('</p>', a) + 4
pct = round(100 * (st['byAddress'] + st['byAddressNear']) / st['buildings'])
pctN = round(100 * st['byNeighbour'] / st['buildings'])
s = s[:a] + f'''<p class="note">З 12–13 жовтня 2026 року в Києві немає черг: ДТЕК розраховує графік окремо для кожного будинку. YASNO відносить кожну адресу до одного з кількох десятків варіантів графіка («груп»). Я запитав групу для {format(st['addresses'], ',').replace(',', ' ')} адрес з OpenStreetMap: {pct}% будинків на карті пофарбовані за власною адресою, ще {pctN}% (переважно без адреси в OSM) отримали групу найближчого перевіреного будинку в радіусі 150 м. Сірі будинки — без даних. Точний графік своєї адреси дивіться на <a href="https://www.dtek-kem.com.ua/ua/shutdowns" target="_blank" rel="noopener">сайті ДТЕК Київські електромережі</a>, у застосунку «Київ Цифровий» або на <a href="https://yasno.ua" target="_blank" rel="noopener">yasno.ua</a>. Графік може змінитися протягом дня.</p>''' + s[b:]
rep('Графіки тепер індивідуальні для кожного будинку, тож колір кварталу орієнтовний.',
    'Будинки пофарбовані за групою своєї адреси в YASNO; частина — за найближчим сусідом.')
open(dst, 'w').write(s)
print('ok', dst, 'by address', pct, '% neighbour', pctN, '%')
