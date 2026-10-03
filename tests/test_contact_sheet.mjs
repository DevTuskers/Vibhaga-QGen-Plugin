/** tests/test_contact_sheet.mjs — node --test over tools/contact-sheet.mjs (W9 item C).
 *  The sheet is a pure HTML string — offline-testable without Chromium. */
import test from "node:test";
import assert from "node:assert/strict";
import { contactSheetHtml } from "../tools/contact-sheet.mjs";

test("one captioned cell per figure, 2 per row, data-URI images", () => {
  const html = contactSheetHtml([
    { id: "Q1", data: "AAAA" },
    { id: "Q3.b", data: "BBBB" },
    { id: "Q4.ans1", data: "CCCC" },
  ]);
  // captions appear above their images, in order
  const iQ1 = html.indexOf(">Q1</figcaption>");
  const iQ3 = html.indexOf(">Q3.b</figcaption>");
  const iQ4 = html.indexOf(">Q4.ans1</figcaption>");
  assert.ok(iQ1 > -1 && iQ3 > iQ1 && iQ4 > iQ3);
  assert.equal((html.match(/<img src="data:image\/png;base64,/g) ?? []).length, 3);
  assert.ok(html.includes("base64,AAAA") && html.includes("base64,CCCC"));
  // two per row on white
  assert.match(html, /grid-template-columns:repeat\(2,max-content\)/);
  assert.match(html, /background:#fff/);
  // each image inside a <figure> with its caption first
  assert.match(html, /<figure[^>]*><figcaption[^>]*>Q1<\/figcaption><img /);
});

test("ids are HTML-escaped — a staged id can carry a label like <a>", () => {
  const html = contactSheetHtml([{ id: "Q1.<b>", data: "AAAA" }]);
  assert.ok(html.includes("Q1.&lt;b&gt;"));
  assert.ok(!html.includes("<b>"));
});

test("empty input still yields a valid page", () => {
  const html = contactSheetHtml([]);
  assert.match(html, /^<!doctype html>/);
  assert.ok(!html.includes("<img"));
});
