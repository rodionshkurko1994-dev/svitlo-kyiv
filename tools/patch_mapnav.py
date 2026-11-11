"""Google-Maps-style camera controls instead of three.js OrbitControls:
drag pans (the point under the finger stays under it), wheel / pinch zoom towards the cursor,
right-drag or Ctrl/Shift+drag rotates and tilts, two-finger twist rotates, two fingers moving up
or down tilt, double click / double tap zooms in, the pan keeps some momentum, arrow keys and +/-
work, and a compass shows north (tap it to turn north-up again).
Applied once: python3 tools/patch_mapnav.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

NAV = r'''/* ---------- map navigation (Google Maps style) ---------- */
class MapNav extends THREE.EventDispatcher {
  constructor(camera, el){
    super();
    this.camera = camera; this.el = el; this.target = new THREE.Vector3();
    this.minDistance = 200; this.maxDistance = 60000; this.maxTilt = 1.25; this.bound = 26000;
    const off = camera.position.clone().sub(this.target);
    this.dist = off.length(); this.az = Math.atan2(off.x, off.z); this.tilt = Math.acos(Math.min(1, off.y/this.dist));
    this.pointers = new Map(); this.vel = new THREE.Vector2(); this.anim = null; this.dirty = true; this.lastTap = 0;
    this._ray = new THREE.Raycaster(); this._ndc = new THREE.Vector2(); this._plane = new THREE.Plane(new THREE.Vector3(0,1,0), 0);
    el.style.touchAction = "none";
    el.addEventListener("pointerdown", e=>this.down(e));
    el.addEventListener("pointermove", e=>this.move(e));
    el.addEventListener("pointerup", e=>this.up(e));
    el.addEventListener("pointercancel", e=>this.up(e));
    el.addEventListener("lostpointercapture", e=>this.up(e));
    // the release of a right-button drag can be swallowed by the context menu: end the drag on any
    // sign that no mouse button is held any more
    addEventListener("pointerup", e=>this.up(e));
    addEventListener("mouseup", e=>{ if (!e.buttons) this.endMouse(); });
    addEventListener("blur", ()=>this.endMouse());
    el.addEventListener("wheel", e=>this.wheel(e), {passive:false});
    el.addEventListener("contextmenu", e=>e.preventDefault());
    el.addEventListener("dblclick", e=>{ if(e.pointerType!=="touch") this.zoomAt(e.clientX, e.clientY, 0.5, true); });
    el.addEventListener("keydown", e=>this.key(e));
  }
  setFrom(target){                         // take the current camera position around a new target
    this.target.copy(target);
    const off = this.camera.position.clone().sub(target);
    this.dist = off.length(); this.az = Math.atan2(off.x, off.z); this.tilt = Math.acos(Math.min(1, off.y/this.dist)); this.apply();
  }
  apply(){
    this.dist = Math.min(this.maxDistance, Math.max(this.minDistance, this.dist));
    this.tilt = Math.min(this.maxTilt, Math.max(0.0001, this.tilt));
    this.target.x = Math.max(-this.bound, Math.min(this.bound, this.target.x));
    this.target.z = Math.max(-this.bound, Math.min(this.bound, this.target.z)); this.target.y = 0;
    const st = Math.sin(this.tilt);
    this.camera.position.set(this.target.x + this.dist*st*Math.sin(this.az), this.dist*Math.cos(this.tilt), this.target.z + this.dist*st*Math.cos(this.az));
    this.camera.lookAt(this.target); this.camera.updateMatrixWorld();
    this.dirty = true;
  }
  ground(x, y){                            // ground point under a screen point (or toward the horizon)
    const r = this.el.getBoundingClientRect();
    this._ndc.set((x-r.left)/r.width*2-1, -(y-r.top)/r.height*2+1);
    this._ray.setFromCamera(this._ndc, this.camera);
    const d = this._ray.ray.direction;
    if (d.y > -0.05){ d.y = -0.05; d.normalize(); }   // above the horizon: clamp so the map never flies away
    const out = new THREE.Vector3(); this._ray.ray.intersectPlane(this._plane, out); return out;
  }
  keep(g, x, y){                           // move the map so ground point g sits under (x, y)
    const now = this.ground(x, y); this.target.x += g.x - now.x; this.target.z += g.z - now.z; this.apply();
  }
  zoomAt(x, y, f, animated){
    if (animated){ this.anim = {x, y, f, t0: performance.now(), done: 1}; return; }
    const g = this.ground(x, y); this.dist *= f; this.apply(); this.keep(g, x, y);
  }
  down(e){
    this.el.focus({preventScroll:true});
    this.el.setPointerCapture && this.el.setPointerCapture(e.pointerId);
    this.vel.set(0,0); this.anim = null;
    this.pointers.set(e.pointerId, {x:e.clientX, y:e.clientY, t:performance.now(), mouse: e.pointerType === "mouse"});
    const rot = e.pointerType === "mouse" && (e.button === 2 || e.ctrlKey || e.shiftKey || e.metaKey);
    this.start(rot ? "rotate" : null);
    if (e.pointerType === "touch" && this.pointers.size === 1){
      const t = performance.now();
      if (t - this.lastTap < 300 && Math.hypot(e.clientX-this.lastTapX, e.clientY-this.lastTapY) < 30){ this.zoomAt(e.clientX, e.clientY, 0.5, true); this.lastTap = 0; }
      else { this.lastTap = t; this.lastTapX = e.clientX; this.lastTapY = e.clientY; }
    }
  }
  start(mode){
    const P = [...this.pointers.values()];
    if (P.length === 1){
      this.mode = mode || "pan"; this.grab = this.ground(P[0].x, P[0].y); this.track = [];
    } else if (P.length >= 2){
      const [a, b] = P; this.mode = "two"; this.gesture = null;
      this.m0 = {x:(a.x+b.x)/2, y:(a.y+b.y)/2, d:Math.hypot(b.x-a.x, b.y-a.y), ang:Math.atan2(b.y-a.y, b.x-a.x)};
      this.prev = {...this.m0}; this.grab = this.ground(this.m0.x, this.m0.y);
      this.f0 = P.slice(0, 2).map(q => ({x:q.x, y:q.y}));
    }
  }
  endMouse(){
    for (const [id, q] of this.pointers) if (q.mouse) this.up({pointerId: id});
  }
  move(e){
    const p = this.pointers.get(e.pointerId); if (!p) return;
    if (p.mouse && e.buttons === 0){ this.up(e); return; }   // button already released
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY; p.t = performance.now();
    if (this.mode === "pan" && this.pointers.size === 1){
      const before = this.target.clone(); this.keep(this.grab, p.x, p.y);
      this.track.push({t: p.t, x: this.target.x - before.x, z: this.target.z - before.z}); if (this.track.length > 6) this.track.shift();
    } else if (this.mode === "rotate"){
      this.az -= dx * 0.006; this.tilt -= dy * 0.006; this.apply();
    } else if (this.mode === "two" && this.pointers.size >= 2){
      const [a, b] = [...this.pointers.values()];
      const m = {x:(a.x+b.x)/2, y:(a.y+b.y)/2, d:Math.hypot(b.x-a.x, b.y-a.y), ang:Math.atan2(b.y-a.y, b.x-a.x)};
      if (!this.gesture){                  // decide once: tilt (both fingers up/down together) or map
        const v = [a, b].map((q, i) => ({x: q.x - this.f0[i].x, y: q.y - this.f0[i].y}));
        const moved = v.map(q => Math.hypot(q.x, q.y));
        const hi = Math.max(...moved), lo = Math.min(...moved);
        if (hi > 12 && (lo > 5 || hi > 40)){   // fingers report in turn: wait until both have moved
          const vertical = v.every(q => Math.abs(q.y) >= 1.6*Math.abs(q.x));
          const together = v[0].y * v[1].y > 0 && lo >= 0.35*hi;
          this.gesture = vertical && together ? "tilt" : "map";
          if (this.gesture === "map"){ this.prev = m; this.grab = this.ground(m.x, m.y); }
        }
      }
      if (this.gesture === "tilt"){ this.tilt -= (m.y - this.prev.y) * 0.008; this.apply(); }
      else if (this.gesture === "map"){
        let da = m.ang - this.prev.ang; if (da > Math.PI) da -= 2*Math.PI; if (da < -Math.PI) da += 2*Math.PI;
        this.dist *= this.prev.d / Math.max(m.d, 1); this.az -= da; this.apply();
        this.keep(this.grab, m.x, m.y);
      }
      this.prev = m;
    }
  }
  up(e){
    if (!this.pointers.has(e.pointerId)) return;
    this.pointers.delete(e.pointerId);
    if (this.mode === "pan" && this.pointers.size === 0 && this.track && this.track.length > 1){
      const now = performance.now(), recent = this.track.filter(q => now - q.t < 90);
      if (recent.length > 1){ const span = Math.max(16, recent[recent.length-1].t - recent[0].t);
        this.vel.set(recent.reduce((s,q)=>s+q.x, 0)/span, recent.reduce((s,q)=>s+q.z, 0)/span);
        const vmax = this.dist * 0.0009; if (this.vel.length() > vmax) this.vel.setLength(vmax); }
    }
    if (this.pointers.size) this.start(null); else this.mode = null;
  }
  wheel(e){
    e.preventDefault(); this.anim = null; this.vel.set(0,0);
    const k = e.deltaMode === 1 ? 40 : e.deltaMode === 2 ? 800 : 1;
    const f = Math.exp(e.deltaY * k * (e.ctrlKey ? 0.01 : 0.0015));   // ctrl+wheel = trackpad pinch
    this.zoomAt(e.clientX, e.clientY, Math.min(2, Math.max(0.5, f)));
  }
  key(e){
    const r = this.el.getBoundingClientRect(), cx = r.left + r.width/2, cy = r.top + r.height/2, step = r.height*0.15;
    const pan = (x, y)=>{ const g = this.ground(cx, cy); this.keep(g, cx - x, cy - y); };
    const map = {ArrowLeft:()=>e.shiftKey ? (this.az += 0.15, this.apply()) : pan(-step, 0), ArrowRight:()=>e.shiftKey ? (this.az -= 0.15, this.apply()) : pan(step, 0),
                 ArrowUp:()=>e.shiftKey ? (this.tilt += 0.08, this.apply()) : pan(0, -step), ArrowDown:()=>e.shiftKey ? (this.tilt -= 0.08, this.apply()) : pan(0, step),
                 "+":()=>this.zoomAt(cx, cy, 0.6, true), "=":()=>this.zoomAt(cx, cy, 0.6, true), "-":()=>this.zoomAt(cx, cy, 1/0.6, true)};
    if (map[e.key]){ e.preventDefault(); map[e.key](); }
  }
  north(){ this.turn = {az0: this.az, az1: Math.round(this.az/(2*Math.PI))*2*Math.PI, t0: performance.now()}; }
  update(){
    const now = performance.now();
    if (this.vel.lengthSq() > 1e-6 && !this.pointers.size){
      const dt = Math.min(48, now - (this._t || now));
      this.target.x += this.vel.x*dt; this.target.z += this.vel.y*dt; this.vel.multiplyScalar(Math.pow(0.0025, dt/1000)); this.apply();
    } else this.vel.set(0,0);
    if (this.anim){                        // smooth zoom for double tap / keys
      const a = this.anim, k = Math.min(1, (now - a.t0)/260), e = 1 - Math.pow(1-k, 3);
      const want = Math.pow(a.f, e), step = want / a.done; a.done = want;
      this.zoomAt(a.x, a.y, step); if (k >= 1) this.anim = null;
    }
    if (this.turn){
      const k = Math.min(1, (now - this.turn.t0)/350), e = 1 - Math.pow(1-k, 3);
      this.az = this.turn.az0 + (this.turn.az1 - this.turn.az0)*e; this.apply(); if (k >= 1) this.turn = null;
    }
    this._t = now;
    const changed = this.dirty; this.dirty = false;
    if (changed) this.dispatchEvent({type:"change"});
    return changed;
  }
}
'''

rep('<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>\n', '')
rep('''const HOME = homeView();
const controls = new THREE.OrbitControls(camera, canvas);
controls.target.copy(HOME);
controls.enableDamping = true; controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI*0.47; controls.minDistance = 250; controls.maxDistance = 60000;
controls.screenSpacePanning = false;''', NAV + '''const HOME = homeView();
const controls = new MapNav(camera, canvas);
controls.setFrom(HOME);
canvas.tabIndex = 0;''')

# compass: shows north, tap to turn north-up again
rep('<div class="compass" aria-hidden="true">Пн ↑<br><span class="hide-sm">тягніть — обертання<br>правою — зсув · колесо — масштаб</span></div>',
    '<div class="compass"><button type="button" id="north" class="north" title="Повернути північ угору" aria-label="Повернути північ угору"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><g id="needle"><path d="M12 3l3.2 9h-6.4z" fill="#ff9636"/><path d="M12 21l-3.2-9h6.4z" fill="currentColor" opacity=".55"/></g></svg></button><span class="hide-sm">перетягніть — рух · колесо — масштаб<br>права кнопка або Ctrl — поворот і нахил</span></div>')
rep('.compass{z-index:2;position:fixed;right:16px;top:calc(16px + env(safe-area-inset-top,0px));font-family:var(--f-mono);font-size:11px;color:var(--muted);text-align:right;line-height:1.6;pointer-events:none}',
    '''.compass{z-index:2;position:fixed;right:16px;top:calc(16px + env(safe-area-inset-top,0px));font-family:var(--f-mono);font-size:11px;color:var(--muted);text-align:right;line-height:1.6;pointer-events:none;display:flex;flex-direction:column;align-items:flex-end;gap:6px}
.north{pointer-events:auto;width:40px;height:40px;border-radius:50%;border:1px solid var(--line);background:rgba(12,16,32,.82);color:var(--ink);display:grid;place-items:center;cursor:pointer;backdrop-filter:blur(8px);padding:0}
.north:focus-visible{outline:2px solid var(--on);outline-offset:2px}
#needle{transform-origin:12px 12px;transition:none}
#scene:focus{outline:none}''')
rep('''  .compass{display:none}''', '''  .compass{top:auto;bottom:calc(var(--dock-h,120px) + 12px);right:12px}
  .compass.north-up{display:none}''')
# compass needle follows the map rotation; tap turns north-up
rep('controls.addEventListener("change", ()=> needs=true);', '''controls.addEventListener("change", ()=>{
  needs=true;
  const nA = controls.target.clone().project(camera), nB = controls.target.clone().add(new THREE.Vector3(0,0,-1000)).project(camera);
  const nDeg = Math.atan2((nB.x-nA.x)*innerWidth, (nB.y-nA.y)*innerHeight)*180/Math.PI;   // where north points on screen
  $("needle").style.transform = `rotate(${nDeg.toFixed(1)}deg)`;
  const a = Math.abs(Math.atan2(Math.sin(controls.az), Math.cos(controls.az)));
  document.querySelector(".compass").classList.toggle("north-up", a < 0.035);
});
$("north").onclick = ()=> controls.north();''')
# dock height for placing the compass above it on phones
rep('''function resize(){
  const w=innerWidth,h=innerHeight;''', '''function resize(){
  const w=innerWidth,h=innerHeight;
  const dk=document.querySelector(".dock"); if(dk) document.documentElement.style.setProperty("--dock-h", dk.offsetHeight+"px");''')
open(p, "w").write(s)
print("ok")
