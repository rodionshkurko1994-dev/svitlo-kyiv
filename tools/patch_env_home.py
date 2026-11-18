"""Weather and time of day on the map, and "Мій дім" (my home).

Weather: Open-Meteo (free, no key, CC BY 4.0) current + hourly forecast for Kyiv. The map follows
the map time (the slider): the sun's real position lights the city by day and the night look
returns after dusk; clouds and fog thicken the haze; rain and snow fall over the map; snow
settles on roofs and ground. A weather chip in the panel shows temperature and conditions.

My home: search an address (addr_index.json, OSM addresses, loaded on first use) or tap the
building on the map. The panel then keeps a card with the building's group, power now, the next
change and today's/tomorrow's hours without power, and a pin marks the building on the map.
Stored only in the visitor's browser.

Applied once: python3 tools/patch_env_home.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new, count=1):
    global s
    assert s.count(old) >= count, old[:90]
    s = s.replace(old, new, count)

# ------------------------------------------------------------------ shaders: daylight, sun, snow, rain
rep('''  uFogCol: { value: new THREE.Color(0x060912) },
  uTime: { value: 0 }''', '''  uFogCol: { value: new THREE.Color(0x060912) },
  uTime: { value: 0 },
  uDay: { value: 0 }, uSnow: { value: 0 }, uWet: { value: 0 }, uSunDir: { value: new THREE.Vector3(-0.45, 0.75, 0.35).normalize() }''')
# buildings
rep('''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol;
    varying vec3 vW; varying float vS; varying float vH; varying float vSeed; varying float vE; varying float vF;
    ${FOG}''', '''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol; uniform float uDay, uSnow, uWet; uniform vec3 uSunDir;
    varying vec3 vW; varying float vS; varying float vH; varying float vSeed; varying float vE; varying float vF;
    ${FOG}''')
rep('''      vec3 L = normalize(vec3(-0.45, 0.75, 0.35));
      float diff = 0.45 + 0.55 * max(dot(n, L), 0.0);''', '''      vec3 L = normalize(mix(vec3(-0.45, 0.75, 0.35), uSunDir, uDay));   // by day the real sun lights the city
      float diff = 0.45 + 0.55 * max(dot(n, L), 0.0);''')
rep('''      c = mix(c, emCol, vE);
      gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0);
    }`
});

const roadMat''', '''      c = mix(c, emCol, vE);
      c = mix(c, c*0.8 + vec3(0.15,0.17,0.21)*diff, uDay*0.55);            // daylight lifts the dark tones
      c = mix(c, vec3(0.80,0.84,0.92)*diff, roof*uSnow*0.5);               // snow on roofs
      c *= 1.0 - 0.12*uWet;                                                // wet, darker walls in rain
      gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0);
    }`
});

const roadMat''')
# roads
rep('''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol;
    varying vec3 vW; varying float vS; varying float vR; varying float vE; varying float vF;
    ${FOG}''', '''    uniform float uFogNear, uFogFar; uniform vec3 uFogCol; uniform float uDay, uSnow;
    varying vec3 vW; varying float vS; varying float vR; varying float vE; varying float vF;
    ${FOG}''')
rep('''      c = mix(c, vec3(0.20,0.17,0.28), vE*0.8);
      float a''', '''      c = mix(c, vec3(0.20,0.17,0.28), vE*0.8);
      c = mix(c, c*0.7 + vec3(0.14,0.15,0.18), uDay*0.45);
      c = mix(c, vec3(0.62,0.64,0.70), uSnow*0.25);
      float a''')
# ground, parks, water
rep('''    uniforms: Object.assign({ uCol: { value: new THREE.Color(hex) } }, common),''',
    '''    uniforms: Object.assign({ uCol: { value: new THREE.Color(hex) }, uSnowable: { value: 1 } }, common),''')
rep('''    fragmentShader: `uniform vec3 uCol; uniform float uFogNear, uFogFar; uniform vec3 uFogCol; varying vec3 vW; ${FOG}
      void main(){ gl_FragColor = vec4(mix(uCol, uFogCol, fogF(vW)), 1.0); }`,''',
    '''    fragmentShader: `uniform vec3 uCol; uniform float uFogNear, uFogFar; uniform vec3 uFogCol; uniform float uDay, uSnow, uSnowable; varying vec3 vW; ${FOG}
      void main(){
        vec3 c = mix(uCol, uCol*2.5 + vec3(0.07,0.08,0.10), uDay);               // daylight ground
        c = mix(c, vec3(0.50,0.54,0.62) * (0.55 + 0.45*uDay), uSnow*uSnowable*0.7); // snow cover (not on water)
        gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0); }`,''')
rep('''  triMesh(view("water",Int16Array), 0x0a1b38, 0.6);''', '''  triMesh(view("water",Int16Array), 0x0a1b38, 0.6).material.uniforms.uSnowable.value = 0;''')

# ------------------------------------------------------------------ markup
rep('''  <div class="bar" aria-hidden="true"><i id="share" style="width:0%"></i></div>''', '''  <div class="bar" aria-hidden="true"><i id="share" style="width:0%"></i></div>
  <div class="homebox">
    <button type="button" class="home-add" id="homeAdd"><svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M2 7.5 8 2.5l6 5M3.5 6.5V13.5h9V6.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>Мій дім: додати адресу</button>
    <div class="home" id="home" hidden>
      <div class="home-top"><svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M2 7.5 8 2.5l6 5M3.5 6.5V13.5h9V6.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg><b id="homeName"></b>
        <button type="button" class="hbtn" id="homeGo" title="Показати на карті" aria-label="Показати мій дім на карті"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="8" r="1.6" fill="currentColor"/></svg></button>
        <button type="button" class="hbtn" id="homeEdit" title="Змінити адресу" aria-label="Змінити адресу"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 13l1-3.5L11 2.5 13.5 5 6.5 12z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg></button></div>
      <div class="home-now" id="homeNow"></div>
      <div class="home-day" id="homeDay"></div>
    </div>
  </div>''')
rep('''    <div class="stat"><span class="k"><i class="sw off"></i>Без світла</span><span class="v" id="nOff">—</span></div>''',
    '''    <div class="stat"><span class="k"><i class="sw off"></i>Без світла</span><span class="v" id="nOff">—</span></div>
    <div class="wx" id="wx" hidden title="Погода в Києві"><span id="wxIcon"></span><b id="wxT"></b><span id="wxL"></span></div>''')
rep('''<div class="labels" id="labels" aria-hidden="true"></div>''', '''<div class="labels" id="labels" aria-hidden="true"></div>
<canvas id="wxfx" aria-hidden="true"></canvas>
<div class="homepin" id="homePin" hidden aria-hidden="true"><svg viewBox="0 0 24 30" width="26" height="32"><path d="M12 29C7 22 2.5 17.5 2.5 11.5a9.5 9.5 0 0 1 19 0C21.5 17.5 17 22 12 29z" fill="#ff9636" stroke="#070b17" stroke-width="1.5"/><path d="M7.5 12 12 8l4.5 4M8.8 11.2V15.5h6.4v-4.3" fill="none" stroke="#070b17" stroke-width="1.6" stroke-linejoin="round"/></svg></div>
<div class="sheet-bg" id="homeSheet" hidden>
  <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="homeTitle">
    <div class="sheet-h"><b id="homeTitle">Мій дім</b><button type="button" class="hbtn" id="homeClose" aria-label="Закрити">×</button></div>
    <label for="homeQ" class="note">Вулиця й номер будинку</label>
    <input id="homeQ" type="search" autocomplete="off" placeholder="Наприклад: Хрещатик 22" spellcheck="false">
    <ul class="sugg" id="homeSugg" role="listbox"></ul>
    <div class="sheet-a"><button type="button" id="homePick">Обрати будинок на карті</button><button type="button" id="homeDel" hidden>Видалити мій дім</button></div>
    <p class="note">Адреса зберігається лише у вашому браузері. Якщо будинку немає в пошуку, оберіть його на карті.</p>
  </div>
</div>
<div class="pickbar" id="pickBar" hidden>Торкніться свого будинку на карті <button type="button" id="pickCancel">Скасувати</button></div>''')
rep('''    <p class="note">Будинки, вулиці, вода й парки взяті з OpenStreetMap''',
    '''    <p class="note">Погода — <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> (CC BY 4.0): освітлення карти відповідає реальному положенню сонця, а дощ, сніг і туман — прогнозу на обраний час.</p>
    <p class="note">Будинки, вулиці, вода й парки взяті з OpenStreetMap''')

# ------------------------------------------------------------------ styles
rep('/* compact phone layout: full-width slim bars top and bottom */', '''.wx{display:flex;align-items:center;gap:6px;margin-left:auto;align-self:center;font-size:12.5px;color:var(--muted);white-space:nowrap}
.wx b{font-family:var(--f-mono);font-size:15px;color:var(--ink);font-weight:500}
.wx svg{display:block}
#wxfx{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
.homebox{display:flex;flex-direction:column}
.home-add{align-self:flex-start;display:inline-flex;align-items:center;gap:7px;background:none;border:1px dashed var(--line);color:var(--muted);border-radius:9px;padding:6px 10px;font:500 12.5px var(--f-body);cursor:pointer}
.home-add:hover{color:var(--ink);border-color:rgba(150,170,230,.45)}
.home{border:1px solid var(--line);border-radius:10px;padding:9px 10px;display:flex;flex-direction:column;gap:4px;background:rgba(255,255,255,.02)}
.home-top{display:flex;align-items:center;gap:7px;font-size:13px}
.home-top b{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.hbtn{background:none;border:1px solid transparent;color:var(--muted);border-radius:7px;width:28px;height:28px;display:grid;place-items:center;cursor:pointer;font-size:18px;line-height:1;padding:0}
.hbtn:hover{color:var(--ink);border-color:var(--line)}
.home-now{font-size:13.5px;font-weight:600}
.home-now.on{color:var(--on)}.home-now.off{color:var(--off-ink)}.home-now.em{color:var(--warn)}
.home-now span{font-weight:400;color:var(--muted)}
.home-day{font-size:12px;color:var(--muted);line-height:1.45}
.homepin{position:fixed;left:0;top:0;z-index:1;pointer-events:none;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))}
.sheet-bg{position:fixed;inset:0;z-index:6;background:rgba(3,5,12,.55);display:flex;align-items:flex-start;justify-content:center;padding:12vh 16px 16px}
.sheet{width:min(440px,100%);background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;display:flex;flex-direction:column;gap:8px;backdrop-filter:blur(10px)}
.sheet-h{display:flex;align-items:center;justify-content:space-between;font-size:15px}
.sheet input{width:100%;font:16px var(--f-body);color:var(--ink);background:var(--night);border:1px solid var(--line);border-radius:9px;padding:10px 12px}
.sheet input:focus-visible,.home-add:focus-visible,.hbtn:focus-visible,.sugg li:focus-visible{outline:2px solid var(--on);outline-offset:2px}
.sugg{list-style:none;margin:0;padding:0;max-height:42vh;overflow:auto}
.sugg li{padding:9px 10px;border-radius:8px;cursor:pointer;font-size:14px}
.sugg li:hover,.sugg li[aria-selected="true"]{background:rgba(150,170,230,.12)}
.sugg li small{color:var(--muted)}
.sheet-a{display:flex;gap:8px;flex-wrap:wrap}
.sheet-a button{font:500 13px var(--f-body);color:var(--ink);background:var(--panel2,rgba(255,255,255,.04));border:1px solid var(--line);border-radius:9px;padding:8px 12px;cursor:pointer}
#homeDel{color:#ff8a8a}
.pickbar{position:fixed;left:50%;top:calc(16px + env(safe-area-inset-top,0px));transform:translateX(-50%);z-index:5;background:var(--panel);border:1px solid var(--on);border-radius:999px;padding:8px 8px 8px 16px;font-size:14px;display:flex;align-items:center;gap:10px;white-space:nowrap}
.pickbar button{font:500 13px var(--f-body);color:var(--ink);background:none;border:1px solid var(--line);border-radius:999px;padding:5px 12px;cursor:pointer}
@media (max-width:640px){
  .wx{font-size:11px;gap:4px}.wx b{font-size:13px}
  .home-add{font-size:11.5px;padding:4px 9px}
  .home{padding:7px 9px;gap:2px}.home-now{font-size:12.5px}.home-day{font-size:11.5px}
  .sheet-bg{align-items:flex-end;padding:0}
  .sheet{border-radius:14px 14px 0 0;padding-bottom:calc(14px + env(safe-area-inset-bottom,0px))}
  .pickbar{top:auto;bottom:calc(var(--dock-h,120px) + 14px);font-size:13px}
}
@media (prefers-reduced-motion:reduce){#wxfx{display:none}}
/* compact phone layout: full-width slim bars top and bottom */''')

# ------------------------------------------------------------------ script
JS = r'''
/* ---------- weather and time of day (Open-Meteo, sun position) ---------- */
const WX = { data: null, cur: null };
const WX_TEXT = {0:"ясно",1:"переважно ясно",2:"мінлива хмарність",3:"хмарно",45:"туман",48:"туман з інеєм",51:"мряка",53:"мряка",55:"сильна мряка",56:"крижана мряка",57:"крижана мряка",
  61:"невеликий дощ",63:"дощ",65:"сильний дощ",66:"крижаний дощ",67:"крижаний дощ",71:"невеликий сніг",73:"сніг",75:"сильний сніг",77:"снігова крупа",
  80:"злива",81:"злива",82:"сильна злива",85:"снігопад",86:"сильний снігопад",95:"гроза",96:"гроза з градом",99:"гроза з градом"};
function wxKind(code){
  if (code >= 95) return "storm";
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow";
  if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return "rain";
  if (code === 45 || code === 48) return "fog";
  if (code === 3) return "cloud";
  if (code === 1 || code === 2) return "part";
  return "clear";
}
const WX_ICON = {
  sun: '<svg viewBox="0 0 20 20" width="16" height="16"><circle cx="10" cy="10" r="3.6" fill="#ffcf5a"/><g stroke="#ffcf5a" stroke-width="1.5" stroke-linecap="round"><path d="M10 2v2.2M10 15.8V18M2 10h2.2M15.8 10H18M4.3 4.3l1.6 1.6M14.1 14.1l1.6 1.6M4.3 15.7l1.6-1.6M14.1 5.9l1.6-1.6"/></g></svg>',
  moon: '<svg viewBox="0 0 20 20" width="16" height="16"><path d="M14.5 13.5A6 6 0 0 1 8.2 3.6a6.5 6.5 0 1 0 8.2 8.2 6 6 0 0 1-1.9 1.7z" fill="#c9d2f0"/></svg>',
  cloud: '<svg viewBox="0 0 20 20" width="16" height="16"><path d="M6 15.5h8.2a3.3 3.3 0 0 0 .3-6.6 4.6 4.6 0 0 0-8.9 1A2.8 2.8 0 0 0 6 15.5z" fill="#aab4d4"/></svg>',
  rain: '<svg viewBox="0 0 20 20" width="16" height="16"><path d="M6 12h8.2a3 3 0 0 0 .3-6 4.3 4.3 0 0 0-8.3 1A2.5 2.5 0 0 0 6 12z" fill="#aab4d4"/><path d="M7 14l-1 3M10.5 14l-1 3M14 14l-1 3" stroke="#8fa6ff" stroke-width="1.5" stroke-linecap="round"/></svg>',
  snow: '<svg viewBox="0 0 20 20" width="16" height="16"><path d="M6 11.5h8.2a3 3 0 0 0 .3-6 4.3 4.3 0 0 0-8.3 1A2.5 2.5 0 0 0 6 11.5z" fill="#aab4d4"/><g fill="#e8ecf8"><circle cx="7" cy="15" r="1.1"/><circle cx="10.5" cy="16.5" r="1.1"/><circle cx="14" cy="15" r="1.1"/></g></svg>',
  fog: '<svg viewBox="0 0 20 20" width="16" height="16"><g stroke="#aab4d4" stroke-width="1.6" stroke-linecap="round"><path d="M3 7h14M5 10.5h12M3 14h11"/></g></svg>',
  storm: '<svg viewBox="0 0 20 20" width="16" height="16"><path d="M6 11h8.2a3 3 0 0 0 .3-6 4.3 4.3 0 0 0-8.3 1A2.5 2.5 0 0 0 6 11z" fill="#8f98b8"/><path d="M10.5 11.5 8 15.5h2.6L9.4 19l3.6-5h-2.6l1.3-2.5z" fill="#ffcf5a"/></svg>'
};
async function pullWeather(){
  try{
    const u = "https://api.open-meteo.com/v1/forecast?latitude=50.45&longitude=30.52&timezone=Europe%2FKyiv&forecast_days=3" +
      "&current=temperature_2m,weather_code,cloud_cover,precipitation,wind_speed_10m,wind_direction_10m,is_day" +
      "&hourly=temperature_2m,weather_code,cloud_cover,precipitation,wind_speed_10m,wind_direction_10m";
    const r = await fetch(u); if (!r.ok) return;
    WX.data = await r.json(); envUpdate();
  }catch(e){}
}
function wxAt(absMin){                     // weather for a map time: "now" uses current, other times the hourly forecast
  const d = WX.data; if (!d) return null;
  if (follow && d.current) return d.current;
  const date = addDays(baseDate, Math.floor(absMin/1440)), hh = String(Math.floor((absMin%1440)/60)).padStart(2,"0");
  const i = d.hourly && d.hourly.time.indexOf(`${date}T${hh}:00`);
  if (i == null || i < 0) return d.current || null;
  const h = d.hourly; return {temperature_2m:h.temperature_2m[i], weather_code:h.weather_code[i], cloud_cover:h.cloud_cover[i], precipitation:h.precipitation[i], wind_speed_10m:h.wind_speed_10m[i], wind_direction_10m:h.wind_direction_10m[i]};
}
function kyivOffsetMin(utcMs){             // Kyiv's offset from UTC at a moment (handles summer time)
  const k = kyivParts(new Date(utcMs)), [y,m,d] = k.date.split("-").map(Number);
  return Math.round((Date.UTC(y, m-1, d) + k.min*60000 - utcMs) / 60000);
}
function mapUtc(absMin){                   // the map's time as a real moment
  const [y,m,d] = baseDate.split("-").map(Number), local = Date.UTC(y, m-1, d) + absMin*60000;
  return local - kyivOffsetMin(local)*60000;
}
function sunPos(ms, lat=50.45, lon=30.52){ // NOAA-style solar position: elevation and azimuth (radians, azimuth from north, clockwise)
  const rad = Math.PI/180, d = ms/86400000 + 2440587.5 - 2451545.0;
  const g = (357.529 + 0.98560028*d)*rad, q = 280.459 + 0.98564736*d;
  const L = (q + 1.915*Math.sin(g) + 0.020*Math.sin(2*g))*rad, e = (23.439 - 0.00000036*d)*rad;
  const ra = Math.atan2(Math.cos(e)*Math.sin(L), Math.cos(L)), dec = Math.asin(Math.sin(e)*Math.sin(L));
  const gmst = (18.697374558 + 24.06570982441908*d) % 24, lst = (gmst*15 + lon)*rad, H = lst - ra, phi = lat*rad;
  const el = Math.asin(Math.sin(phi)*Math.sin(dec) + Math.cos(phi)*Math.cos(dec)*Math.cos(H));
  const az = Math.atan2(-Math.sin(H), Math.tan(dec)*Math.cos(phi) - Math.sin(phi)*Math.cos(H));
  return {el, az: (az + 2*Math.PI) % (2*Math.PI)};
}
const ENV = { day: 0, snow: 0, wet: 0, haze: 0, kind: "clear", precip: 0, wind: 0, windDir: 0, bg: new THREE.Color(0x060912) };
const _night = new THREE.Color(0x060912), _dayClear = new THREE.Color(0x7b98c2), _dayGrey = new THREE.Color(0x56637a), _dusk = new THREE.Color(0x3a2c4a);
function envUpdate(){
  const ms = follow ? Date.now() : mapUtc(tMin), sp = sunPos(ms), elDeg = sp.el*180/Math.PI;
  const w = wxAt(follow ? absNow() : tMin), code = w ? w.weather_code : 0, kind = wxKind(code), cloud = w ? (w.cloud_cover||0)/100 : 0;
  const day = Math.max(0, Math.min(1, (elDeg + 5) / 13));              // civil twilight .. sun 8° up
  const dusk = Math.max(0, 1 - Math.abs(elDeg + 1) / 7) * (1 - 0.6*cloud);
  const precip = w ? Math.min(1, (w.precipitation||0) / 3) : 0;
  ENV.kind = kind; ENV.precip = (kind === "rain" || kind === "snow" || kind === "storm") ? Math.max(0.25, precip) : 0;
  ENV.wind = w ? w.wind_speed_10m || 0 : 0; ENV.windDir = w ? w.wind_direction_10m || 0 : 0;
  ENV.day = day; ENV.haze = kind === "fog" ? 1 : kind === "snow" ? 0.55 : kind === "rain" || kind === "storm" ? 0.4 : cloud*0.2;
  ENV.wet = (kind === "rain" || kind === "storm") ? 1 : 0;
  const t = w ? w.temperature_2m : 5;
  ENV.snowTarget = kind === "snow" ? 1 : (t <= 0 && WX.data && (WX.data.hourly.weather_code.slice(0, 30).some(c => wxKind(c) === "snow"))) ? 0.6 : 0;
  // sky / fog colour
  const sky = _dayClear.clone().lerp(_dayGrey, Math.min(1, cloud*0.8 + ENV.haze*0.6));
  ENV.bg.copy(_night).lerp(sky, day);
  ENV.bg.lerp(_dusk, dusk * 0.55 * (1 - day*0.5));
  // sun direction in map space (x east, z south)
  const ce = Math.cos(Math.max(sp.el, 0.15));
  ENV.sun = new THREE.Vector3(Math.sin(sp.az)*ce, Math.sin(Math.max(sp.el, 0.15)), -Math.cos(sp.az)*ce).normalize();
  // panel chip
  if (w){
    $("wx").hidden = false; $("wxT").textContent = (t > 0 ? "+" : "") + Math.round(t) + "°";
    $("wxL").textContent = WX_TEXT[code] || "";
    const icon = kind === "clear" || kind === "part" ? (day > 0.3 ? "sun" : "moon") : kind === "cloud" ? "cloud" : kind;
    $("wxIcon").innerHTML = WX_ICON[icon] || WX_ICON.cloud;
    $("wx").title = `Погода в Києві${follow ? " зараз" : " на обраний час"}: ${WX_TEXT[code] || ""}, ${Math.round(t)}°, вітер ${Math.round(ENV.wind)} км/год`;
  }
  envTarget = true; needs = true;
}
let envTarget = false;
function envTick(dt){                      // ease the look towards the target, called every frame
  const u = common, k = 1 - Math.exp(-dt/600);
  let moving = false;
  const ease = (o, key, v) => { const d = v - o[key]; if (Math.abs(d) > 0.002){ o[key] += d*k; moving = true; } else o[key] = v; };
  ease(u.uDay, "value", ENV.day); ease(u.uWet, "value", ENV.wet); ease(u.uSnow, "value", ENV.snowTarget || 0);
  if (ENV.sun){ u.uSunDir.value.lerp(ENV.sun, k).normalize(); }
  const fc = u.uFogCol.value; if (Math.abs(fc.r-ENV.bg.r)+Math.abs(fc.g-ENV.bg.g)+Math.abs(fc.b-ENV.bg.b) > 0.004){ fc.lerp(ENV.bg, k); moving = true; } else fc.copy(ENV.bg);
  renderer.setClearColor(fc, 1);
  const near = 30000*(1 - 0.75*ENV.haze), far = 80000*(1 - 0.65*ENV.haze);
  ease(u.uFogNear, "value", near); ease(u.uFogFar, "value", far);
  if (moving) needs = true;
}
pullWeather(); setInterval(pullWeather, 15*60*1000);
setInterval(()=>{ if (follow) envUpdate(); }, 60*1000);

/* rain, snow and lightning drawn over the map */
const FX = { cv: $("wxfx"), parts: [], flash: 0, last: 0 };
function fxResize(){ const r = Math.min(devicePixelRatio, 1.5); FX.cv.width = innerWidth*r; FX.cv.height = innerHeight*r; FX.r = r; }
fxResize(); addEventListener("resize", fxResize);
function fxFrame(now){
  requestAnimationFrame(fxFrame);
  const cv = FX.cv, ctx = cv.getContext("2d"), kind = ENV.kind, want = ENV.precip > 0 && !document.hidden ? Math.round((kind === "snow" ? 160 : 220) * ENV.precip * (innerWidth*innerHeight/1e6 + 0.4)) : 0;
  if (!want && !FX.parts.length && !FX.flash){ if (FX.drawn){ ctx.clearRect(0,0,cv.width,cv.height); FX.drawn = false; } return; }
  const dt = Math.min(50, now - (FX.last || now)); FX.last = now;
  while (FX.parts.length < want) FX.parts.push({x: Math.random()*innerWidth, y: Math.random()*innerHeight, s: 0.6 + Math.random()*0.8, p: Math.random()*6.28});
  if (FX.parts.length > want) FX.parts.length = want;
  ctx.setTransform(FX.r,0,0,FX.r,0,0); ctx.clearRect(0,0,innerWidth,innerHeight); FX.drawn = true;
  const windX = Math.sin((ENV.windDir + 180) * Math.PI/180) * Math.min(1, ENV.wind/40);
  if (kind === "snow"){
    ctx.fillStyle = "rgba(235,240,255,.85)";
    for (const q of FX.parts){
      q.y += dt*0.045*q.s; q.p += dt*0.002; q.x += dt*(0.02*windX + 0.012*Math.sin(q.p));
      if (q.y > innerHeight + 4){ q.y = -4; q.x = Math.random()*innerWidth; } if (q.x < -4) q.x = innerWidth + 4; if (q.x > innerWidth + 4) q.x = -4;
      ctx.beginPath(); ctx.arc(q.x, q.y, 1.1 + q.s*1.1, 0, 6.283); ctx.fill();
    }
  } else if (want){
    ctx.strokeStyle = "rgba(170,190,235,.42)"; ctx.lineWidth = 1; ctx.beginPath();
    const vx = windX*0.35, vy = 1;
    for (const q of FX.parts){
      q.y += dt*0.9*q.s; q.x += dt*0.9*q.s*vx;
      if (q.y > innerHeight + 20){ q.y = -20; q.x = Math.random()*innerWidth; } if (q.x < -20) q.x = innerWidth + 20; if (q.x > innerWidth + 20) q.x = -20;
      const L = 9 + q.s*8; ctx.moveTo(q.x, q.y); ctx.lineTo(q.x - vx*L, q.y - vy*L);
    }
    ctx.stroke();
  }
  if (kind === "storm" && Math.random() < dt/9000) FX.flash = 1;
  if (FX.flash > 0.01){ ctx.fillStyle = `rgba(220,230,255,${(FX.flash*0.35).toFixed(3)})`; ctx.fillRect(0,0,innerWidth,innerHeight); FX.flash *= Math.pow(0.02, dt/1000); } else FX.flash = 0;
}
requestAnimationFrame(fxFrame);

/* ---------- my home ---------- */
const HOME_KEY = "ck_home";
let homeSaved = null, ADDR = null, homePicking = false;
try { homeSaved = JSON.parse(localStorage.getItem(HOME_KEY) || "null"); } catch(e) {}
function homeBuilding(){ return homeSaved && cellIdx ? buildingAt(homeSaved.x, homeSaved.z) : -1; }
function offRanges(group, date){            // "03:00–06:30, 17:00–20:30" for a day (or the fallback during emergencies)
  const e = dayEntry(group, date); if (!e) return null;
  let slots = e.slots || [];
  if (e.status && /Emergency/i.test(e.status)){ const lk = lastKnown[group+".1"] || {}; const d = lk[date] ? date : Object.keys(lk).filter(x=>x<=date).sort().pop(); slots = d ? lk[d] : []; }
  else if (e.status === "WaitingForSchedule") return "графік ще не опубліковано";
  const out = [];
  for (const s of slots) if (s.type === "Definite"){ if (out.length && out[out.length-1][1] === s.start) out[out.length-1][1] = s.end; else out.push([s.start, s.end]); }
  return out.length ? out.map(([a,b]) => `${hhmm(a)}–${b >= 1440 ? "24:00" : hhmm(b)}`).join(", ") : "без відключень";
}
function homeRender(){
  const has = !!homeSaved; $("home").hidden = !has; $("homeAdd").hidden = has;
  if (!has){ $("homePin").hidden = true; return; }
  $("homeName").textContent = homeSaved.label;
  const bi = homeBuilding();
  if (bi < 0){ $("homeNow").className = "home-now"; $("homeNow").textContent = "Завантаження…"; $("homeDay").textContent = ""; return; }
  const grp = zoneArr[bi] > 60 ? 0 : zoneArr[bi];
  if (!grp){ $("homeNow").className = "home-now"; $("homeNow").textContent = "Група для цього будинку невідома"; $("homeDay").innerHTML = 'Перевірте на <a href="https://www.dtek-kem.com.ua/ua/shutdowns" target="_blank" rel="noopener">сайті ДТЕК</a>'; return; }
  const now = absNow(), st = stateAt(grp, now), nx = nextChange(grp, now), blind = st.emergency && !st.fallback;
  const label = blind ? "Екстрені відключення" : st.state === "on" ? "Світло є" : st.state === "off" ? "Світла немає" : "Немає графіка";
  const next = !blind && nx ? ` <span>· ${nx.to === "on" ? "увімкнуть" : nx.to === "off" ? "вимкнуть" : "далі без графіка"} о ${hhmm(nx.at%1440)}${nx.at >= 1440 ? " завтра" : ""}</span>` : "";
  $("homeNow").className = "home-now " + (blind ? "em" : st.state);
  $("homeNow").innerHTML = label + next;
  const t1 = offRanges(grp, baseDate), t2 = offRanges(grp, addDays(baseDate, 1));
  $("homeDay").textContent = `Група ${grp}` + (st.fallback ? " · екстрені, показано останній графік" : "") +
    (t1 ? ` · сьогодні без світла: ${t1}` : "") + (t2 ? ` · завтра: ${t2}` : "");
}
function homePinUpdate(){
  const pin = $("homePin"); if (!homeSaved){ pin.hidden = true; return; }
  _v.set(homeSaved.x, 30, homeSaved.z).project(camera);
  if (_v.z > 1 || Math.abs(_v.x) > 1.05 || Math.abs(_v.y) > 1.05){ pin.hidden = true; return; }
  pin.hidden = false;
  pin.style.transform = `translate(${((_v.x+1)/2*innerWidth).toFixed(1)}px, ${((1-_v.y)/2*innerHeight).toFixed(1)}px) translate(-50%,-100%)`;
}
function homeSave(bi, label){
  homeSaved = {x: Math.round(bcx[bi]), z: Math.round(bcz[bi]), label};
  try { localStorage.setItem(HOME_KEY, JSON.stringify(homeSaved)); } catch(e) {}
  homeRender(); homeFly(); needs = true;
}
function homeFly(){
  if (!homeSaved) return;
  const t = new THREE.Vector3(homeSaved.x, 0, homeSaved.z), from = controls.target.clone(), d0 = controls.dist, d1 = Math.min(d0, 2600), t0 = performance.now();
  (function step(){
    const k = Math.min(1, (performance.now() - t0)/900), e = 1 - Math.pow(1-k, 3);
    controls.target.copy(from).lerp(t, e); controls.dist = d0 + (d1 - d0)*e; controls.apply();
    if (k < 1) requestAnimationFrame(step);
  })();
}
const NORM = s => s.toLowerCase().replace(/[’ʼ`]/g, "'").replace(/ё/g, "е").replace(/[.,]/g, " ").replace(/\b(вулиця|вул|проспект|просп|пр-т|провулок|пров|бульвар|бульв|б-р|площа|пл|набережна|наб|шосе|узвіз|тупик|алея|проїзд|майдан|дорога|лінія)\b/g, " ").replace(/\s+/g, " ").trim();
async function addrLoad(){
  if (ADDR) return ADDR;
  const d = await (await fetch("addr_index.json")).json();
  ADDR = {streets: d.streets, norm: d.streets.map(NORM), a: d.a, byStreet: new Map()};
  for (const r of d.a){ let l = ADDR.byStreet.get(r[0]); if (!l){ l = []; ADDR.byStreet.set(r[0], l); } l.push(r); }
  return ADDR;
}
function houseKey(h){ return h.toUpperCase().replace(/\s|-/g, "").replace(/[A]/g, "А").replace(/[B]/g, "В").replace(/[E]/g, "Е"); }
function addrSearch(q){
  const m = q.match(/^(.*?)[,\s]+(\d+[^\s,]*)\s*$/), street = NORM(m ? m[1] : q), house = m ? houseKey(m[2]) : "";
  const words = street.split(" ").filter(Boolean); if (!words.length) return [];
  const hits = [];
  ADDR.norm.forEach((n, i) => { const nw = n.split(" "); if (words.every(w => nw.some(x => x.startsWith(w)))) hits.push(i); });
  hits.sort((a, b) => ADDR.streets[a].length - ADDR.streets[b].length);
  const out = [];
  for (const si of hits.slice(0, 40)){
    const list = ADDR.byStreet.get(si) || [];
    const hs = house ? list.filter(r => houseKey(r[1]).startsWith(house)) : list;
    hs.sort((a, b) => (parseInt(a[1]) || 0) - (parseInt(b[1]) || 0) || a[1].localeCompare(b[1]));
    for (const r of (house ? hs : hs.slice(0, 3))) { out.push(r); if (out.length >= 12) return out; }
  }
  return out;
}
function sheetOpen(){
  $("homeSheet").hidden = false; $("homeDel").hidden = !homeSaved; $("homeQ").value = ""; $("homeSugg").innerHTML = "";
  setTimeout(()=> $("homeQ").focus(), 30);
  addrLoad().catch(()=>{ $("homeSugg").innerHTML = '<li aria-disabled="true">Не вдалося завантажити адреси. Оберіть будинок на карті.</li>'; });
}
function sheetClose(){ $("homeSheet").hidden = true; }
$("homeAdd").onclick = sheetOpen; $("homeEdit").onclick = sheetOpen; $("homeClose").onclick = sheetClose; $("homeGo").onclick = homeFly;
$("homeSheet").addEventListener("click", e => { if (e.target === $("homeSheet")) sheetClose(); });
addEventListener("keydown", e => { if (e.key === "Escape" && !$("homeSheet").hidden) sheetClose(); });
$("homeQ").addEventListener("input", async () => {
  const q = $("homeQ").value.trim(), ul = $("homeSugg");
  if (q.length < 2){ ul.innerHTML = ""; return; }
  try { await addrLoad(); } catch(e) { return; }
  const res = addrSearch(q);
  ul.innerHTML = res.length ? res.map((r, i) => `<li role="option" tabindex="0" data-i="${i}">${ADDR.streets[r[0]].replace(/</g,"&lt;")}, <b>${r[1].replace(/</g,"&lt;")}</b></li>`).join("")
    : '<li aria-disabled="true"><small>Нічого не знайдено. Спробуйте інакше або оберіть будинок на карті.</small></li>';
  ul.querySelectorAll("li[data-i]").forEach(li => {
    const choose = () => { const r = res[+li.dataset.i]; sheetClose(); homeSave(r[2], `${ADDR.streets[r[0]]}, ${r[1]}`); };
    li.onclick = choose; li.onkeydown = e => { if (e.key === "Enter") choose(); };
  });
});
$("homePick").onclick = () => { sheetClose(); homePicking = true; $("pickBar").hidden = false; };
$("pickCancel").onclick = () => { homePicking = false; $("pickBar").hidden = true; };
$("homeDel").onclick = () => { homeSaved = null; try { localStorage.removeItem(HOME_KEY); } catch(e) {} sheetClose(); homeRender(); needs = true; };
function homePickAt(ev){                   // called from the map tap while choosing
  const r = canvas.getBoundingClientRect(); mouse.set(((ev.clientX-r.left)/r.width)*2-1, -((ev.clientY-r.top)/r.height)*2+1);
  ray.setFromCamera(mouse, camera); if (!ray.ray.intersectPlane(plane, hit)) return;
  const bi = buildingAt(hit.x, hit.z); if (bi < 0) return;
  homePicking = false; $("pickBar").hidden = true; tip.hidden = true;
  homeSave(bi, "Мій будинок на карті");
}
setInterval(homeRender, 30*1000);
'''
rep('/* ---------- district labels floating above the map ---------- */', JS + '\n/* ---------- district labels floating above the map ---------- */')

# taps while choosing a home pick the building
rep('''canvas.addEventListener("pointerup", e=>{ if(downAt && Math.hypot(e.clientX-downAt[0], e.clientY-downAt[1])<6) pick(e); downAt=null; });''',
    '''canvas.addEventListener("pointerup", e=>{ if(downAt && Math.hypot(e.clientX-downAt[0], e.clientY-downAt[1])<6){ if(homePicking) homePickAt(e); else pick(e); } downAt=null; });''')
# pin follows the camera; weather look eases every frame; everything refreshes with the map time
rep('''function updateLabels(){
  const w=innerWidth, h=innerHeight;''', '''function updateLabels(){
  const w=innerWidth, h=innerHeight;
  if (typeof homePinUpdate === "function") homePinUpdate();''')
rep('''  if(controls.update()){ needs=true; lastCam = now; if (TR.on && TR.ready) trUpdate(); }   // keep vehicles glued to the moving camera''',
    '''  if(controls.update()){ needs=true; lastCam = now; if (TR.on && TR.ready) trUpdate(); }   // keep vehicles glued to the moving camera
  envTick(Math.min(100, now - (loop.t || now))); loop.t = now;''')
rep('''(function loop(now){''', '''function loop(now){''')
rep('''    const dt = now - lastFrame; if (dt < 120) frameAvg = frameAvg*0.9 + dt*0.1; lastFrame = now;
  }
})();''', '''    const dt = now - lastFrame; if (dt < 120) frameAvg = frameAvg*0.9 + dt*0.1; lastFrame = now;
  }
}
loop();''')
rep('''function setT(v, f=false){ tMin=Math.max(0,Math.min(2879,v)); follow=f; slider.value=tMin; $("nowBtn").classList.toggle("active",f); trBase=tMin; trSetAt=performance.now(); apply();''',
    '''function setT(v, f=false){ tMin=Math.max(0,Math.min(2879,v)); follow=f; slider.value=tMin; $("nowBtn").classList.toggle("active",f); trBase=tMin; trSetAt=performance.now(); apply(); if (typeof envUpdate === "function") envUpdate();''')
# home card and look refresh once the city has loaded and whenever the schedule arrives
rep('''  $("loader").hidden = true;
  loadTransit();''', '''  $("loader").hidden = true;
  loadTransit(); homeRender(); envUpdate();''')
open(p, "w").write(s)
print("ok")
