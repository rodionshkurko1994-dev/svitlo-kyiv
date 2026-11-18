"""Kyiv region power: DTEK KREM group schedules (12 groups, GPV1.1..6.2).

Source: the open dataset github.com/Baskerville42/outage-data-ua (MIT), data/kyiv-region.json, which keeps the
DTEK KREM public schedule page as JSON and is refreshed every few minutes by its own GitHub Actions. The page
reads it from raw.githubusercontent.com; nothing is requested from DTEK by this site.

There is no open address -> group list for the region, so:
- region buildings (zone 63) are tinted by the share of groups with power at the chosen time
- "Мій дім" in the region asks the person for their group once and then shows the exact schedule
Applied once after patch_region.py: python3 tools/patch_region_power.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

JS = r'''/* ---------- Kyiv region schedules (DTEK KREM via the open outage-data-ua dataset) ---------- */
var RP = { days: {}, upd: "", ok: false };
var RP_GROUPS = ["1.1","1.2","2.1","2.2","3.1","3.2","4.1","4.2","5.1","5.2","6.1","6.2"];
async function regionPower(){
  try{
    const r = await fetch("https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/kyiv-region.json?t=" + Math.floor(Date.now()/300000), {cache:"no-store"});
    if (!r.ok) return;
    const d = await r.json(), f = d && d.fact; if (!f || !f.data) return;
    const days = {};
    for (const ts in f.data){ const date = kyivParts(new Date(+ts*1000 + 3600e3)).date; days[date] = f.data[ts]; }
    RP.days = days; RP.upd = f.update || ""; RP.ok = true;
    apply(); if (typeof homeRender === "function") homeRender();
  }catch(e){}
}
function rpState(g, absMin){                     // "on" | "off" | "maybe" | null for group "1.1" at minutes from baseDate
  const date = addDays(baseDate, Math.floor(absMin/1440)), day = RP.days[date]; if (!day) return null;
  const row = day["GPV" + g]; if (!row) return null;
  const m = ((absMin % 1440) + 1440) % 1440, v = row[String(Math.floor(m/60) + 1)], first = m % 60 < 30;
  if (v === "yes") return "on"; if (v === "no") return "off"; if (v === "maybe") return "maybe";
  if (v === "first") return first ? "off" : "on"; if (v === "second") return first ? "on" : "off";
  if (v === "mfirst") return first ? "maybe" : "on"; if (v === "msecond") return first ? "on" : "maybe";
  return null;
}
function rpShare(absMin){
  let on = 0, n = 0;
  for (const g of RP_GROUPS){ const st = rpState(g, absMin); if (st === "on"){ on++; n++; } else if (st === "off"){ n++; } else if (st === "maybe"){ on += 0.5; n++; } }
  return n ? { on, n, share: on/n } : null;
}
function rpNext(g, absMin){
  const cur = rpState(g, absMin);
  for (let t = Math.floor(absMin/30)*30 + 30; t < 2880; t += 30){ const st = rpState(g, t); if (st !== cur) return { at: t, to: st }; }
  return null;
}
function rpRanges(g, dayOff){
  const out = []; let has = false;
  for (let t = dayOff*1440; t < dayOff*1440 + 1440; t += 30){
    const st = rpState(g, t); if (st) has = true;
    if (st === "off"){ const a = t % 1440; if (out.length && out[out.length-1][1] === a) out[out.length-1][1] = a + 30; else out.push([a, a + 30]); }
  }
  if (!has) return null;
  return out.length ? out.map(([a, b]) => `${hhmm(a)}–${b >= 1440 ? "24:00" : hhmm(b)}`).join(", ") : "без відключень";
}
function regionApply(){
  if (typeof RP === "undefined" || !RP) return;   // zone 63 = region buildings and roads
  const sh = RP.ok ? rpShare(tMin) : null;
  target[63] = sh ? sh.share : 0.5; targetE[63] = 0; targetF[63] = 0;
  const el = $("rpNote"); if (!el) return;
  el.hidden = !RP.ok;
  if (RP.ok) el.innerHTML = sh ? `Київщина (ДТЕК КРЕМ): світло ${follow ? "зараз" : "о " + hhmm(tMin%1440)} у <strong>${sh.on % 1 ? sh.on.toFixed(1) : sh.on} з ${sh.n}</strong> груп. Графік оновлено ${RP.upd}.`
    : `Київщина (ДТЕК КРЕМ): графіка на цей день ще немає.`;
}
regionPower(); setInterval(regionPower, 5*60*1000);

'''

rep('/* ---------- Kyiv agglomeration (OpenStreetMap, no power data) ---------- */', JS + '/* ---------- Kyiv agglomeration (OpenStreetMap) ---------- */')
# region buildings and roads get their own zone
rep('const pos = new Float32Array(V*3), zat = new Uint8Array(V), idx = new Uint32Array(I);\n    let vv = 0',
    'const pos = new Float32Array(V*3), zat = new Uint8Array(V).fill(63), idx = new Uint32Array(I);\n    let vv = 0')
rep('const rp = new Float32Array(segs*6), rz = new Uint8Array(segs*2), rk = new Uint8Array(segs*2);\n  let p = 0, q = 0;',
    'const rp = new Float32Array(segs*6), rz = new Uint8Array(segs*2).fill(63), rk = new Uint8Array(segs*2);\n  let p = 0, q = 0;')
# state: zone 63 follows the region share
rep('  target[NZ]=0.5; targetE[NZ]=0; targetF[NZ]=0; unk += zoneBuildings[NZ];',
    '  target[NZ]=0.5; targetE[NZ]=0; targetF[NZ]=0; unk += zoneBuildings[NZ];\n  if (typeof regionApply === "function") regionApply();')
rep('<p class="note" id="fresh">Графік YASNO: завантаження…</p>',
    '<p class="note" id="fresh">Графік YASNO: завантаження…</p>\n  <p class="note" id="rpNote" hidden></p>')
rep('<span><i class="sw na"></i>немає даних про групу</span>',
    '<span><i class="sw na"></i>немає даних про групу</span><span><i class="sw rg"></i>Київщина: частка груп зі світлом</span>')
rep('.home-now span{', '.sw.rg{background:linear-gradient(90deg,#2a3f8f,#5a5d70,#ff9636)}\n.home-grp{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px}\n.home-grp button{font:inherit;font-size:11.5px;padding:3px 7px;border-radius:7px;border:1px solid var(--line,#2a3150);background:none;color:inherit;cursor:pointer}\n.home-grp button:hover{border-color:#ff9636}\n.home-now span{')

# tooltip in the region
rep('''  const town = regionTown(x, z);
  return `<div class="st">Київська область</div>` + (town ? `<div>${town.replace(/</g,"&lt;")}</div>` : "") +
    `<div class="m">Графіків відключень для області на карті поки немає: ДТЕК Київські регіональні електромережі не публікує їх у відкритому доступі</div>`;''',
'''  const town = regionTown(x, z), sh = RP.ok ? rpShare(tMin) : null;
  return `<div class="st">Київщина</div>` + (town ? `<div>${town.replace(/</g,"&lt;")}</div>` : "") +
    (sh ? `<div class="m">Світло у ${sh.on % 1 ? sh.on.toFixed(1) : sh.on} з ${sh.n} груп ДТЕК КРЕМ</div>` : `<div class="m">Графік ДТЕК КРЕМ на цей час ще не отримано</div>`) +
    `<div class="m">Група цього будинку невідома: колір показує частку груп зі світлом. Додайте свою адресу в «Мій дім» і вкажіть групу, щоб бачити точний графік</div>`;''')

# my home in the region: choose a group once, then exact schedule
rep('''  if (homeSaved.reg){
    $("homeNow").className = "home-now"; $("homeNow").textContent = "Київська область: графіків поки немає";
    $("homeDay").innerHTML = 'ДТЕК не публікує графіки області відкрито. Перевірте на <a href="https://www.dtek-krem.com.ua/ua/shutdowns" target="_blank" rel="noopener">сайті ДТЕК КРЕМ</a>';
    return;
  }''', '''  if (homeSaved.reg){
    const g = homeSaved.grp, link = '<a href="https://www.dtek-krem.com.ua/ua/shutdowns" target="_blank" rel="noopener">сайті ДТЕК КРЕМ</a>';
    const pick = `<div class="home-grp">${RP_GROUPS.map(x => `<button type="button" data-g="${x}">${x}</button>`).join("")}</div>`;
    if (!g){
      $("homeNow").className = "home-now"; $("homeNow").textContent = "Оберіть свою групу ДТЕК КРЕМ";
      $("homeDay").innerHTML = `Групу за адресою можна дізнатися на ${link}.` + pick;
    } else if (!RP.ok){
      $("homeNow").className = "home-now"; $("homeNow").textContent = `Група ${g}: завантаження графіка…`; $("homeDay").textContent = "";
    } else {
      const now = absNow(), st = rpState(g, now), nx = rpNext(g, now);
      const label = st === "on" ? "Світло є" : st === "off" ? "Світла немає" : st === "maybe" ? "Можливе відключення" : "Немає графіка";
      const next = nx ? ` <span>· ${nx.to === "on" ? "увімкнуть" : nx.to === "off" ? "вимкнуть" : nx.to === "maybe" ? "можливе відключення" : "далі без графіка"} о ${hhmm(nx.at%1440)}${nx.at >= 1440 ? " завтра" : ""}</span>` : "";
      $("homeNow").className = "home-now " + (st === "on" || st === "off" ? st : "");
      $("homeNow").innerHTML = label + next;
      const t1 = rpRanges(g, 0), t2 = rpRanges(g, 1);
      $("homeDay").innerHTML = `Група ${g} (ДТЕК КРЕМ)` + (t1 ? ` · сьогодні без світла: ${t1}` : "") + (t2 ? ` · завтра: ${t2}` : "") +
        ` · <a href="#" id="homeGrpChange">змінити групу</a>`;
      const ch = $("homeGrpChange"); if (ch) ch.onclick = e => { e.preventDefault(); delete homeSaved.grp; homeStore(); homeRender(); };
    }
    $("homeDay").querySelectorAll("button[data-g]").forEach(b => b.onclick = () => { homeSaved.grp = b.dataset.g; homeStore(); homeRender(); });
    return;
  }''')
rep('function homeSave(bi, label){', 'function homeStore(){ try { localStorage.setItem(HOME_KEY, JSON.stringify(homeSaved)); } catch(e) {} }\nfunction homeSave(bi, label){')
open(p, "w").write(s)
print("ok")
