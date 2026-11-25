# read-figure-claim-set — examples and troubleshooting

[Operational rules](SKILL.md). Open this reference for examples or to diagnose a failure.

## 4. ⭐ Worked example — a constructed cuboid-face rectangle

Synthetic (no paper): the stem is *"A cuboid has a face 5 cm long and 2 cm wide. Find the ratio of the
face's length to its width."* The figure is the face.

```
figure:   q1
source:   constructed; frame is the question's own canvas, 200 x 120, y down
channel:  constructed
stem:     A cuboid has a face 5 cm long and 2 cm wide. Find the ratio of the face's length to its width.
ask:      1  ratio of length to width
labels:   A B C D "5 cm" "2 cm"
points:   A B C D
segments: AB BC CD DA
anchors:
  A 20 20
  B 180 20
  C 180 84
  D 20 84

claims:
  K1  right A B C                           | inferred | face of a cuboid is rectangular — and the mark
                                                    will be drawn (see departures if omitted)
  K2  right B C D                           | inferred | same
  K3  ratio len AB / len BC = 2.5           | stem     | "5 cm long and 2 cm wide" — 5/2; the stem-ratio
                                                    check finds 5 and 2 in the stem's numbers and agrees
  K4  ratio len CD / len DA = 2.5           | stem     | opposite sides of a rectangle
  K5  equal AB CD                           | inferred | rectangle
  K6  equal BC DA                           | inferred | rectangle
  K7  label "A" names A                     | inferred | label placement, above-left of the corner
  K8  label "B" names B                     | inferred | label placement, above-right of the corner
  K9  label "C" names C                     | inferred | label placement, below-right of the corner
  K10 label "D" names D                     | inferred | label placement, below-left of the corner
  K11 label "5 cm" names AB                 | stem     | the stem's 5 on the long side
  K12 label "2 cm" names BC                 | stem     | the stem's 2 on the short side
  K13 derive 5 / 2 = 2.5                    | inferred | REQUIRED on constructed (check 2c) — the ratio
                                                    the figure must honour, from the stem's own numbers
  K14 none tickMark parallelMark angleArc arrow shaded | inferred | no marks declared; the right-angle
                                                    marks are drawn by the drawing skill's convention
                                                    (see departures if dropped)

scale:    drawn to scale — AB:BC = 5:2 as the stem states (160 x 64 px of ink at this canvas)
load-bearing:
  1 -> K3, K13                     # the ratio the stem states and the derive that proves the figure honours it
unreadable: (none)
ambiguous:  (none)
departures: (none)                 # the drawing skill fills this in
```

⚠️ **This is exactly the shape the old audit got wrong.** Draw the anchors 160 × 107 px and K3 still reads
`ratio len AB / len BC = 2.5` — anchors and claim disagree so the audit fails — but draw them 160 × 107 px
**and claim `= 1.5`** and the OLD audit passed it (anchors agree with the claim; both are self-consistently
wrong). The stem-ratio check is what refuses the second one: `1.5` is not `a/b` for any pair of stem numbers
and no `derive` claim yields it.

## 6. Traps — stories with the catch

Cross-cutting traps: [`docs/TRAPS.md`](../../docs/TRAPS.md) — in particular **T25** in Vibhaga-Docs
(self-verification is not verification). The paper side's reading traps (endpoint clustering, filter-
invisible marks, glyph-as-space labels) went out with the page; these are what the constructed side keeps:

### T-S6a-C1 — The self-consistent liar needs a second ground truth
**Looked true:** the anchors and the claims agree, so the figure is right.
**Actually:** on a constructed figure the author writes both. The 1.5:1 rectangle for the 5:2 stem was
self-consistent and wrong — claim and anchors were authored from the same misreading of the stem.
**The check:** the `stem:` header is the second ground truth — the stem-ratio check recomputes the claim
against the *stem's numbers*, not the anchors. Keep `stem:` verbatim from the authored stem; an audit
that cannot see it cannot check the figure.

### T-S6a-C2 — `derive` is a floor, not a proof
**Looked true:** `derive 4 + 2 = 6` passes check 2c, so the answer's arithmetic is verified.
**Actually:** 2c checks that the expression evaluates and the drawing lands on it — never that the
expression is the right one for the question. The wrong-but-valid `derive` passes with the wrong figure.
**The check:** the two-method answer derivation (author-question-answers §3) is the real check on the
arithmetic; 2c only binds drawing to claim.
