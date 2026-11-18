"""Clear city limits: everything outside Kyiv's boundary (META.city) is cut away and the boundary is drawn as a
glowing curtain. A mask texture rasterised from the outline is sampled by every map shader.
Applied once: python3 tools/patch_bounds.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:90])
    s = s.replace(old, new)

MASK = r'''/* city limits mask: 1 inside Kyiv, 0 outside (rasterised from the boundary in META.city) */
const CITY_MASK = (()=>{
  let x0=1e9, z0=1e9, x1=-1e9, z1=-1e9;
  for (const [x,z] of META.city){ x0=Math.min(x0,x); x1=Math.max(x1,x); z0=Math.min(z0,z); z1=Math.max(z1,z); }
  x0-=300; z0-=300; x1+=300; z1+=300;
  const N = 2048, cv = document.createElement("canvas"); cv.width = cv.height = N;
  const g = cv.getContext("2d"); g.fillStyle = "#000"; g.fillRect(0,0,N,N); g.fillStyle = "#fff"; g.beginPath();
  META.city.forEach(([x,z],i)=>{ const u=(x-x0)/(x1-x0)*N, v=(z-z0)/(z1-z0)*N; i ? g.lineTo(u,v) : g.moveTo(u,v); });
  g.closePath(); g.fill();
  const t = new THREE.CanvasTexture(cv); t.flipY = false; t.minFilter = t.magFilter = THREE.LinearFilter; t.generateMipmaps = false;
  return { tex: t, box: new THREE.Vector4(x0, z0, x1-x0, z1-z0) };
})();
'''

rep('const FOG = `\n  float fogF(vec3 wp){ float d = distance(wp, cameraPosition); return smoothstep(uFogNear, uFogFar, d); }`;',
    MASK + 'const FOG = `\n  float fogF(vec3 wp){ float d = distance(wp, cameraPosition); return smoothstep(uFogNear, uFogFar, d); }\n'
    '  uniform sampler2D uMask; uniform vec4 uMaskB;\n'
    '  float inCity(vec3 wp){ vec2 uv = (wp.xz - uMaskB.xy) / uMaskB.zw; if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return 0.0; return texture2D(uMask, uv).r; }\n'
    '  #define CITY_CLIP if (inCity(vW) < 0.5) discard;`;')
rep('  uFogNear: { value: 30000 }, uFogFar: { value: 80000 },',
    '  uFogNear: { value: 30000 }, uFogFar: { value: 80000 },\n  uMask: { value: CITY_MASK.tex }, uMaskB: { value: CITY_MASK.box },')

# clip in every map shader: buildings, roads, flat layers, transit vehicles
rep('''    ${FOG}
    void main(){
      vec3 n = normalize(cross(dFdx(vW), dFdy(vW)));''', '''    ${FOG}
    void main(){
      CITY_CLIP
      vec3 n = normalize(cross(dFdx(vW), dFdy(vW)));''')
rep('''    ${FOG}
    void main(){
      float major =''', '''    ${FOG}
    void main(){
      CITY_CLIP
      float major =''')
rep('''varying vec3 vW; ${FOG}
      void main(){
        vec3 c = mix(uCol, uColDay, uDay);''', '''varying vec3 vW; ${FOG}
      void main(){
        CITY_CLIP
        vec3 c = mix(uCol, uColDay, uDay);''')
rep('''      varying float vP; varying vec3 vN; varying vec3 vW; ${FOG}
      void main(){''', '''      varying float vP; varying vec3 vN; varying vec3 vW; ${FOG}
      void main(){
        CITY_CLIP''')

# boundary: bright line and a soft glowing curtain
rep('''  const cpts = META.city.map(q=>new THREE.Vector3(q[0],2,q[1]));
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(cpts), new THREE.LineBasicMaterial({color:0x34427a, transparent:true, opacity:.8})));''',
'''  const cpts = META.city.map(q=>new THREE.Vector3(q[0],3,q[1]));
  const edge = new THREE.Line(new THREE.BufferGeometry().setFromPoints(cpts), new THREE.LineBasicMaterial({color:0x9fb0ff, transparent:true, opacity:.95}));
  edge.renderOrder = 4; scene.add(edge);
  {
    const H = 260, P = [], A = [];
    for (let i = 0; i < META.city.length - 1; i++){
      const [ax,az] = META.city[i], [bx,bz] = META.city[i+1];
      P.push(ax,0,az, bx,0,bz, bx,H,bz,  ax,0,az, bx,H,bz, ax,H,az); A.push(1,1,0, 1,0,0);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(P,3)); g.setAttribute("a", new THREE.Float32BufferAttribute(A,1));
    const m = new THREE.ShaderMaterial({ transparent:true, depthWrite:false, side:THREE.DoubleSide, blending:THREE.AdditiveBlending,
      uniforms: { uDay: common.uDay },
      vertexShader: `attribute float a; varying float vA; void main(){ vA = a; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
      fragmentShader: `uniform float uDay; varying float vA; void main(){ gl_FragColor = vec4(vec3(0.42,0.50,1.0) * vA*vA * (0.55 - 0.25*uDay), 1.0); }` });
    const curtain = new THREE.Mesh(g, m); curtain.frustumCulled = false; curtain.renderOrder = 3; scene.add(curtain);
  }''')
open(p, "w").write(s)
print("ok")
