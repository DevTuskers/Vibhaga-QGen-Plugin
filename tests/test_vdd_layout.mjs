import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { similarity, validateMatrix, mapPoint, compose, parsePath, transformPath, transformDocument, transformAnchors, createMeasurer, layout, writeOutputs, loadOutputs, loadLocalFonts, normalizationIntegrity, measureUnion, fitMeasuredUnion, validateCommonFrame, documentDigest, clipHalfPlanes, validateViewportCertificate, writeCommonFrameOutputs, METADATA_CONTRACT } from '../tools/vdd-layout.mjs';

const doc = (elements) => ({schema:'vibhaga.diagram',schemaVersion:1,canvas:{width:300,height:240},defaults:{strokeWidth:2,fontSize:18},elements,a11y:{title:'Synthetic orientation fixture',description:'Synthetic finite artwork only, unrelated to any paper or recovery figure.'}});
const near = (a,b,eps=1e-9) => assert.ok(Math.abs(a-b)<eps,`${a} != ${b}`);
const nearPoint = (a,b) => a.forEach((v,i)=>near(v,b[i]));
const length = (a,b) => Math.hypot(a[0]-b[0],a[1]-b[1]);
const signedArea = (a,b,c) => ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2;
const roundedMutant = source => {
  const document=structuredClone(source),unroundedCoordinates=[],round=v=>{unroundedCoordinates.push(v);return Math.round(v);};
  for(const e of document.elements) {
    if(e.points)e.points=e.points.map(p=>p.map(round));
    if(e.at)e.at=e.at.map(round);
    if(e.center)e.center=e.center.map(round);
    if(e.d)e.d=parsePath(e.d).map(([c,a])=>[c,...a.map((v,k)=>c==='A'&&k<5?v:round(v))].join(' ')).join(' ');
  }
  return {document,unroundedCoordinates};
};
const config = (angleDegrees=0) => ({angleDegrees,pivot:[150,120],reference:'synthetic explicit reference, no source inference',framing:{mode:'bounded-artwork',declaration:'Finite synthetic artwork only; no unbounded regions or plot window.'},canvas:[400,320],padding:32});

for(const angleDegrees of [-4.5,3.25,90,180,270]) test(`similarity ${angleDegrees}: lengths, ratios, area sign, orthogonality, collinearity and inverse`,()=>{
  const m=similarity({angleDegrees,pivot:[23,-19],scale:1.7,translation:[-80,210]});
  const A=[2,3],B=[22,3],C=[22,43],D=[12,3];
  const [a,b,c,d]=[A,B,C,D].map(p=>mapPoint(m,p));
  near(length(a,b)/length(A,B),1.7); near(length(a,b)/length(b,c),.5);
  near(signedArea(a,b,c),signedArea(A,B,C)*1.7**2);
  near((a[0]-b[0])*(c[0]-b[0])+(a[1]-b[1])*(c[1]-b[1]),0);
  near(signedArea(a,b,d),0); nearPoint(d,[(a[0]+b[0])/2,(a[1]+b[1])/2]);
  const s2=m[0]**2+m[1]**2, inv=[m[0]/s2,-m[1]/s2,m[1]/s2,m[0]/s2,0,0];
  [inv[4],inv[5]]=mapPoint(inv,[-m[4],-m[5]]); nearPoint(mapPoint(inv,a),A);
  nearPoint(mapPoint(compose(inv,m),C),C);
});

test('supported geometry, real label bindings, uniform styles, rect baking and circular/elliptical arc parameters',()=>{
  const m=similarity({angleDegrees:90,pivot:[0,0],scale:2,translation:[100,100]});
  const original=doc([
    {id:'l',type:'line',points:[[0,0],[20,0]],stroke:{width:3}},
    {id:'pl',type:'polyline',points:[[0,0],[20,0],[20,10]]},
    {id:'pg',type:'polygon',points:[[0,0],[20,0],[20,10]],fill:{color:'#eee'}},
    {id:'a',type:'arrow',points:[[0,0],[20,0]],head:'both',headSize:12},
    {id:'p',type:'point',at:[20,10],r:4,label:'P',labelOffset:[8,-12]},
    {id:'t',type:'text',at:[35,10],value:'upright',fontSize:20},
    {id:'m',type:'math',at:[-10,0],latex:'x^2'},
    {id:'c',type:'circle',center:[10,10],r:8},
    {id:'r',type:'rect',x:0,y:0,width:40,height:20,rx:6},
    {id:'path',type:'path',d:'M 0 0 L 10 0 Q 12 0 15 5 C 15 6 17 8 20 10 A 10 10 20 0 1 40 10 Z',fill:{color:'#ddd'}},
  ]);
  original.meta={anchors:{P:[20,10]},source:'synthetic'};
  const before=structuredClone(original),out=transformDocument(original,m);
  assert.deepEqual(original,before); assert.equal(out.defaults.fontSize,36); assert.equal(out.defaults.strokeWidth,4);
  nearPoint(out.elements[0].points[1],[100,140]); assert.equal(out.elements[0].stroke.width,6);
  assert.equal(out.elements[3].headSize,24); nearPoint(out.elements[4].labelOffset,[24,16]);
  assert.equal(out.elements[4].r,8); assert.equal(out.elements[5].fontSize,40);
  nearPoint(out.elements[5].at,[80,170]); assert.ok(out.elements.every(e=>!e.rotation));
  nearPoint(out.elements[7].center,[80,120]); assert.equal(out.elements[7].r,16);
  assert.equal(out.elements[8].type,'path'); assert.equal(parsePath(out.elements[8].d).filter(([c])=>c==='A').length,4);
  const arc=parsePath(out.elements[9].d).find(([c])=>c==='A')[1];
  assert.deepEqual(arc.slice(0,5),[20,20,110,0,1]); nearPoint(arc.slice(5),[80,180]);
  nearPoint(out.meta.anchors.P,[80,140]); assert.equal(out.meta.inputMetadata.source,'synthetic');assert.equal(out.meta.anchorsFrame,'STORED_OUTPUT_CANVAS');
  assert.deepEqual(transformAnchors(original.meta.anchors,m),out.meta.anchors);
});

test('metadata frames are namespaced as input provenance without losing unrelated or nested metadata',()=>{
  const source=doc([{id:'p',type:'point',at:[20,10],label:'P'}]);
  source.meta={anchors:{P:[20,10]},anchorsFrame:'INPUT_VDD_CANVAS',sourceFrame:'caller-specific-input-frame',unrelated:{author:'synthetic',tags:['keep',null,false],version:7},inputMetadata:{existing:'must not flatten'}};
  const before=structuredClone(source),matrix=similarity({angleDegrees:90,pivot:[0,0],translation:[100,100]});
  const output=transformDocument(source,matrix),geometryOnly=transformDocument(doc(source.elements),matrix);
  assert.deepEqual(output.elements,geometryOnly.elements);assert.deepEqual(source,before);
  nearPoint(output.meta.anchors.P,[90,120]);assert.equal(output.meta.anchorsFrame,'STORED_OUTPUT_CANVAS');
  assert.equal(output.meta.inputMetadataRole,'INPUT_PROVENANCE');assert.equal(output.meta.inputMetadataPresent,true);
  assert.deepEqual(output.meta.inputMetadata,before.meta);assert.equal(output.meta.inputMetadata.anchorsFrame,'INPUT_VDD_CANVAS');
  assert.equal(Object.hasOwn(output.meta,'sourceFrame'),false);assert.equal(Object.hasOwn(output.meta,'unrelated'),false);
  const twice=transformDocument(output,similarity({angleDegrees:0,pivot:[0,0],translation:[5,6]}));
  assert.deepEqual(twice.meta.inputMetadata,output.meta);assert.deepEqual(twice.meta.inputMetadata.inputMetadata,before.meta);
  assert.equal(geometryOnly.meta.inputMetadataPresent,false);assert.deepEqual(geometryOnly.meta.inputMetadata,{});
  output.meta.inputMetadata.unrelated.tags.push('copy-only');assert.deepEqual(source,before);
});

test('off-center translated copies produce identical pivot-relative geometry',()=>{
  const d=doc([{id:'a',type:'arrow',points:[[40,60],[80,90]]},{id:'t',type:'text',at:[90,60],value:'x'}]);
  const move=similarity({angleDegrees:0,pivot:[0,0],translation:[1700,-600]});
  const shifted=transformDocument(d,move), a=similarity({angleDegrees:-7,pivot:[60,70]}), b=similarity({angleDegrees:-7,pivot:[1760,-530],translation:[-1700,600]});
  const x=transformDocument(d,a),y=transformDocument(shifted,b);
  x.elements[0].points.forEach((p,i)=>nearPoint(p,y.elements[0].points[i])); nearPoint(x.elements[1].at,y.elements[1].at);
});

test('strict path lexer accepts numeric exponent and repeated moveto pairs; malformed tails fail',()=>{
  assert.equal(parsePath('M 1e1,2 .5,-4 L 4 5 Z')[1][0],'L');
  for(const d of ['M 0 0 l 10 10','M 0 0 H 3','M 0','M 0 0 Q 2 3','M 0 0 Z 3 4','M 0 0 A 2 2 0 2 1 4 4','M 0 0 A -2 2 0 0 1 4 4','M 1e309 0','M 0 0 junk','M 0 0 L']) assert.throws(()=>parsePath(d),/path|empty/);
  assert.match(transformPath('M 0 0 A 8 4 30 1 0 20 0 Z',similarity({angleDegrees:90,pivot:[0,0]})),/A 8 4 120 1 0/);
});

test('unsupported types, extension geometry, nonzero rotations and invalid transforms fail closed',()=>{
  const identity=similarity({angleDegrees:0,pivot:[0,0]});
  for(const type of ['ellipse','arc','angleMark','tickMark','parallelMark','plot','image','group']) assert.throws(()=>transformDocument(doc([{id:'bad',type}]),identity),/unsupported type/);
  for(const rotation of [1,90,180,270,360]) assert.throws(()=>transformDocument(doc([{id:'r',type:'line',points:[[0,0],[1,1]],rotation}]),identity),/nonzero element rotation/);
  assert.throws(()=>transformDocument(doc([{id:'bad',type:'line',points:[[0,0],[1,1]],transform:'rotate(2)'}]),identity),/unsupported field/);
  for(const scale of [0,-1,Infinity,NaN]) assert.throws(()=>similarity({angleDegrees:0,pivot:[0,0],scale}));
  for(const m of [[1,0,0,-1,0,0],[1,0,0,2,0,0],[1,0,1,1,0,0],[0,0,0,0,0,0],[1,0,0,1,Infinity,0]]) assert.throws(()=>validateMatrix(m));
  assert.throws(()=>similarity({angleDegrees:NaN,pivot:[0,0]}),/finite/);
  assert.throws(()=>transformDocument(doc([{id:'bad',type:'text',at:[Infinity,0],value:'x'}]),identity),/nonfinite/);
});

test('new-file-only writer preserves raw bytes and refuses rejected output/collisions',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vdd-layout-test-'));
  try {
    const prefix=path.join(dir,'new'),raw=Buffer.from('{ "A" : [1, 2] }\n');
    const input={...doc([{id:'p',type:'point',at:[1,2]}]),meta:{anchors:{A:[1,2]},anchorsFrame:'INPUT_VDD_CANVAS',unrelated:{keep:['all',7]}}};
    const result={document:transformDocument(input,similarity({angleDegrees:0,pivot:[0,0]})),anchors:{A:[1,2]},provenance:{approved:true,failures:[]}};
    const files=writeOutputs(prefix,raw,result); assert.equal(files.length,5); assert.deepEqual(fs.readFileSync(files[2]),raw);
    assert.throws(()=>writeOutputs(prefix,raw,result),/NEW file/);
    assert.throws(()=>writeOutputs(path.join(dir,'refused'),raw,{...result,provenance:{approved:false,failures:['normalize failure']}}),/layout refused/);
    assert.equal(fs.readdirSync(dir).length,5);
    const loaded=loadOutputs(prefix);assert.deepEqual(loaded.rawAnchors,raw);assert.equal(loaded.rawAnchorsFrame,'INPUT_VDD_CANVAS');
    assert.deepEqual(loaded.document.meta.inputMetadata,input.meta);assert.equal(loaded.document.meta.anchorsFrame,'STORED_OUTPUT_CANVAS');
    assert.deepEqual(loaded.provenance.metadataContract,METADATA_CONTRACT);assert.deepEqual(loaded.manifest.metadataContract,METADATA_CONTRACT);
    assert.match(METADATA_CONTRACT.rawAnchorsMeaning,/not automatically raw PDF/);
    const legacy=structuredClone(loaded.manifest);delete legacy.metadataContract;fs.writeFileSync(files[4],JSON.stringify(legacy));
    assert.throws(()=>loadOutputs(prefix),/metadata frame contract/);fs.writeFileSync(files[4],JSON.stringify(loaded.manifest));
    const stale=structuredClone(result);stale.document.meta.anchorsFrame='INPUT_VDD_CANVAS';
    assert.throws(()=>writeOutputs(path.join(dir,'stale'),raw,stale),/anchor frame/);
    const bytes=JSON.stringify(stale.document),manifest=JSON.parse(fs.readFileSync(files[4],'utf8')),entry=manifest.files.find(e=>e.role==='document');
    fs.writeFileSync(files[0],bytes);entry.bytes=Buffer.byteLength(bytes);entry.sha256=createHash('sha256').update(bytes).digest('hex');fs.writeFileSync(files[4],JSON.stringify(manifest));
    assert.throws(()=>loadOutputs(prefix),/anchor frame/);
    fs.appendFileSync(files[0],' ');
    assert.throws(()=>loadOutputs(prefix),/tampered/);
  } finally { fs.rmSync(dir,{recursive:true,force:true}); }
});

test('normalization checks bounded quantization, critical incidence, topology, flags and CSS error separately',()=>{
  const round=d=>{const n=structuredClone(d);for(const e of n.elements){if(e.points)e.points=e.points.map(p=>p.map(Math.round));if(e.at)e.at=e.at.map(Math.round);if(e.center)e.center=e.center.map(Math.round);}return n;};
  const simple=doc([{id:'p',type:'polygon',points:[[20.1,20.4],[180.4,20.1],[90.2,180.3]]}]);
  const n=round(simple),ok=normalizationIntegrity(simple,n);assert.equal(ok.modelValid,true);assert.deepEqual(ok.failures,[]);
  assert.ok(ok.maximumAbsoluteRoundingPerAxis.every(v=>v<=.5));assert.equal(ok.screen.length,3);
  const wrong=structuredClone(n);wrong.elements[0].points[0][0]+=3;assert.equal(normalizationIntegrity(simple,wrong).modelValid,false);
  assert.ok(normalizationIntegrity(simple,n,{maxCssError:.01}).failures.some(f=>f.includes('screen budget')));
  for(const type of ['polygon','arrow']) {
    const thin=doc([{id:'thin',type,points:type==='polygon'?[[.1,.1],[.4,.2],[10,10]]:[[.1,.1],[.4,.2]]}]);
    assert.ok(normalizationIntegrity(thin,round(thin)).failures.some(f=>f.includes('collapsed')));
  }
  const collinear=doc([{id:'a',type:'point',at:[.1,.2]},{id:'b',type:'point',at:[.6,.9]},{id:'c',type:'point',at:[1.1,1.6]}]);
  assert.ok(normalizationIntegrity(collinear,round(collinear),{critical:[{kind:'collinear',points:[['a',0],['b',0],['c',0]]}]}).failures.includes('critical collinear incidence regression'));
  const tangent=doc([{id:'c',type:'circle',center:[.2,.4],r:.8},{id:'l',type:'line',points:[[-10,1.2],[10,1.2]]}]);
  assert.ok(normalizationIntegrity(tangent,round(tangent),{critical:[{kind:'tangent',circle:'c',points:[['l',0],['l',1]]}]}).failures.includes('critical tangent incidence regression'));
  const curve=doc([{id:'a',type:'path',d:'M 0 0 A 10 10 0 0 1 20 0'}]),bad=structuredClone(curve);bad.elements[0].d='M 0 0 A 10 10 0 1 0 20 0';assert.throws(()=>normalizationIntegrity(curve,bad),/arc flags/);
});

test('precision-preserving translations and observed legacy rounding are distinct fail-closed models',()=>{
  const source=doc([{id:'triangle',type:'polygon',points:[[20.1,20.4],[180.4,20.1],[90.2,180.3]]}]);
  for(const translation of [[0,0],[.125,-.25],[37.123,-61.789]]) {
    const moved=transformDocument(source,similarity({angleDegrees:0,pivot:[0,0],translation}));
    for(const options of [{},{unroundedCoordinates:[]}]) {
      const result=normalizationIntegrity(source,moved,options);
      assert.equal(result.modelValid,true);assert.deepEqual(result.failures,[]);nearPoint(result.translation,translation);
      assert.equal(result.model,translation[0]===0?'unchanged':'common-translation');
      assert.ok(result.maximumAbsoluteRoundingWorld<1e-12);
    }
    const rounded=roundedMutant(moved),legacy=normalizationIntegrity(source,rounded.document,{unroundedCoordinates:rounded.unroundedCoordinates});
    assert.equal(legacy.modelValid,true);assert.equal(legacy.model,'common-translation-then-Math.round');assert.deepEqual(legacy.failures,[]);
    assert.equal(normalizationIntegrity(source,rounded.document,{unroundedCoordinates:[]}).modelValid,false);
    for(const audit of [rounded.unroundedCoordinates.slice(1),[...rounded.unroundedCoordinates,0],rounded.unroundedCoordinates.map((v,i)=>i===2?v+.01:v)])assert.equal(normalizationIntegrity(source,rounded.document,{unroundedCoordinates:audit}).modelValid,false);
    for(const error of [1e-10,.01,.49]) {
      const bad=structuredClone(moved);bad.elements[0].points[1][0]+=error;
      for(const options of [{},{unroundedCoordinates:[]}])assert.equal(normalizationIntegrity(source,bad,options).modelValid,false);
    }
  }
});

test('rotated lerp endpoint incidence stays touch despite floating cross-product signs',()=>{
  const a=[20,30],b=[220,230];
  for(const t of [.1,.2,.3,.4,.6,.7,.8,.9]) for(const angleDegrees of [90,180,270,-90,-180]) {
    const c=a.map((v,k)=>v+t*(b[k]-v)),d=[c[0]+50,c[1]-50];
    const source=doc([{id:'base',type:'line',points:[a,b]},{id:'stem',type:'line',points:[c,d]}]);
    const stored=transformDocument(source,similarity({angleDegrees,pivot:[0,0],translation:[300,300]})),normalized=structuredClone(stored);
    normalized.elements.forEach(e=>e.points=e.points.map(p=>p.map(Math.round)));
    const result=normalizationIntegrity(stored,normalized);
    assert.equal(result.modelValid,true);assert.deepEqual(result.failures,[],`rotation ${angleDegrees}, lerp ${t}`);
    assert.equal(result.linearArrangement.stored.eventCount,1);assert.equal(result.linearArrangement.normalized.eventCount,1);
    if(angleDegrees===180&&t===.1) {
      const [p,q]=stored.elements[0].points,r=stored.elements[1].points[0];
      assert.ok(Math.abs(signedArea(p,q,r)*2)>0);
    }
  }
});

test('endpoint incidence does not conceal real touch cross or apart topology changes',()=>{
  const make=y=>doc([{id:'base',type:'line',points:[[0,100],[200,100]]},{id:'stem',type:'line',points:[[100,y],[100,150]]}]);
  for(const [before,after] of [[100,99.9],[99.9,100],[100,100.1],[100.1,100],[99.9,100.1],[100.1,99.9]]) {
    const result=normalizationIntegrity(make(before),make(after));
    assert.ok(result.failures.includes('linear intersection topology/order changed'),`${before} -> ${after}`);
  }
});

test('linear intersection events preserve existing concurrency and reject loss or reordering',()=>{
  const make=(y,left,right)=>doc([{id:'horizontal',type:'line',points:[[0,y],[200,y]]},{id:'vertical',type:'line',points:[[100,0],[100,200]]},{id:'diagonal',type:'line',points:[[left,0],[right,200]]}]);
  const concurrent=make(100,80,120),shift=similarity({angleDegrees:0,pivot:[0,0],translation:[7,7]});
  const good=normalizationIntegrity(concurrent,transformDocument(concurrent,shift));assert.deepEqual(good.failures,[]);
  assert.ok(good.linearArrangement.stored.strokes.every(s=>s.groups.length===3&&s.groups[1].events.length===2));
  const distinct=make(110,80,120);
  const lost=normalizationIntegrity(concurrent,distinct);assert.ok(lost.failures.includes('linear intersection event order/coincidence changed'));
  const reversed=normalizationIntegrity(make(90,80,120),distinct);assert.ok(reversed.failures.includes('linear intersection event order/coincidence changed'));
});

test('M/L/Z subpaths keep movetos separate and match polygon area/winding checks',()=>{
  const disconnected=doc([{id:'path',type:'path',d:'M 0 0 L 40 0 M 100 100 L 140 100'},{id:'probe',type:'line',points:[[60,30],[60,40]]}]);
  const shift=similarity({angleDegrees:0,pivot:[0,0],translation:[10,20]});
  const check=normalizationIntegrity(disconnected,transformDocument(disconnected,shift));assert.deepEqual(check.failures,[]);
  assert.equal(check.linearArrangement.stored.strokes.length,3);assert.equal(check.linearArrangement.stored.eventCount,0);
  assert.deepEqual(check.linearArrangement.stored.strokes.filter(s=>s.id==='path').map(s=>s.subpath),[0,1]);
  const opposite=doc([{id:'loops',type:'path',d:'M 0 0 L 20 0 L 0 20 L 0 0 Z M 40 0 L 40 20 L 60 0 Z'}]);
  const valid=normalizationIntegrity(opposite,transformDocument(opposite,shift));assert.deepEqual(valid.failures,[]);assert.equal(valid.linearArrangement.stored.strokes.length,6);
  for(const prefix of ['', 'M 0 0 Q 10 20 20 0 Z ']) {
    const source=doc([{id:'thin',type:'path',d:prefix+'M 60.1 90.1 L 140.1 90.1 L 100.1 90.4 Z',fill:{color:'#777'},stroke:{width:0}}]);
    const normalized=doc([{...source.elements[0],d:prefix+'M 60 90 L 140 90 L 100 90 Z'}]);
    const result=normalizationIntegrity(source,normalized);
    assert.equal(result.modelValid,true);assert.ok(result.failures.includes('thin: collapsed/reversed winding'));
    assert.equal(result.linearArrangement.stored.strokes.length,3);
    assert.ok(result.linearArrangement.stored.strokes.every(s=>s.subpath===(prefix?1:0)));
  }
});

test('manifest consumer refuses process-interrupted payloads, missing members, malformed marker and tampering',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vdd-layout-crash-'));
  try {
    const prefix=path.join(dir,'interrupted'),helper=new URL('../tools/vdd-layout.mjs',import.meta.url).href;
    const fixture=transformDocument({...doc([{id:'p',type:'point',at:[1,2]}]),meta:{anchors:{}}},similarity({angleDegrees:0,pivot:[0,0]}));
    const program=`import fs from 'node:fs';import {writeOutputs} from ${JSON.stringify(helper)};let count=0;const sync=fs.fsyncSync;fs.fsyncSync=function(fd){sync(fd);if(++count===2)process.exit(77);};writeOutputs(${JSON.stringify(prefix)},Buffer.from('{}'),{document:${JSON.stringify(fixture)},anchors:{},provenance:{approved:true,failures:[]}});`;
    assert.throws(()=>execFileSync(process.execPath,['--input-type=module','-e',program],{stdio:'pipe'}),e=>e.status===77);
    assert.ok(fs.existsSync(prefix+'.json'));assert.equal(fs.existsSync(prefix+'.manifest.json'),false);assert.throws(()=>loadOutputs(prefix),/manifest missing/);
    const complete=path.join(dir,'complete'),result={document:fixture,anchors:{},provenance:{approved:true,failures:[]}};
    writeOutputs(complete,Buffer.from('{}'),result);fs.unlinkSync(complete+'.anchors.json');assert.throws(()=>loadOutputs(complete),/payload missing/);
    fs.writeFileSync(prefix+'.manifest.json','{"schema":');assert.throws(()=>loadOutputs(prefix));
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('CLI synthetic new outputs include exact provenance and preserve inputs byte-for-byte', {timeout:30000},()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vdd-layout-cli-test-'));
  try {
    const input=path.join(dir,'source.json'),anchors=path.join(dir,'source.anchors.json'),cfg=path.join(dir,'config.json'),prefix=path.join(dir,'corrected');
    const inputMeta={anchors:{O:[150,120]},anchorsFrame:'INPUT_VDD_CANVAS',unrelated:{label:'retain',items:[1,null,false]}};
    const original=JSON.stringify({...doc([{id:'c',type:'circle',center:[150,120],r:90}]),meta:inputMeta}),raw='{ "O" : [150, 120] }\n';
    fs.writeFileSync(input,original);fs.writeFileSync(anchors,raw);fs.writeFileSync(cfg,JSON.stringify(config(3)));
    const stdout=execFileSync(process.execPath,[fileURLToPath(new URL('../tools/vdd-layout.mjs',import.meta.url)),'--input',input,'--anchors',anchors,'--config',cfg,'--out',prefix],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
    assert.equal(JSON.parse(stdout).approved,true);
    const report=JSON.parse(fs.readFileSync(prefix+'.layout.json','utf8'));
    assert.equal(report.matrix.length,6);assert.match(report.source.rawAnchorsSHA256,/^[0-9a-f]{64}$/);
    assert.equal(fs.readFileSync(input,'utf8'),original);assert.equal(fs.readFileSync(anchors,'utf8'),raw);assert.equal(fs.readFileSync(prefix+'.raw.anchors.json','utf8'),raw);
    assert.equal(report.reports.length,6);
    const loaded=loadOutputs(prefix);assert.equal(loaded.rawAnchorsFrame,'INPUT_VDD_CANVAS');
    assert.equal(loaded.document.meta.anchorsFrame,'STORED_OUTPUT_CANVAS');assert.deepEqual(loaded.document.meta.anchors,loaded.anchors);
    assert.deepEqual(loaded.document.meta.inputMetadata,inputMeta);assert.equal(loaded.document.meta.inputMetadataRole,'INPUT_PROVENANCE');
    assert.deepEqual(loaded.manifest.metadataContract,report.metadataContract);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

const semanticViewport=[0,0,200,200];
const semanticFixture=()=>{
  const question=doc([
    {id:'x',type:'arrow',points:[[0,100],[200,100]],headSize:12},
    {id:'y',type:'arrow',points:[[100,200],[100,0]],headSize:12},
    {id:'boundary',type:'line',points:[[0,200],[200,0]]},
    {id:'origin',type:'point',at:[100,100],label:'O',labelOffset:[9,18]},
    {id:'label-x',type:'text',at:[183,122],value:'x'},
    {id:'label-y',type:'text',at:[112,16],value:'y'},
    {id:'label-si',type:'text',at:[18,28],value:'අක්ෂ',fontSize:14}
  ]);
  const answer=structuredClone(question);
  answer.elements.unshift({id:'shade',type:'polygon',points:clipHalfPlanes(semanticViewport,[[1,1,200]]),fill:{color:'#ddd'},stroke:{width:0}});
  const anchors={L:[0,100],R:[200,100]};
  const members=[{id:'question',document:question,anchors,certificate:unshadedCertificate(question)},{id:'answer',document:answer,anchors,certificate:shadedCertificate(answer)}];
  const frame={mode:'semantic-viewport',matrix:similarity({angleDegrees:0,pivot:[0,0],scale:1.2,translation:[80,40]}),canvas:[400,320],reference:'synthetic chosen viewport',sourceFrame:'synthetic mathematical axes',pitch:['L','R'],sharedAnchors:['L','R'],viewport:semanticViewport,sourceOrientation:{angleDegrees:3,pivot:[100,100],reference:'synthetic regeneration, not finite-fill rotation'}};
  return {question,answer,members,frame};
};
const unshadedCertificate=(d,viewport=semanticViewport)=>({kind:'half-plane-viewport-v1',reference:'synthetic explicit unshaded apparatus',viewport,documentSHA256:documentDigest(d),unshaded:true,regions:[]});
const shadedCertificate=(d,viewport=semanticViewport,inequalities=[[1,1,200]])=>({kind:'half-plane-viewport-v1',reference:'synthetic explicit half-plane',viewport,documentSHA256:documentDigest(d),regions:[{elementId:'shade',inequalities}]});

test('unshaded attestation is literal explicit digest-bound and never mixed with regions',()=>{
  const {question:q,answer:a}=semanticFixture(),validate=c=>validateViewportCertificate(q,c,semanticViewport);
  const result=validate(unshadedCertificate(q));
  assert.equal(result.validated,true);assert.equal(result.unshaded,true);assert.equal(result.areaFillCount,0);assert.deepEqual(result.regions,[]);assert.match(result.markerPolicy,/not.*area-fill/);
  assert.throws(()=>validate(undefined),/certificate/);
  const missing=unshadedCertificate(q);delete missing.unshaded;assert.throws(()=>validate(missing),/attestation/);
  for(const unshaded of [undefined,false,'true',1,null,{},[]])assert.throws(()=>validate({...unshadedCertificate(q),unshaded}),/attestation/);
  for(const regions of [undefined,null,{},''])assert.throws(()=>validate({...unshadedCertificate(q),regions}),/array/);
  for(const d of [q,a])assert.throws(()=>validateViewportCertificate(d,{...unshadedCertificate(d),regions:shadedCertificate(a).regions},semanticViewport),/mixed/);
  for(const patch of [{reference:''},{reference:' '},{kind:'other'},{documentSHA256:'a'.repeat(64)},{viewport:[0,0,201,200]}])assert.throws(()=>validate({...unshadedCertificate(q),...patch}),/certificate/);
  const changed=structuredClone(q);changed.elements[0].points[0][0]=1;assert.throws(()=>validateViewportCertificate(changed,unshadedCertificate(q),semanticViewport),/bind/);
});

test('rehashed unexpected area fills cannot satisfy an unshaded certificate',()=>{
  const {question}=semanticFixture();
  const shapes=[{type:'polygon',points:[[10,10],[20,10],[20,20]]},{type:'rect',x:10,y:10,width:20,height:20},{type:'path',d:'M 10 10 L 20 10 L 20 20 Z'},{type:'circle',center:[15,15],r:5}];
  for(const shape of shapes)for(const inherited of [false,true]) {
    const d=structuredClone(question);d.elements.push({id:'unexpected',...shape,...(inherited?{}:{fill:{color:'#aaa'}})});
    if(inherited)d.defaults.fillColor='#aaa';
    assert.throws(()=>validateViewportCertificate(d,unshadedCertificate(question),semanticViewport),/bind/);
    assert.throws(()=>validateViewportCertificate(d,unshadedCertificate(d),semanticViewport),/no visible area fills/);
  }
});

test('both certificate branches reject coercive opacity color and malformed fill',()=>{
  const {answer}=semanticFixture();
  for(const certificate of [unshadedCertificate,shadedCertificate]) {
    for(const bad of ['0','1','',false,true,null,[],{},NaN,Infinity,-Infinity,-.1,1.1])for(const location of ['default','element','fill']) {
      const d=structuredClone(answer),e=d.elements[0];
      if(location==='default')d.defaults.opacity=bad;else if(location==='element')e.opacity=bad;else e.fill.opacity=bad;
      assert.throws(()=>validateViewportCertificate(d,certificate(d),semanticViewport),/opacity/);
    }
    for(const bad of [null,false,0,[],{}])for(const location of ['default','fill']) {
      const d=structuredClone(answer);if(location==='default')d.defaults.fillColor=bad;else d.elements[0].fill.color=bad;
      assert.throws(()=>validateViewportCertificate(d,certificate(d),semanticViewport),/color/);
    }
    for(const bad of [null,false,0,[],'none']) {
      const d=structuredClone(answer);d.elements[0].fill=bad;
      assert.throws(()=>validateViewportCertificate(d,certificate(d),semanticViewport),/fill must/);
    }
  }
});

test('unshaded classifier retains none transparent and numeric zero-opacity semantics',()=>{
  const {answer}=semanticFixture();
  for(const fill of [{color:'none'},{color:'transparent'},{color:'#ddd',opacity:0}]) {
    const d=structuredClone(answer);d.elements[0].fill=fill;assert.equal(validateViewportCertificate(d,unshadedCertificate(d),semanticViewport).validated,true);
  }
  for(const location of ['default','element']) {
    const d=structuredClone(answer);if(location==='default')d.defaults.opacity=0;else d.elements[0].opacity=0;
    assert.equal(validateViewportCertificate(d,unshadedCertificate(d),semanticViewport).validated,true);
  }
});

test('shared viewport gate rejects malformed reversed zero nonfinite and string coordinates before either branch or common-frame measurement',async()=>{
  const {question,answer,members,frame}=semanticFixture();
  const invalid=[undefined,null,{},'0,0,200,200',[],[0,0,200],[0,0,200,200,1],[200,200,0,0],[200,0,0,200],[0,200,200,0],[0,0,0,200],[0,0,200,0]];
  for(const bad of ['0','200',null,false,undefined,NaN,Infinity,-Infinity,[],{}])for(let i=0;i<4;i++) {const v=[...semanticViewport];v[i]=bad;invalid.push(v);}
  for(const viewport of invalid) {
    assert.throws(()=>clipHalfPlanes(viewport,[[1,1,200]]),/invalid semantic viewport/);
    for(const [d,certificate] of [[question,unshadedCertificate],[answer,shadedCertificate]]) {
      const c={...certificate(d),viewport};
      assert.throws(()=>validateViewportCertificate(d,c,viewport),/invalid semantic viewport/);
      await assert.rejects(()=>validateCommonFrame([{...members[0],document:d,certificate:c}],{...frame,viewport},{}),/invalid semantic viewport/);
    }
  }
});

test('shaded certificates retain exact cyclic reversed fill and fail holes rotations extras duplicates and invalid inequalities',()=>{
  const {answer:a}=semanticFixture();
  assert.equal(validateViewportCertificate(a,shadedCertificate(a),semanticViewport).validated,true);
  for(const points of [[...a.elements[0].points].reverse(),[...a.elements[0].points.slice(1),a.elements[0].points[0]]]) {
    const d=structuredClone(a);d.elements[0].points=points;assert.equal(validateViewportCertificate(d,shadedCertificate(d),semanticViewport).validated,true);
  }
  const hole=structuredClone(a);hole.elements[0].points[0]=[20,20];assert.throws(()=>validateViewportCertificate(hole,shadedCertificate(hole),semanticViewport),/leave holes/);
  const rotated=structuredClone(a);rotated.elements[0].rotation=3;assert.throws(()=>validateViewportCertificate(rotated,shadedCertificate(rotated),semanticViewport),/regenerated polygon/);
  const extra=structuredClone(a);extra.elements.push({id:'extra',type:'circle',center:[10,10],r:3,fill:{color:'#ddd'}});assert.throws(()=>validateViewportCertificate(extra,shadedCertificate(extra),semanticViewport),/every visible/);
  const c=shadedCertificate(a);assert.throws(()=>validateViewportCertificate(a,{...c,regions:[...c.regions,...c.regions]},semanticViewport),/every visible/);
  for(const inequalities of [[],[[0,0,1]],[[1,NaN,2]],[[1,'1',200]]])assert.throws(()=>validateViewportCertificate(a,shadedCertificate(a,semanticViewport,inequalities),semanticViewport),/inequalities|expected/);
});

test('actual Chromium paint fitting and normalizer refusal on synthetic fixtures only', {timeout:180000}, async(t)=>{
  const renderer=await createMeasurer({headed:true});
  const roundedRenderer={...renderer,normalizeAudited:async d=>roundedMutant(await renderer.normalize(d))};
  try {
    const symmetric=doc([{id:'frame',type:'circle',center:[150,120],r:90,stroke:{width:4}},{id:'text',type:'text',at:[150,120],align:'middle',baseline:'top',value:'upright'},{id:'math',type:'math',at:[150,120],align:'middle',baseline:'alphabetic',latex:'x^2'}]);
    for(const angle of [-3,4,90,180,270]) await t.test(`paint +/-/quarter-turn ${angle}`,async()=>{
      const result=await layout(symmetric,{O:[150,120]},config(angle),renderer);
      assert.deepEqual(result.provenance.failures,[]); assert.equal(result.provenance.reports.length,6);
      assert.ok(result.provenance.reports.every(r=>r.allLabelsInside&&r.glyphsUpright));
      assert.ok(result.provenance.reports.every(r=>r.labels.length===2));
      for(const r of result.provenance.reports) assert.ok(Math.max(...r.centerResidualPx.map(Math.abs))<=3);
    });
    await t.test('off-center copy centers whole paint identically',async()=>{
      const shifted=transformDocument(symmetric,similarity({angleDegrees:0,pivot:[0,0],translation:[1000,-700]}));
      const cfg=config(-4);cfg.pivot=[1150,-580];
      const a=await layout(symmetric,{O:[150,120]},config(-4),renderer), b=await layout(shifted,{O:[1150,-580]},cfg,renderer);
      nearPoint(a.anchors.O,b.anchors.O); assert.deepEqual(b.provenance.failures,[]);
    });
    await t.test('long glyph outside geometry is centered using real ink; normalize defect refuses',async()=>{
      const d=doc([{id:'c',type:'circle',center:[100,100],r:20},{id:'label',type:'text',at:[125,100],value:'WWWWWWWWWWWWWWWWWWWW',fontSize:24,baseline:'middle'}]);
      const result=await layout(d,{C:[100,100]},config(0),renderer);
      const stored=result.provenance.reports.filter(r=>r.surface==='stored');
      assert.ok(stored.every(r=>r.allLabelsInside&&Math.max(...r.centerResidualPx.map(Math.abs))<=3));
      assert.ok(result.provenance.failures.some(f=>f.startsWith('normalizeVdd/')));
      assert.equal(result.provenance.approved,false);
    });
    await t.test('filled circular arc, curve controls, arrows and rounded rectangle use actual pixels',async()=>{
      const d=doc([{id:'p',type:'path',d:'M 40 120 A 70 70 0 0 1 180 120 L 40 120 Z',fill:{color:'#999'}},{id:'a',type:'arrow',points:[[30,150],[100,150],[190,150]],headSize:24,stroke:{width:5}},{id:'q',type:'path',d:'M 40 180 Q 60 150 90 180 C 100 190 130 140 180 180',stroke:{width:3}},{id:'r',type:'rect',x:30,y:195,width:160,height:20,rx:8}]);
      const result=await layout(d,{A:[30,150],B:[190,150]},config(4),renderer);
      assert.ok(result.provenance.reports.filter(r=>r.surface==='stored').every(r=>Math.max(...r.centerResidualPx.map(Math.abs))<=3&&Math.min(...Object.values(r.padding))>1));
      const transformed=transformDocument(d,result.provenance.matrix);
      assert.deepEqual(transformed.elements,result.document.elements);
    });
    await t.test('background-colored paint cannot act as invisible padding',async()=>{
      const d=doc([{id:'ink',type:'circle',center:[150,120],r:30},{id:'invisible',type:'rect',x:220,y:20,width:40,height:180,fill:{color:'white'},stroke:{width:0}}]);
      const plain=await renderer.measure(doc([d.elements[0]]),300);
      const extra=await renderer.measure(d,300);
      assert.deepEqual(plain.bounds,extra.bounds);
    });
    await t.test('exact three-line arrangement passes real normalization and refuses synthetic rounded merged intersections',async()=>{
      const d=doc([{id:'horizontal',type:'line',points:[[0,100.1],[200,100.1]]},{id:'near-vertical',type:'line',points:[[99.6,0],[100.4,200]]},{id:'diagonal',type:'line',points:[[80.2,0],[120.1,200]]}]);
      const actual=await layout(d,{}, {...config(0),canvas:[266,266]},renderer);
      assert.deepEqual(actual.provenance.failures,[]);assert.equal(actual.provenance.approved,true);
      const result=await layout(d,{}, {...config(0),canvas:[266,266]},roundedRenderer),integrity=result.provenance.normalization;
      const events=a=>new Set(a.strokes.flatMap(s=>s.groups.filter(g=>g.events.some(e=>e.includes(':'))).map(g=>g.point.map(v=>v.toFixed(7)).join(','))));
      assert.equal(integrity.modelValid,true);assert.equal(events(integrity.linearArrangement.stored).size,3);assert.equal(events(integrity.linearArrangement.normalized).size,1);
      assert.equal(result.provenance.approved,false);assert.ok(result.provenance.failures.some(f=>f.includes('linear intersection event order/coincidence changed')));
      assert.ok(result.provenance.reports.every(r=>r.allLabelsInside&&r.glyphsUpright));
    });
    await t.test('thin M/L/Z and polygon triangles pass real normalization and refuse synthetic rounded area collapse',async()=>{
      const points=[[60.1,90.1],[140.1,90.1],[100.1,90.4]],outline={id:'circle',type:'circle',center:[100,100],r:100};
      for(const shape of [{id:'thin-triangle',type:'path',d:'M 60.1 90.1 L 140.1 90.1 L 100.1 90.4 Z'},{id:'thin-triangle',type:'polygon',points}]) {
        const d=doc([outline,{...shape,fill:{color:'#777'},stroke:{width:0}}]);
        const cfg={...config(0),pivot:[100,100],canvas:[266,266]},actual=await layout(d,{},cfg,renderer);
        assert.deepEqual(actual.provenance.failures,[]);assert.equal(actual.provenance.approved,true);
        const result=await layout(d,{},cfg,roundedRenderer),normalized=(await roundedRenderer.normalizeAudited(result.document)).document;
        const vertices=e=>e.points??parsePath(e.d).filter(([cmd])=>cmd==='M'||cmd==='L').map(([,p])=>p);
        near(signedArea(...vertices((await renderer.normalize(actual.document)).elements[1])),12,1e-6);
        near(signedArea(...vertices(result.document.elements[1])),12,1e-6);near(signedArea(...vertices(normalized.elements[1])),0);
        assert.equal(result.provenance.normalization.modelValid,true);assert.equal(result.provenance.approved,false);
        assert.ok(result.provenance.failures.some(f=>f.includes('thin-triangle: collapsed/reversed winding')));
      }
    });
    await t.test('ordinary rotated polygon/arrow/labels pass expected quantization at 400x320',async()=>{
      const d=doc([{id:'triangle',type:'polygon',points:[[60,40],[240,40],[150,200]]},{id:'direction',type:'arrow',points:[[115,110],[185,110]],head:'end',headSize:14},{id:'A',type:'text',at:[100,65],value:'A',align:'middle'},{id:'B',type:'text',at:[200,65],value:'B',align:'middle'},{id:'C',type:'text',at:[150,160],value:'C',align:'middle'},{id:'math',type:'math',at:[150,85],latex:'x^2',align:'middle'}]);
      for(const angle of [-7.3,-4.5,-3,-1.1,.5,1,2.7,3,3.25,4,7.3,12.7]) {
        const result=await layout(d,{},config(angle),renderer);
        assert.deepEqual(result.provenance.failures,[],`angle ${angle}`);
        assert.equal(result.provenance.normalization.modelValid,true);
        assert.ok(result.provenance.normalization.maximumAbsoluteRoundingPerAxis.every(v=>v<=.500000001));
        assert.equal(result.provenance.semanticApproval,false);
        assert.equal(result.provenance.measurement.fonts.status,'actual-local-assets');
        assert.ok(result.provenance.reports.every(r=>r.allLabelsInside&&r.glyphsUpright));
      }
    });
    await t.test('source text and unsafe paint payloads do not become HTML, script, or off-site requests',async()=>{
      const d=doc([{id:'c',type:'circle',center:[150,120],r:30,fill:{color:'url(https://example.invalid/fill)'},stroke:{color:'url(https://example.invalid/stroke)'}},{id:'text',type:'text',at:[10,10],fontSize:8,value:'</script><script>window.PWNED=1</script><img src=x onerror=window.PWNED=2>'}]);
      d.canvas.background='url(https://example.invalid/bg)';const r=await renderer.measure(d,375,{guard:256});
      assert.equal(r.security.unsafeHtmlNodes,0);assert.equal(r.security.pwned,null);assert.deepEqual(r.security.blockedRequests,[]);
    });
    await t.test('runtime normalization audit is observational and reused claim evaluators retain critical math gates',async()=>{
      const d=doc([{id:'triangle',type:'polygon',points:[[60,40],[240,40],[240,200]]}]),anchors={A:[60,40],B:[240,40],C:[240,200]};
      const cfg={...config(3),claimsText:'claims:\n S1 right A B C | vector\n S2 ratio len AB / len BC = 1.125 | vector'};
      const result=await layout(d,anchors,cfg,renderer);assert.deepEqual(result.provenance.failures,[]);assert.equal(result.provenance.claims.normalized.length,2);
      const plain=await renderer.normalize(result.document),audit=await renderer.normalizeAudited(result.document);assert.deepEqual(plain,audit.document);assert.equal(result.provenance.normalization.audited,true);
      assert.ok(result.provenance.normalization.maximumAbsoluteRoundingPerAxis.every(v=>v<=.500000001));
      assert.deepEqual(audit.unroundedCoordinates,[]);assert.equal(result.provenance.normalization.model,'common-translation');
      const strictConfig={...cfg,critical:[{kind:'perpendicular',points:[['triangle',0],['triangle',1],['triangle',2]]}]};
      const actualStrict=await layout(d,anchors,strictConfig,renderer);assert.deepEqual(actualStrict.provenance.failures,[]);assert.equal(actualStrict.provenance.approved,true);
      const strict=await layout(d,anchors,strictConfig,roundedRenderer);
      assert.equal(strict.provenance.approved,false);assert.ok(strict.provenance.failures.some(f=>f.includes('critical perpendicular')));
    });
    await t.test('real Inter/Noto metadata and Webpack/Turbo local asset discovery; missing fonts cannot approve',async()=>{
      const fonts=renderer.provenance.fonts;
      assert.equal(fonts.status,'actual-local-assets');assert.ok(fonts.assets.length>=2);assert.ok(fonts.resolvedFaces.some(f=>/Inter/.test(f.family)));assert.ok(fonts.resolvedFaces.some(f=>/Noto/.test(f.family)));
      const admin=path.resolve(process.env.VIBHAGA_ADMIN??path.join(fileURLToPath(new URL('.',import.meta.url)),'../../Vibhaga-Admin')),dir=fs.mkdtempSync(path.join(os.tmpdir(),'vdd-fonts-'));
      try {
        for(const mode of ['css','chunks']) {
          const root=path.join(dir,mode);fs.mkdirSync(root);fs.mkdirSync(path.join(root,mode));fs.mkdirSync(path.join(root,'media'));
          const local=loadLocalFonts(admin);
          for(const [url,a] of local.assets)fs.writeFileSync(path.join(root,'media',path.basename(url)),a.body);
          fs.writeFileSync(path.join(root,mode,'layout.css'),local.css);
          const found=loadLocalFonts(admin,root);assert.deepEqual(found.families,local.families);assert.equal(found.assets.size,local.assets.size);
        }
        await assert.rejects(()=>createMeasurer({fontStaticDirectory:path.join(dir,'missing')}),/font approval refused/);
        const provisional=await createMeasurer({fontStaticDirectory:path.join(dir,'missing'),allowProvisionalFonts:true});
        try {const result=await layout(symmetric,{},config(),provisional);assert.equal(result.provenance.approved,false);assert.ok(result.provenance.failures.some(f=>f.includes('provisional')));}finally{await provisional.close();}
      } finally {fs.rmSync(dir,{recursive:true,force:true});}
    });
    await t.test('caller-measured shared union uses one matrix, translation and displayed pitch on both paths',async()=>{
      const base=doc([{id:'circle',type:'circle',center:[150,120],r:90},{id:'diameter',type:'line',points:[[60,120],[240,120]]}]);
      const answer=structuredClone(base);answer.elements.push({id:'answer',type:'text',at:[150,90],align:'middle',value:'answer'});
      const anchors={L:[60,120],R:[240,120]},members=[{id:'question',document:base,anchors},{id:'answer',document:answer,anchors}];
      for(const m of members)m.document.meta={anchors,anchorsFrame:'INPUT_VDD_CANVAS',unrelated:{member:m.id,tags:['preserved',null]},inputMetadata:{preexisting:'namespace'}};
      const union=await measureUnion([base,answer],300,renderer),matrix=fitMeasuredUnion(union.bounds,[400,320]);
      const frame={mode:'common-frame',matrix,canvas:[400,320],reference:'explicit synthetic shared union fit',sourceFrame:'same original coordinate units',orientation:{angleDegrees:0,pivot:[0,0],reference:'explicit no rotation'},pitch:['L','R'],sharedAnchors:['L','R']};
      const result=await validateCommonFrame(members,frame,renderer);assert.deepEqual(result.provenance.failures,[]);
      assert.ok(result.provenance.reports.every(r=>r.commonCanvas&&Math.abs(r.pitchCssPx[0]-r.pitchCssPx[1])<1e-6));
      const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vdd-common-bundle-'));
      try {
        const prefix=path.join(dir,'pair'),raw=Buffer.from(JSON.stringify(anchors));writeCommonFrameOutputs(prefix,{question:raw,answer:raw},result);
        const loaded=loadOutputs(prefix);assert.equal(loaded.members.length,2);assert.deepEqual(loaded.provenance.metadataContract,METADATA_CONTRACT);
        loaded.members.forEach((m,i)=>{assert.deepEqual(m.document.meta.inputMetadata,members[i].document.meta);assert.equal(m.document.meta.inputMetadataRole,'INPUT_PROVENANCE');assert.equal(m.document.meta.anchorsFrame,'STORED_OUTPUT_CANVAS');assert.deepEqual(m.document.meta.anchors,m.anchors);assert.deepEqual(m.rawAnchors,raw);assert.equal(m.rawAnchorsFrame,'INPUT_VDD_CANVAS');});
        const bad=structuredClone(result);bad.members[0].document.meta.anchorsFrame='INPUT_VDD_CANVAS';assert.throws(()=>writeCommonFrameOutputs(path.join(dir,'stale'),{question:raw,answer:raw},bad),/anchor frame/);
      }finally{fs.rmSync(dir,{recursive:true,force:true});}
      const extra=structuredClone(answer);extra.elements.push({id:'extension',type:'line',points:[[150,120],[260,160]]});
      const rejected=await validateCommonFrame([{...members[0]},{...members[1],document:extra}],frame,renderer);
      assert.equal(rejected.provenance.approved,false);assert.ok(rejected.provenance.failures.some(f=>/common viewport|common translation/.test(f)));
    });
    await t.test('explicit unshaded question and shaded answer share both rendered surfaces at 320 375 768',async()=>{
      const {members,frame}=semanticFixture(),before=structuredClone(members);
      const result=await validateCommonFrame(members,frame,renderer),p=result.provenance;
      assert.deepEqual(members,before);assert.deepEqual(p.failures,[]);assert.equal(p.approved,true);assert.equal(p.semanticApproval,false);
      assert.equal(p.measurement.fonts.status,'actual-local-assets');
      for(const family of [/Inter/,/Noto/])assert.ok(p.measurement.fonts.resolvedFaces.some(f=>family.test(f.family)&&f.status==='loaded'));
      assert.equal(p.certificates[0].unshaded,true);assert.equal(p.certificates[0].areaFillCount,0);assert.equal(p.certificates[1].regions.length,1);
      assert.equal(result.members[0].document.elements.some(e=>e.type==='polygon'),false);assert.equal(result.members[1].document.elements.filter(e=>e.type==='polygon').length,1);
      assert.deepEqual(p.reports.map(r=>[r.surface,r.width]),['stored','normalizeVdd'].flatMap(s=>[320,375,768].map(w=>[s,w])));
      for(const report of p.reports) {
        assert.equal(report.commonCanvas,true);near(report.pitchCssPx[0],report.pitchCssPx[1]);assert.deepEqual(report.coordinates[0],report.coordinates[1]);
        assert.ok(report.members.every(m=>m.allLabelsInside&&m.glyphsUpright&&Math.min(...Object.values(m.padding))>=1));
        assert.ok(report.members.every(m=>m.labels.length>=4));
      }
      await assert.rejects(()=>validateCommonFrame([{...members[0],certificate:undefined},members[1]],frame,renderer),/certificate/);
      await assert.rejects(()=>validateCommonFrame(members,{...frame,matrix:similarity({angleDegrees:3,pivot:[0,0]})},renderer),/never rotation/);
    });
    await t.test('chosen semantic viewport validates regenerated half-plane fills, rejects holes and raw fill rotation',async()=>{
      const viewport=[0,0,200,200],make=inequalities=>doc([{id:'shade',type:'polygon',points:clipHalfPlanes(viewport,inequalities),fill:{color:'#ddd'},stroke:{width:0}},{id:'x',type:'arrow',points:[[0,100],[200,100]],headSize:12},{id:'y',type:'arrow',points:[[100,200],[100,0]],headSize:12},{id:'boundary',type:'line',points:[[0,200],[200,0]]}]);
      const q=make([[1,1,200]]),a=make([[1,1,200],[1,0,100]]),anchors={L:[0,100],R:[200,100]};
      const cert=(d,inequalities)=>({kind:'half-plane-viewport-v1',reference:'synthetic explicit mathematical inequalities',viewport,documentSHA256:documentDigest(d),regions:[{elementId:'shade',inequalities}]});
      const members=[{id:'question',document:q,anchors,certificate:cert(q,[[1,1,200]])},{id:'answer',document:a,anchors,certificate:cert(a,[[1,1,200],[1,0,100]])}];
      const frame={mode:'semantic-viewport',matrix:similarity({angleDegrees:0,pivot:[0,0],scale:1.2,translation:[80,40]}),canvas:[400,320],reference:'chosen finite plot viewport',sourceFrame:'mathematical axes, not capture roll',pitch:['L','R'],sharedAnchors:['L','R'],viewport,sourceOrientation:{angleDegrees:3,pivot:[100,100],reference:'supplied capture reference; apparatus regenerated'}};
      const result=await validateCommonFrame(members,frame,renderer);assert.deepEqual(result.provenance.failures,[]);assert.ok(result.provenance.certificates.every(c=>c.validated));
      await assert.rejects(()=>validateCommonFrame(members,{...frame,matrix:similarity({angleDegrees:3,pivot:[0,0]})},renderer),/never rotation/);
      const bad=structuredClone(q);bad.elements[0].points[0]=[20,20];assert.throws(()=>validateViewportCertificate(bad,cert(bad,[[1,1,200]]),viewport),/leave holes/);
      assert.throws(()=>validateViewportCertificate(q,undefined,viewport),/certificate/);
    });
    await t.test('missing reference, unbounded framing and unsupported pair config refuse before measurement',async()=>{
      await assert.rejects(()=>layout(symmetric,{}, {...config(),reference:''},renderer),/reference/);
      await assert.rejects(()=>layout(symmetric,{}, {...config(),framing:{mode:'unbounded'}},renderer),/regeneration/);
      await assert.rejects(()=>layout(symmetric,{}, {...config(),sharedFrame:'auto'},renderer),/unsupported field/);
      const marked=transformDocument({...symmetric,meta:{unbounded:true,unrelated:'retained'}},similarity({angleDegrees:0,pivot:[0,0]}));
      assert.equal(marked.meta.inputMetadata.unrelated,'retained');await assert.rejects(()=>layout(marked,{},config(),renderer),/cannot bypass/);
    });
  } finally { await renderer.close(); }
});
