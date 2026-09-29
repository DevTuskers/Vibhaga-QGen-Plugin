#!/usr/bin/env python3
"""S8 §6 check #10 / S9 advisory — inline `$…$` runs that will CLIP on a 375 px phone.

Why: both renderers put `whitespace-nowrap` on `.katex` (Vibhaga-Web `src/lib/markdown/ContentMarkdown.tsx`,
`WRAPPER`), so an INLINE formula never wraps. (Display math `$$…$$` is different: `.katex-display` has
`overflow-x: auto` in both apps' `globals.css`, so it scrolls rather than clips — this script skips it.)
At 375 px the stem's content box is ~301 px wide and a sub-answer's box ~313 px. Measured 2026-09-05 on
run 6 Q25 in the real renderer: a ten-number data row reached x = 391 and `\\sum fx = 96 + 180 + 400 + 396 +
144 = 1216` reached x = 407 — both cut off; the same day the owner had asked for answers "students can read".

The width is ESTIMATED from the LaTeX source in em:
  digit / upright letter 0.5 · italic letter 0.6 · binary operator or `=` 0.95 (glyph + KaTeX's spacing;
  the Unicode forms − × · ° count the same as their commands) · `,\\ ` 0.78 · superscript / subscript 0.35
  (`\\hat` adds nothing) · `\\sum` 1.4 · `\\dfrac{a}{b}` 0.2 + width of the wider row (brace-less `\\tfrac14`
  likewise) · `\\left(` / `\\right)` one glyph · thin spaces `\\,` `\\;` 0.15
then px = em × 18 (the body size) × 1.17 (the calibration factor).

Calibration — seven inline runs measured with `getBoundingClientRect()` in Admin's 375 px student frame
(the real `ContentMarkdown` + KaTeX), 2026-09-05, run 6 Q22/Q23/Q25:
  est  meas  run
  321   310  O\\hat{Q}B = 180^\\circ - O\\hat{Q}P = 180^\\circ - 63^\\circ = 117^\\circ
  364   370  \\sum fx = 96 + 180 + 400 + 396 + 144 = 1216
  358   354  44,\\ 47,\\ 44,\\ 45,\\ 37,\\ 35,\\ 35,\\ 39,\\ 40,\\ 36
  276   255  \\dfrac{1}{2} \\times \\dfrac{22}{7} \\times 14 \\times 14 = 11 \\times 28 = 308
  237   226  = \\pi r^2 = \\dfrac{22}{7} \\times 7 \\times 7 = 154\\ \\text{cm}^2
  216   199  = \\dfrac{1}{2} \\times 2\\pi r = \\dfrac{22}{7} \\times 14 = 44
  201   186  = 2\\pi r = 2 \\times \\dfrac{22}{7} \\times 7 = 44
All within +8.5% / −1.5%; the estimate errs high on `\\dfrac`-heavy runs, so a borderline `\\dfrac` run is
probably fine and a borderline digit run probably is not. Re-run `python3 - <<EOF` with these seven when
you change a weight.

Usage:
  check-inline-math-width.py staged.json [--ids id1,id2] [--fields fields.json] [--clip 330] [--warn 270]
    staged.json  the staged doc — checks question_text, part text, approach, final_answer_latex (scoped to --ids)
    --fields     instead, a `[{id, field, text}]` list (the markdown gate's input shape)
Prints every run estimated at or over --warn px; exits 1 only for runs at or over --clip px (the widest box).
A run between the two is BORDERLINE — look at it in the 375 px preview before deciding.
"""
import argparse, json, re, sys

INLINE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', re.S)
EM_PER_PX = 18 * 1.17

def em_width(seg: str) -> float:
    s = seg
    w = 0.0
    # Unicode operator glyphs an OCR/paste leaves behind count like their commands
    s = s.replace('−', '-').replace('×', ' \\times ').replace('·', ' \\cdot ').replace('°', '^\\circ')
    # \left( … \right): the fences are one glyph each; \big( likewise
    s = re.sub(r'\\(?:left|right|big|Big|bigg|Bigg)\s*([()\[\]|.])', r'\1', s)
    # thin/medium spaces
    w += 0.15 * len(re.findall(r'\\[,;:!]', s)); s = re.sub(r'\\[,;:!]', '', s)
    # \dfrac / \frac / \tfrac {a}{b} (and brace-less \tfrac14): the wider row, plus the bar's slack
    def frac(m):
        nonlocal w
        w += 0.2 + max(em_width(m.group(1)), em_width(m.group(2)))
        return ' '
    s = re.sub(r'\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}', frac, s)
    s = re.sub(r'\\[dt]?frac(\d)(\d)', frac, s)
    # \text{…} / \mathrm{…}: upright proportional text
    def text(m):
        nonlocal w
        w += 0.5 * len(m.group(1).replace(' ', '')) + 0.25 * m.group(1).count(' ')
        return ' '
    s = re.sub(r'\\(?:text|mathrm|mathbf|operatorname)\{([^{}]*)\}', text, s)
    # superscripts / subscripts / hats: small
    SUP = r'[\^_](?:\{[^{}]*\}|\\[a-zA-Z]+|.)'          # ^\circ, ^{2}, ^2, _n — one small glyph each
    w += 0.35 * len(re.findall(SUP, s)); s = re.sub(SUP, '', s)
    w += 0.0 * len(re.findall(r'\\hat|\\bar|\\vec', s)); s = re.sub(r'\\hat|\\bar|\\vec', '', s)
    # big operators and named commands
    w += 1.4 * len(re.findall(r'\\sum|\\int|\\prod', s)); s = re.sub(r'\\sum|\\int|\\prod', '', s)
    w += 0.95 * len(re.findall(r'\\times|\\div|\\pm|\\cdot|\\approx|\\le|\\ge|\\neq|\\equiv', s)); s = re.sub(r'\\times|\\div|\\pm|\\cdot|\\approx|\\le|\\ge|\\neq|\\equiv', '', s)
    w += 0.78 * len(re.findall(r',\\ |,\\,|,\s', s)); s = re.sub(r',\\ |,\\,|,\s', '', s)
    w += 0.5 * len(re.findall(r'\\[a-zA-Z]+', s)); s = re.sub(r'\\[a-zA-Z]+', '', s)   # \pi, \circ, \angle …
    w += 0.95 * len(re.findall(r'[=+\-<>]', s)); s = re.sub(r'[=+\-<>]', '', s)
    s = re.sub(r'[{}\\\s]', '', s)
    w += 0.6 * len(re.findall(r'[a-zA-Z]', s)) + 0.5 * len(re.findall(r'[0-9.,:;()\[\]|]', s))
    return w

def fields_from_staged(doc, ids):
    out = []
    for q in doc.get('questions', []):
        if ids and q.get('question_id') not in ids: continue
        tag = f"Q{q.get('question_number')} {str(q.get('question_id'))[:8]}"
        out.append({'id': f'{tag}.question_text', 'text': q.get('question_text') or ''})
        for a in q.get('answers') or []:
            out.append({'id': f'{tag}.answer.approach', 'text': a.get('approach') or ''})
            out.append({'id': f'{tag}.answer.final', 'text': a.get('final_answer_latex') or ''})
        def walk(subs, path):
            for s in subs:
                p = f"{path}/{s.get('label')}"
                out.append({'id': f'{tag}{p}.text', 'text': s.get('text') or ''})
                for a in s.get('answers') or []:
                    out.append({'id': f'{tag}{p}.approach', 'text': a.get('approach') or ''})
                    out.append({'id': f'{tag}{p}.final', 'text': a.get('final_answer_latex') or ''})
                walk(s.get('sub_questions') or [], p)
        walk(q.get('sub_questions') or [], '')
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('staged', nargs='?')
    ap.add_argument('--ids', default='')
    ap.add_argument('--fields')
    ap.add_argument('--clip', type=int, default=330)
    ap.add_argument('--warn', type=int, default=270)
    a = ap.parse_args()
    if a.fields:
        fields = json.load(open(a.fields, encoding='utf-8'))
    elif a.staged:
        fields = fields_from_staged(json.load(open(a.staged, encoding='utf-8')), set(x for x in a.ids.split(',') if x))
    else:
        ap.error('give a staged doc or --fields')
    clip, warn = [], []
    for f in fields:
        for m in INLINE.finditer(f.get('text') or ''):
            px = em_width(m.group(1)) * EM_PER_PX
            if px >= a.clip: clip.append((px, f['id'], m.group(1)))
            elif px >= a.warn: warn.append((px, f['id'], m.group(1)))
    for px, fid, seg in sorted(clip, reverse=True): print(f'  CLIP  ~{px:4.0f} px  {fid}  ${seg[:90]}$')
    for px, fid, seg in sorted(warn, reverse=True): print(f'  warn  ~{px:4.0f} px  {fid}  ${seg[:90]}$')
    print(f'inline-math-width: {len(fields)} fields · {len(clip)} run(s) >= {a.clip} px (clip at 375) · {len(warn)} borderline ({a.warn}–{a.clip} px)')
    sys.exit(1 if clip else 0)

if __name__ == '__main__':
    main()
