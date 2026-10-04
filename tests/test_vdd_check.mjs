/** tests/test_vdd_check.mjs — node --test over tools/vdd-check.mjs rule 3 (ADR 0021).
 *  Runs the real CLI with --no-render so it works wherever Vibhaga-Admin resolves. */
import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const TOOLS = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "tools");

const FIG = {
  schema: "vibhaga.diagram", schemaVersion: 1,
  canvas: { width: 200, height: 200 },
  a11y: {
    title: "Two labelled points A and B joined by a segment",
    description: "A horizontal segment with endpoint A on the left and endpoint B on the right; both endpoints are lettered.",
  },
  elements: [
    { id: "AB", type: "line", points: [[40, 100], [160, 100]] },
    { id: "pA", type: "point", at: [40, 100], r: 3, label: "A", labelOffset: [-12, -12] },
    { id: "pB", type: "point", at: [160, 100], r: 3, label: "B", labelOffset: [12, -12] },
  ],
};

function runCheck(doc, extra = []) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vdd-check-test-"));
  const file = path.join(dir, "fig.json");
  fs.writeFileSync(file, JSON.stringify(doc));
  try {
    const out = execFileSync(process.execPath,
      [path.join(TOOLS, "vdd-check.mjs"), file, "--no-render", ...extra],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { code: 0, out };
  } catch (e) {
    return { code: e.status ?? 1, out: `${e.stdout ?? ""}${e.stderr ?? ""}` };
  }
}

for (const medium of ["english", "sinhala"]) {
  test(`ADR 0021: Sinhala in a drawn label refuses on medium=${medium}`, () => {
    const doc = { ...FIG, elements: [...FIG.elements, { id: "t", type: "text", at: [100, 60], value: "අ" }] };
    const r = runCheck(doc, ["--medium", medium]);
    assert.equal(r.code, 1);
    assert.match(r.out, /label "අ" contains Sinhala — diagram text must be simple English \(ADR 0021\)/);
  });
}

test("ADR 0021: Sinhala inside math.latex refuses", () => {
  const doc = { ...FIG, elements: [...FIG.elements, { id: "m", type: "math", at: [100, 60], latex: "උ" }] };
  const r = runCheck(doc, ["--medium", "sinhala"]);
  assert.equal(r.code, 1);
  assert.match(r.out, /math label "උ" contains Sinhala — diagram text must be simple English \(ADR 0021\)/);
});

test("ADR 0021: Sinhala a11y title/description is exempt (not drawn)", () => {
  const doc = {
    ...FIG,
    a11y: {
      title: "අ — a synthetic Sinhala a11y title",
      description: "අ — a synthetic Sinhala a11y description that is never drawn on the figure itself.",
    },
  };
  const r = runCheck(doc, ["--medium", "sinhala"]);
  assert.equal(r.code, 0, r.out);
});
