"""Add an 'emergency outages' state: buildings whose group YASNO marks as under
emergency shutdowns are shaded dark (schedule not in force). Applied once to index.html."""
import sys
p = sys.argv[1]
s = open(p).read()

def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

# uniforms: one emergency flag per group
rep('const target = new Array(64).fill(0.5);',
    'const target = new Array(64).fill(0.5);\nconst uEm = { value: new Array(64).fill(0) }, targetE = new Array(64).fill(0);')
rep('  uState: uState,', '  uState: uState, uEm: uEm,')

# building shader
rep('''    uniform float uState[64];
    varying vec3 vW; varying float vS; varying float vH; varying float vSeed;''',
    '''    uniform float uState[64]; uniform float uEm[64];
    varying vec3 vW; varying float vS; varying float vH; varying float vSeed; varying float vE;''')
rep('      vS = uState[int(zone + 0.5)];\n      vSeed', '      vS = uState[int(zone + 0.5)]; vE = uEm[int(zone + 0.5)];\n      vSeed')
rep('''    varying vec3 vW; varying float vS; varying float vH; varying float vSeed;
    ${FOG}''', '''    varying vec3 vW; varying float vS; varying float vH; varying float vSeed; varying float vE;
    ${FOG}''')
rep('      gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0);\n    }`\n});\n\nconst roadMat',
    '      c = mix(c, vec3(0.045,0.05,0.085) + 0.05*diff, vE*0.85);   // emergency: shaded\n      gl_FragColor = vec4(mix(c, uFogCol, fogF(vW)), 1.0);\n    }`\n});\n\nconst roadMat')

# road shader
rep('''    uniform float uState[64];
    varying vec3 vW; varying float vS; varying float vR;''',
    '''    uniform float uState[64]; uniform float uEm[64];
    varying vec3 vW; varying float vS; varying float vR; varying float vE;''')
rep('      vS = uState[int(zone + 0.5)];\n      gl_Position', '      vS = uState[int(zone + 0.5)]; vE = uEm[int(zone + 0.5)];\n      gl_Position')
rep('''    varying vec3 vW; varying float vS; varying float vR;
    ${FOG}''', '''    varying vec3 vW; varying float vS; varying float vR; varying float vE;
    ${FOG}''')
rep('      float a = (0.35 + 0.55*major) * (1.0 - fogF(vW));',
    '      c = mix(c, vec3(0.10,0.11,0.16), vE*0.8);\n      float a = (0.35 + 0.55*major) * (1.0 - fogF(vW)) * (1.0 - 0.45*vE);')

# state per group
rep('''    if(st.emergency) emergency=true;
    target[g] = st.state==="on"?1:st.state==="off"?0:0.5;
    const n = zoneBuildings[g]; st.state==="on"?on+=n:st.state==="off"?off+=n:unk+=n; }''',
    '''    if(st.emergency) emergency=true;
    target[g] = st.state==="on"?1:st.state==="off"?0:0.5;
    targetE[g] = st.emergency ? 1 : 0;
    const n = zoneBuildings[g]; st.emergency ? emc+=n : st.state==="on"?on+=n:st.state==="off"?off+=n:unk+=n; }''')
rep('  let on=0, off=0, unk=0, emergency=false;', '  let on=0, off=0, unk=0, emc=0, emergency=false;')
rep('  target[NZ]=0.5; unk += zoneBuildings[NZ];', '  target[NZ]=0.5; targetE[NZ]=0; unk += zoneBuildings[NZ];')
# emergency banner text: make it about shaded buildings
s = s.replace('ban.textContent="YASNO повідомляє про екстрені відключення: планові графіки зараз не діють, тож карта не показує реальний стан.";',
              'ban.textContent="Діють екстрені відключення: для затінених будинків графік зараз не діє, світла може не бути будь-коли.";')

# animation of the flags
rep('    for(let i=0;i<64;i++){ const d=target[i]-uState.value[i];',
    '    for(let i=0;i<64;i++){ const de=targetE[i]-uEm.value[i]; if(Math.abs(de)>0.002){ uEm.value[i]+= reduce? de : de*0.12; moving=true; } else uEm.value[i]=targetE[i]; }\n    for(let i=0;i<64;i++){ const d=target[i]-uState.value[i];')

# tooltip
rep('''    const label = st.state==="on"?"Світло є":st.state==="off"?"Світла немає":"Немає графіка";
    const src = how===1''', '''    const label = st.emergency ? "Екстрені відключення" : st.state==="on"?"Світло є":st.state==="off"?"Світла немає":"Немає графіка";
    const src = how===1''')
rep('''    html = `<div class="st ${st.state}">${label}</div><div>Група ${grp}</div>`+
      (nx?''', '''    html = `<div class="st ${st.emergency?"em":st.state}">${label}</div><div>Група ${grp}</div>`+
      (st.emergency?`<div class="m">Графік зараз не діє, світла може не бути будь-коли</div>`:"")+
      (!st.emergency && nx?''')

# legend + styles
rep('<div class="legend"><span><i class="sw na"></i>немає даних про групу</span></div>',
    '<div class="legend"><span><i class="sw na"></i>немає даних про групу</span><span id="lgEm" hidden><i class="sw em"></i>екстрені відключення</span></div>')
rep('.legend span{display:inline-flex;align-items:center;gap:6px}',
    '.legend span{display:inline-flex;align-items:center;gap:6px}\n.sw.em{background:#14172a;box-shadow:inset 0 0 0 1px rgba(150,170,230,.35)}\n.tip .st.em{color:var(--warn)}')
rep('  const known = on+off || 1;', '  $("lgEm").hidden = !emc;\n  const known = on+off || 1;')
open(p, 'w').write(s)
print('ok')
