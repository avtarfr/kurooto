/* Brain 3D (0.8.2): the dashboard's Brain page. Needs vendor/three/three.min.js (three.js r128, MIT). */
(function(){const STYLE='@media(max-width:900px){.b3{grid-template-columns:1fr !important;grid-template-rows:62vh auto !important}}\n.b3{--bg:var(--panel,#121810);--panel:var(--panel,#121810);--line:var(--line,#27311f);--ink:var(--fg,#dad3c8);--mute:var(--dim,#8d9a84);position:relative;display:block;width:100%;height:100%;min-height:420px;color:var(--ink);font:13.5px/1.45 inherit;background:transparent;overflow:hidden}\n.b3 .b3app{display:block;position:relative;width:100%;height:100%}\n.b3 #b3-stage{position:absolute;inset:0;overflow:hidden;z-index:1}\n.b3 canvas{display:block;width:100%;height:100%;cursor:grab}\n.b3 canvas:active{cursor:grabbing}\n.b3 #b3-top{position:absolute;left:22px;top:16px;z-index:3;pointer-events:none}\n.b3 #b3-top h1{font-size:18px;font-weight:650}\n.b3 #b3-crumb{color:var(--mute);font-size:12.5px;margin-top:2px;pointer-events:auto}\n.b3 #b3-crumb a{color:var(--accent-text,#a9cf72);cursor:pointer}\n.b3 .seg{position:absolute;right:16px;top:14px;z-index:3;display:flex;gap:3px;background:var(--panel,#121810);border:1px solid var(--line);border-radius:99px;padding:3px;box-shadow:0 2px 8px rgba(0,0,0,0.35)}\n.b3 .seg button{border:0;background:none;color:var(--mute);padding:5px 12px;border-radius:99px;cursor:pointer;font:500 12px var(--mono,monospace);transition:all .15s ease}\n.b3 .seg button.on{background:var(--accent,#6b8a42);color:var(--fg,#dad3c8);font-weight:600}\n.b3 .sw8{display:inline-block;width:18px;height:12px;border-radius:3px;margin-right:8px;vertical-align:-1px;border:1px solid #ffffff22}\n.b3 #b3-back{position:absolute;left:22px;top:64px;z-index:3;display:none;padding:7px 14px;border-radius:99px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;font-size:12.5px}\n.b3 .lab{position:absolute;z-index:2;transform:translate(-50%,-50%);font-size:12.5px;white-space:nowrap;text-shadow:0 0 6px #000,0 0 3px #000;pointer-events:none;transition:opacity .25s,font-size .15s}\n.b3 .lab small{display:block;text-align:center;color:var(--mute);font-size:10.5px;margin-top:-1px}\n.b3 .lab.hot{font-size:14px;font-weight:650}\n.b3 .lab.dim{opacity:.18}\n.b3 .cl{position:absolute;z-index:2;transform:translate(-50%,0);font-size:12px;white-space:nowrap;text-shadow:0 0 6px #000;pointer-events:none;color:var(--ink)}\n.b3 #b3-side{position:absolute;right:0;top:0;bottom:0;width:290px;max-width:85%;background:var(--panel);border-left:1px solid var(--line);padding:20px 18px;overflow-y:auto;z-index:15;transform:translateX(100%);transition:transform .22s cubic-bezier(0.2,0.9,0.3,1);box-shadow:-6px 0 24px rgba(0,0,0,0.5)}\n.b3.side-open #b3-side, .b3 #b3-side:hover{transform:translateX(0)}\n.b3 #b3-tab{position:absolute;right:0;top:50%;transform:translateY(-50%);z-index:10;background:var(--panel);border:1px solid var(--line);border-right:0;border-radius:6px 0 0 6px;padding:8px 6px;cursor:pointer;color:var(--mute);display:flex;align-items:center;justify-content:center;font-size:12px;box-shadow:-3px 0 10px rgba(0,0,0,0.3);transition:color .15s,background .15s}\n.b3 #b3-tab:hover{color:var(--ink);background:var(--well,var(--panel))}\n.b3.side-open #b3-tab{display:none}\n.b3 h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;color:var(--mute);font-weight:600;margin:16px 0 8px}\n.b3 .chip{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;border:1px solid var(--line);background:rgba(255,255,255,0.05)}\n.b3 .m{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--line)}\n.b3 .m span:first-child{color:var(--mute)}\n.b3 .sw{display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding:10px 12px;border:1px solid var(--line);border-radius:14px}\n.b3 .tog{width:42px;height:24px;border-radius:99px;background:var(--accent,#43582f);position:relative;flex:none}\n.b3 .tog:after{content:"";position:absolute;right:3px;top:3px;width:18px;height:18px;border-radius:50%;background:var(--ink)}\n.b3 .tog.off{background:rgba(255,255,255,0.12)}\n.b3 .tog.off:after{right:auto;left:3px}\n.b3 .ev{font-size:12.5px;color:var(--ink);padding:5px 0;border-bottom:1px solid var(--line)}\n.b3 .ev b{color:var(--mute);font-weight:500;margin-right:6px}\n.b3 .cap{position:absolute;left:0;right:0;bottom:0;padding:9px 20px;background:rgba(10,13,9,0.8);color:var(--mute);font-size:12px;border-top:1px solid var(--line);z-index:4}\n.b3 .legend{position:absolute;right:16px;bottom:44px;color:var(--mute);font-size:11.5px;z-index:3;text-align:right}\n.b3 .hint{position:absolute;left:22px;bottom:44px;color:var(--mute);font-size:12px;z-index:3}';
window.brain3dMount=function(host,DATA,OPTS){OPTS=OPTS||{};if(!document.getElementById("b3-style")){const s=document.createElement("style");s.id="b3-style";s.textContent=STYLE;document.head.appendChild(s)}host.classList.add("b3");host.innerHTML='<div class=b3app><div id=b3-stage><canvas id=b3-cv></canvas><div id=b3-top><h1>Brain <span style="color:var(--mute);font-weight:400">· 3D</span></h1><div id=b3-crumb></div></div><div class=seg id=b3-seg><button data-m=solid class=on>Solid</button><button data-m=cut>Cutaway</button><button data-m=xray>X-ray</button></div><button id=b3-back>‹ whole brain</button><div id=b3-labs></div><div class=hint>drag to turn · scroll to zoom · click a region</div><div class=legend id=b3-lg></div></div><button id=b3-tab title="Toggle region info panel">‹</button><div id=b3-side></div></div>';
const C={};const P_THEME=typeof window!=="undefined"&&window.PAL?{hq:window.PAL.accent||"#a6c07a",fore:window.PAL.peach||"#ddb866",cons:window.PAL.pink||"#d6967a",memory:window.PAL.lav||"#8dbdb3",mirror:window.PAL.rose||"#b9a6cc",senses:window.PAL.sand||"#e4d8b4",shop:window.PAL.ok||"#8ccb98",body:window.PAL.bad||"#e8735a"}:{};
DATA.islands.forEach(i=>C[i.id]=P_THEME[i.id]||i.color);const S=DATA.islands.slice();

/* where each island lives in a human-shaped brain: z is front (+) to back (-), y up, x left/right */
const G={hq:{c:[[0,.02,.05]],why:"thalamic hub: everything passes through it"},fore:{c:[[0,.4,.95]],why:"prefrontal: planning and forecasting"},cons:{c:[[0,-.02,.66]],why:"orbitofrontal and cingulate: conscience, control"},
 memory:{c:[[.62,-.32,.12],[-.62,-.32,.12]],why:"temporal lobes and hippocampus: memory"},mirror:{c:[[.5,.4,-.4],[-.5,.4,-.4]],why:"temporoparietal: a model of other minds"},
 senses:{c:[[0,.08,-1.0]],why:"occipital and sensory cortex: the senses"},shop:{c:[[0,-.58,-.72]],why:"cerebellum: skills and practice"},body:{c:[[0,-.64,-.12]],why:"insula and brainstem: the body's state"}};
const ids=Object.keys(G),V=(a)=>new THREE.Vector3(a[0],a[1],a[2]);
const cv=host.querySelector("#b3-cv"),side=host.querySelector("#b3-side"),labs=host.querySelector("#b3-labs"),crumb=host.querySelector("#b3-crumb");
const renderer=new THREE.WebGLRenderer({canvas:cv,antialias:true,alpha:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
const scene=new THREE.Scene(),cam=new THREE.PerspectiveCamera(38,1,.05,50);
let seed=7;const rand=()=>(seed=(seed*16807)%2147483647)/2147483647,gauss=()=>{let u=0;for(let i=0;i<4;i++)u+=rand();return (u-2)*1.73};
/* the brain as points */
const P=[],tag=[],lum=[];
function add(x,y,z,t,l){P.push(x,y,z);tag.push(t);lum.push(l)}
function hemi(s,n){for(let i=0;i<n;i++){let ux=gauss(),uy=gauss(),uz=gauss();const m=Math.hypot(ux,uy,uz)||1;ux/=m;uy/=m;uz/=m;
 const fold=1+.055*Math.sin(9*ux+3*uy)*Math.sin(7*uz+2*ux)+.04*Math.sin(13*uy+5*uz)+.03*Math.sin(17*uz+4*ux*uy);const inner=rand()<.45?Math.cbrt(rand()):1;
 let x=s*.34+ux*.5*fold*inner,y=uy*.74*fold*inner+.02,z=uz*1.1*fold*inner+.0;if(y<-.42)y=-.42+(y+.42)*.32;if(Math.abs(x)<.05&&y>-.1&&inner==1)x=s*.05+(x>0?.02:-.02);
 add(x,y,z,"",inner==1?1:.45)}}
hemi(1,9000);hemi(-1,9000);
for(const s of[1,-1])for(let i=0;i<500;i++){let ux=gauss(),uy=gauss(),uz=gauss();const m=Math.hypot(ux,uy,uz);add(s*.62+ux/m*.2,-.34+uy/m*.19,.1+uz/m*.5,"memory",1)}
for(let i=0;i<1100;i++){let ux=gauss(),uy=gauss(),uz=gauss();const m=Math.hypot(ux,uy,uz);const st=.82+.18*Math.sin(34*uy+6*ux);add(ux/m*.52*st,-.57+uy/m*.21*st,-.72+uz/m*.3*st,"shop",1)}
for(let i=0;i<500;i++){const t=rand(),a=rand()*6.283,r=.085+.02*gauss();add(Math.cos(a)*r,-.36-t*.62+Math.sin(a)*.0,-.02-t*.24+Math.sin(a)*r,"body",1)}
for(let i=0;i<260;i++){let ux=gauss(),uy=gauss(),uz=gauss();const m=Math.hypot(ux,uy,uz);add(ux/m*.16,.02+uy/m*.14,.05+uz/m*.2,"hq",1.3)}
const N=P.length/3,reg=[],colors=new Float32Array(N*3),Cc={};for(const k in C)Cc[k]=new THREE.Color(C[k]);
for(let i=0;i<N;i++){if(tag[i]){reg.push(tag[i]);continue}let best="hq",bd=9;for(const k of ids){for(const c of G[k].c){const d=Math.hypot(P[i*3]-c[0],P[i*3+1]-c[1],P[i*3+2]-c[2])*(k=="hq"?1.6:1);if(d<bd){bd=d;best=k}}}reg.push(best)}
const rid=new Float32Array(N),aux=new Float32Array(N*3);
for(let i=0;i<N;i++){const c=Cc[reg[i]];colors[i*3]=c.r;colors[i*3+1]=c.g;colors[i*3+2]=c.b;rid[i]=ids.indexOf(reg[i]);aux[i*3]=rand();aux[i*3+1]=lum[i]*(.75+.5*rand());aux[i*3+2]=.7+rand()*.9}
const geo=new THREE.BufferGeometry();geo.setAttribute("position",new THREE.BufferAttribute(new Float32Array(P),3));geo.setAttribute("col",new THREE.BufferAttribute(colors,3));geo.setAttribute("rid",new THREE.BufferAttribute(rid,1));geo.setAttribute("aux",new THREE.BufferAttribute(aux,3));
const spr=(()=>{const c=document.createElement("canvas");c.width=c.height=64;const g=c.getContext("2d"),r=g.createRadialGradient(32,32,0,32,32,32);r.addColorStop(0,"#fff");r.addColorStop(.35,"#fff8");r.addColorStop(1,"#0000");g.fillStyle=r;g.fillRect(0,0,64,64);return new THREE.CanvasTexture(c)})();
const U={uTime:{value:0},uSel:{value:0},uHov:{value:-1},uDim:{value:0},uScale:{value:.036*renderer.getPixelRatio()}};
const pts=new THREE.Points(geo,new THREE.ShaderMaterial({uniforms:U,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
vertexShader:`attribute vec3 col;attribute float rid;attribute vec3 aux;uniform float uTime,uSel,uHov,uDim,uScale;varying vec3 vC;
void main(){float tw=.7+.3*sin(uTime*(1.2+aux.x*2.)+aux.x*40.);float wave=pow(max(0.,sin(uTime*1.3-position.z*3.2+rid*.9)),10.);
float sel=(abs(rid-uSel)<.5)?1.:mix(1.,.1,uDim);float hov=(abs(rid-uHov)<.5)?1.6:1.;
vC=col*aux.y*tw*sel*hov*(.34+1.25*wave*(sel>.5?1.:0.));vec4 mv=modelViewMatrix*vec4(position,1.);
gl_PointSize=aux.z*uScale*(1.+.7*wave)*(260./-mv.z)*(sel>.5?1.:.6);gl_Position=projectionMatrix*mv;}`,
fragmentShader:`varying vec3 vC;void main(){float d=length(gl_PointCoord-.5);float a=smoothstep(.5,.05,d);gl_FragColor=vec4(vC,a);}`}));
const brain=new THREE.Group();brain.add(pts);scene.add(brain);
/* tracts: curves between regions, with pulses */
const tracts=[];function tract(a,b,bulge){const A=V(G[a].c[0]),B=V(G[b].c[0]);const mid=A.clone().add(B).multiplyScalar(.5);mid.y+=bulge[0];mid.x+=bulge[1]||0;const cu=new THREE.CatmullRomCurve3([A,mid,B]);
 const l=new THREE.Line(new THREE.BufferGeometry().setFromPoints(cu.getPoints(40)),new THREE.LineBasicMaterial({color:Cc[b=="hq"?a:b],transparent:true,opacity:.42,blending:THREE.AdditiveBlending}));brain.add(l);
 const pg=new THREE.BufferGeometry();pg.setAttribute("position",new THREE.BufferAttribute(new Float32Array(9),3));const pp=new THREE.Points(pg,new THREE.PointsMaterial({size:.085,map:spr,color:Cc[b=="hq"?a:b],transparent:true,depthWrite:false,blending:THREE.AdditiveBlending}));brain.add(pp);tracts.push({cu,pp,a,b,l,o:rand()})}
for(const k of ids)if(k!="hq")tract(k,"hq",[k=="fore"?.12:k=="senses"?.1:.06,0]);tract("fore","cons",[.05]);tract("memory","mirror",[.1]);tract("senses","mirror",[.2]);tract("shop","body",[-.04]);tract("cons","memory",[-.1]);

/* the surface: a solid cortex with a pattern of its own for each sector, smooth seams between sectors, and a cutaway */
const CEN=[],CID=[];ids.forEach((k,i)=>G[k].c.forEach(c=>{CEN.push(V(c));CID.push(i)}));while(CEN.length<10){CEN.push(V([9,9,9]));CID.push(0)}
const UC=ids.map(k=>{const c=Cc[k];return new THREE.Vector3(c.r*.92,c.g*.98,c.b*.88)});
const SU={uTime:{value:0},uSel:{value:0},uHov:{value:-1},uDim:{value:0},uCut:{value:1.2},uXray:{value:0},uCol:{value:UC},uCen:{value:CEN},uCid:{value:CID}};
const shellMat=new THREE.ShaderMaterial({uniforms:SU,transparent:true,side:THREE.DoubleSide,
vertexShader:`attribute float frc;attribute float fd;varying vec3 vP;varying vec3 vN;varying float vF;varying float vD;void main(){vP=position;vN=normalize(normalMatrix*normal);vF=frc;vD=fd;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
fragmentShader:`uniform float uTime,uSel,uHov,uDim,uCut,uXray;uniform vec3 uCol[8];uniform vec3 uCen[10];uniform float uCid[10];varying vec3 vP;varying vec3 vN;varying float vF;varying float vD;
vec3 rc(float r){vec3 c=uCol[0];for(int k=0;k<8;k++){if(abs(float(k)-r)<.5)c=uCol[k];}return c;}
float pat(float r,vec3 p){
 if(r<.5)return .5+.5*sin(length(p-vec3(0.,.02,.05))*95.);
 if(r<1.5)return smoothstep(.35,.65,fract(p.y*46.));
 if(r<2.5)return smoothstep(.35,.65,fract((p.x+p.y)*52.));
 if(r<3.5){vec3 q=fract(p*34.)-.5;return 1.-smoothstep(.16,.24,length(q.xy));}
 if(r<4.5)return max(smoothstep(.4,.6,fract((p.x+p.z)*44.)),smoothstep(.4,.6,fract((p.z-p.x)*44.)));
 if(r<5.5){vec2 g=abs(fract(p.xy*30.)-.5);return smoothstep(.38,.45,max(g.x,g.y));}
 if(r<6.5)return .5+.5*sin(p.y*150.+sin(p.x*20.)*2.);
 return smoothstep(.35,.65,fract(p.z*52.));}
void main(){if(vP.x>uCut)discard;
 float d1=9.,r1=0.;for(int k=0;k<10;k++){float d=distance(vP,uCen[k])*(uCid[k]<.5?1.7:1.);if(d<d1){d1=d;r1=uCid[k];}}
 float d2=9.;for(int k=0;k<10;k++){float d=distance(vP,uCen[k])*(uCid[k]<.5?1.7:1.);if(abs(uCid[k]-r1)>.5&&d<d2)d2=d;}
 float r=(vF>-.5)?vF:r1;float seam=(vF>-.5)?0.:1.-smoothstep(0.,.05,d2-d1);
 vec3 base=rc(r);float p=pat(r,vP);
 float sel=(abs(r-uSel)<.5)?1.:mix(1.,.14,uDim);float hov=(abs(r-uHov)<.5)?1.35:1.;
 vec3 n=normalize(vN);if(!gl_FrontFacing)n=-n;float L=.3+.7*max(0.,dot(n,normalize(vec3(.45,.75,.55))));float fres=pow(1.-max(0.,n.z),2.2);
 float groove=smoothstep(-.07,.025,vD);float gl=1.-.28*smoothstep(.42,.5,abs(fract(vD*26.)-.5)*2.);
 vec3 col=base*(.14+.52*L)*(.45+.55*groove)*gl*(.86+.22*p);col+=base*fres*.45;col+=base*seam*.8;
 float wave=pow(max(0.,sin(uTime*1.3-vP.z*3.2+r*.9)),10.);col+=base*wave*.45*(sel>.5?1.:0.);
 col*=sel*hov;if(!gl_FrontFacing){col=base*.10*(.55+.45*p)*sel+vec3(.012,.018,.012);}
 float scan=smoothstep(uCut-.035,uCut,vP.x)*(uCut<1.1?1.:0.);col+=vec3(.7,.95,.55)*scan*.75;
 gl_FragColor=vec4(col,mix(.985,.14,uXray));}`});
function fold(ux,uy,uz){return .05*Math.sin(9*ux+3*uy)*Math.sin(7*uz+2*ux)+.04*Math.sin(13*uy+5*uz)+.03*Math.sin(17*uz+4*ux*uy)+.02*Math.sin(23*ux+19*uz)*Math.sin(21*uy)}
function shellMesh(cx,cy,cz,rx,ry,rz,o){o=o||{};const g=new THREE.SphereGeometry(1,170,120),pa=g.attributes.position,n=pa.count,fr=new Float32Array(n).fill(o.force?ids.indexOf(o.force):-1),fd=new Float32Array(n),amp=o.amp==null?1:o.amp;
 for(let i=0;i<n;i++){let ux=pa.getX(i),uy=pa.getY(i),uz=pa.getZ(i);const f=o.smooth?0:fold(ux,uy,uz)*amp;let x=cx+ux*rx*(1+f),y=cy+uy*ry*(1+f),z=cz+uz*rz*(1+f);
  if(o.flat&&y<o.flat)y=o.flat+(y-o.flat)*.32;if(o.ridge){const k=.82+.18*Math.sin(34*uy+6*ux);x=cx+ux*rx*k;y=cy+uy*ry*k;z=cz+uz*rz*k}
  pa.setXYZ(i,x,y,z);fd[i]=o.ridge?(Math.sin(34*uy)*.04):f}
 g.setAttribute("frc",new THREE.BufferAttribute(fr,1));g.setAttribute("fd",new THREE.BufferAttribute(fd,1));g.computeVertexNormals();const m=new THREE.Mesh(g,o.mat||shellMat);if(!o.free)brain.add(m);return m}
const shells=[shellMesh(.34,.02,0,.5,.74,1.1,{flat:-.42}),shellMesh(-.34,.02,0,.5,.74,1.1,{flat:-.42}),
 shellMesh(.62,-.34,.1,.2,.19,.5,{force:"memory",smooth:1}),shellMesh(-.62,-.34,.1,.2,.19,.5,{force:"memory",smooth:1}),
 shellMesh(0,-.57,-.72,.52,.21,.3,{ridge:1,force:"shop"})];
{const g=new THREE.CylinderGeometry(.095,.075,.66,24,16,true),pa=g.attributes.position,n=pa.count,fr=new Float32Array(n).fill(ids.indexOf("body")),fd=new Float32Array(n);
 for(let i=0;i<n;i++){const y=pa.getY(i);pa.setXYZ(i,pa.getX(i),y,pa.getZ(i)-(.33-y)*.36)}g.setAttribute("frc",new THREE.BufferAttribute(fr,1));g.setAttribute("fd",new THREE.BufferAttribute(fd,1));g.computeVertexNormals();const m=new THREE.Mesh(g,shellMat);m.position.set(0,-.7,-.12);brain.add(m);shells.push(m)}
/* inside: fibre bundles (corpus callosum, hippocampal arcs) as many thin strands, and a bilobed thalamus that glows */
function bundle(pts,col,n,spread,op){const base=pts.map(V);for(let i=0;i<n;i++){const j=base.map(p=>p.clone().add(new THREE.Vector3(gauss()*spread,gauss()*spread*.6,gauss()*spread)));const cu=new THREE.CatmullRomCurve3(j);
 brain.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(cu.getPoints(48)),new THREE.LineBasicMaterial({color:col,transparent:true,opacity:op,blending:THREE.AdditiveBlending,depthWrite:false})))}}
bundle([[0,.16,.55],[0,.3,.2],[0,.32,-.2],[0,.18,-.55]],Cc.hq,34,.012,.22);bundle([[.6,-.22,.5],[.7,-.3,.15],[.6,-.34,-.2],[.4,-.2,-.4]],Cc.memory,22,.012,.3);bundle([[-.6,-.22,.5],[-.7,-.3,.15],[-.6,-.34,-.2],[-.4,-.2,-.4]],Cc.memory,22,.012,.3);
const glow=new THREE.ShaderMaterial({uniforms:{uTime:SU.uTime,uC:{value:new THREE.Vector3(Cc.hq.r,Cc.hq.g,Cc.hq.b)}},transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,depthTest:false,side:THREE.DoubleSide,
 vertexShader:`varying vec3 vN;varying vec3 vP;void main(){vN=normalize(normalMatrix*normal);vP=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
 fragmentShader:`uniform float uTime;uniform vec3 uC;varying vec3 vN;varying vec3 vP;void main(){float f=pow(1.-abs(dot(normalize(vN),vec3(0.,0.,1.))),1.6);float v=.55+.45*sin(uTime*2.2+vP.y*40.+sin(vP.x*30.)*2.);gl_FragColor=vec4(uC*(.5+.8*f)*(.7+.3*v),.65+.35*f);}`});
const core=new THREE.Group();core.renderOrder=10;for(const sx of[1,-1]){const m=shellMesh(sx*.07,.0,.0,.14,.11,.17,{mat:glow,amp:1.5,free:1,flat:-9});core.add(m)}core.position.copy(V(G.hq.c[0]));brain.add(core);
/* picking spheres, comps, state */
const pick=[];for(const k of ids)G[k].c.forEach(c=>{const m=new THREE.Mesh(new THREE.SphereGeometry(k=="hq"?.2:.3,12,12),new THREE.MeshBasicMaterial({visible:false}));m.position.copy(V(c));m.userData={id:k};brain.add(m);pick.push(m)});
const st={r:null,c:null,hover:null};const rings=[];
function ring(pos,col){const m=new THREE.Mesh(new THREE.RingGeometry(.05,.065,64),new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:1,blending:THREE.AdditiveBlending,depthWrite:false,side:THREE.DoubleSide}));m.position.copy(pos);m.userData.t0=T;brain.add(m);rings.push(m)}let compMesh=[],compLines=[],compLabs=[];
const sph={th:.85,ph:1.3,d:3.4,tx:0,ty:-.05,tz:0},goal={th:.85,ph:1.3,d:3.4,tx:0,ty:-.05,tz:0};let idle=0;
function shade(){SU.uSel.value=st.r?ids.indexOf(st.r):SU.uSel.value;SU.uHov.value=st.hover?ids.indexOf(st.hover):-1;U.uSel.value=st.r?ids.indexOf(st.r):U.uSel.value;U.uHov.value=st.hover?ids.indexOf(st.hover):-1}
function shadeOld(){for(let i=0;i<N;i++){const k=reg[i],on=!st.r||st.r==k,hot=st.hover==k||st.r==k;const b=(on?(hot?1.15:.75):.12)*lum[i]*(.82+.18*Math.sin(i*1.7));const c=Cc[k];colors[i*3]=c.r*b;colors[i*3+1]=c.g*b;colors[i*3+2]=c.b*b}geo.attributes.color.needsUpdate=true}
const lab={};ids.forEach(k=>{const s=S.find(x=>x.id==k),d=document.createElement("div");d.className="lab";d.style.color=C[k];d.innerHTML=`${s.n}<small>${s.t}</small>`;labs.appendChild(d);lab[k]=d});
function clearComps(){compMesh.forEach(m=>brain.remove(m));compLines.forEach(m=>brain.remove(m));compLabs.forEach(m=>m.remove());compMesh=[];compLines=[];compLabs=[]}
function setComps(r){clearComps();if(!r)return;const s=S.find(x=>x.id==r),sign=Math.sin(sph.th)>=0?1:-1;const cs=G[r].c;const base=V(cs.find(c=>Math.sign(c[0])==sign)||cs[0]);
 const f=new THREE.Vector3().subVectors(cam.position,new THREE.Vector3(goal.tx,goal.ty,goal.tz)).normalize(),right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),f).normalize(),up=new THREE.Vector3().crossVectors(f,right).normalize();
 const n=s.comps.length;s.comps.forEach((c,i)=>{const a=-1.57+i/n*6.283,off=right.clone().multiplyScalar(Math.cos(a)*.62).add(up.clone().multiplyScalar(Math.sin(a)*.5)).add(f.clone().multiplyScalar(.15));const pos=base.clone().add(off);
  const col=c[2]?(/shadow|collect|waiting/.test(c[3])?new THREE.Color("#e0b04f"):Cc[r]):new THREE.Color("#4d5a45");const m=new THREE.Sprite(new THREE.SpriteMaterial({map:spr,color:col,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending}));m.position.copy(pos);m.scale.setScalar(.001);m.userData={comp:c[0],t0:T+i*.08,sel:st.c==c[0]};brain.add(m);compMesh.push(m);
  const core2=new THREE.Mesh(new THREE.SphereGeometry(.014,10,10),new THREE.MeshBasicMaterial({color:0xffffff}));core2.position.copy(pos);brain.add(core2);compLines.push(core2);
  const halo=new THREE.Mesh(new THREE.SphereGeometry(.13,12,12),new THREE.MeshBasicMaterial({visible:false}));halo.position.copy(pos);halo.userData={comp:c[0]};brain.add(halo);compMesh.push(halo);
  const ln=new THREE.Line(new THREE.BufferGeometry().setFromPoints([base,pos]),new THREE.LineBasicMaterial({color:Cc[r],transparent:true,opacity:.5}));brain.add(ln);compLines.push(ln);
  const d=document.createElement("div");d.className="cl";d.innerHTML=`${c[1]}<br><span style="color:#9aa790;font-size:10.5px">${c[2]?c[3].slice(0,24):"off"}</span>`;labs.appendChild(d);compLabs.push(d);d._p=pos}) }
function focus(r,instant){const sign=Math.sin(sph.th)>=0?1:-1;if(r){const cs=G[r].c,c=cs.find(c=>Math.sign(c[0])==sign)||cs[0];goal.tx=c[0]*.6;goal.ty=c[1];goal.tz=c[2];goal.d=r=="hq"?1.9:2.1}else{goal.tx=0;goal.ty=-.05;goal.tz=0;goal.d=3.4}if(instant)Object.assign(sph,goal)}
function legend(){host.querySelector("#b3-lg").innerHTML=[["working","#9ccf5e"],["shadow / learning","#e0b04f"],["off","#4d5a45"]].map(([a,b])=>`<span style="color:${b}">●</span> ${a}`).join("&nbsp;&nbsp;")}
function go(r,c,instant){st.r=r||null;st.c=c||null;focus(st.r,instant);if(instant){Object.assign(sph,goal);U.uDim.value=st.r?1:0}shade();setComps(st.r);if(!instant&&st.r)ring(V(G[st.r].c[0]),Cc[st.r]);
 host.querySelector("#b3-back").style.display=st.r?"block":"none";const s=st.r&&S.find(x=>x.id==st.r);crumb.innerHTML=s?`<a data-go="">Brain</a> › ${s.n}`+(c?` › ${s.comps.find(x=>x[0]==c)[1]}`:""):"whole brain";
 side.innerHTML=!s?home():c?panel(s,c):secinfo(s)}
host.querySelector("#b3-back").onclick=()=>go();
const sparkUnused=id=>{let x=0;for(const ch of id)x=(x*31+ch.charCodeAt(0))%9973;let d="",y=18;for(let i=0;i<24;i++){x=(x*7919+13)%9973;y=Math.max(4,Math.min(34,y+(x/9973-.5)*14));d+=(i?"L":"M")+i*11+" "+y.toFixed(1)}return `<svg viewBox="0 0 253 38" style="width:100%;height:42px"><path d="${d}" fill="none" stroke="currentColor" stroke-width="2"/></svg>`};
const SWATCH=(()=>{const o={};const mk=(id,bg)=>o[id]=`background:${bg}`;const c=k=>C[k];mk("hq",`repeating-radial-gradient(circle,${c("hq")} 0 2px,#1b2417 2px 5px)`);mk("fore",`repeating-linear-gradient(0deg,${c("fore")} 0 2px,#1b2417 2px 5px)`);mk("cons",`repeating-linear-gradient(45deg,${c("cons")} 0 2px,#1b2417 2px 5px)`);mk("memory",`radial-gradient(${c("memory")} 35%,#1b2417 38%) 0 0/6px 6px`);mk("mirror",`repeating-linear-gradient(45deg,${c("mirror")} 0 1px,transparent 1px 5px),repeating-linear-gradient(-45deg,${c("mirror")} 0 1px,#1b2417 1px 5px)`);mk("senses",`linear-gradient(${c("senses")} 1px,transparent 1px) 0 0/6px 6px,linear-gradient(90deg,${c("senses")} 1px,#1b2417 1px) 0 0/6px 6px`);mk("shop",`repeating-linear-gradient(0deg,${c("shop")} 0 1px,#1b2417 1px 3px)`);mk("body",`repeating-linear-gradient(90deg,${c("body")} 0 3px,#1b2417 3px 6px)`);return o})();
function home(){return `<h2>The whole brain</h2><div class=m><span>Brain</span><span>${DATA.on?"on":"off"}</span></div><div class=m><span>Parts on</span><span>${DATA.parts_on} of ${DATA.parts_total}</span></div><div class=m><span>Log</span><span>${DATA.records} records</span></div>${DATA.mode?`<div class=m><span>Mode</span><span>${DATA.mode}</span></div>`:""}
<h2>Regions and what they keep</h2>${S.map(s=>`<div class=m style="cursor:pointer" data-go="${s.id}"><span><i class=sw8 style="${SWATCH[s.id]}"></i>${s.n}</span><span style="font-size:12px;color:var(--mute)">${G[s.id].why.split(":")[0]}</span></div>`).join("")}
<div style="color:var(--mute);margin-top:14px;font-size:12.5px">Turn the model, click a region, then a part.</div>`}
function secinfo(s){const on=s.comps.filter(c=>c[2]).length;return `<h2>${s.n}</h2><div style="font-size:17px;font-weight:600">${s.t}</div><div style="color:var(--mute);font-size:12.5px;margin-top:4px">like the ${G[s.id].why}</div><div class=m style="margin-top:10px"><span>Parts</span><span>${on} on · ${s.comps.length-on} off</span></div>
${s.comps.map(c=>`<div class=m style="cursor:pointer" data-go="${s.id}" data-c="${c[0]}"><span>${c[1]}</span><span>${c[2]?c[3]:"off"}</span></div>`).join("")}<div style="color:var(--mute);margin-top:14px;font-size:12.5px">Click a glowing point in the model, or a row here, to monitor that part.</div>`}
function panel(s,id){const c=s.comps.find(x=>x[0]==id),live=c[2];return `<h2>${s.n} › part</h2><div style="font-size:19px;font-weight:650">${c[1]}</div><div style="margin:6px 0 10px"><span class=chip style="color:${live?C[s.id]:"#8d9a84"}">${live?c[3]:"off"}</span></div><div style="color:var(--mute);font-size:13px">${c[6]}</div>
<div class=sw><div><b>${c[1]}</b><div style="font-size:11.5px;color:var(--mute)">${c[5]}</div></div><div class="tog ${live?"":"off"}" data-key="${c[5]}" data-on="${live?1:0}" title="${/^mind\.[a-z_.]+$/.test(c[5])?"switch it":"always with Brain"}"></div></div><h2>Now</h2>${c[4].map(m=>`<div class=m><span>${m[0]}</span><span>${m[1]}</span></div>`).join("")}
<div style="color:var(--mute);margin-top:14px;font-size:12.5px">History, settings and why-did-it for each part come with the Brain console.</div>`}
/* interaction */
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2();let down=null,drag=false;
function hit(ev,list){const r=cv.getBoundingClientRect();mouse.set((ev.clientX-r.left)/r.width*2-1,-(ev.clientY-r.top)/r.height*2+1);ray.setFromCamera(mouse,cam);const h=ray.intersectObjects(list,false);return h.length?h[0].object.userData:null}
cv.addEventListener("pointerdown",e=>{down={x:e.clientX,y:e.clientY,th:goal.th,ph:goal.ph};drag=false;idle=0;cv.setPointerCapture(e.pointerId)});
cv.addEventListener("pointermove",e=>{if(down){const dx=e.clientX-down.x,dy=e.clientY-down.y;if(Math.hypot(dx,dy)>4)drag=true;if(drag){goal.th=down.th-dx*.006;goal.ph=Math.max(.35,Math.min(2.7,down.ph-dy*.006))}return}
 const h=hit(e,pick);const k=h&&h.id;if(k!=st.hover){st.hover=k;shade();cv.style.cursor=k?"pointer":"grab"}});
cv.addEventListener("pointerup",e=>{if(!drag){const hc=hit(e,compMesh);if(hc&&hc.comp){go(st.r,hc.comp);down=null;return}const h=hit(e,pick);if(h&&h.id!=st.r)go(h.id);else if(!h&&st.r&&!hc)go()}down=null});
cv.addEventListener("wheel",e=>{e.preventDefault();goal.d=Math.max(1.3,Math.min(6,goal.d*(1+e.deltaY*.0012)));idle=0},{passive:false});
function size(){const stage=host.querySelector("#b3-stage")||cv.parentElement;const r=stage.getBoundingClientRect();if(!r.width||!r.height)return;renderer.setSize(r.width,r.height,false);cam.aspect=r.width/r.height;cam.updateProjectionMatrix()}const ro=new ResizeObserver(size);ro.observe(host);
function place(el,v,dy){const p=v.clone();brain.localToWorld(p);p.project(cam);const r=cv.getBoundingClientRect();const vis=p.z<1;el.style.display=vis?"block":"none";el.style.left=((p.x+1)/2*r.width)+"px";el.style.top=((1-p.y)/2*r.height+(dy||0))+"px"}
const VIEW={solid:{cut:1.2,x:0},cut:{cut:-.02,x:0},xray:{cut:1.2,x:1}};let view="solid";function setView(v){view=v;host.querySelectorAll("#b3-seg button").forEach(x=>x.classList.toggle("on",x.dataset.m==v))}
host.querySelectorAll("#b3-seg button").forEach(b=>b.onclick=()=>setView(b.dataset.m));
let T=0,dead=false;function frame(){if(dead)return;T+=.016;idle+=.016;if(!down)goal.th+=.0022;for(const k of["th","ph","d","tx","ty","tz"])sph[k]+=(goal[k]-sph[k])*.09;
 const t=new THREE.Vector3(sph.tx,sph.ty,sph.tz);cam.position.set(t.x+sph.d*Math.sin(sph.ph)*Math.sin(sph.th),t.y+sph.d*Math.cos(sph.ph),t.z+sph.d*Math.sin(sph.ph)*Math.cos(sph.th));cam.lookAt(t);
 tracts.forEach((tr,i)=>{const a=tr.pp.geometry.attributes.position;for(let j=0;j<3;j++){const u=(T*.12+tr.o+j/3)%1,p=tr.cu.getPoint(u);a.setXYZ(j,p.x,p.y,p.z)}a.needsUpdate=true;const on=!st.r||st.r==tr.a||st.r==tr.b;tr.pp.material.opacity=on?1:.1;tr.l.material.opacity=on?.42:.05});
 core.scale.setScalar(1+.12*Math.sin(T*2.4));U.uTime.value=T;SU.uTime.value=T;SU.uDim.value=U.uDim.value;const vm=VIEW[view];SU.uCut.value+=(((st.r&&view=="cut")?1.2:vm.cut)-SU.uCut.value)*.035;SU.uXray.value+=(vm.x-SU.uXray.value)*.08;shellMat.depthWrite=vm.x<.5;U.uDim.value+=((st.r?1:0)-U.uDim.value)*.08;brain.scale.setScalar(1+.012*Math.sin(T*.9));
 for(const m of compMesh){if(m.isSprite){const u=Math.min(1,Math.max(0,(T-m.userData.t0)/.55)),e=1+2.7*Math.pow(u-1,3)+1.7*Math.pow(u-1,2);m.scale.setScalar(Math.max(.001,e*(m.userData.sel?.34:.24)*(1+.1*Math.sin(T*3+m.userData.t0*5))))}}
 for(let i=rings.length-1;i>=0;i--){const m=rings[i],u=(T-m.userData.t0)/1.3;if(u>=1){brain.remove(m);rings.splice(i,1);continue}m.scale.setScalar(1+u*9);m.material.opacity=1-u;m.lookAt(cam.position)}
 ids.forEach(k=>{const c=V(G[k].c[0]);const l=lab[k];place(l,c.clone().add(new THREE.Vector3(0,k=="hq"?-.16:.16,0)));l.classList.toggle("hot",st.hover==k||st.r==k);l.classList.toggle("dim",!!st.r&&st.r!=k)});
 compLabs.forEach(d=>place(d,d._p,10));renderer.render(scene,cam);if(!dead)requestAnimationFrame(frame)}
size();legend();go(null,null,true);setTimeout(()=>setView("cut"),1400);frame();
function refreshSide(){side.innerHTML=!st.r?home():st.c?panel(S.find(x=>x.id==st.r),st.c):secinfo(S.find(x=>x.id==st.r))}
const onNav=e=>{const t=e.target.closest("[data-go]");if(t){go(t.dataset.go||undefined,t.dataset.c||undefined);return}
 const g=e.target.closest(".tog");if(g&&OPTS.toggle&&/^mind\.[a-z_.]+$/.test(g.dataset.key||"")){const on=g.dataset.on!="1";OPTS.toggle(g.dataset.key,on).then(ok=>{if(ok){const s=S.find(x=>x.id==st.r),c=s&&s.comps.find(x=>x[0]==st.c);if(c){c[2]=on?1:0;c[3]=on?"on":"off";refreshSide();setComps(st.r)}}})}};
const tab=host.querySelector("#b3-tab");
if(tab){tab.onclick=()=>host.classList.toggle("side-open");tab.onmouseenter=()=>host.classList.add("side-open");}
host.addEventListener("mouseleave",()=>host.classList.remove("side-open"));
side.addEventListener("click",onNav);crumb.addEventListener("click",onNav);
return {update(d){DATA=d;S.length=0;d.islands.forEach(x=>S.push(x));refreshSide()},stop(){dead=true;ro.disconnect();renderer.dispose();clearComps();host.innerHTML=""}};

}})();
