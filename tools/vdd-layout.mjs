import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { angleAt, offLine, onSegment, parseClaimSet, evalClaims } from './vdd-check.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TYPES = {
  line: ['points'], polyline: ['points'], polygon: ['points'], arrow: ['points', 'head', 'headSize'],
  point: ['at', 'r', 'label', 'labelOffset'], text: ['at', 'value', 'fontSize', 'fontFamily', 'color', 'align', 'baseline'],
  math: ['at', 'latex', 'fontSize', 'color', 'align', 'baseline'], circle: ['center', 'r'],
  rect: ['x', 'y', 'width', 'height', 'rx'], path: ['d'],
};
const COMMON = ['type', 'id', 'z', 'rotation', 'stroke', 'fill', 'opacity', 'groupId', 'link'];
const need = (ok, message) => { if (!ok) throw new Error(message); };
const copy = (x) => structuredClone(x);
const finite = (x) => typeof x === 'number' && Number.isFinite(x);
const xy = (p) => Array.isArray(p) && p.length === 2 && p.every(finite);
const hash = (x) => crypto.createHash('sha256').update(x).digest('hex');
function finiteTree(x) {
  if (typeof x === 'number') need(finite(x), 'nonfinite number');
  if (x && typeof x === 'object') Object.values(x).forEach(finiteTree);
}
function keys(x, allowed, where) {
  need(x && typeof x === 'object' && !Array.isArray(x), `${where}: expected object`);
  for (const k of Object.keys(x)) need(allowed.includes(k), `${where}: unsupported field ${k}`);
}

export function similarity({ angleDegrees, pivot, scale = 1, translation = [0, 0] }) {
  need(finite(angleDegrees) && xy(pivot) && xy(translation), 'explicit finite angle, pivot and translation required');
  need(finite(scale) && scale > 0, 'scale must be positive: singular transforms/reflection are forbidden');
  const t = angleDegrees * Math.PI / 180, a = scale * Math.cos(t), b = scale * Math.sin(t);
  return validateMatrix([a, b, -b, a, pivot[0] + translation[0] - a * pivot[0] + b * pivot[1], pivot[1] + translation[1] - b * pivot[0] - a * pivot[1]]);
}
export function validateMatrix(m) {
  need(Array.isArray(m) && m.length === 6 && m.every(finite), 'matrix must contain six finite numbers');
  const [a, b, c, d] = m, s = Math.hypot(a, b), determinant = a * d - b * c;
  need(s > 1e-12 && finite(s) && finite(determinant) && determinant > 0, 'singular/reflection/overflow matrix refused');
  need(Math.abs(c + b) <= s * 1e-12 && Math.abs(d - a) <= s * 1e-12, 'nonuniform scale/shear refused');
  return m;
}
export const mapPoint = (m, p) => {
  validateMatrix(m);
  need(xy(p), 'invalid coordinate pair');
  const q = [m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5]];
  need(xy(q), 'coordinate overflow');
  return q;
};
export function compose(outer, inner) {
  validateMatrix(outer); validateMatrix(inner);
  const [a, b, c, d, e, f] = outer, [g, h, i, j, k, l] = inner;
  return validateMatrix([a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f]);
}
export function parsePath(d) {
  need(typeof d === 'string' && d.length <= 100000, 'invalid path');
  const token = /[MLQCAZ]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/g;
  const tokens = []; let end = 0;
  for (const m of d.matchAll(token)) {
    need(/^[\s,]*$/.test(d.slice(end, m.index)), 'path: only absolute M L Q C A Z allowed');
    tokens.push(m[0]); end = m.index + m[0].length;
  }
  need(/^[\s,]*$/.test(d.slice(end)) && tokens[0] === 'M', 'path must begin with absolute M');
  const arity = { M: 2, L: 2, Q: 4, C: 6, A: 7, Z: 0 }, out = [];
  let i = 0, cmd;
  while (i < tokens.length) {
    if (tokens[i] in arity) {
      cmd = tokens[i++];
      if (cmd === 'Z') { out.push(['Z', []]); cmd = undefined; continue; }
    }
    need(cmd && i + arity[cmd] <= tokens.length, 'path: incomplete command');
    const a = tokens.slice(i, i + arity[cmd]).map(Number);
    need(a.every(finite), 'path: incomplete/nonfinite arguments');
    if (cmd === 'A') need(a[0] >= 0 && a[1] >= 0 && [0, 1].includes(a[3]) && [0, 1].includes(a[4]), 'path: invalid arc radii/flags');
    out.push([cmd, a]); i += arity[cmd];
    if (cmd === 'M') cmd = 'L';
  }
  need(out.length && out[0][0] === 'M', 'empty path');
  return out;
}
export function transformPath(d, m) {
  validateMatrix(m);
  const s = Math.hypot(m[0], m[1]), angle = Math.atan2(m[1], m[0]) * 180 / Math.PI;
  return parsePath(d).map(([cmd, a]) => {
    const b = a.slice();
    if (cmd === 'A') { b[0] *= s; b[1] *= s; b[2] += angle; }
    for (let i = cmd === 'A' ? 5 : 0; i < a.length; i += 2) b.splice(i, 2, ...mapPoint(m, a.slice(i, i + 2)));
    need(b.every(finite), 'path transform overflow');
    return [cmd, ...b].join(' ');
  }).join(' ');
}
function rectPath(el) {
  const { x, y, width: w, height: h } = el;
  need([x, y, w, h].every(finite) && w > 0 && h > 0 && (el.rx === undefined || finite(el.rx) && el.rx >= 0), 'invalid rect dimensions');
  const rx = Math.min(el.rx ?? 0, w / 2), ry = Math.min(el.rx ?? 0, h / 2);
  if (!rx || !ry) return `M ${x} ${y} L ${x+w} ${y} L ${x+w} ${y+h} L ${x} ${y+h} Z`;
  return `M ${x+rx} ${y} L ${x+w-rx} ${y} A ${rx} ${ry} 0 0 1 ${x+w} ${y+ry} L ${x+w} ${y+h-ry} A ${rx} ${ry} 0 0 1 ${x+w-rx} ${y+h} L ${x+rx} ${y+h} A ${rx} ${ry} 0 0 1 ${x} ${y+h-ry} L ${x} ${y+ry} A ${rx} ${ry} 0 0 1 ${x+rx} ${y} Z`;
}
export const METADATA_CONTRACT = Object.freeze({
  schema:'vdd-layout-metadata-v1',
  inputMetadataRole:'INPUT_PROVENANCE',
  anchorsFrame:'STORED_OUTPUT_CANVAS',
  rawAnchorsFrame:'INPUT_VDD_CANVAS',
  inheritedMetadata:'meta.inputMetadata is the complete lossless JSON metadata snapshot of the immediate input document. inputMetadataPresent distinguishes absent metadata. Unknown keys, including non-frame metadata, are preserved here only; none are implicitly asserted to describe the output.',
  compatibility:'Consumers formerly reading inherited meta keys at the root must read meta.inputMetadata as input provenance, or explicitly re-author output metadata. Repeated transforms nest snapshots without flattening. Legacy bundles without this contract require regeneration; the loader does not guess their frames.',
  rawAnchorsMeaning:'.raw.anchors.json preserves the supplied INPUT_VDD_CANVAS sidecar bytes. It is not automatically raw PDF/page anchors; a PDF-to-input-VDD mapping is a separate caller responsibility.',
  normalization:'normalizeVdd leaves metadata unchanged. Anchors labeled STORED_OUTPUT_CANVAS continue to refer to stored geometry, not the normalized canvas.'
});
function outputMetadata(document, anchors) {
  return {layoutMetadataSchema:METADATA_CONTRACT.schema,inputMetadataRole:METADATA_CONTRACT.inputMetadataRole,inputMetadataPresent:Object.hasOwn(document,'meta'),inputMetadata:Object.hasOwn(document,'meta')?copy(document.meta):{},anchorsFrame:METADATA_CONTRACT.anchorsFrame,...(anchors===undefined?{}:{anchors:copy(anchors)})};
}
function inputDeclaresUnbounded(document) {
  let meta=document.meta;
  while(meta && typeof meta==='object') {
    if(meta.semanticViewport||meta.unbounded||['semantic-viewport','unbounded'].includes(meta.framing?.mode))return true;
    if(meta.layoutMetadataSchema!==METADATA_CONTRACT.schema||meta.inputMetadataRole!==METADATA_CONTRACT.inputMetadataRole)break;
    meta=meta.inputMetadata;
  }
  return false;
}
function assertOutputMetadata(document, anchors) {
  const meta=document.meta;
  need(meta?.layoutMetadataSchema===METADATA_CONTRACT.schema && meta.inputMetadataRole===METADATA_CONTRACT.inputMetadataRole && typeof meta.inputMetadataPresent==='boolean' && Object.hasOwn(meta,'inputMetadata'),'output metadata contract missing; regenerate rather than guessing legacy metadata frames');
  need(meta.anchorsFrame===METADATA_CONTRACT.anchorsFrame && Object.hasOwn(meta,'anchors') && stable(meta.anchors)===stable(anchors),'stored output anchor frame/sidecar mismatch');
}
export function transformDocument(document, matrix) {
  validateMatrix(matrix); finiteTree(document);
  keys(document, ['schema', 'schemaVersion', 'canvas', 'defaults', 'elements', 'a11y', 'meta'], 'document');
  need(document.schema === 'vibhaga.diagram' && document.schemaVersion === 1, 'unsupported VDD version');
  keys(document.canvas, ['width','height','background'], 'canvas');
  need([document.canvas.width,document.canvas.height].every(n=>finite(n)&&n>0), 'invalid canvas dimensions');
  if(document.defaults) keys(document.defaults, ['strokeColor','strokeWidth','strokeStyle','fillColor','opacity','fontSize','fontFamily'], 'defaults');
  need(finite(document.defaults?.strokeWidth??2) && (document.defaults?.strokeWidth??2)>=0, 'invalid default stroke width');
  need(finite(document.defaults?.fontSize??18) && (document.defaults?.fontSize??18)>0, 'invalid default font size');
  need(Array.isArray(document.elements) && document.elements.length > 0 && document.elements.length <= 1000, 'expected 1..1000 elements');
  const d = copy(document), s = Math.hypot(matrix[0], matrix[1]);
  d.defaults = { ...d.defaults, strokeWidth: (d.defaults?.strokeWidth ?? 2) * s, fontSize: (d.defaults?.fontSize ?? 18) * s };
  const ids = new Set();
  d.elements = d.elements.map((el) => {
    need(Object.hasOwn(TYPES, el.type), `unsupported type ${el.type}: regenerate explicitly`);
    keys(el, [...COMMON, ...TYPES[el.type]], el.id);
    need(typeof el.id === 'string' && el.id && !ids.has(el.id), 'missing/duplicate element id'); ids.add(el.id);
    need(el.rotation === undefined || el.rotation === 0, `${el.id}: existing nonzero element rotation requires explicit pre-baking; never discarded`);
    if(el.stroke) keys(el.stroke,['color','width','style','opacity'],`${el.id}.stroke`);
    if(el.fill) keys(el.fill,['color','opacity'],`${el.id}.fill`);
    if (el.stroke?.width !== undefined) { need(finite(el.stroke.width)&&el.stroke.width>=0,'invalid stroke width'); el.stroke.width *= s; }
    if (el.fontSize !== undefined) { need(finite(el.fontSize)&&el.fontSize>0,'invalid font size'); el.fontSize *= s; }
    switch (el.type) {
      case 'line': case 'polyline': case 'polygon': case 'arrow':
        need(Array.isArray(el.points) && el.points.length >= (el.type === 'polygon' ? 3 : 2) && (el.type !== 'line' || el.points.length === 2), 'invalid points');
        el.points = el.points.map((p) => mapPoint(matrix, p));
        if (el.headSize !== undefined) { need(finite(el.headSize) && el.headSize > 0, 'headSize must be finite and positive'); el.headSize *= s; }
        break;
      case 'point': {
        el.at = mapPoint(matrix, el.at);
        need(finite(el.r ?? 3.5) && (el.r ?? 3.5) >= 0, 'invalid point radius'); el.r = (el.r ?? 3.5) * s;
        const offset = el.labelOffset ?? [8, -8];
        el.labelOffset = mapPoint([...matrix.slice(0, 4), 0, 0], offset);
        break;
      }
      case 'text': case 'math': el.at = mapPoint(matrix, el.at); break;
      case 'circle':
        el.center = mapPoint(matrix, el.center); need(finite(el.r) && el.r >= 0, 'invalid circle radius'); el.r *= s; break;
      case 'rect': {
        const d = rectPath(el);
        for (const k of TYPES.rect) delete el[k];
        el.type = 'path'; el.d = transformPath(d, matrix); break;
      }
      case 'path': el.d = transformPath(el.d, matrix); break;
    }
    return el;
  });
  d.meta=outputMetadata(document,document.meta?.anchors===undefined?undefined:transformAnchors(document.meta.anchors,matrix));
  finiteTree(d);
  return d;
}
export function transformAnchors(anchors, m) {
  validateMatrix(m);
  need(anchors && typeof anchors === 'object' && !Array.isArray(anchors), 'anchors must be a name-to-[x,y] object');
  return Object.fromEntries(Object.entries(anchors).map(([name, p]) => [name, mapPoint(m, p)]));
}
function coordinateEnvelope(d) {
  const points = [];
  for (const e of d.elements) {
    if (e.points) points.push(...e.points);
    if (e.at) points.push(e.at);
    if (e.center) points.push([e.center[0]-e.r, e.center[1]-e.r], [e.center[0]+e.r, e.center[1]+e.r]);
    if (e.type === 'path') for (const [cmd, a] of parsePath(e.d)) {
      for (let i = cmd === 'A' ? 5 : 0; i < a.length; i += 2) points.push(a.slice(i, i+2));
      if (cmd === 'A') points.push([a[5]-2*Math.max(a[0],a[1]), a[6]-2*Math.max(a[0],a[1])], [a[5]+2*Math.max(a[0],a[1]), a[6]+2*Math.max(a[0],a[1])]);
    }
  }
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

export function loadLocalFonts(admin, staticDirectory) {
  const root = fs.realpathSync(staticDirectory ?? path.join(admin, '.next/dev/static'));
  const cssFiles = [];
  function walk(dir) {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, {withFileTypes:true})) {
      const p=path.join(dir,entry.name);
      if(entry.isDirectory()) walk(p);
      else if(entry.isFile() && p.endsWith('.css')) cssFiles.push(p);
    }
  }
  walk(path.join(root,'css')); walk(path.join(root,'chunks'));
  const assets=new Map(), blocks=new Set(), variables={}, cssHashes=[];
  for(const file of cssFiles.sort()) {
    const raw=fs.readFileSync(file,'utf8'), css=raw.replace(/\/\*[\s\S]*?\*\//g,'');
    if(!/--font-(inter|noto-sinhala)\s*:/.test(css)) continue;
    cssHashes.push({file,sha256:hash(raw)});
    for(const m of css.matchAll(/--font-(inter|noto-sinhala)\s*:\s*([^;}]+)/g)) {
      const value=m[2].trim().replace(/'/g,'"');  // quote style is a compiler choice, not a font choice — accumulated dev builds mix them
      need(!variables[m[1]] || variables[m[1]]===value,'ambiguous compiled font variables; select one static build');
      variables[m[1]]=value;
    }
    for(const m of css.matchAll(/@font-face\s*\{[^}]*\}/g)) if(/font-family\s*:\s*[^;]*(Inter|Noto|noto)/.test(m[0])) {
      const block=m[0].replace(/url\(\s*["']?([^\s"')]+)["']?\s*\)/g,(_,url)=>{
        const base='/_next/static/'+path.relative(root,file).split(path.sep).join('/');
        const u=new URL(url,'http://vdd-layout.invalid'+base);
        need(u.origin==='http://vdd-layout.invalid' && /^\/_next\/static\/media\/[^/]+\.(woff2?|ttf|otf)$/.test(u.pathname) && !u.search && !u.hash,'nonlocal font asset refused');
        const local=fs.realpathSync(path.join(root,u.pathname.slice('/_next/static/'.length)));
        need(local.startsWith(root+path.sep),'font path escape');
        const body=fs.readFileSync(local); assets.set(u.pathname,{body,sha256:hash(body),file:local});
        return `url("${u.pathname}")`;
      });
      blocks.add(block);
    }
  }
  need(variables.inter && variables['noto-sinhala'] && assets.size>=2,'actual compiled Inter/Noto assets unavailable');
  const globalFile=path.join(admin,'src/app/globals.css'), globals=fs.readFileSync(globalFile,'utf8');
  const sans=globals.match(/--font-sans\s*:\s*([^;]+);/)?.[1];
  need(sans?.includes('var(--font-inter)') && sans.includes('var(--font-noto-sinhala)'),'actual --font-sans mapping unavailable');
  const families=Object.values(variables).map(v=>v.split(',')[0].trim().replace(/^["']|["']$/g,''));
  return {assets,css:[...blocks,`:root{--font-inter:${variables.inter};--font-noto-sinhala:${variables['noto-sinhala']};--font-sans:${sans}}`].join('\n'),families,metadata:{status:'actual-local-assets',cssHashes,globalsSHA256:hash(globals),variables,sans,families,assets:[...assets].map(([url,a])=>({url,file:a.file,sha256:a.sha256}))}};
}

export async function createMeasurer({ admin = path.resolve(process.env.VIBHAGA_ADMIN ?? path.join(HERE, '..', '..', 'Vibhaga-Admin')), headed = false, fontStaticDirectory, allowProvisionalFonts = false } = {}) {
  let fonts;
  try { fonts=loadLocalFonts(admin,fontStaticDirectory); }
  catch(e) { need(allowProvisionalFonts,`font approval refused: ${e.message}`); fonts={assets:new Map(),css:'',families:[],metadata:{status:'provisional-fallback',reason:e.message}}; }
  const req = createRequire(path.join(admin, 'package.json'));
  for (const dep of ['esbuild', 'playwright', 'sharp', 'katex', 'react', 'react-dom']) {
    try { req.resolve(dep); } catch { throw new Error(`missing installed Admin dependency ${dep}; nothing will be installed`); }
  }
  const esbuild = req('esbuild'), { chromium } = req('playwright'), sharp = req('sharp');
  const bundle = await esbuild.build({ stdin: { contents: `import React from 'react'; import {createRoot} from 'react-dom/client'; import {flushSync} from 'react-dom'; import {DiagramRenderer} from '@/components/diagram/DiagramRenderer'; import {parseVddDocument} from '@vibhaga/shared/vdd-schema'; import {normalizeVdd} from '@/components/diagram/normalize'; const parse=(d)=>{const r=parseVddDocument(d);if(!r.ok)throw new Error('invalid VDD: '+r.errors.map(e=>e.message).join('; '));return r.value;}; const root=createRoot(document.getElementById('root')); window.paint=(d)=>{const p=parse(d); flushSync(()=>root.render(<DiagramRenderer dsl={p}/>));}; window.normalize=(d)=>normalizeVdd(parse(d)); window.normalizeAudited=(d)=>{const p=parse(d),unroundedCoordinates=[],round=Math.round;Math.round=(x)=>{unroundedCoordinates.push(x);return round(x);};try{return {document:normalizeVdd(p),unroundedCoordinates};}finally{Math.round=round;}};`, loader: 'tsx', resolveDir: admin }, bundle: true, write: false, format: 'iife', jsx: 'automatic', alias: { '@': path.join(admin, 'src') }, define: { 'process.env.NODE_ENV': '"production"' }, logLevel: 'silent' });
  const cssPath = req.resolve('katex/dist/katex.min.css');
  const browser = await chromium.launch({ headless: !headed });
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  const errors = [], blockedRequests=[];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog',d=>{errors.push('unexpected browser dialog');d.dismiss();});
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname !== 'vdd-layout.invalid' || route.request().method()!=='GET') {blockedRequests.push(u.href);return route.abort();}
    if (u.pathname === '/') return route.fulfill({ contentType: 'text/html', body: '<!doctype html><link rel="stylesheet" href="/katex.css"><link rel="stylesheet" href="/app-fonts.css"><style>html,body{margin:0;background:white;font-family:var(--font-sans,system-ui),sans-serif}.relative{position:relative}.absolute{position:absolute}.w-full{width:100%}.h-full{height:100%}.inset-0{inset:0}.overflow-hidden{overflow:hidden}.pointer-events-none{pointer-events:none}</style><div id="root"></div><script src="/bundle.js"></script>' });
    if (u.pathname === '/app-fonts.css') return route.fulfill({contentType:'text/css',body:fonts.css});
    if (fonts.assets.has(u.pathname)) return route.fulfill({body:fonts.assets.get(u.pathname).body});
    if (u.pathname === '/bundle.js') return route.fulfill({ contentType: 'text/javascript', body: Buffer.from(bundle.outputFiles[0].contents) });
    if (u.pathname === '/katex.css') return route.fulfill({ contentType: 'text/css', body: fs.readFileSync(cssPath) });
    if (/^\/fonts\/KaTeX_[A-Za-z0-9_-]+\.(woff2?|ttf)$/.test(u.pathname)) return route.fulfill({ body: fs.readFileSync(path.join(path.dirname(cssPath), u.pathname.slice(1))) });
    return route.abort();
  });
  try {
    await page.goto('http://vdd-layout.invalid/'); await page.waitForFunction(() => !!window.paint);
    fonts.metadata.resolvedFaces=await page.evaluate(async families=>{
      const out=[];
      for(const [i,family] of families.entries()) {
        const faces=await document.fonts.load(`18px "${family}"`,i?'සිංහල':'ABCxyz012');
        if(!faces.length || faces.some(f=>f.status!=='loaded')) throw new Error(`font not loaded: ${family}`);
        out.push(...faces.map(f=>({family:f.family,status:f.status,weight:f.weight,style:f.style})));
      }
      return out;
    },fonts.families);
  }
  catch (e) { await browser.close(); throw e; }
  async function measure(doc, width, { guard = 0, screenshot } = {}) {
    need(finite(width) && width > 0 && width <= 8192, 'measurement width outside 1..8192');
    const height = width * doc.canvas.height / doc.canvas.width;
    need(finite(height) && height > 0 && height + 2 * guard <= 8192 && width + 2 * guard <= 8192, 'measurement canvas exceeds 8192px; manually reduce uniform scale');
    await page.setViewportSize({ width: Math.ceil(width + 2 * guard), height: Math.ceil(height + 2 * guard) });
    await page.evaluate(({ doc, width, guard }) => {
      const root = document.getElementById('root'); root.style.width = `${width}px`; root.style.margin = `${guard}px`;
      window.paint(doc);
      root.querySelector('[role="img"]').style.overflow = guard ? 'visible' : 'hidden';
      root.querySelector('svg').style.overflow = guard ? 'visible' : 'hidden';
    }, { doc, width, guard });
    await page.evaluate(async () => { await document.fonts.ready; await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); });
    need(!errors.length, `renderer error: ${errors.join('; ')}`);
    const dom = await page.evaluate(() => {
      const root = document.querySelector('[role="img"]'), box = root.getBoundingClientRect();
      const labels = [...root.querySelectorAll('svg text, [data-vdd-math]')];
      const math = [...root.querySelectorAll('.katex')].map(e => e.parentElement);
      const unique = [...new Set([...labels, ...math])];
      return { labels: unique.map(e => {
        const b = e.getBoundingClientRect(); const transforms = [];
        for (let n=e; n && n!==root; n=n.parentElement) { const t=getComputedStyle(n).transform; if(t!=='none') transforms.push(t); }
        const upright = transforms.every(t => { const m=new DOMMatrix(t); return Math.abs(m.b)<1e-8 && Math.abs(m.c)<1e-8 && m.a>0 && m.d>0; });
        return { text: e.textContent, fontFamily:getComputedStyle(e).fontFamily, bounds: [b.left-box.left,b.top-box.top,b.right-box.left,b.bottom-box.top], upright, inside: b.left>=box.left-.1 && b.top>=box.top-.1 && b.right<=box.right+.1 && b.bottom<=box.bottom+.1 };
      }), mathErrors: root.querySelectorAll('.katex-error').length, security:{unsafeHtmlNodes:root.querySelectorAll('script,img,a').length,pwned:window.PWNED??null} };
    });
    need(!dom.mathErrors, 'KaTeX render error');
    const expectedLabels = doc.elements.filter(e => ['text','math'].includes(e.type) || e.type === 'point' && e.label).length;
    need(dom.labels.length === expectedLabels, 'renderer omitted a label');
    const png = await page.screenshot();
    await page.evaluate(d => window.paint({...d, elements: []}), doc);
    const blank = await page.screenshot();
    const { data, info } = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const background = await sharp(blank).ensureAlpha().raw().toBuffer();
    need(data.length === background.length, 'background measurement dimensions changed');
    let x0 = info.width, y0 = info.height, x1 = -1, y1 = -1;
    for (let y=0; y<info.height; y++) for (let x=0; x<info.width; x++) {
      const i = (y*info.width+x)*4;
      if (data[i] !== background[i] || data[i+1] !== background[i+1] || data[i+2] !== background[i+2]) {
        x0=Math.min(x0,x); y0=Math.min(y0,y); x1=Math.max(x1,x); y1=Math.max(y1,y);
      }
    }
    need(x1 >= x0, 'no rendered ink');
    const bounds = [x0-guard,y0-guard,x1+1-guard,y1+1-guard];
    const padding = { left: bounds[0], top: bounds[1], right: width-bounds[2], bottom: height-bounds[3] };
    if (screenshot) fs.writeFileSync(screenshot, png, { flag: 'wx' });
    return { bounds, padding, security:{...dom.security,blockedRequests:[...blockedRequests]}, centerResidualPx: [(bounds[0]+bounds[2]-width)/2,(bounds[1]+bounds[3]-height)/2], labels: dom.labels, allLabelsInside: dom.labels.every(l=>l.inside), glyphsUpright: dom.labels.every(l=>l.upright), measurementEdgeTouched: x0<=1 || y0<=1 || x1>=info.width-2 || y1>=info.height-2 };
  }
  return { measure, securityState:()=>page.evaluate(blocked=>({blockedRequests:blocked,scriptCount:document.scripts.length,imageCount:document.images.length,linkCount:document.querySelectorAll('a').length,pwned:window.PWNED??null}),blockedRequests), normalize: doc => page.evaluate(d => window.normalize(d), doc), normalizeAudited:doc=>page.evaluate(d=>window.normalizeAudited(d),doc), close: () => browser.close(), provenance: { engine: 'Chromium actual DiagramRenderer + KaTeX; RGB pixel difference from same empty canvas on white page; canvas background excluded', chromium: browser.version(), fonts:fonts.metadata, rendererSHA256: hash(fs.readFileSync(path.join(admin, 'src/components/diagram/DiagramRenderer.tsx'))), normalizeSHA256: hash(fs.readFileSync(path.join(admin, 'src/components/diagram/normalize.ts'))), katexCSSSHA256: hash(fs.readFileSync(cssPath)), pixelUncertainty: 1 } };
}

export function elementCoordinates(e) {
  if(e.points) return e.points;
  if(e.at) return [e.at];
  if(e.center) return [e.center];
  if(e.type==='path') return parsePath(e.d).flatMap(([cmd,a])=>{
    const out=[]; for(let i=cmd==='A'?5:0;i<a.length;i+=2) out.push(a.slice(i,i+2)); return out;
  });
  throw new Error(`unsupported coordinate extraction: ${e.type}`);
}
const stable = x => JSON.stringify(x,(_,v)=>v && typeof v==='object' && !Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);
const distance = (a,b) => Math.hypot(a[0]-b[0],a[1]-b[1]);
const cross = (a,b,c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const area = p => p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-a[1]*b[0];},0)/2;
function linearSubpaths(e) {
  if(e.points)return [{points:e.points,closed:e.type==='polygon',subpath:0}];
  if(e.type!=='path')return [];
  const out=[];let active,origin,cursor,subpath=0;
  const flush=()=>{if(active?.linear && active.points.length>1)out.push({points:active.points,closed:active.closed,subpath});if(active)subpath++;active=undefined;};
  for(const [cmd,a] of parsePath(e.d)) {
    if(cmd==='M') {flush();origin=a;cursor=a;active={points:[a],linear:true,closed:false};}
    else if(cmd==='Z') {if(active)active.closed=true;flush();cursor=origin;}
    else {
      if(!active)active={points:[cursor],linear:true,closed:false};
      cursor=a.slice(-2);active.points.push(cursor);if(cmd!=='L')active.linear=false;
    }
  }
  flush();return out;
}
function linearIntersectionEvents(segments, side) {
  const edges=segments.map(s=>s[side]);
  const magnitude=Math.max(1,...edges.flat(2).map(Math.abs));
  const tolerance=Math.max(1e-8,64*Number.EPSILON*magnitude);
  const lists=edges.map(()=>[{at:0,key:'start'},{at:1,key:'end'}]);
  let eventCount=0;
  const vector=(a,b)=>[b[0]-a[0],b[1]-a[1]],det=(u,v)=>u[0]*v[1]-u[1]*v[0];
  const add=(i,j,t,u,key)=>{
    need(finite(t)&&finite(u),'nonfinite linear intersection event');
    need(++eventCount<=20000,'linear arrangement exceeds 20000 events; explicit split/check required');
    lists[i].push({at:Math.max(0,Math.min(1,t)),key});lists[j].push({at:Math.max(0,Math.min(1,u)),key});
  };
  for(let i=0;i<edges.length;i++)for(let j=0;j<i;j++) {
    const [a,b]=edges[i],[c,d]=edges[j],r=vector(a,b),s=vector(c,d),v=vector(a,c),lr=distance(a,b),ls=distance(c,d);
    if(lr<=tolerance||ls<=tolerance)continue;
    const denominator=det(r,s),roundoff=64*Number.EPSILON*(Math.abs(r[0]*s[1])+Math.abs(r[1]*s[0]));
    if(Math.abs(denominator)>roundoff) {
      const t=det(v,s)/denominator,u=det(v,r)/denominator;
      if(t>=-tolerance/lr&&t<=1+tolerance/lr&&u>=-tolerance/ls&&u<=1+tolerance/ls)add(i,j,t,u,`${j}:${i}:0`);
    } else if(Math.abs(det(v,r))/lr<=tolerance && Math.abs(cross(a,b,d))/lr<=tolerance) {
      const project=p=>((p[0]-a[0])*r[0]+(p[1]-a[1])*r[1])/(lr*lr);
      const tc=project(c),td=project(d),lo=Math.max(0,Math.min(tc,td)),hi=Math.min(1,Math.max(tc,td));
      if(lo>hi+tolerance/lr)continue;
      const positions=(hi-lo)*lr<=tolerance?[(lo+hi)/2]:[lo,hi];
      positions.forEach((t,k)=>{const p=[a[0]+t*r[0],a[1]+t*r[1]],u=((p[0]-c[0])*s[0]+(p[1]-c[1])*s[1])/(ls*ls);add(i,j,t,u,`${j}:${i}:${k}`);});
    }
  }
  const strokes=lists.map((events,i)=>{
    const [a,b]=edges[i],length=distance(a,b),groups=[];
    events.sort((p,q)=>p.at-q.at||p.key.localeCompare(q.key));
    for(const event of events) {
      const last=groups.at(-1);
      if(last && (event.at-last.at)*length<=tolerance)last.events.push(event.key);
      else groups.push({at:event.at,point:[a[0]+event.at*(b[0]-a[0]),a[1]+event.at*(b[1]-a[1])],events:[event.key]});
    }
    groups.forEach(g=>g.events.sort());
    return {id:segments[i].id,subpath:segments[i].subpath,edge:segments[i].edge,groups};
  });
  return {toleranceWorld:tolerance,eventCount,strokes};
}
function pointRef(doc, ref) {
  need(Array.isArray(ref) && ref.length===2,'critical point reference must be [elementId,coordinateIndex]');
  const e=doc.elements.find(e=>e.id===ref[0]),p=e && elementCoordinates(e)[ref[1]];
  need(p,'critical point reference does not resolve'); return p;
}
function criticalChecks(stored,normalized,critical) {
  const failures=[];
  for(const c of critical) {
    need(['incidence','collinear','perpendicular','onSegment','tangent'].includes(c.kind),'unsupported critical constraint; manual S6b check required');
    const evaluate=doc=>{
      const p=c.points.map(r=>pointRef(doc,r));
      if(c.kind==='incidence') { need(p.length===2,'incidence needs 2 points'); return distance(...p); }
      if(c.kind==='collinear') { need(p.length===3,'collinear needs 3 points'); return offLine(...p); }
      if(c.kind==='onSegment') { need(p.length===3,'onSegment needs [point,start,end]'); return onSegment(...p,1e-8)?0:1; }
      if(c.kind==='perpendicular') { need(p.length===3,'perpendicular needs [first,vertex,last]'); return Math.abs(angleAt(...p)-90); }
      const circle=doc.elements.find(e=>e.id===c.circle);
      need(circle?.type==='circle' && p.length===2,'tangent needs circle ID and two line points');
      const length=distance(...p); need(length>0,'collapsed tangent');
      return Math.abs(Math.abs(cross(p[0],p[1],circle.center))/length-circle.r)/Math.max(circle.r,1);
    };
    need(evaluate(stored)<=1e-7,`critical ${c.kind} is not true in stored geometry`);
    if(!(evaluate(normalized)<=1e-7)) failures.push(`critical ${c.kind} incidence regression`);
  }
  return failures;
}
export function normalizationIntegrity(stored, normalized, {band='vector', maxCssError=2, critical=[], unroundedCoordinates}={}) {
  need(['vector','raster'].includes(band),'band must be vector or raster');
  need(finite(maxCssError) && maxCssError>0 && maxCssError<=4,'quantization CSS budget must be >0 and <=4px');
  const angleBand=band==='vector'?1:3, ratioBand=band==='vector'?.02:.05, failures=[], pairs=[], segments=[];
  const signature=e=>{const out=copy(e);delete out.points;delete out.at;delete out.center;if(out.d)out.d=parsePath(out.d).map(([c,a])=>[c,c==='A'?a.slice(0,5):[]]);return stable(out);};
  need(stored.elements.length===normalized.elements.length,'normalize changed element count');
  stored.elements.forEach((e,i)=>{
    const n=normalized.elements[i];need(signature(e)===signature(n),`normalize changed non-position fields/arc flags on ${e.id}`);
    const a=elementCoordinates(e),b=elementCoordinates(n);need(a.length===b.length,'normalize changed coordinate count');
    a.forEach((p,j)=>pairs.push({id:e.id,index:j,stored:p,normalized:b[j],delta:[b[j][0]-p[0],b[j][1]-p[1]]}));
    const chains=linearSubpaths(e),normalizedChains=linearSubpaths(n);
    need(chains.length===normalizedChains.length,'normalize changed linear subpath count');
    for(let ci=0;ci<chains.length;ci++) {
      let a=chains[ci].points,b=normalizedChains[ci].points;
      const closed=chains[ci].closed;
      need(a.length===b.length&&closed===normalizedChains[ci].closed,'normalize changed linear subpath structure');
      if(closed&&distance(a[0],a.at(-1))===0){a=a.slice(0,-1);b=b.slice(0,-1);}
      const count=closed?a.length:a.length-1;
      for(let j=0;j<count;j++) {
        const k=(j+1)%a.length, before=distance(a[j],a[k]), after=distance(b[j],b[k]);
        if(before<=1e-9 || after<=1e-9) failures.push(`${e.id}: collapsed edge`);
        else if(Math.abs(after/before-1)>ratioBand) failures.push(`${e.id}: edge length exceeds ${band} ratio band`);
        segments.push({id:e.id,subpath:chains[ci].subpath,edge:j,a:[a[j],a[k]],b:[b[j],b[k]]});
        if(closed || j>0) {
          const h=(j+a.length-1)%a.length, error=Math.abs(angleAt(a[h],a[j],a[k])-angleAt(b[h],b[j],b[k]));
          if(!finite(error)||error>angleBand) failures.push(`${e.id}: angle exceeds ${band} band`);
        }
      }
      if(closed && (Math.abs(area(a))<=1e-9 || area(a)*area(b)<=0)) failures.push(`${e.id}: collapsed/reversed winding`);
      if(e.type==='arrow') {
        const u=[a.at(-1)[0]-a[0][0],a.at(-1)[1]-a[0][1]],v=[b.at(-1)[0]-b[0][0],b.at(-1)[1]-b[0][1]];
        if(u[0]*v[0]+u[1]*v[1]<=0) failures.push(`${e.id}: arrow direction reversed/collapsed`);
      }
    }
  });
  need(pairs.length<=4000,'quantization topology budget exceeds 4000 coordinates');
  for(let i=0;i<pairs.length;i++) for(let j=0;j<i;j++) {
    const same=distance(pairs[i].stored,pairs[j].stored)<=1e-8, sameAfter=distance(pairs[i].normalized,pairs[j].normalized)<=1e-8;
    if(same!==sameAfter) failures.push(same?'shared endpoint/label binding split':'distinct coordinates collapsed');
  }
  const relation=([a,b],[c,d])=>{
    if(onSegment(a,c,d,1e-9)||onSegment(b,c,d,1e-9)||onSegment(c,a,b,1e-9)||onSegment(d,a,b,1e-9))return 'touch';
    const x=cross(a,b,c),y=cross(a,b,d),z=cross(c,d,a),w=cross(c,d,b);
    if(x*y< -1e-12 && z*w< -1e-12)return 'cross';
    return 'apart';
  };
  for(let i=0;i<segments.length;i++)for(let j=0;j<i;j++)if(relation(segments[i].a,segments[j].a)!==relation(segments[i].b,segments[j].b))failures.push('linear intersection topology/order changed');
  const linearArrangement={stored:linearIntersectionEvents(segments,'a'),normalized:linearIntersectionEvents(segments,'b')};
  const eventSignature=arrangement=>arrangement.strokes.map(s=>s.groups.map(g=>g.events));
  if(stable(eventSignature(linearArrangement.stored))!==stable(eventSignature(linearArrangement.normalized)))failures.push('linear intersection event order/coincidence changed');
  const unchanged=pairs.every(p=>p.stored.every((v,k)=>v===p.normalized[k]));
  const uniformTranslation=pairs.every(p=>p.delta.every((v,k)=>Math.abs(v-pairs[0].delta[k])<=4*Number.EPSILON*Math.max(1,Math.abs(p.stored[k])+Math.abs(p.normalized[k])+Math.abs(pairs[0].stored[k])+Math.abs(pairs[0].normalized[k]))));
  const unquantized=uniformTranslation && !unroundedCoordinates?.length;
  const intervals=[0,1].map(k=>[Math.max(...pairs.map(p=>p.delta[k]-.5)),Math.min(...pairs.map(p=>p.delta[k]+.5))]);
  let translation=unquantized?(pairs[0]?.delta??[0,0]):intervals.map(([lo,hi])=>(lo+hi)/2);
  let translationIdentification=unquantized?'coordinate deltas identify a common translation within IEEE-754 roundoff; direct API has no runtime audit':'feasible interval midpoint only; direct API has no runtime audit';
  let auditValid=true;
  if(unroundedCoordinates!==undefined) {
    need(Array.isArray(unroundedCoordinates)&&unroundedCoordinates.every(finite),'invalid runtime rounding audit');
    translationIdentification='actual synchronous Math.round input arguments from the real normalizer; original Math.round invoked and restored in finally';
    if(unroundedCoordinates.length===0) {auditValid=uniformTranslation;translationIdentification='no synchronous Math.round calls observed; coordinate deltas checked for common translation within IEEE-754 roundoff';}
    else {
      auditValid=unroundedCoordinates.length===pairs.length*2;
      translation=[0,1].map(k=>unroundedCoordinates[k]-pairs[0].stored[k]);
      auditValid=auditValid&&pairs.every((p,i)=>p.stored.every((v,k)=>Math.abs(unroundedCoordinates[2*i+k]-v-translation[k])<1e-7));
    }
  }
  const modelValid=auditValid && (unquantized || intervals.every(([lo,hi])=>hi>lo-1e-10) && pairs.every((p,i)=>p.normalized.every((v,k)=>Number.isInteger(v) && Math.round(unroundedCoordinates?.length?unroundedCoordinates[2*i+k]:p.stored[k]+translation[k])===v)));
  if(!modelValid)failures.push('normalize does not match a precision-preserving common translation or common translation followed by per-coordinate integer quantization');
  pairs.forEach(p=>{p.roundingError=p.delta.map((v,k)=>v-translation[k]);});
  const maximumAbsoluteRoundingPerAxis=[0,1].map(k=>Math.max(...pairs.map(p=>Math.abs(p.delta[k]-translation[k]))));
  const maximumAbsoluteRoundingWorld=Math.max(...pairs.map(p=>Math.hypot(p.delta[0]-translation[0],p.delta[1]-translation[1])));
  const maximumRigidTranslationResidualCanvas=Math.max(...pairs.map(p=>distance(p.delta,pairs[0].delta)));
  const screen=[320,375,768].map(width=>({width,absoluteRoundingCssPx:maximumAbsoluteRoundingWorld*width/normalized.canvas.width,firstPointRelativeCssPx:maximumRigidTranslationResidualCanvas*width/normalized.canvas.width}));
  if(screen.some(r=>r.absoluteRoundingCssPx>maxCssError))failures.push(`normalized coordinate error exceeds measured ${maxCssError}px screen budget`);
  failures.push(...criticalChecks(stored,normalized,critical));
  return {model:unchanged?'unchanged':unquantized?'common-translation':'common-translation-then-Math.round',translation,translationFeasibleIntervals:intervals,translationIdentification,audited:unroundedCoordinates!==undefined,modelValid,maximumAbsoluteRoundingPerAxis,maximumAbsoluteRoundingWorld,maximumRigidTranslationResidualCanvas,screen,maxCssError,band,critical,linearArrangement,failures:[...new Set(failures)],pairs,anchorsPolicy:'Stored sidecar only; normalized claim anchors must bind to actual normalized element coordinates, never stale meta.anchors.'};
}
function claimChecks(source,stored,normalized,anchors,matrix,claimsText,band) {
  if(!claimsText)return {status:'required-later-S6b',semanticApproval:false,failures:[]};
  const cs=parseClaimSet(claimsText), corrected=transformAnchors(anchors,matrix), actual={};
  for(const [name,p] of Object.entries(corrected)) {
    const candidates=[];
    stored.elements.forEach((e,i)=>elementCoordinates(e).forEach((q,j)=>{if(distance(p,q)<1e-7)candidates.push(elementCoordinates(normalized.elements[i])[j]);}));
    need(candidates.length && candidates.every(q=>distance(q,candidates[0])<1e-7),`claim anchor ${name} needs an unambiguous actual geometry binding`); actual[name]=candidates[0];
  }
  const before=evalClaims(cs,anchors), exact=evalClaims(cs,corrected), after=evalClaims(cs,actual), failures=[];
  need(before.length===cs.claims.length && after.length===before.length,'unsupported/missing claim; complete S6b validation required');
  before.forEach((a,i)=>{
    need(finite(a.value)&&finite(exact[i].value)&&Math.abs(a.value-exact[i].value)<1e-7,'input-to-stored claim not preserved by exact similarity');
    const b=after[i],budget=a.kind==='angle'?(band==='raster'?3:1):(band==='raster'?.05:.02);
    const delta=a.kind==='ratio'?Math.abs(b.value/a.value-1):Math.abs(b.value-a.value);
    if(!finite(delta)||delta>budget)failures.push(`claim ${a.id}: normalization exceeds ${band} band`);
  });
  return {status:'numeric-preservation-checked; full S6b coverage/source/stated-value checks still required',semanticApproval:false,before,stored:exact,normalized:after,failures};
}

export async function layout(document, anchors, config, measurer) {
  keys(config, ['angleDegrees', 'pivot', 'reference', 'scale', 'framing', 'canvas', 'padding', 'centerTolerancePx', 'band', 'quantizationBudgetPx', 'critical', 'claimsText'], 'config');
  need(typeof config.reference === 'string' && config.reference.trim(), 'orientation reference metadata is required; no automatic orientation inference');
  need(config.framing?.mode === 'bounded-artwork' && typeof config.framing.declaration === 'string' && config.framing.declaration.trim(), 'bounded single-figure mode only; unbounded apparatus requires semantic-viewport regeneration certificate, not a bounded attestation');
  keys(config.framing,['mode','declaration'],'bounded framing');
  need(!inputDeclaresUnbounded(document),'declared unbounded apparatus cannot bypass semantic-viewport certification');
  need(xy(config.canvas) && config.canvas.every(n=>n>=80 && n<=4096), 'canvas must be [width,height], each 80..4096');
  const padding = config.padding ?? 32, tolerance = config.centerTolerancePx ?? 3;
  need(finite(padding) && padding >= 8 && padding < Math.min(...config.canvas)/2, 'padding must be at least 8 and below half canvas');
  need(finite(tolerance) && tolerance >= 1 && tolerance <= 4, 'centerTolerancePx must be 1..4');
  const rawMatrix = similarity(config);
  transformAnchors(anchors, rawMatrix);
  if (document.meta?.anchors) {
    const embedded = Object.entries(document.meta.anchors).sort(([a],[b])=>a.localeCompare(b));
    const sidecar = Object.entries(anchors).sort(([a],[b])=>a.localeCompare(b));
    need(JSON.stringify(embedded) === JSON.stringify(sidecar), 'meta.anchors and raw sidecar disagree; reconcile explicitly');
  }
  const turned = transformDocument(document, rawMatrix), envelope = coordinateEnvelope(turned);
  const span = Math.max(envelope[2]-envelope[0],envelope[3]-envelope[1]);
  const side = Math.ceil(Math.max(1024, span*3+1024));
  need(side <= 8192, 'provisional canvas exceeds 8192; explicitly reduce scale');
  const provisionalMatrix = similarity({ angleDegrees: 0, pivot: [0,0], translation: [side/2-(envelope[0]+envelope[2])/2,side/2-(envelope[1]+envelope[3])/2] });
  const provisional = transformDocument(turned, provisionalMatrix);
  provisional.canvas = { ...provisional.canvas, width: side, height: side };
  const ink = await measurer.measure(provisional, side);
  need(!ink.measurementEdgeTouched && ink.allLabelsInside, 'provisional measurement may clip ink; reduce scale or regenerate; no guessed bounds accepted');
  const [x0,y0,x1,y1] = ink.bounds, [width,height] = config.canvas;
  const fitScale = Math.min((width-2*padding)/(x1-x0), (height-2*padding)/(y1-y0));
  const fitMatrix = similarity({ angleDegrees: 0, pivot: [0,0], scale: fitScale, translation: [width/2-fitScale*(x0+x1)/2,height/2-fitScale*(y0+y1)/2] });
  let matrix = compose(fitMatrix, compose(provisionalMatrix, rawMatrix));
  let result;
  for (let attempt=0; attempt<3; attempt++) {
    result = transformDocument(document, matrix); result.canvas = { ...result.canvas, width, height };
    const measured = await measurer.measure(result, width, { guard: 128 });
    const [dx,dy] = measured.centerResidualPx;
    if (Math.max(Math.abs(dx),Math.abs(dy)) <= .6) break;
    matrix = compose(similarity({angleDegrees:0,pivot:[0,0],translation:[-dx,-dy]}),matrix);
  }
  result = transformDocument(document, matrix); result.canvas = { ...result.canvas, width, height };
  const corrected=transformAnchors(anchors,matrix);result.meta.anchors=copy(corrected);
  const audit=await measurer.normalizeAudited(result), normalized=audit.document, reports = [], failures = [];
  const normalization = normalizationIntegrity(result, normalized, {band:config.band??'vector',maxCssError:config.quantizationBudgetPx??2,critical:config.critical??[],unroundedCoordinates:audit.unroundedCoordinates});
  failures.push(...normalization.failures.map(f=>`normalizeVdd: ${f}`));
  if(measurer.provenance.fonts?.status!=='actual-local-assets')failures.push('font measurement is provisional; actual Inter/Noto recheck required');
  const claims=claimChecks(document,result,normalized,anchors,matrix,config.claimsText,config.band??'vector');
  failures.push(...claims.failures);
  for (const [surface, doc] of [['stored',result],['normalizeVdd',normalized]]) {
    for (const w of [320,375,768]) {
      const measured = await measurer.measure(doc, w, { guard: 256 });
      const report = { surface, width: w, canvas: doc.canvas, quantization:surface==='stored'?{absoluteRoundingCssPx:0,firstPointRelativeCssPx:0}:normalization.screen.find(r=>r.width===w), ...measured }; reports.push(report);
      if (measured.measurementEdgeTouched) failures.push(`${surface}/${w}: measurement guard exhausted`);
      if (!measured.allLabelsInside) failures.push(`${surface}/${w}: label outside canvas`);
      if (!measured.glyphsUpright) failures.push(`${surface}/${w}: glyph baseline not upright`);
      if (Math.min(...Object.values(measured.padding)) < 1) failures.push(`${surface}/${w}: painted ink clips canvas or lacks 1px clearance`);
      if (Math.max(...measured.centerResidualPx.map(Math.abs)) > tolerance) failures.push(`${surface}/${w}: center residual exceeds ${tolerance}px`);
    }
  }
  const provenance = { version: 1, metadataContract:METADATA_CONTRACT, config: copy(config), matrixConvention: '[a,b,c,d,e,f]: x\u2032=a*x+c*y+e, y\u2032=b*x+d*y+f; clockwise screen coordinates; no reflection', matrix, determinant: matrix[0]*matrix[3]-matrix[1]*matrix[2], glyphPolicy: 'source binding positions and point label offsets transformed; glyph baselines upright; sizes uniformly scaled', framingPolicy: 'finite visible artwork only; caller is responsible for semantic regeneration of unbounded shading and plots', sharedFrame: 'Use measureUnion/fitMeasuredUnion/validateCommonFrame for extending pairs; independent layout() calls cannot establish a common frame', normalizationPolicy: 'measured and refused on framing defects; no invisible anchors or normalizer changes', measurement: measurer.provenance, provisionalInk: ink.bounds, normalization, claims, semanticApproval:false, requiredNextGate:'S6b source/claim-set coverage and critical mathematical checks plus fresh visual critique; layout approval is not mathematical approval', reports, failures, approved: failures.length === 0 };
  return { document: result, anchors: corrected, provenance };
}

export async function measureUnion(documents, width, measurer) {
  need(documents.length>0 && documents.every(d=>d.canvas.width===documents[0].canvas.width && d.canvas.height===documents[0].canvas.height),'union requires one common canvas');
  const members=[];for(const d of documents)members.push(await measurer.measure(d,width,{guard:256}));
  const bounds=[Math.min(...members.map(m=>m.bounds[0])),Math.min(...members.map(m=>m.bounds[1])),Math.max(...members.map(m=>m.bounds[2])),Math.max(...members.map(m=>m.bounds[3]))];
  const height=width*documents[0].canvas.height/documents[0].canvas.width;
  return {width,bounds,centerResidualPx:[(bounds[0]+bounds[2]-width)/2,(bounds[1]+bounds[3]-height)/2],padding:{left:bounds[0],top:bounds[1],right:width-bounds[2],bottom:height-bounds[3]},members};
}
export function fitMeasuredUnion(bounds, canvas, padding=32) {
  need(Array.isArray(bounds)&&bounds.length===4&&bounds.every(finite)&&xy(canvas)&&finite(padding)&&padding>=8,'invalid union fit');
  const [x0,y0,x1,y1]=bounds,[w,h]=canvas;
  need(x1>x0 && y1>y0 && w>2*padding && h>2*padding,'singular union fit');
  const scale=Math.min((w-2*padding)/(x1-x0),(h-2*padding)/(y1-y0));
  return similarity({angleDegrees:0,pivot:[0,0],scale,translation:[w/2-scale*(x0+x1)/2,h/2-scale*(y0+y1)/2]});
}
export const documentDigest = document => hash(stable(document));
function validateSemanticViewport(viewport) {
  need(Array.isArray(viewport)&&viewport.length===4&&viewport.every(finite)&&viewport[2]>viewport[0]&&viewport[3]>viewport[1],'invalid semantic viewport');
}
export function clipHalfPlanes(viewport, inequalities) {
  validateSemanticViewport(viewport);
  need(Array.isArray(inequalities)&&inequalities.length>0,'half-plane inequalities required');
  let polygon=[[viewport[0],viewport[1]],[viewport[2],viewport[1]],[viewport[2],viewport[3]],[viewport[0],viewport[3]]];
  for(const coefficients of inequalities) {
    need(Array.isArray(coefficients)&&coefficients.length===3&&coefficients.every(finite)&&Math.hypot(coefficients[0],coefficients[1])>0,'expected [a,b,c] for a*x+b*y<=c');
    const [a,b,c]=coefficients, value=p=>a*p[0]+b*p[1]-c, out=[];
    for(let i=0;i<polygon.length;i++) {
      const p=polygon[i],q=polygon[(i+1)%polygon.length],u=value(p),v=value(q);
      if(u<=0)out.push(p);
      if((u<0&&v>0)||(u>0&&v<0)){const t=u/(u-v);out.push([p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])]);}
    }
    polygon=out.filter((p,i)=>!i||distance(p,out[i-1])>1e-8);
    if(polygon.length>1&&distance(polygon[0],polygon.at(-1))<1e-8)polygon.pop();
  }
  return polygon;
}
export function validateViewportCertificate(document, certificate, viewport) {
  validateSemanticViewport(viewport);
  need(certificate?.kind==='half-plane-viewport-v1' && typeof certificate.reference==='string' && certificate.reference.trim(),'explicit caller regeneration certificate required');
  need(certificate.documentSHA256===documentDigest(document) && stable(certificate.viewport)===stable(viewport),'regeneration certificate does not bind this document and chosen viewport');
  need(Array.isArray(certificate.regions),'certificate regions must be an array');
  const unshaded=Object.hasOwn(certificate,'unshaded');
  if(unshaded)need(certificate.unshaded===true && certificate.regions.length===0,'unshaded attestation must be literal true with regions: []; mixed certificates are refused');
  else need(certificate.regions.length>0,'empty regions require explicit unshaded: true attestation');
  const areas=document.elements.filter(e=>['polygon','rect','path','circle'].includes(e.type));
  const opacity=value=>need(value===undefined || finite(value)&&value>=0&&value<=1,'area classifier opacity must be a finite number in [0,1], without coercion');
  const color=value=>need(value===undefined || typeof value==='string','area classifier color must be a string, without coercion');
  opacity(document.defaults?.opacity);color(document.defaults?.fillColor);
  for(const e of areas) {
    need(e.fill===undefined || e.fill!==null && typeof e.fill==='object' && !Array.isArray(e.fill),'area classifier fill must be an object');
    opacity(e.opacity);opacity(e.fill?.opacity);color(e.fill?.color);
  }
  const filled=areas.filter(e=>(e.fill?.opacity??1)*(e.opacity??document.defaults?.opacity??1)>0 && !['none','transparent'].includes(e.fill?.color??document.defaults?.fillColor??'none'));
  if(unshaded) {
    need(filled.length===0,'unshaded certificate requires no visible area fills under the area classifier');
    return {validated:true,kind:certificate.kind,documentSHA256:certificate.documentSHA256,viewport,unshaded:true,regions:[],areaFillCount:0,markerPolicy:'Typed point markers and arrowheads are not polygon/rect/path/circle area-fill regions; unshaded does not mean zero rendered ink.'};
  }
  need(new Set(certificate.regions.map(r=>r.elementId)).size===certificate.regions.length && filled.length===certificate.regions.length && filled.every(e=>certificate.regions.some(r=>r.elementId===e.id)),'every visible area fill must be a certified half-plane region; masks/other plot fills need a separately supported generator');
  for(const region of certificate.regions) {
    const element=filled.find(e=>e.id===region.elementId), expected=clipHalfPlanes(viewport,region.inequalities);
    need(element?.type==='polygon' && !element.rotation && expected.length>=3,'certified fill must be a nonempty regenerated polygon');
    const p=element.points;
    const cyclic=target=>p.length===target.length&&target.some((_,start)=>p.every((q,i)=>distance(q,target[(start+i)%target.length])<1e-7));
    need(cyclic(expected)||cyclic([...expected].reverse()),`region ${region.elementId} does not fill the chosen half-plane viewport; finite rotated shading would leave holes`);
  }
  return {validated:true,kind:certificate.kind,documentSHA256:certificate.documentSHA256,viewport,regions:certificate.regions};
}
function boundAnchor(stored,normalized,p) {
  const found=[];stored.elements.forEach((e,i)=>elementCoordinates(e).forEach((q,j)=>{if(distance(q,p)<1e-7)found.push(elementCoordinates(normalized.elements[i])[j]);}));
  need(found.length && found.every(q=>distance(q,found[0])<1e-7),'common pitch/correspondence anchor needs an actual shared geometry binding');return found[0];
}
export async function validateCommonFrame(members, frame, measurer) {
  keys(frame,['mode','matrix','canvas','reference','sourceFrame','pitch','sharedAnchors','viewport','sourceOrientation','orientation','band','critical','quantizationBudgetPx','centerTolerancePx'],'common frame');
  need(['common-frame','semantic-viewport'].includes(frame.mode),'explicit common-frame or semantic-viewport mode required');
  need(Array.isArray(members)&&members.length>=(frame.mode==='common-frame'?2:1)&&new Set(members.map(m=>m.id)).size===members.length,'distinct common-frame members required');
  need(typeof frame.reference==='string'&&frame.reference.trim()&&typeof frame.sourceFrame==='string'&&frame.sourceFrame.trim(),'explicit shared source frame and reference required');
  validateMatrix(frame.matrix);need(xy(frame.canvas)&&frame.canvas.every(n=>n>=80&&n<=4096),'invalid shared canvas');
  need(Array.isArray(frame.pitch)&&frame.pitch.length===2&&Array.isArray(frame.sharedAnchors)&&frame.sharedAnchors.length>=2,'pitch and at least two common anchor names required');
  const failures=[], prepared=[], normalization=[], certificates=[];
  for(const m of members) {
    need(typeof m.id==='string'&&m.id.trim(),'member ID must be nonempty text');
    transformAnchors(m.anchors,frame.matrix);
    need(!m.document.meta?.anchors||stable(m.document.meta.anchors)===stable(m.anchors),'member meta.anchors and raw sidecar disagree');
  }
  const names=[...new Set([...frame.pitch,...frame.sharedAnchors])];
  for(const name of names) {
    need(members.every(m=>xy(m.anchors[name])),'common anchor missing');
    need(members.every(m=>distance(m.anchors[name],members[0].anchors[name])<1e-8),'members do not have one common source frame');
  }
  need(distance(...frame.pitch.map(n=>members[0].anchors[n]))>0,'zero common pitch');
  const proportions=m=>({fontSize:m.document.defaults?.fontSize??18,strokeWidth:m.document.defaults?.strokeWidth??2,fontFamily:m.document.defaults?.fontFamily??'sans'});
  need(members.every(m=>stable(proportions(m))===stable(proportions(members[0]))),'common default typographic/stroke proportions differ');
  const styles=(e,d)=>({type:e.type,fontSize:e.fontSize??d.defaults?.fontSize??18,fontFamily:e.fontFamily??d.defaults?.fontFamily??'sans',strokeWidth:e.stroke?.width??d.defaults?.strokeWidth??2,headSize:e.headSize,pointRadius:e.type==='point'?(e.r??3.5):undefined});
  for(let i=1;i<members.length;i++)for(const e of members[0].document.elements) {
    const other=members[i].document.elements.find(q=>q.id===e.id);
    need(!other||stable(styles(e,members[0].document))===stable(styles(other,members[i].document)),'corresponding apparatus changed typographic/stroke/head proportions');
  }
  if(frame.mode==='semantic-viewport') {
    need(Math.abs(frame.matrix[1])<1e-12&&Math.abs(frame.matrix[2])<1e-12&&frame.matrix[0]>0,'semantic viewport accepts already regenerated mathematical axes, never rotation of finite fill');
    need(typeof frame.sourceOrientation?.reference==='string' && frame.sourceOrientation.reference.trim() && xy(frame.sourceOrientation.pivot) && finite(frame.sourceOrientation.angleDegrees),'explicit source orientation provenance required, not applied to regenerated apparatus');
    for(const m of members)certificates.push(validateViewportCertificate(m.document,m.certificate,frame.viewport));
    const [x0,y0,x1,y1]=frame.viewport, a=mapPoint(frame.matrix,[x0,y0]),b=mapPoint(frame.matrix,[x1,y1]);
    need(a[0]>=8&&a[1]>=8&&b[0]<=frame.canvas[0]-8&&b[1]<=frame.canvas[1]-8,'chosen viewport requires visible apparatus padding');
  } else {
    need(!members.some(m=>m.certificate||inputDeclaresUnbounded(m.document)),'use semantic-viewport mode for regenerated unbounded apparatus');
    need(typeof frame.orientation?.reference==='string' && frame.orientation.reference.trim() && xy(frame.orientation.pivot) && finite(frame.orientation.angleDegrees),'explicit common angle/pivot/reference metadata required');
    keys(frame.orientation,['angleDegrees','pivot','reference'],'common orientation');
    const expected=similarity(frame.orientation),s=Math.hypot(frame.matrix[0],frame.matrix[1]);
    need(Math.abs(frame.matrix[0]/s-expected[0])<1e-8&&Math.abs(frame.matrix[1]/s-expected[1])<1e-8,'common matrix does not match supplied orientation angle');
  }
  for(const m of members) {
    const document=transformDocument(m.document,frame.matrix);document.canvas={...document.canvas,width:frame.canvas[0],height:frame.canvas[1]};
    const anchors=transformAnchors(m.anchors,frame.matrix);document.meta.anchors=copy(anchors);
    const audit=await measurer.normalizeAudited(document), n=audit.document;
    const integrity=normalizationIntegrity(document,n,{band:frame.band??'vector',critical:frame.critical??[],maxCssError:frame.quantizationBudgetPx??2,unroundedCoordinates:audit.unroundedCoordinates});
    failures.push(...integrity.failures.map(f=>`${m.id}: ${f}`));normalization.push(integrity);prepared.push({id:m.id,document,anchors,normalized:n});
  }
  const reports=[];
  for(const surface of ['stored','normalizeVdd']) {
    const documents=prepared.map(m=>surface==='stored'?m.document:m.normalized), sameCanvas=documents.every(d=>d.canvas.width===documents[0].canvas.width&&d.canvas.height===documents[0].canvas.height);
    if(!sameCanvas)failures.push(`${surface}: independent normalization changed common viewport/range`);
    for(const width of [320,375,768]) {
      const measurements=[];for(const d of documents)measurements.push(await measurer.measure(d,width,{guard:256}));
      const bounds=[Math.min(...measurements.map(r=>r.bounds[0])),Math.min(...measurements.map(r=>r.bounds[1])),Math.max(...measurements.map(r=>r.bounds[2])),Math.max(...measurements.map(r=>r.bounds[3]))];
      const height=width*documents[0].canvas.height/documents[0].canvas.width,centerResidualPx=[(bounds[0]+bounds[2]-width)/2,(bounds[1]+bounds[3]-height)/2];
      const coordinates=prepared.map((m,i)=>Object.fromEntries(names.map(name=>[name,(surface==='stored'?m.anchors[name]:boundAnchor(m.document,m.normalized,m.anchors[name])).map(v=>v*width/documents[i].canvas.width)])));
      const pitchCssPx=coordinates.map(c=>distance(...frame.pitch.map(n=>c[n])));
      if(pitchCssPx.some(p=>Math.abs(p-pitchCssPx[0])>1e-6)||coordinates.some(c=>names.some(n=>distance(c[n],coordinates[0][n])>1e-6)))failures.push(`${surface}/${width}: independent framing broke common translation/pitch/correspondence`);
      measurements.forEach((r,i)=>{if(r.measurementEdgeTouched||!r.allLabelsInside||!r.glyphsUpright||Math.min(...Object.values(r.padding))<1)failures.push(`${surface}/${width}/${members[i].id}: ink/label clipping or baseline failure`);});
      if(frame.mode==='common-frame'&&Math.max(...centerResidualPx.map(Math.abs))>(frame.centerTolerancePx??3))failures.push(`${surface}/${width}: shared union is not centered`);
      reports.push({surface,width,commonCanvas:sameCanvas,bounds,centerResidualPx,pitchCssPx,coordinates,members:measurements,quantization:surface==='stored'?normalization.map(()=>({absoluteRoundingCssPx:0})):normalization.map(n=>n.screen.find(r=>r.width===width))});
    }
  }
  if(measurer.provenance.fonts?.status!=='actual-local-assets')failures.push('provisional fonts cannot approve a common frame');
  const provenance={version:2,metadataContract:METADATA_CONTRACT,mode:frame.mode,memberIds:members.map(m=>m.id),frame:copy(frame),matrix:frame.matrix,sourceDocuments:members.map(m=>({id:m.id,documentSHA256:documentDigest(m.document),canonicalAnchorsSHA256:hash(stable(m.anchors))})),measurement:measurer.provenance,normalization,certificates,reports,failures:[...new Set(failures)],approved:failures.length===0,semanticApproval:false,requiredNextGate:'S6b claim/source/coverage and critical incidence checks plus fresh visual critique',centeringException:frame.mode==='common-frame'?'Center shared visible-ink union once; individual ink centers may differ because of meaningful additions.':'Chosen semantic viewport takes precedence over ink/origin centering; certificate verifies only declared convex half-plane fills, not all plot semantics.'};
  return {members:prepared.map(({normalized,...m})=>m),provenance};
}
export function writeCommonFrameOutputs(prefix, rawAnchors, result) {
  need(result.provenance.approved,'common frame refused');
  const entries=[];result.members.forEach((m,i)=>{need(Object.hasOwn(rawAnchors,m.id),'raw member sidecar required');assertOutputMetadata(m.document,m.anchors);entries.push({role:`document-${i}`,suffix:`.${i}.json`,data:jsonBytes(m.document)},{role:`anchors-${i}`,suffix:`.${i}.anchors.json`,data:jsonBytes(m.anchors)},{role:`rawAnchors-${i}`,suffix:`.${i}.raw.anchors.json`,data:rawAnchors[m.id]});});
  entries.push({role:'provenance',suffix:'.layout.json',data:jsonBytes({...result.provenance,metadataContract:METADATA_CONTRACT})});return commitBundle(prefix,entries);
}

function commitBundle(prefix, entries) {
  const manifestPath=prefix+'.manifest.json', files=entries.map(e=>prefix+e.suffix);
  need(new Set(files).size===files.length && !files.includes(manifestPath),'duplicate bundle paths');
  for(const p of [...files,manifestPath]) need(!fs.existsSync(p) && fs.statSync(path.dirname(p)).isDirectory(),`output must be a NEW file in an existing directory: ${p}`);
  const manifest={schema:'vdd-layout-commit-v1',metadataContract:METADATA_CONTRACT,contract:'Consumers MUST use loadOutputs; no manifest means incomplete. Manifest is written last after all payloads are fsynced. This is not four-file rename atomicity.',files:entries.map((e,i)=>({role:e.role,name:path.basename(files[i]),sha256:hash(e.data),bytes:Buffer.byteLength(e.data)}))};
  const created=[];
  const syncDirectory=()=>{const fd=fs.openSync(path.dirname(path.resolve(prefix)),'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}};
  const put=(file,data)=>{const fd=fs.openSync(file,'wx');created.push(file);try{fs.writeFileSync(fd,data);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}};
  try {
    entries.forEach((e,i)=>put(files[i],e.data));syncDirectory();
    put(manifestPath,JSON.stringify(manifest,null,2)+'\n');syncDirectory();
  } catch(e) {for(const file of created)fs.unlinkSync(file);throw e;}
  return [...files,manifestPath];
}
const jsonBytes=x=>JSON.stringify(x,null,2)+'\n';
export function writeOutputs(prefix, rawAnchors, result, source = {}) {
  need(result.provenance.approved, `layout refused: ${result.provenance.failures.join('; ')}`);
  assertOutputMetadata(result.document,result.anchors);
  return commitBundle(prefix,[{role:'document',suffix:'.json',data:jsonBytes(result.document)},{role:'anchors',suffix:'.anchors.json',data:jsonBytes(result.anchors)},{role:'rawAnchors',suffix:'.raw.anchors.json',data:rawAnchors},{role:'provenance',suffix:'.layout.json',data:jsonBytes({...result.provenance,source,metadataContract:METADATA_CONTRACT})}]);
}
export function loadOutputs(prefix) {
  const manifestPath=prefix+'.manifest.json';
  need(fs.existsSync(manifestPath),'incomplete bundle: commit manifest missing; do not consume partial payloads');
  need(fs.lstatSync(manifestPath).isFile() && !fs.lstatSync(manifestPath).isSymbolicLink(),'manifest must be a regular file');
  const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
  need(manifest.schema==='vdd-layout-commit-v1' && Array.isArray(manifest.files) && manifest.files.length>=4,'invalid commit manifest');
  const bytes={},seen=new Set(),base=path.basename(prefix);
  for(const e of manifest.files) {
    need(typeof e.role==='string' && !Object.hasOwn(bytes,e.role) && typeof e.name==='string' && e.name.startsWith(base+'.') && path.basename(e.name)===e.name && e.name!==path.basename(manifestPath) && !seen.has(e.name),'invalid manifest member');seen.add(e.name);
    const file=path.join(path.dirname(prefix),e.name);
    need(fs.existsSync(file) && fs.lstatSync(file).isFile() && !fs.lstatSync(file).isSymbolicLink(),'incomplete bundle: payload missing or not a regular file');
    const data=fs.readFileSync(file);need(data.length===e.bytes && hash(data)===e.sha256,`tampered/incomplete payload: ${e.role}`);Object.defineProperty(bytes,e.role,{value:data,enumerable:true});
  }
  need(bytes.provenance,'missing provenance');
  const provenance=JSON.parse(bytes.provenance);need(provenance.approved,'bundle not layout-approved');
  need(stable(manifest.metadataContract)===stable(METADATA_CONTRACT) && stable(provenance.metadataContract)===stable(METADATA_CONTRACT),'missing/incompatible metadata frame contract; regenerate legacy bundles, do not guess frames');
  const member=(documentBytes,anchorBytes,rawAnchors)=>{
    const document=JSON.parse(documentBytes),anchors=JSON.parse(anchorBytes);assertOutputMetadata(document,anchors);
    return {document,anchors,rawAnchors,rawAnchorsFrame:METADATA_CONTRACT.rawAnchorsFrame};
  };
  if(bytes.document) {
    need(Object.keys(bytes).length===4 && bytes.anchors && bytes.rawAnchors,'incomplete single-figure bundle roles');
    return {...member(bytes.document,bytes.anchors,bytes.rawAnchors),provenance,manifest};
  }
  need(provenance.mode==='common-frame'||provenance.mode==='semantic-viewport','unrecognized bundle mode');
  need(Array.isArray(provenance.memberIds) && Object.keys(bytes).length===1+provenance.memberIds.length*3,'incomplete common-frame roles');
  const members=provenance.memberIds.map((id,i)=>{need(bytes[`document-${i}`]&&bytes[`anchors-${i}`]&&bytes[`rawAnchors-${i}`],'incomplete common-frame member');return {id,...member(bytes[`document-${i}`],bytes[`anchors-${i}`],bytes[`rawAnchors-${i}`])};});
  return {members,provenance,manifest};
}

const HELP = `node vdd-layout.mjs --input source.json --anchors source.anchors.json --config explicit-layout.json --out /existing/directory/NEW-prefix [--admin /path/to/Vibhaga-Admin] [--headed]
Config: {"angleDegrees":-3,"pivot":[100,100],"reference":"actor supplied source baseline reference","framing":{"mode":"bounded-artwork","declaration":"Finite artwork, not a clipped unbounded region"},"canvas":[400,320],"padding":32,"band":"vector","quantizationBudgetPx":2}
No orientation inference. Nonzero existing rotations/unsupported types refuse. Absolute M/L/Q/C/A/Z paths only; glyphs upright. Real local compiled Inter/Noto assets are required by default (.next/dev/static/css or chunks plus media). createMeasurer({fontStaticDirectory,allowProvisionalFonts:true}) can collect fallback evidence, never approve it.
Stored geometry uses one exact positive similarity. normalizeVdd is checked as precision-preserving uniform translation with bounded IEEE-754 roundoff, or as audited legacy translation plus integer quantization (bounded by 0.5 per axis). Empty rounding audits require uniform translation. Vector/raster angle and ratio bands, collapse/winding/linear-intersection/arrow gates and the measured CSS budget at 320/375/768 remain active. Reported first-point-relative errors can exceed 1 CSS pixel. critical:[{kind:"collinear",points:[["element-id",0],["other-id",0],["third-id",0]]}] adds strict source-critical constraints (incidence, collinear, perpendicular, onSegment, tangent with circle ID). claimsText reuses vdd-check numeric evaluators. These are layout/preservation gates, NOT semantic approval: later S6b source/stated-value/coverage/critical math checks and fresh visual critique are REQUIRED. Curved intersection topology and undeclared critical incidences are not inferred.
Metadata compatibility: the complete immediate input meta object is preserved losslessly under meta.inputMetadata with inputMetadataRole:"INPUT_PROVENANCE"; inputMetadataPresent records whether it existed. Unknown frame fields and unrelated metadata are not dropped, flattened, or implicitly reasserted as output properties. Active meta.anchors and the corrected sidecar are labeled STORED_OUTPUT_CANVAS. Repeated transforms nest the prior metadata snapshot. Consumers must migrate inherited-key reads to the input provenance namespace or explicitly re-author output metadata. Exported METADATA_CONTRACT is included in provenance and the manifest; loadOutputs validates it and the active anchor map/frame. Legacy bundles without this contract require regeneration, not guessed relabeling. normalizeVdd still leaves these STORED_OUTPUT_CANVAS anchors unchanged; they never become normalized-canvas anchors.
The byte-preserved .raw.anchors.json is the supplied INPUT_VDD_CANVAS sidecar, NOT automatically raw PDF/page anchors. Any PDF-to-input-VDD mapping is a separate caller responsibility. loadOutputs labels rawAnchorsFrame explicitly for single and common-frame members.
Writes four NEW payloads and a fifth manifest LAST after payload fsync. ALL consumers must use loadOutputs(prefix); missing/partial/tampered bundles refuse. Interrupted uncommitted files are not consumable; retain for diagnosis or explicitly discard, then use a new prefix. Existing files are never replaced. Four files are not an atomic batch without the manifest contract.
Manual extending-pair API (no independent fits): transform both originals by the SAME explicit orientation matrix into a generous shared provisional canvas; measureUnion(documents, canvas.width, measurer); fitMeasuredUnion(union.bounds, targetCanvas, padding); compose that fit with the shared provisional/orientation matrix. Pass original members [{id,document,anchors}] to validateCommonFrame(members,{mode:"common-frame",matrix,canvas,reference,sourceFrame,orientation:{angleDegrees,pivot,reference},pitch:["P","Q"],sharedAnchors:["P","Q"]},measurer). It checks actual union centering, common range/translation/pitch/anchor correspondence on BOTH surfaces at all widths. Member centering is an explicit exception, not independently repaired. Pitch/correspondence anchors must bind to real geometry. writeCommonFrameOutputs(prefix,rawAnchorBuffersById,result) commits the pair with one manifest; loadOutputs verifies it.
Unbounded apparatus API: regenerate geometry in mathematical coordinates FIRST; do not rotate an old finite fill. validateCommonFrame mode:"semantic-viewport" requires viewport:[xmin,ymin,xmax,ymax], sourceOrientation:{angleDegrees,pivot,reference}, a positive axis-aligned scale+translation matrix, and each member.certificate:{kind:"half-plane-viewport-v1",reference,viewport,documentSHA256:documentDigest(document),regions:[{elementId,inequalities:[[a,b,c]]}]} for a*x+b*y<=c. clipHalfPlanes generates the chosen finite viewport intersection. Every area fill must match its certified clipped polygon (no triangular holes). An explicitly unshaded member instead requires {kind:"half-plane-viewport-v1",reference,viewport,documentSHA256:documentDigest(document),unshaded:true,regions:[]}, bound to its own exact input document and the same chosen viewport. Empty regions without that literal-boolean attestation, mixed unshaded/nonempty-region certificates, and coercive opacity/color values refuse. The unshaded branch requires no polygon/rect/path/circle area fills under the existing opacity/color classifier; typed point markers and arrowheads remain apparatus ink, not area regions. It does not assert a blank image or infer an unshaded member from its ID. Unshaded-question/shaded-answer pairs use the same validateCommonFrame and manifest APIs with all common-frame/normalization gates active. Other nonlinear plots/fills remain unsupported pending an appropriate generator/certificate. The chosen viewport, not origin/ink centering, takes precedence. Independent normalizer refits breaking pair correspondence still REFUSE; never add invisible pads.
Frame failures print JSON to stdout and write nothing; invalid inputs/measurement failures report to stderr.`;
async function main() {
  const args=process.argv.slice(2);
  if(args.includes('--help')) { console.log(HELP); return; }
  const values={};
  for(let i=0;i<args.length;i++) {
    const key=args[i]; need(['--input','--anchors','--config','--out','--admin','--headed'].includes(key), `unknown argument ${key}`);
    need(!(key in values),`duplicate argument ${key}`);
    values[key]=key==='--headed'?true:args[++i]; need(values[key] && !String(values[key]).startsWith('--'),`missing value for ${key}`);
  }
  for(const key of ['--input','--anchors','--config','--out']) need(values[key],HELP);
  const input=fs.readFileSync(values['--input']), raw=fs.readFileSync(values['--anchors']), config=JSON.parse(fs.readFileSync(values['--config'],'utf8'));
  const measurer=await createMeasurer({admin:values['--admin'],headed:values['--headed']});
  try {
    const result=await layout(JSON.parse(input),JSON.parse(raw),config,measurer);
    console.log(JSON.stringify(result.provenance,null,2));
    if(!result.provenance.approved) { process.exitCode=1; return; }
    const files=writeOutputs(values['--out'],raw,result,{input:path.resolve(values['--input']),anchors:path.resolve(values['--anchors']),inputSHA256:hash(input),rawAnchorsSHA256:hash(raw)});
    console.error(`Wrote ${files.join(', ')}. Independent fresh visual critique required before use.`);
  } finally { await measurer.close(); }
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) main().catch(e=>{console.error(`vdd-layout: ${e.message}`);process.exitCode=2;});
