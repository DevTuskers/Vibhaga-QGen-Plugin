# Paper-era trap cases

[Trap index](../TRAPS.md). Historical context; the one-line rules in the index still apply.

<a name="t13"></a>

## T13 — The R2 mechanical gate catches OCR-confusables, NOT a wrong digit

**Looked true:** the born-digital gate works — seed a corrupt fixture, it fires.
**Actually:** measured on a real page — `37 → 3S` **fires**, `37 → 31` produces **zero findings**. The gate
is a control against *glyph-confusable* corruption only. Seed only the confusable case and you will
wrongly conclude you are protected against transcription error.
**The check:** a red-team fixture must include a **digit-for-digit** case, and its expected result must be
recorded as **"blind"** so nobody later reads the pass as coverage.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T13 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t25"></a>

## T25 — "A separate agent turn" is not something one agent can do to itself.

**Looked true:** S2b §6 asks for two transcriptions at different dpi and crop framing, "in a separate
agent turn, with no access to A". Run 2 varied both, produced B, and B agreed with A on every token of
both pages. Two independent passes, perfect agreement — the strongest possible result.
**Actually:** the agreement is worthless as evidence. One context wrote both. Having just written A, the
reader cannot unsee it, and cannot distinguish "B re-derived this glyph" from "B recalled it". §6 names
this exact failure — *"the same model, in the same context, shown the same pixels, will reproduce its own
misread"* — and then proposes a mechanism that changes the **pixels** and not the **reader**.
⇒ **Two of the three decorrelation levers are self-serve; the load-bearing one is not.** A transcription
whose second pass came from the same context must be recorded as **one channel**, and the F-R1 fixture
pass over it recorded as **blind** (T13). Genuine independence has to be *delegated* — the orchestrator
spawns a separate agent for B and hands it the renders and nothing else — or bought from a different
algorithm entirely (see T26).

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T25 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t34"></a>

## T34 — Paper-faithful part labels are a defect when you onboard a subset.

**Looked true:** transcribe the paper's own scheme (S5 §3.4, as written), so a question shipping printed
parts `III` and `IV` is labelled `III`, `IV`.
**Actually:** the student has no paper. Run 4 shipped one question whose parts read **`III, IV`**, one
**`b) I…III`** with no `a)`, and one **`I, IV, V`**. Every part faithful, every answer correct, and three of
seven questions presented as broken — the owner's first reaction on seeing them. **Nothing was wrong with
the content**, which is exactly why no content gate could see it.
**The check:** label for the reader, not for provenance — **contiguous from the start of the scheme, over
the parts you actually shipped**. Traceability belongs to `question_number` and to S7's manifest.
⇒ **Owner ruling, 2026-08-14:** *"students never see the paper — they are the customer."* Now S5 §3.4 and
S13's **C9**.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T34 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---
