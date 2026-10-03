/**
 * contact-sheet.mjs — the pure HTML builder behind visual-check mode 1's
 * `contact-light-375.png` (W9 item C).
 *
 * The sheet is an HTML page of <img> + caption cells — one per figure's light-375.png,
 * inlined as a data URI (a setContent() page may not load file:// subresources), shown at
 * native size, TWO per row, figure id captioned above, on white — screenshotted full-page
 * by the caller's existing Chromium. Kept in its own module so `node --test` can exercise
 * it without the Admin checkout (importing visual-check.mjs runs its env checks).
 *
 * items: [{id: "Q3.b", data: "<base64 png>"}]
 */
const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function contactSheetHtml(items) {
  const cells = (items ?? [])
    .map(
      ({ id, data }) =>
        `<figure style="margin:0">` +
        `<figcaption style="font:600 14px/1.4 ui-monospace,Menlo,monospace;color:#111;padding-bottom:4px">${esc(id)}</figcaption>` +
        `<img src="data:image/png;base64,${data}" style="display:block;border:1px solid #ccc;image-rendering:auto">` +
        `</figure>`
    )
    .join("\n");
  return (
    `<!doctype html><html><head><meta charset="utf-8"></head>` +
    `<body style="margin:0;background:#fff">` +
    `<div style="display:grid;grid-template-columns:repeat(2,max-content);gap:28px 36px;padding:20px">` +
    `${cells}</div></body></html>`
  );
}
