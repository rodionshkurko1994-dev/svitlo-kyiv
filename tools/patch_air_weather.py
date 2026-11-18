"""Air quality by district with haze, and more visible weather.

Air: Open-Meteo Air Quality (CAMS model, European AQI, PM2.5, PM10) for every district centre, refined with
Sensor.Community citizen sensors in Kyiv when a district has at least two live sensors (median PM -> EAQI).
Polluted districts get a light haze in the map shaders: the worse the air, the thicker it is.
Weather: moving cloud shadows on cloudy days, a colour veil for rain / fog / snow, denser and more visible
rain and snow.
Applied once: python3 tools/patch_air_weather.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new)

# ---------- shared GLSL: haze and cloud shadows (only for shaders that declare uDay) ----------
rep("const FOG = `", r'''const HAZE = `
  uniform vec3 uAq[10]; uniform float uCloud; uniform float uTime;
  float hazeAt(vec2 p){ float ws = 0.0, s = 0.0; for (int i = 0; i < 10; i++){ vec2 d = p - uAq[i].xy; float w = 1.0/(dot(d,d) + 6.0e6); ws += w; s += w*uAq[i].z; } return s/ws; }
  vec3 applyHaze(vec3 c, vec3 wp, float h){
    float hz = hazeAt(wp.xz); if (hz < 0.002) return c;
    float dv = distance(wp, cameraPosition);
    float k = hz * (0.22 + 0.38*smoothstep(600.0, 9000.0, dv)) * mix(1.0, 0.55, smoothstep(15.0, 160.0, h));
    vec3 hc = mix(vec3(0.24,0.21,0.19), vec3(0.66,0.62,0.55), uDay);
    return mix(c, hc, k);
  }
  float hsh(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
  float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
    return mix(mix(hsh(i), hsh(i+vec2(1,0)), f.x), mix(hsh(i+vec2(0,1)), hsh(i+vec2(1,1)), f.x), f.y); }
  float cloudShadow(vec3 wp){
    if (uCloud < 0.01) return 1.0;
    vec2 q = wp.xz/4200.0 + vec2(uTime*0.010, uTime*0.004);
    float n = 0.6*vnoise(q) + 0.3*vnoise(q*2.3 + 7.1) + 0.1*vnoise(q*5.1 + 3.3);
    return 1.0 - uCloud*0.42*smoothstep(0.42, 0.68, n);
  }`;
const FOG = `''')
rep("  uMask: { value: CITY_MASK.tex }, uMaskB: { value: CITY_MASK.box },",
    "  uMask: { value: CITY_MASK.tex }, uMaskB: { value: CITY_MASK.box },\n"
    "  uAq: { value: Array.from({length:10}, (_, i) => new THREE.Vector3(DISTRICTS[i] ? DISTRICTS[i].x : 0, DISTRICTS[i] ? DISTRICTS[i].z : 0, 0)) }, uCloud: { value: 0 },")

# buildings
rep('''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol; uniform float uDay, uSnow, uWet; uniform vec3 uSunDir;
    varying vec3 vW; varying float vS; varying float vH; varying float vSeed; varying float vE; varying float vF;
    ${FOG}''', '''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol; uniform float uDay, uSnow, uWet; uniform vec3 uSunDir;
    varying vec3 vW; varying float vS; varying float vH; varying float vSeed; varying float vE; varying float vF;
    ${FOG}
    ${HAZE}''')
rep('''      c *= 1.0 - 0.12*uWet;                                                // wet, darker walls in rain
      gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0);''', '''      c *= 1.0 - 0.18*uWet;                                                // wet, darker walls in rain
      c *= mix(1.0, cloudShadow(vW), uDay);                                // cloud shadows drifting over the city
      c = applyHaze(c, vW, vH);                                            // polluted air
      gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0);''')
# roads
rep('''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol; uniform float uDay, uSnow;
    varying vec3 vW; varying float vS; varying float vR; varying float vE; varying float vF;
    ${FOG}''', '''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol; uniform float uDay, uSnow;
    varying vec3 vW; varying float vS; varying float vR; varying float vE; varying float vF;
    ${FOG}
    ${HAZE}''')
rep('''      float a = (0.35 + 0.55*major) * (1.0 - fogF(vW)) * (1.0 - 0.25*vE);''',
    '''      c = applyHaze(c, vW, 0.0);
      float a = (0.35 + 0.55*major) * (1.0 - fogF(vW)) * (1.0 - 0.25*vE);''')
# ground, parks, water
rep('''uniform float uDay, uSnow, uSnowable; varying vec3 vW; ${FOG}''', '''uniform float uDay, uSnow, uSnowable; uniform float uWet; varying vec3 vW; ${FOG} ${HAZE}''')
rep('''        gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0); }`,''', '''        c *= (1.0 - 0.15*uWet*uSnowable) * mix(1.0, cloudShadow(vW), uDay);       // wet ground, cloud shadows
        c = applyHaze(c, vW, 0.0);
        gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0); }`,''')

# ---------- weather: veil, cloud shadows, stronger precipitation ----------
rep('#wxfx{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}',
    '#wxfx{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}\n'
    '#wxveil{position:fixed;inset:0;pointer-events:none;z-index:1;opacity:0;transition:opacity 2.5s ease,background 2.5s ease}\n'
    '.dlabel .aq{display:inline-block;margin-left:7px;padding:1px 6px 1px 5px;border-radius:7px;font-size:10px;letter-spacing:.02em;text-transform:none;'
    'background:rgba(6,9,18,.55);color:#e8ecf8;vertical-align:1px}\n'
    '.dlabel .aq i{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:4px;vertical-align:1px}\n'
    '.air{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);line-height:1.35}\n'
    '.air i{flex:none;width:8px;height:8px;border-radius:50%}\n'
    '.air b{color:var(--ink);font-weight:600}')
rep('<canvas id="wxfx" aria-hidden="true"></canvas>', '<div id="wxveil" aria-hidden="true"></div>\n<canvas id="wxfx" aria-hidden="true"></canvas>')
rep('<p class="note" id="fresh">', '<div class="air" id="air" hidden><i id="airDot"></i><span id="airTxt"></span></div>\n  <p class="note" id="fresh">')
rep('''  ENV.kind = kind; ENV.precip = (kind === "rain" || kind === "snow" || kind === "storm") ? Math.max(0.25, precip) : 0;''',
    '''  ENV.kind = kind; ENV.precip = (kind === "rain" || kind === "snow" || kind === "storm") ? Math.max(0.5, precip) : 0;
  ENV.cloud = kind === "fog" ? 0 : Math.min(1, cloud*1.1);''')
rep('''  envTarget = true; needs = true;
}''', '''  // colour veil over the map: rain darkens, fog and snow whiten, overcast greys
  const veil = $("wxveil");
  if (veil){
    const v = kind === "fog" ? ["linear-gradient(to top, rgba(178,186,204,.30), rgba(178,186,204,.08))", 1]
      : kind === "rain" || kind === "storm" ? ["linear-gradient(to bottom, rgba(18,28,58,.34), rgba(30,44,80,.14))", 1]
      : kind === "snow" ? ["linear-gradient(to bottom, rgba(225,232,248,.20), rgba(225,232,248,.07))", 1]
      : kind === "cloud" ? ["linear-gradient(to bottom, rgba(96,106,128,.20), rgba(96,106,128,.05))", 0.6 + 0.4*day]
      : ["none", 0];
    veil.style.background = v[0]; veil.style.opacity = v[1];
  }
  envTarget = true; needs = true;
}''')
rep('''  ease(u.uDay, "value", ENV.day); ease(u.uWet, "value", ENV.wet); ease(u.uSnow, "value", ENV.snowTarget || 0);''',
    '''  ease(u.uDay, "value", ENV.day); ease(u.uWet, "value", ENV.wet); ease(u.uSnow, "value", ENV.snowTarget || 0); ease(u.uCloud, "value", ENV.cloud || 0);
  const tNow = performance.now();                                  // drift the cloud shadows a few times a second
  if (u.uCloud.value > 0.02 && u.uDay.value > 0.05 && tNow - (envTick.tc || 0) > 220){ envTick.tc = tNow; u.uTime.value = tNow/1000; moving = true; }''')
# denser, more visible rain and snow
rep('Math.round((kind === "snow" ? 160 : 220) * ENV.precip', 'Math.round((kind === "snow" ? 280 : 420) * ENV.precip')
rep('ctx.fillStyle = "rgba(235,240,255,.85)";', 'ctx.fillStyle = "rgba(240,244,255,.92)";')
rep('ctx.arc(q.x, q.y, 1.1 + q.s*1.1, 0, 6.283)', 'ctx.arc(q.x, q.y, 1.4 + q.s*1.6, 0, 6.283)')
rep('ctx.strokeStyle = "rgba(170,190,235,.42)"; ctx.lineWidth = 1;', 'ctx.strokeStyle = "rgba(185,205,245,.58)"; ctx.lineWidth = 1.3;')
rep('const L = 9 + q.s*8;', 'const L = 12 + q.s*12;')

# ---------- air quality ----------
AIR = r'''/* ---------- air quality by district (Open-Meteo CAMS + Sensor.Community) ---------- */
const AQ = { d: DISTRICTS.map(() => null), at: 0 };
const AQ_LV = [[20,"добре","#4fd1a5"],[40,"прийнятне","#a8d672"],[60,"помірне","#ffd25a"],[80,"погане","#ff9a4d"],[100,"дуже погане","#ff5d5d"],[1e9,"надзвичайно погане","#b56cff"]];
function aqLevel(v){ return AQ_LV.find(l => v < l[0]); }
function aqFromPm(pm25, pm10){              // European AQI scale from concentrations (µg/m³)
  const pw = (v, b) => { for (let i = 1; i < b.length; i++) if (v <= b[i]) return (i-1)*20 + (v - b[i-1])/(b[i] - b[i-1])*20; return 100 + (v - b[b.length-1])/b[b.length-1]*50; };
  const a = pm25 == null ? 0 : pw(pm25, [0,10,20,25,50,75]), b = pm10 == null ? 0 : pw(pm10, [0,20,40,50,100,150]);
  return Math.max(a, b);
}
function inCityXZ(x, z){
  const P = META.city; let c = false;
  for (let i = 0, j = P.length - 1; i < P.length; j = i++){ const [xi,zi] = P[i], [xj,zj] = P[j]; if ((zi > z) !== (zj > z) && x < (xj - xi)*(z - zi)/(zj - zi) + xi) c = !c; }
  return c;
}
function nearestDistrict(x, z){ let b = 0, bd = Infinity; DISTRICTS.forEach((d, i) => { const e = (d.x-x)**2 + (d.z-z)**2; if (e < bd){ bd = e; b = i; } }); return b; }
const KXA = 111320*Math.cos(50.45*Math.PI/180);
async function pullAir(){
  const ll = DISTRICTS.map(d => [(50.45 - d.z/110570).toFixed(4), (30.52 + d.x/KXA).toFixed(4)]);
  const out = DISTRICTS.map(() => null);
  try{
    const u = "https://air-quality-api.open-meteo.com/v1/air-quality?timezone=Europe%2FKyiv&current=european_aqi,pm2_5,pm10" +
      "&latitude=" + ll.map(q => q[0]).join(",") + "&longitude=" + ll.map(q => q[1]).join(",");
    const r = await fetch(u);
    if (r.ok){ let j = await r.json(); if (!Array.isArray(j)) j = [j];
      j.forEach((x, i) => { const c = x && x.current; if (c && c.european_aqi != null && i < out.length) out[i] = { aqi: c.european_aqi, pm25: c.pm2_5, pm10: c.pm10, src: "model", n: 0 }; }); }
  }catch(e){}
  try{                                       // live citizen sensors refine the model where there are enough of them
    const r = await fetch("https://data.sensor.community/airrohr/v1/filter/area=50.45,30.52,22");
    if (r.ok){
      const rows = await r.json(), per = DISTRICTS.map(() => ({ p2: [], p1: [], ids: new Set() }));
      for (const row of rows){
        const lat = +row.location?.latitude, lon = +row.location?.longitude; if (!lat || !lon) continue;
        const x = (lon - 30.52)*KXA, z = -(lat - 50.45)*110570; if (!inCityXZ(x, z)) continue;
        const v = {}; for (const s of row.sensordatavalues || []) v[s.value_type] = +s.value;
        if (!(v.P2 >= 0 && v.P2 < 500)) continue;
        const k = per[nearestDistrict(x, z)], id = row.sensor?.id; if (k.ids.has(id)) continue; k.ids.add(id);
        k.p2.push(v.P2); if (v.P1 >= 0 && v.P1 < 800) k.p1.push(v.P1);
      }
      const med = a => { if (!a.length) return null; const b = a.slice().sort((x, y) => x - y), m = b.length >> 1; return b.length % 2 ? b[m] : (b[m-1] + b[m])/2; };
      per.forEach((k, i) => { if (k.p2.length >= 2){ const pm25 = med(k.p2), pm10 = med(k.p1); out[i] = { aqi: Math.round(aqFromPm(pm25, pm10)), pm25, pm10, src: "sensors", n: k.p2.length }; } });
    }
  }catch(e){}
  if (!out.some(Boolean)) return;
  out.forEach((v, i) => { if (v) AQ.d[i] = v; }); AQ.at = Date.now();
  airRender();
}
function airRender(){
  AQ.d.forEach((v, i) => {
    common.uAq.value[i].z = v ? Math.max(0, Math.min(1, (v.aqi - 28)/72)) : 0;   // haze from "moderate" upwards
    const el = labelEls[i]; if (!el) return;
    el.innerHTML = "";
    el.append(DISTRICTS[i].name);
    if (v){ const l = aqLevel(v.aqi), b = document.createElement("span"); b.className = "aq"; b.innerHTML = `<i style="background:${l[2]}"></i>${Math.round(v.aqi)}`; b.title = `Повітря: ${l[1]}`; el.append(b); }
  });
  const ok = AQ.d.map((v, i) => v && [v, i]).filter(Boolean); if (!ok.length) return;
  ok.sort((a, b) => b[0].aqi - a[0].aqi);
  const [worst, wi] = ok[0], lv = aqLevel(worst.aqi), avg = ok.reduce((s, q) => s + q[0].aqi, 0)/ok.length, la = aqLevel(avg);
  $("air").hidden = false; $("airDot").style.background = la[2];
  const sens = ok.filter(q => q[0].src === "sensors").length;
  $("airTxt").innerHTML = `Повітря зараз: <b>${la[1]}</b>` + (worst.aqi >= 40 ? ` · найгірше: ${DISTRICTS[wi].name} (${Math.round(worst.aqi)}, ${lv[1]})` : "") +
    (worst.aqi >= 40 ? " · над такими районами — димка" : "");
  $("air").title = `Європейський індекс якості повітря (EAQI) по районах. ${sens ? `Датчики Sensor.Community: ${sens} з ${ok.length} районів, решта — модель CAMS (Open-Meteo).` : "Модель CAMS (Open-Meteo)."}`;
  needs = true;
}
function aqTip(x, z){
  const i = nearestDistrict(x, z), v = AQ.d[i]; if (!v) return "";
  const l = aqLevel(v.aqi);
  return `<div class="m">Повітря (${DISTRICTS[i].name}): <span style="color:${l[2]}">${l[1]}</span>, індекс ${Math.round(v.aqi)}` +
    (v.pm25 != null ? `, PM2.5 ${Math.round(v.pm25)} мкг/м³` : "") + (v.src === "sensors" ? ` · ${v.n} датчиків` : " · модель") + `</div>`;
}
pullAir(); setInterval(pullAir, 10*60*1000);

'''
rep('/* ---------- public transport by timetable ---------- */', AIR + '/* ---------- public transport by timetable ---------- */')
rep('  tip.innerHTML = html; tip.hidden=false;', '  html += aqTip(hit.x, hit.z);\n  tip.innerHTML = html; tip.hidden=false;')
open(p, "w").write(s)
print("ok")
