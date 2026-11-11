"""Public transport on the map: minimal 3D trams, trolleybuses and buses moving along their
routes by the Kyivpastrans timetable (transit.bin, see scripts/build_transit.py).
Applied once: python3 tools/patch_transit.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

JS = r'''
/* ---------- public transport by timetable ---------- */
const TR = { on: true, ready: false, kinds: [], shapes: null, trips: null, last: 0, vis: [] };
try { if (localStorage.getItem("svitlo.transit") === "off") TR.on = false; } catch(e) {}
const TR_NAMES = ["Трамвай", "Тролейбус", "Автобус"];
const TR_COL = [0xb9a9ff, 0x6fd6c4, 0xd9e0f0];          // lavender tram, teal trolleybus, silver bus
const TR_MAX = [260, 520, 900];

function trBoxes(list){
  // list of [cx, cy, cz, sx, sy, sz, part]; part 0 body, 1 glass, 2 roof gear
  const pos = [], nor = [], part = [];
  for (const [cx,cy,cz,sx,sy,sz,pt] of list){
    const g = new THREE.BoxGeometry(sx,sy,sz).toNonIndexed(); g.translate(cx,cy,cz);
    pos.push(...g.attributes.position.array); nor.push(...g.attributes.normal.array);
    for (let i=0;i<g.attributes.position.count;i++) part.push(pt);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos,3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(nor,3));
  g.setAttribute("part", new THREE.Float32BufferAttribute(part,1));
  return g;
}
function trGeometry(kind){
  // local x = direction of travel, metres
  if (kind === 0){                        // tram: three short sections and a pantograph
    const L=[];
    for (const x of [-9.6, 0, 9.6]){ L.push([x,1.95,0, 9.0,2.9,2.5, 0]); L.push([x,2.2,0, 8.2,1.0,2.56, 1]); }
    L.push([-14.0,2.0,0, 0.8,2.6,2.3, 0], [14.0,2.0,0, 0.8,2.6,2.3, 0]);   // rounded ends
    L.push([0,3.75,0, 2.4,0.18,1.6, 2], [0,4.15,0, 0.2,0.8,1.2, 2]);
    return trBoxes(L);
  }
  const L = [[0,1.75,0, 11.4,2.7,2.5, 0], [0.3,2.05,0, 10.4,0.95,2.56, 1], [5.55,1.75,0, 0.35,2.3,2.3, 0], [-1,3.25,0, 4.5,0.3,1.8, 2]];
  if (kind === 1){                        // trolleybus: two trolley poles slanting back
    for (const z of [-0.45, 0.45]){ L.push([-2.6,4.0,z, 6.4,0.14,0.14, 2]); }
  }
  return trBoxes(L);
}
function trMaterial(hex){
  return new THREE.ShaderMaterial({
    uniforms: Object.assign({ uBody: { value: new THREE.Color(hex) } }, common),
    vertexShader: `
      attribute float part; varying float vP; varying vec3 vN; varying vec3 vW;
      void main(){
        vec4 w = modelMatrix * instanceMatrix * vec4(position,1.0); vW = w.xyz; vP = part;
        vN = normalize(mat3(instanceMatrix) * normal);
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: `
      uniform vec3 uBody; uniform float uFogNear, uFogFar; uniform vec3 uFogCol;
      varying float vP; varying vec3 vN; varying vec3 vW; ${FOG}
      void main(){
        float diff = 0.55 + 0.45*max(dot(normalize(vN), normalize(vec3(-0.35,0.85,0.4))), 0.0);
        vec3 c = vP < 0.5 ? uBody : (vP < 1.5 ? vec3(0.10,0.13,0.24) : uBody*0.7);
        if (vN.y > 0.5 && vP < 0.5) c = mix(c, vec3(1.0), 0.12);     // light roof
        c *= diff;
        gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)*0.85), 1.0);
      }`
  });
}
TR.meshes = [0,1,2].map(k=>{
  const m = new THREE.InstancedMesh(trGeometry(k), trMaterial(TR_COL[k]), TR_MAX[k]);
  m.count = 0; m.frustumCulled = false; m.renderOrder = 4; m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(m); return m;
});

async function loadTransit(){
  try{
    const r = await fetch("transit.bin", {cache:"no-cache"}); if(!r.ok) return;
    const buf = await r.arrayBuffer(), dv = new DataView(buf);
    const hl = dv.getUint32(0, true), head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, hl))), base = 4 + hl;
    const A = (n, T) => { const [o,l] = head.arrays[n]; return new T(buf.slice(base+o, base+o+l)); };
    const sl = A("shapeLen", Uint16Array), xz = A("shapeXZ", Int16Array);
    const shapes = []; let o = 0;
    for (let i=0;i<sl.length;i++){
      const n = sl[i], pts = new Float32Array(n*2), cum = new Float32Array(n);
      for (let j=0;j<n;j++){ pts[j*2]=xz[(o+j)*2]; pts[j*2+1]=xz[(o+j)*2+1]; if(j) cum[j]=cum[j-1]+Math.hypot(pts[j*2]-pts[j*2-2], pts[j*2+1]-pts[j*2-1]); }
      shapes.push({pts, cum, len: cum[n-1]}); o += n;
    }
    TR.routes = head.routes; TR.shapes = shapes; TR.source = head.source;
    TR.trips = { shape: A("tripShape", Uint16Array), route: A("tripRoute", Uint16Array), start: A("tripStart", Uint16Array), end: A("tripEnd", Uint16Array), days: A("tripDays", Uint8Array) };
    TR.ready = true; trSync();
  }catch(e){ console.warn("transit", e); }
}
function trWeekday(dayOffset){            // 0 = Monday, for baseDate + dayOffset
  const d = new Date(addDays(baseDate, dayOffset) + "T12:00:00Z"); return (d.getUTCDay() + 6) % 7;
}
let trSetAt = performance.now(), trBase = 0;
function trTime(){                        // minutes from today's midnight, with seconds
  if (follow){ const now = new Date(), k = kyivParts(now); return (k.date===baseDate?0:1440) + k.min + now.getSeconds()/60 + now.getMilliseconds()/60000; }
  return trBase + (performance.now() - trSetAt) / 60000;
}
function trFirst(arr, v){ let lo=0, hi=arr.length; while(lo<hi){ const m=(lo+hi)>>1; if(arr[m]<v) lo=m+1; else hi=m; } return lo; }
const _m = new THREE.Matrix4();
function trUpdate(){
  const T = trTime(), t = TR.trips, cnt = [0,0,0], vis = [];
  const camD = camera.position.distanceTo(controls.target), sc = Math.min(15, Math.max(1.6, camD/950));
  for (const d of [-1, 0, 1]){
    const tt = T - 1440*d; if (tt < 0 || tt > 1440 + 300) continue;
    const bit = 1 << trWeekday(d);
    for (let i = trFirst(t.start, tt - 300); i < t.start.length && t.start[i] <= tt; i++){
      if (t.end[i] <= tt || !(t.days[i] & bit)) continue;
      const r = t.route[i], k = TR.routes[r][2]; if (cnt[k] >= TR_MAX[k]) continue;
      const sh = TR.shapes[t.shape[i]], along = (tt - t.start[i]) / (t.end[i] - t.start[i]) * sh.len;
      let j = trFirst(sh.cum, along); j = Math.min(Math.max(j, 1), sh.cum.length - 1);
      const p = sh.pts, seg = (sh.cum[j] - sh.cum[j-1]) || 1, f = (along - sh.cum[j-1]) / seg;
      let dx = p[j*2] - p[j*2-2], dz = p[j*2+1] - p[j*2-1]; const dl = Math.hypot(dx, dz) || 1; dx/=dl; dz/=dl;
      const off = 2.2*sc;                                         // keep to the right-hand side of the road
      const x = p[j*2-2] + dx*f*seg - dz*off, z = p[j*2-1] + dz*f*seg + dx*off;
      _m.set(dx*sc, 0, -dz*sc, x,   0, sc, 0, 0.6,   dz*sc, 0, dx*sc, z,   0, 0, 0, 1);
      TR.meshes[k].setMatrixAt(cnt[k]++, _m);
      vis.push(x, z, r);
    }
  }
  TR.meshes.forEach((m,k)=>{ m.count = cnt[k]; m.instanceMatrix.needsUpdate = true; });
  TR.vis = vis;
}
function trSync(){
  TR.meshes.forEach(m=> m.visible = TR.on && TR.ready);
  const b = $("trBtn"); if (b){ b.classList.toggle("active", TR.on); b.setAttribute("aria-pressed", TR.on); }
  if (TR.on && TR.ready) trUpdate();
  needs = true;
}
function trTick(now){                     // called from the render loop
  if (!(TR.on && TR.ready)) return;
  const camD = camera.position.distanceTo(controls.target);
  const every = camD < 6000 ? 33 : camD < 16000 ? 120 : 400;    // smooth up close, cheap from afar
  if (now - TR.last < every) return;
  TR.last = now; trUpdate(); needs = true;
}
function trPick(ev){                      // vehicle under the pointer, if any
  if (!(TR.on && TR.ready) || !TR.vis.length) return null;
  const r = canvas.getBoundingClientRect(), v = new THREE.Vector3(); let best = null, bd = 14*14;
  for (let i=0;i<TR.vis.length;i+=3){
    v.set(TR.vis[i], 3, TR.vis[i+1]).project(camera); if (v.z > 1) continue;
    const sx = (v.x+1)/2*r.width + r.left, sy = (1-v.y)/2*r.height + r.top, d = (sx-ev.clientX)**2 + (sy-ev.clientY)**2;
    if (d < bd){ bd = d; best = TR.vis[i+2]; }
  }
  if (best === null) return null;
  const [num, name, k] = TR.routes[best];
  return `<div class="st tr k${k}">${TR_NAMES[k]} ${num}</div>` + (name ? `<div>${name.replace(/</g,"&lt;")}</div>` : "") +
         `<div class="m">Положення за розкладом Київпастрансу, не GPS</div>`;
}
'''

rep("/* ---------- render loop ---------- */", JS + "\n/* ---------- render loop ---------- */")
rep('''(function loop(){
  requestAnimationFrame(loop);''', '''(function loop(now){
  requestAnimationFrame(loop);
  trTick(now || performance.now());''')
# start loading once the city is up
rep('''  $("loader").hidden = true;
  console.log("city built"''', '''  $("loader").hidden = true;
  loadTransit();
  console.log("city built"''')
# slider: vehicles keep moving from the chosen time
rep('function setT(v, f=false){ tMin=Math.max(0,Math.min(2879,v)); follow=f; slider.value=tMin; $("nowBtn").classList.toggle("active",f); apply(); }',
    'function setT(v, f=false){ tMin=Math.max(0,Math.min(2879,v)); follow=f; slider.value=tMin; $("nowBtn").classList.toggle("active",f); trBase=tMin; trSetAt=performance.now(); apply(); if(typeof TR!=="undefined" && TR.ready) trSync(); }')
# tooltip: a vehicle wins over the building below it
rep('''  ray.setFromCamera(mouse,camera);
  if(!ray.ray.intersectPlane(plane, hit)){ tip.hidden=true; return; }''', '''  ray.setFromCamera(mouse,camera);
  const veh = trPick(ev);
  if(veh){ tip.innerHTML = veh; tip.hidden=false;
    const tx=Math.min(ev.clientX+14, innerWidth-tip.offsetWidth-8), ty=Math.min(ev.clientY+14, innerHeight-tip.offsetHeight-8);
    tip.style.left=Math.max(8,tx)+"px"; tip.style.top=Math.max(8,ty)+"px"; return; }
  if(!ray.ray.intersectPlane(plane, hit)){ tip.hidden=true; return; }''')
# toggle button next to the time buttons
rep('''      <button type="button" id="nowBtn" class="active">Зараз</button>''',
    '''      <button type="button" id="trBtn" class="tr-btn active" aria-pressed="true" title="Громадський транспорт за розкладом" aria-label="Громадський транспорт"><svg viewBox="0 0 20 20" width="15" height="15" aria-hidden="true"><rect x="3.5" y="2.5" width="13" height="12" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M3.5 9h13M7 14.5v2.5M13 14.5v2.5" stroke="currentColor" stroke-width="1.6" fill="none"/><circle cx="7" cy="12" r="1" fill="currentColor"/><circle cx="13" cy="12" r="1" fill="currentColor"/></svg></button>
      <button type="button" id="nowBtn" class="active">Зараз</button>''')
rep('$("nowBtn").onclick = ()=> setT(absNow(), true);', '''$("nowBtn").onclick = ()=> setT(absNow(), true);
$("trBtn").onclick = ()=>{ TR.on = !TR.on; try{ localStorage.setItem("svitlo.transit", TR.on ? "on" : "off"); }catch(e){} trSync(); };''')
# legend and source note
rep('''<span id="lgEm" hidden><i class="sw em"></i>екстрені відключення</span></div>''',
    '''<span id="lgEm" hidden><i class="sw em"></i>екстрені відключення</span><span><i class="sw t0"></i>трамвай</span><span><i class="sw t1"></i>тролейбус</span><span><i class="sw t2"></i>автобус</span></div>''')
rep('''    <p class="note">Будинки, вулиці, вода й парки взяті з OpenStreetMap''',
    '''    <p class="note"><strong>Транспорт рухається за розкладом</strong> КП «Київпастранс» (відкриті дані, CC BY 4.0), а не за GPS: затримки, скасовані рейси й зупинки під час тривог карта не показує. Траси маршрутів — з OpenStreetMap. Метро й маршруток у цих даних немає. Кнопка з автобусом унизу вмикає й вимикає транспорт.</p>
    <p class="note">Будинки, вулиці, вода й парки взяті з OpenStreetMap''')
rep('.sw.em{background:#4a3f63}', '''.sw.em{background:#4a3f63}
.sw.t0{background:#b9a9ff;border-radius:3px}.sw.t1{background:#6fd6c4;border-radius:3px}.sw.t2{background:#d9e0f0;border-radius:3px}
.tip .st.tr.k0{color:#b9a9ff}.tip .st.tr.k1{color:#6fd6c4}.tip .st.tr.k2{color:#d9e0f0}
.btns .tr-btn{padding-left:9px;padding-right:9px;display:inline-flex;align-items:center;justify-content:center;color:var(--muted)}
.btns .tr-btn.active{color:#6fd6c4;border-color:rgba(111,214,196,.45)}''')
open(p, "w").write(s)
print("ok")
