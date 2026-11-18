"""Living sky behind the map: gradient sky, real sun and moon position (moon in its current phase), stars at
night, drifting clouds by real cloud cover. Drawn on a 2D canvas under a transparent WebGL canvas; the sun and
moon sit where they really are relative to the way the camera looks, so rotating the map moves them.
Applied once: python3 tools/patch_sky.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new)

rep('#scene{position:fixed;inset:0;display:block;width:100%;height:100%;touch-action:none}',
    '#sky{position:fixed;inset:0;width:100%;height:100%;display:block;pointer-events:none}\n'
    '#scene{position:fixed;inset:0;display:block;width:100%;height:100%;touch-action:none}')
rep('<canvas id="scene" ', '<canvas id="sky" aria-hidden="true"></canvas>\n<canvas id="scene" ')
rep('new THREE.WebGLRenderer({canvas, antialias:true, powerPreference:"high-performance"})',
    'new THREE.WebGLRenderer({canvas, antialias:true, alpha:true, powerPreference:"high-performance"})')
rep('renderer.setClearColor(0x060912, 1);', 'renderer.setClearColor(0x060912, 0);   // transparent: the sky canvas shows behind the city')
rep('  renderer.setClearColor(fc, 1);', '  renderer.setClearColor(fc, 0);')

SKY = r'''
/* ---------- sky: sun, moon in its phase, stars, clouds ---------- */
function moonPos(ms, lat=50.45, lon=30.52){  // low-precision lunar position (as in SunCalc): elevation, azimuth from north
  const rad = Math.PI/180, d = ms/86400000 - 0.5 + 2440588 - 2451545;
  const L = rad*(218.316 + 13.176396*d), M = rad*(134.963 + 13.064993*d), F = rad*(93.272 + 13.229350*d);
  const l = L + rad*6.289*Math.sin(M), b = rad*5.128*Math.sin(F), e = rad*23.4397;
  const ra = Math.atan2(Math.sin(l)*Math.cos(e) - Math.tan(b)*Math.sin(e), Math.cos(l));
  const dec = Math.asin(Math.sin(b)*Math.cos(e) + Math.cos(b)*Math.sin(e)*Math.sin(l));
  const H = rad*(280.16 + 360.9856235*d) + lon*rad - ra, phi = lat*rad;
  const el = Math.asin(Math.sin(phi)*Math.sin(dec) + Math.cos(phi)*Math.cos(dec)*Math.cos(H));
  const az = Math.atan2(Math.sin(H), Math.cos(H)*Math.sin(phi) - Math.tan(dec)*Math.cos(phi)) + Math.PI;
  return { el, az: (az + 2*Math.PI) % (2*Math.PI) };
}
function moonPhase(ms){                        // 0 new, 0.25 first quarter, 0.5 full, 0.75 last quarter
  const jd = ms/86400000 + 2440587.5, p = ((jd - 2451550.26)/29.530588853) % 1;
  return p < 0 ? p + 1 : p;
}
const SKY = { cv: $("sky"), stars: [], clouds: [], last: 0, t0: performance.now() };
(function(){
  let seed = 7; const rnd = () => (seed = (seed*16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 260; i++) SKY.stars.push({ x: rnd(), y: rnd(), r: 0.4 + rnd()*rnd()*1.5, tw: rnd()*6.28, sp: 0.6 + rnd()*1.6 });
  for (let i = 0; i < 9; i++){
    const parts = []; const n = 4 + Math.floor(rnd()*4);
    for (let k = 0; k < n; k++) parts.push({ dx: (k - n/2)*0.55 + rnd()*0.3, dy: (rnd() - 0.5)*0.35, r: 0.45 + rnd()*0.45 });
    SKY.clouds.push({ x: rnd(), y: 0.04 + rnd()*0.36, s: 0.6 + rnd()*0.8, v: 0.5 + rnd(), parts, seed: rnd() });
  }
})();
function skyResize(){ const r = Math.min(devicePixelRatio, 1.5); SKY.cv.width = innerWidth*r; SKY.cv.height = innerHeight*r; SKY.r = r; SKY.dirty = true; }
skyResize(); addEventListener("resize", skyResize);
function skyBodyXY(az, el, viewB, W, H){      // where a sky body sits on screen for the current camera heading
  let r = az - viewB; r = Math.atan2(Math.sin(r), Math.cos(r));
  if (Math.abs(r) > 1.9) return null;
  const x = W/2 + (r/1.6)*W*0.55, y = H*0.07 + (1 - Math.min(Math.max(el, 0), 1.05)/1.05)*H*0.30;
  return [x, y];
}
function moonDraw(ctx, x, y, R, ph, glow){
  const waxing = ph < 0.5, k = Math.cos(2*Math.PI*ph);           // k: 1 new .. -1 full
  ctx.save();
  const g = ctx.createRadialGradient(x, y, R*0.8, x, y, R*5); g.addColorStop(0, `rgba(210,220,255,${0.22*glow})`); g.addColorStop(1, "rgba(210,220,255,0)");
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R*5, 0, 6.283); ctx.fill();
  ctx.fillStyle = "rgba(60,68,96,.55)"; ctx.beginPath(); ctx.arc(x, y, R, 0, 6.283); ctx.fill();   // earthshine on the dark part
  ctx.fillStyle = "#eef1fb"; ctx.beginPath();
  if (waxing){ ctx.arc(x, y, R, -Math.PI/2, Math.PI/2, false);
    if (k > 0) ctx.ellipse(x, y, R*Math.abs(k), R, 0, Math.PI/2, -Math.PI/2, true); else ctx.ellipse(x, y, R*Math.abs(k), R, 0, Math.PI/2, 3*Math.PI/2, false); }
  else { ctx.arc(x, y, R, -Math.PI/2, Math.PI/2, true);
    if (k > 0) ctx.ellipse(x, y, R*Math.abs(k), R, 0, Math.PI/2, 3*Math.PI/2, false); else ctx.ellipse(x, y, R*Math.abs(k), R, 0, Math.PI/2, -Math.PI/2, true); }
  ctx.fill();
  ctx.globalAlpha = 0.12; ctx.fillStyle = "#7d86a8";                                                  // a few maria
  for (const [dx, dy, rr] of [[-0.25,-0.2,0.22],[0.2,0.1,0.18],[-0.05,0.35,0.14]]){ ctx.beginPath(); ctx.arc(x + dx*R, y + dy*R, rr*R, 0, 6.283); ctx.fill(); }
  ctx.restore();
}
function skyFrame(now){
  requestAnimationFrame(skyFrame);
  if (document.hidden || now - SKY.last < 66) return;                                                 // ~15 fps is plenty for the sky
  SKY.last = now;
  const cv = SKY.cv, ctx = cv.getContext("2d"), W = innerWidth, H = innerHeight;
  ctx.setTransform(SKY.r, 0, 0, SKY.r, 0, 0);
  const day = common.uDay.value, cloud = Math.min(1, ENV.cloud != null ? ENV.cloud : 0), kind = ENV.kind, fog = kind === "fog";
  const ms = follow ? Date.now() : mapUtc(tMin), sp = sunPos(ms), mp = moonPos(ms), viewB = -controls.az;
  const bottom = common.uFogCol.value;
  // sky gradient: deep blue (day) or near-black (night) above, fog colour at the horizon
  const top = new THREE.Color(0x02040b).lerp(new THREE.Color(0x2f5b9a).lerp(new THREE.Color(0x5d6879), cloud*0.8), day);
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "#" + top.getHexString()); g.addColorStop(0.75, "#" + bottom.getHexString()); g.addColorStop(1, "#" + bottom.getHexString());
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  const t = (now - SKY.t0)/1000;
  // sunset / sunrise glow towards the sun
  const elD = sp.el*180/Math.PI, sxy = skyBodyXY(sp.az, sp.el, viewB, W, H);
  const glow = Math.max(0, 1 - Math.abs(elD - 1)/9) * (1 - 0.7*cloud);
  if (glow > 0.02 && sxy){ const gg = ctx.createRadialGradient(sxy[0], H*0.38, 0, sxy[0], H*0.38, W*0.55);
    gg.addColorStop(0, `rgba(255,140,70,${0.45*glow})`); gg.addColorStop(1, "rgba(255,140,70,0)"); ctx.fillStyle = gg; ctx.fillRect(0, 0, W, H); }
  // stars
  const starA = (1 - day) * (1 - cloud*0.9) * (fog ? 0.15 : 1);
  if (starA > 0.02){
    const shift = viewB/(2*Math.PI);
    for (const st of SKY.stars){
      const x = (((st.x - shift) % 1) + 1) % 1 * W, y = st.y*H*0.62;
      const a = starA * (0.55 + 0.45*Math.sin(t*st.sp + st.tw)) * (1 - y/(H*0.7));
      if (a < 0.02) continue;
      ctx.fillStyle = `rgba(230,236,255,${a.toFixed(3)})`; ctx.beginPath(); ctx.arc(x, y, st.r, 0, 6.283); ctx.fill();
    }
  }
  // sun
  if (elD > -2 && sxy && !fog){
    const a = Math.min(1, (elD + 2)/5) * (1 - 0.75*cloud), [x, y] = sxy, R = 16;
    const gs = ctx.createRadialGradient(x, y, 0, x, y, R*7); gs.addColorStop(0, `rgba(255,236,190,${0.55*a})`); gs.addColorStop(0.25, `rgba(255,214,140,${0.22*a})`); gs.addColorStop(1, "rgba(255,214,140,0)");
    ctx.fillStyle = gs; ctx.beginPath(); ctx.arc(x, y, R*7, 0, 6.283); ctx.fill();
    ctx.fillStyle = `rgba(255,246,222,${Math.min(1, a*1.4)})`; ctx.beginPath(); ctx.arc(x, y, R, 0, 6.283); ctx.fill();
  }
  // moon in its current phase
  const mxy = skyBodyXY(mp.az, mp.el, viewB, W, H);
  if (mp.el > -0.02 && mxy && !fog){
    ctx.globalAlpha = Math.max(0.25, 1 - day*0.7) * (1 - 0.7*cloud);
    moonDraw(ctx, mxy[0], mxy[1], 13, moonPhase(ms), 1 - day);
    ctx.globalAlpha = 1;
  }
  // clouds drifting with the wind
  const nC = Math.round(cloud*SKY.clouds.length + (kind === "part" ? 2 : 0));
  if (nC > 0){
    const windX = Math.sin((ENV.windDir + 180)*Math.PI/180) || 0.5, spd = 0.004 + Math.min(1, ENV.wind/40)*0.01;
    const lit = day > 0.3 ? [235,238,246] : [70,78,104], dark = day > 0.3 ? [150,158,178] : [28,32,48];
    const col = cloud > 0.75 ? dark : lit, a = (day > 0.3 ? 0.55 : 0.45) * (0.5 + 0.5*Math.min(1, cloud*1.3));
    for (let i = 0; i < Math.min(nC, SKY.clouds.length); i++){
      const c = SKY.clouds[i], sc = c.s*Math.min(W, 900)*0.16;
      const x = ((((c.x + t*spd*c.v*windX/10 - viewB/(2*Math.PI)) % 1.4) + 1.4) % 1.4 - 0.2) * W, y = c.y*H;
      for (const q of c.parts){
        const px = x + q.dx*sc, py = y + q.dy*sc, r = q.r*sc;
        const gc = ctx.createRadialGradient(px, py, 0, px, py, r);
        gc.addColorStop(0, `rgba(${col[0]},${col[1]},${col[2]},${a})`); gc.addColorStop(1, `rgba(${col[0]},${col[1]},${col[2]},0)`);
        ctx.fillStyle = gc; ctx.beginPath(); ctx.arc(px, py, r, 0, 6.283); ctx.fill();
      }
    }
  }
}
requestAnimationFrame(skyFrame);
'''
rep('/* rain, snow and lightning drawn over the map */', SKY + '\n/* rain, snow and lightning drawn over the map */')
open(p, "w").write(s)
print("ok")
