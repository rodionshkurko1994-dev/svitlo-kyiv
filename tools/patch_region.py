"""Kyiv agglomeration on the map (data from tools/build_region.py, folder region/).

- base layer (ground, water, forests, main roads, railways) loads right after the city
- buildings come in 8 km tiles, loaded when the camera gets close; drawn neutral: no power data for the oblast
- town labels, wider camera bounds, hover tip, "Мій дім" search and pick for region addresses
Applied once: python3 tools/patch_region.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new, count=1):
    global s
    assert s.count(old) >= 1, old[:90]
    s = s.replace(old, new, count)

JS = r'''/* ---------- Kyiv agglomeration (OpenStreetMap, no power data) ---------- */
const RG = { man: null, tiles: [], loading: 0, cell: new Map(), bx: [], bz: [], towns: [], els: [] };
function rgParse(buf){
  const n = new DataView(buf).getUint32(0, true), H = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n))), b0 = 4 + n;
  return { H, v: (k, T) => { const [o, l] = H.arrays[k]; return new T(buf, b0 + o, l / T.BYTES_PER_ELEMENT); } };
}
function rgLines(len, co, scale, ox, oz, rankArr, rankConst){
  let segs = 0; for (let i = 0; i < len.length; i++) segs += Math.max(0, len[i] - 1);
  const rp = new Float32Array(segs*6), rz = new Uint8Array(segs*2), rk = new Uint8Array(segs*2);
  let p = 0, q = 0;
  for (let i = 0; i < len.length; i++){
    const n = len[i], r = rankArr ? rankArr[i] : rankConst;
    for (let k = 0; k < n - 1; k++){
      rp.set([co[(p+k)*2]*scale + ox, 1.5, co[(p+k)*2+1]*scale + oz, co[(p+k+1)*2]*scale + ox, 1.5, co[(p+k+1)*2+1]*scale + oz], q*6);
      rk[q*2] = rk[q*2+1] = r; q++;
    }
    p += n;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(rp, 3));
  g.setAttribute("zone", new THREE.BufferAttribute(rz, 1));
  g.setAttribute("rank", new THREE.BufferAttribute(rk, 1));
  const m = new THREE.LineSegments(g, roadMat); m.frustumCulled = false; m.renderOrder = 2; scene.add(m); return m;
}
async function regionInit(){
  try{
    RG.man = await (await fetch("region/manifest.json")).json();
    RG.tiles = RG.man.tiles.map(t => Object.assign({ state: 0 }, t));
    RG.towns = RG.man.towns.filter(t => t.k === "city" || t.k === "town" || t.p >= 5000);
    RG.els = RG.towns.map(t => { const el = document.createElement("div"); el.className = "dlabel town"; el.textContent = t.n; $("labels").appendChild(el); return el; });
    const { v } = rgParse(await (await fetch("region/base.bin")).arrayBuffer());
    const sc = a => { const f = new Float32Array(a.length); for (let i = 0; i < a.length; i++) f[i] = a[i]*2; return f; };
    triMesh(sc(v("ground", Int16Array)), 0x0c1122, 0, 0x454a54);
    triMesh(sc(v("green", Int16Array)), 0x0c1a17, 0.3, 0x3b483f);
    triMesh(sc(v("water", Int16Array)), 0x0a1b38, 0.6, 0x34465f).material.uniforms.uSnowable.value = 0;
    rgLines(v("roadLen", Uint16Array), v("roadCoords", Int16Array), 2, 0, 0, v("roadRank", Uint8Array));
    needs = true; setInterval(regionTick, 400); regionTick();
    if (homeSaved && homeSaved.reg) homeRender();
  }catch(e){ console.warn("region", e); }
}
function regionTick(){
  if (!RG.man || RG.loading >= 2) return;
  const d = controls.dist; if (d > 24000) return;
  const R = Math.min(26000, d*0.9 + 7000), tx = controls.target.x, tz = controls.target.z;
  let best = null, bd = R*R;
  for (const t of RG.tiles){ if (t.state) continue; const e = (t.x-tx)**2 + (t.z-tz)**2; if (e < bd){ bd = e; best = t; } }
  if (best) regionTile(best);
}
async function regionTile(t){
  t.state = 1; RG.loading++;
  try{
    const { H, v } = rgParse(await (await fetch("region/" + t.f)).arrayBuffer());
    const [ox, oz] = H.origin, height = v("height", Uint16Array), rc = v("ringCount", Uint8Array), rl = v("ringLen", Uint16Array), co = v("coords", Int16Array);
    const n = height.length;
    let V = 0, I = 0, ri = 0;
    for (let b = 0; b < n; b++){ for (let r = 0; r < rc[b]; r++){ const k = rl[ri+r]; V += k*2; I += k*9; } ri += rc[b]; }
    const pos = new Float32Array(V*3), zat = new Uint8Array(V), idx = new Uint32Array(I);
    let vv = 0, ii = 0, pi = 0; ri = 0;
    for (let b = 0; b < n; b++){
      const h = height[b]/10, contour = [], holes = [], starts = []; let sx = 0, sz = 0, sn = 0;
      for (let r = 0; r < rc[b]; r++){
        const k = rl[ri+r], ring = [], st = vv;
        for (let j = 0; j < k; j++){
          const x = co[pi*2] + ox, y = co[pi*2+1] + oz; pi++;
          pos.set([x, 0, y, x, h, y], vv*3); ring.push(new THREE.Vector2(x, y)); vv += 2;
          if (r === 0){ sx += x; sz += y; sn++; }
        }
        for (let j = 0; j < k; j++){ const a = st + j*2, c = st + ((j+1)%k)*2; idx.set([a, c, c+1, a, c+1, a+1], ii); ii += 6; }
        if (r === 0) contour.push(...ring); else holes.push(ring);
        starts.push(st);
      }
      ri += rc[b];
      let faces; try{ faces = THREE.ShapeUtils.triangulateShape(contour, holes); }catch(e){ faces = []; }
      const map = []; starts.forEach((st, r) => { const k = r === 0 ? contour.length : holes[r-1].length; for (let j = 0; j < k; j++) map.push(st + j*2 + 1); });
      for (const f of faces){ idx[ii++] = map[f[0]]; idx[ii++] = map[f[1]]; idx[ii++] = map[f[2]]; }
      const cx = sx/sn, cz = sz/sn, key = Math.floor(cx/200)*100000 + Math.floor(cz/200), id = RG.bx.length;
      RG.bx.push(cx); RG.bz.push(cz); let l = RG.cell.get(key); if (!l){ l = []; RG.cell.set(key, l); } l.push(id);
      if ((b & 2047) === 2047) await new Promise(r => setTimeout(r, 0));
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("zone", new THREE.BufferAttribute(zat, 1));
    g.setIndex(new THREE.BufferAttribute(idx.subarray(0, ii), 1));
    const m = new THREE.Mesh(g, bMat); m.frustumCulled = false; scene.add(m);
    rgLines(v("streetLen", Uint16Array), v("streetCoords", Int16Array), 1, ox, oz, null, 3);
    t.state = 2; needs = true;
    if (homeSaved && homeSaved.reg) homeRender();
  }catch(e){ t.state = 0; console.warn("region tile", t.f, e); }
  RG.loading--;
}
function regionAt(x, z){
  const cx = Math.floor(x/200), cz = Math.floor(z/200); let best = -1, bd = 45*45;
  for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++){
    const l = RG.cell.get((cx+dx)*100000 + (cz+dz)); if (!l) continue;
    for (const i of l){ const ex = RG.bx[i]-x, ez = RG.bz[i]-z, d = ex*ex + ez*ez; if (d < bd){ bd = d; best = i; } }
  }
  return best;
}
function regionTown(x, z){
  let best = "", bd = 6000*6000;
  if (RG.man) for (const t of RG.man.towns){ const d = (t.x-x)**2 + (t.z-z)**2; if (d < bd){ bd = d; best = t.n; } }
  return best;
}
function regionTip(x, z){
  if (regionAt(x, z) < 0) return null;
  const town = regionTown(x, z);
  return `<div class="st">Київська область</div>` + (town ? `<div>${town.replace(/</g,"&lt;")}</div>` : "") +
    `<div class="m">Графіків відключень для області на карті поки немає: ДТЕК Київські регіональні електромережі не публікує їх у відкритому доступі</div>`;
}
function regionLabels(){
  const w = innerWidth, h = innerHeight;
  RG.towns.forEach((t, i) => {
    const el = RG.els[i];
    _v.set(t.x, 420, t.z).project(camera);
    if (_v.z > 1 || _v.z < -1 || Math.abs(_v.x) > 1.1 || Math.abs(_v.y) > 1.1){ el.style.opacity = "0"; return; }
    const dist = camera.position.distanceTo(_v.set(t.x, 420, t.z)), far = t.k === "city" || t.p >= 30000 ? 80000 : 42000;
    el.style.opacity = Math.max(0, Math.min(1, (far - dist)/18000)).toFixed(2);
    _v.project(camera);
    el.style.transform = `translate(${((_v.x+1)/2*w).toFixed(1)}px, ${((1-_v.y)/2*h).toFixed(1)}px) translate(-50%,-100%)`;
  });
}

'''

# region block before the district labels, labels updated with them
rep('/* ---------- district labels floating above the map ---------- */', JS + '/* ---------- district labels floating above the map ---------- */')
rep('if (typeof homePinUpdate === "function") homePinUpdate();', 'if (typeof homePinUpdate === "function") homePinUpdate();\n  if (RG.els.length) regionLabels();')
rep('loadTransit(); homeRender(); envUpdate();', 'loadTransit(); homeRender(); envUpdate(); regionInit();')
rep('this.bound = 26000;', 'this.bound = 48000;')
rep('.dlabel{', '.dlabel.town{font-size:10px;opacity:0;color:#aeb8d8;letter-spacing:.06em}\n.dlabel{')

# hover / tap tip in the region
rep('  if(bi < 0){ tip.hidden=true; return; }',
    '  if(bi < 0){ const rt = regionTip(hit.x, hit.z); if(!rt){ tip.hidden=true; return; } html = rt; }\n  else {')
rep('''      `<div class="m">${src}</div>`;
  }
  tip.innerHTML = html;''', '''      `<div class="m">${src}</div>`;
  }
  }
  tip.innerHTML = html;''')

# "Мій дім": region addresses and buildings
rep('''  $("homeName").textContent = homeSaved.label;
  const bi = homeBuilding();''', '''  $("homeName").textContent = homeSaved.label;
  if (homeSaved.reg){
    $("homeNow").className = "home-now"; $("homeNow").textContent = "Київська область: графіків поки немає";
    $("homeDay").innerHTML = 'ДТЕК не публікує графіки області відкрито. Перевірте на <a href="https://www.dtek-krem.com.ua/ua/shutdowns" target="_blank" rel="noopener">сайті ДТЕК КРЕМ</a>';
    return;
  }
  const bi = homeBuilding();''')
rep('''function homeSave(bi, label){
  homeSaved = {x: Math.round(bcx[bi]), z: Math.round(bcz[bi]), label};''', '''function homeSave(bi, label){ homeSaveAt(bcx[bi], bcz[bi], label, false); }
function homeSaveAt(x, z, label, reg){
  homeSaved = {x: Math.round(x), z: Math.round(z), label}; if (reg) homeSaved.reg = 1;''')
rep('''  ADDR = {streets: d.streets, norm: d.streets.map(NORM), a: d.a, byStreet: new Map()};
  for (const r of d.a){''', '''  ADDR = {streets: d.streets, place: d.streets.map(() => ""), norm: d.streets.map(NORM), a: d.a, byStreet: new Map()};
  try{                                       // Kyiv agglomeration: rows [street, house, -1, x, z]
    const g = await (await fetch("region/addr.json")).json(), base = ADDR.streets.length, key = new Map();
    for (const [pi, si, hn, x, z] of g.a){
      const k = pi + "|" + si; let id = key.get(k);
      if (id == null){ id = ADDR.streets.length; key.set(k, id); ADDR.streets.push(g.streets[si]); ADDR.place.push(g.places[pi] || ""); ADDR.norm.push(NORM(g.streets[si] + " " + (g.places[pi] || ""))); }
      ADDR.a.push([id, hn, -1, x, z]);
    }
  }catch(e){}
  for (const r of ADDR.a){''')
rep('''`<li role="option" tabindex="0" data-i="${i}">${ADDR.streets[r[0]].replace(/</g,"&lt;")}, <b>${r[1].replace(/</g,"&lt;")}</b></li>`''',
    '''`<li role="option" tabindex="0" data-i="${i}">${ADDR.streets[r[0]].replace(/</g,"&lt;")}, <b>${r[1].replace(/</g,"&lt;")}</b>${ADDR.place[r[0]] ? ` <small>· ${ADDR.place[r[0]].replace(/</g,"&lt;")}</small>` : ""}</li>`''')
rep('''const choose = () => { const r = res[+li.dataset.i]; sheetClose(); homeSave(r[2], `${ADDR.streets[r[0]]}, ${r[1]}`); };''',
    '''const choose = () => { const r = res[+li.dataset.i], pl = ADDR.place[r[0]]; sheetClose();
      if (r[2] >= 0) homeSave(r[2], `${ADDR.streets[r[0]]}, ${r[1]}`); else homeSaveAt(r[3], r[4], `${pl ? pl + ", " : ""}${ADDR.streets[r[0]]}, ${r[1]}`, true); };''')
rep('''  const bi = buildingAt(hit.x, hit.z); if (bi < 0) return;
  homePicking = false; $("pickBar").hidden = true; tip.hidden = true;
  homeSave(bi, "Мій будинок на карті");''', '''  const bi = buildingAt(hit.x, hit.z), rb = bi < 0 ? regionAt(hit.x, hit.z) : -1; if (bi < 0 && rb < 0) return;
  homePicking = false; $("pickBar").hidden = true; tip.hidden = true;
  if (bi >= 0) homeSave(bi, "Мій будинок на карті");
  else { const t = regionTown(RG.bx[rb], RG.bz[rb]); homeSaveAt(RG.bx[rb], RG.bz[rb], (t ? t + ", " : "") + "мій будинок на карті", true); }''')
open(p, "w").write(s)
print("ok")
