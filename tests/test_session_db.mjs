import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { claimsFor, pushFigure, claimsForWarn, pairRenderedFigures } from "../tools/session-db.mjs";
import { assess } from "../tools/visual-metrics.mjs";

test("claimsFor: --claims-dir resolves <id>-claims.txt (the vdd_templates name) too", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vc-claims-"));
  // Only the dash name exists — a staged doc's figure id Q3 must still find it.
  fs.writeFileSync(path.join(dir, "Q3-claims.txt"), "claims:\n  K1 none x | stem |\n");
  const hit = claimsFor("Q3", null, dir);
  assert.equal(hit.path, path.join(dir, "Q3-claims.txt"));
  assert.match(hit.text, /K1 none x/);
  // <id>.claims.txt still wins when both exist beside it.
  fs.writeFileSync(path.join(dir, "Q3.claims.txt"), "claims:\n  K9 none y | stem |\n");
  assert.equal(claimsFor("Q3", null, dir).path, path.join(dir, "Q3.claims.txt"));
  // A dotted part id works the same way; a missing figure resolves to null.
  fs.writeFileSync(path.join(dir, "Q3.b-claims.txt"), "x");
  assert.equal(claimsFor("Q3.b", null, dir).path, path.join(dir, "Q3.b-claims.txt"));
  assert.equal(claimsFor("Q9", null, dir), null);
  // Beside a VDD input file the sibling names are unchanged.
  const base = path.join(dir, "fig");
  fs.writeFileSync(`${base}-claims.txt`, "x");
  assert.equal(claimsFor("fig", base, dir).path, `${base}-claims.txt`);
});

test("pushFigure: a duplicate id lands as <id>~k but claims resolve by the BASE id", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vc-dup-"));
  fs.writeFileSync(path.join(dir, "Q3-claims.txt"), "claims:\n  K1 none x | stem |\n");
  const figures = [], seen = new Map();
  pushFigure(figures, seen, "Q3", {}, "t", null, dir);
  pushFigure(figures, seen, "Q3", {}, "t", null, dir);
  assert.equal(figures[0].id, "Q3");
  assert.equal(figures[1].id, "Q3~2");       // the dup keeps its display suffix
  assert.equal(figures[1].baseId, "Q3");
  // …but `Q3~2.claims.txt` is never a real filename — the dup shares Q3's claim set.
  assert.equal(figures[0].claims.path, path.join(dir, "Q3-claims.txt"));
  assert.equal(figures[1].claims.path, path.join(dir, "Q3-claims.txt"));
});

test("claimsForWarn: warns only under --claims-dir and only when nothing resolved", () => {
  const dir = "/tmp/vc-claims-dir";
  assert.equal(claimsForWarn("Q3", dir, null),
    `WARN no claim set for Q3 (looked for Q3.claims.txt / Q3-claims.txt in ${dir})`);
  assert.equal(claimsForWarn("Q3", dir, { path: "p", text: "t" }), null); // resolved → silent
  assert.equal(claimsForWarn("Q3", null, null), null);                    // no --claims-dir → silent
});

test("--session --staged/--claims-dir: the staged figure's claim set applies the same allow/target outcome as mode 1", () => {
  // visual-check --session reads the staged doc from --staged and resolves each rendered
  // figure's claims via pushFigure/claimsFor, then calls the same assess() batch mode does — a
  // numeral floating
  // far from paint is a `target` finding claims-less, `allowed` with `allow: label:"…"`, and
  // the session-mode call and the batch-mode call produce byte-identical findings.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vc-session-claims-"));
  fs.writeFileSync(path.join(dir, "Q5-claims.txt"), [
    'labels: "3502"',
    "claims:",
    '  K1 describe "a numeral card inside the ring" | inferred |',
    'allow: label:"3502"',
  ].join("\n"));
  const doc = {
    schema: "vibhaga.diagram", schemaVersion: 1,
    canvas: { width: 300, height: 260 }, defaults: { strokeWidth: 2, fontSize: 18 },
    elements: [{ id: "ring", type: "circle", center: [150, 130], r: 80 }],
  };
  // what __vc.measure() would hand back: one text label 60u from the nearest paint
  const measured = [{ width: 375, pxPerUnit: 1, labels: [{
    i: 0, text: "3502", kind: "text", bbox: [140, 120, 40, 18],
    fontFamily: "Inter, sans-serif", fontSizeU: 18, edge_u: 60, stroke_u: 60, geom_u: 60,
  }] }];
  const figures = [], seen = new Map();
  pushFigure(figures, seen, "Q5", doc, "the session doc", null, dir);
  const fig = figures[0];
  const sessionMode = assess({ doc: fig.doc, claims: fig.claims?.text ?? null, widths: measured });
  const batchMode = assess({ doc: fig.doc, claims: fig.claims?.text ?? null, widths: measured });
  const claimsLess = assess({ doc: fig.doc, claims: null, widths: measured });
  assert.equal(fig.claims.path, path.join(dir, "Q5-claims.txt"));
  assert.deepEqual(sessionMode.findings, batchMode.findings);
  assert.ok(claimsLess.findings.some((f) => f.rule === "target" && f.severity === "fail"));
  assert.equal(claimsLess.verdict, "FAIL");
  assert.ok(sessionMode.findings.some((f) => f.rule === "target" && f.severity === "allowed"));
  assert.equal(sessionMode.findings.filter((f) => f.severity === "fail").length, 0);
  assert.equal(sessionMode.verdict, "PASS");
});

test("pairRenderedFigures: the k-th svg host pairs with the k-th staged figure — m.index counts svg-less hosts", () => {
  // StudentPreview renders a "Diagram coming soon" plate (role=img, no svg) for an unparseable
  // figure; that host still takes an index in measure()'s list. Pairing by m.index would shift
  // every figure behind it onto the wrong claim set — the pairing must count only svg entries.
  const figs = [{ id: "Q1" }, { id: "Q1.a" }, { id: "Q1.ans1" }];
  const measured = [
    { index: 0, svg: false, labels: [] },                    // unparseable-figure plate, no svg
    { index: 1, svg: true, pxPerUnit: 1, labels: [] },
    { index: 2, svg: false, labels: [] },                    // another plate, mid-list
    { index: 3, svg: true, pxPerUnit: 1, labels: [] },
  ];
  const pairs = pairRenderedFigures(measured, figs);
  assert.equal(pairs.length, 2);                             // only svg hosts pair
  assert.equal(pairs[0].measured.index, 1);
  assert.equal(pairs[0].fig.id, "Q1");                       // svg #1 → figs[0], not figs[1]
  assert.equal(pairs[1].measured.index, 3);
  assert.equal(pairs[1].fig.id, "Q1.a");                     // svg #2 → figs[1], not figs[3]
  // More rendered figures than staged → the extras get fig null (claims-less, never a
  // wrong-figure claim set); no staged list at all → every fig null.
  const short = pairRenderedFigures(measured, [figs[0]]);
  assert.equal(short[1].fig, null);
  assert.ok(pairRenderedFigures(measured, null).every((p) => p.fig === null));
  assert.deepEqual(pairRenderedFigures([], figs), []);
});
