/** tests/test_note_render.mjs — node --test over tools/note-render.mjs's pure helpers (no browser). */
import test from "node:test";
import assert from "node:assert/strict";
import { expectedCounts, failures } from "../tools/note-render.mjs";

const MD = "## A\n\nFor $x$ and $y$:\n\n$$\nx + y\n$$\n\n<table><tr><td>$1$</td></tr></table>\n\n## B\n";
const clean = { math: 4, display: 1, tables: 1, h2: 2, figures: 0, errors: 0, rawDollar: 0,
  overflow: [], overflow375: [], status: "Draft · v1" };

test("expectedCounts counts inline, display, tables, headings and figures", () => {
  assert.deepEqual(expectedCounts(MD, []), { math: 4, display: 1, tables: 1, h2: 2, figures: 0 });
  assert.equal(expectedCounts(MD, [{}, {}]).figures, 2);
});

test("failures: a clean measurement passes, stored needs Draft", () => {
  const exp = expectedCounts(MD, []);
  assert.deepEqual(failures(clean, exp), []);
  assert.deepEqual(failures(clean, exp, { stored: true }), []);
  assert.match(failures({ ...clean, status: "Verified" }, exp, { stored: true })[0], /not Draft/);
});

test("failures: every defect is named", () => {
  const exp = expectedCounts(MD, []);
  assert.deepEqual(failures(null, exp), ["note preview article not found"]);
  const bad = failures({ ...clean, math: 3, errors: 1, rawDollar: 2, overflow: ["a"], overflow375: ["b"] }, exp);
  assert.equal(bad.length, 5);
  assert.ok(bad.some((b) => /overflow at 375 px: b/.test(b)));
});
