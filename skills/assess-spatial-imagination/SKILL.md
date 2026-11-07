---
name: assess-spatial-imagination
description: >-
  Assess the mental spatial imagination and cognitive decoding load required to understand
  a math question's description. Provides developmental benchmarks across Grades 6 to 13
  grounded in Cognitive Load Theory and visuospatial working memory limits. Enforces visual
  scaffolding (VDD diagrams or chunked layouts) whenever description complexity exceeds the
  grade benchmark, ensuring students are tested on mathematical insight rather than verbal-spatial
  decoding overload. Use when authoring, reviewing, or critiquing question stems and figure needs.
argument-hint: "[grade] [question stem or staged doc]"
---

# Assess Spatial Imagination and Cognitive Load of Question Descriptions

> **Pedagogical North Star:** Vibhaga's purpose is *learning and conceptual mastery*, not decoding
> obscure or over-complicated text. When a student reads a geometry or word problem, their finite
> working memory must be spent on the **mathematical concept** (intrinsic load), not exhausted by
> mentally rendering, rotating, and tracking multi-coordinate spatial networks solely from verbal
> prose (extraneous cognitive load).

---

## 0. Theoretical Foundation & Rationale

Why do seemingly simple math questions cause widespread student failure when presented as text?
Cognitive science and mathematics education research identify three core constraints:

1. **Cognitive Load Theory (Sweller, 1988, 2011):**
   Working memory capacity is strictly limited. Presenting spatial configurations purely in text
   creates a severe **split-attention and representational translation bottleneck**: the student must
   parse words (phonological loop), build a 2D/3D spatial mental model (visuo-spatial sketchpad),
   maintain that model while reading further conditions, and only then execute mathematical steps.
   Providing a visual diagram acts as **external cognitive offloading**, eliminating extraneous load.

2. **Visuospatial Working Memory (VSWM) Limits Across Adolescence (Baddeley, Cowan):**
   The capacity to hold independent spatial chunks in memory grows slowly from ~2–3 elements at age 11
   to ~5–6 elements at age 18. Asking a 12-year-old (Grade 7) to mentally juggle 5 points with distinct
   horizontal and vertical offsets exceeds their physiological working memory capacity.

3. **Van Hiele Levels of Geometric Thought:**
   - **Level 1 (Visualization):** Grades 6–7 students reason primarily from visual appearance and holistic shapes.
   - **Level 2 (Analysis):** Grades 8–9 students analyze components and relations, but still require concrete visual anchors.
   - **Level 3 (Informal Deduction / Deduction):** Grades 10–11 (O/L) can deduce properties from definitions and self-sketch standard figures.
   - **Level 4 (Formal Rigor):** Grades 12–13 (A/L) can handle abstract symbolic geometry and coordinate spaces.

---

## 1. The Cognitive Decoding & Spatial Imagery Index (CDS Index)

Every question description is scored on a composite scale from **0 to 10** based on three factors:

$$\text{CDS Score} = E + T + D$$

### Component 1: Spatial Entity & Layout Count ($E$, 0–3 points)
- **0 points:** Pure arithmetic/algebra or symbolic problem; zero spatial entities.
- **1 point:** Single standard 1D/2D entity (e.g. a simple line segment, a single square).
- **2 points:** 2 to 3 related spatial entities or an object with internal components (e.g. pitch with creases, pool with fountains).
- **3 points:** $\ge 4$ independent spatial entities or multi-point layouts (e.g. 5 tassels at $(x, y)$, 8 vertices of an octagon).

### Component 2: Mental Coordinate / Transformation Demands ($T$, 0–4 points)
- **0 points:** Static, direct statement of length or property.
- **1 point:** Simple 1D distance or 1-step reflection along a horizontal/vertical axis.
- **2 points:** 2D relative offsets (e.g. $x$ cm left of axis AND $y$ cm down from top edge).
- **3 points:** Mental reflection/rotation of multiple points, or along inclined/diagonal axes.
- **4 points:** Multi-step composite transformations, non-horizontal polygon folding, or combinatorial point selections without visual reference.

### Component 3: Text Density & Relational Juggling ($D$, 0–3 points)
- **0 points:** Terse, direct statements ($< 25$ words), 1–2 simple clauses.
- **1 point:** Moderate length ($25–40$ words), single reference frame.
- **2 points:** Multiple nested spatial clauses or relative preposition chains ("between X and Y, 2 m from X").
- **3 points:** Dense technical jargon or $>60$ words with multiple directional references.

### Effect of a Supporting Visual Diagram
When an accurate visual VDD diagram is provided alongside the text:
$$\text{Effective CDS} = \max(1, \text{Raw CDS} - 4)$$
The visual diagram externalizes the spatial entities and relative coordinates, reducing extraneous mental load by **4 points**.

---

## 2. Grade-by-Grade Benchmarks (Grades 6 to 13)

The table below sets the **maximum allowable raw text-only CDS score** before visual scaffolding
(diagram or visual schematic) becomes **mandatory**.

| Grade | Student Age | Stage / Van Hiele Level | Visuospatial Chunk Capacity | Max Text-Only CDS | Visual Scaffolding Threshold |
|:---:|:---:|:---|:---:|:---:|:---|
| **Grade 6** | 11–12 | Concrete Operational / Van Hiele 1 | 2–3 chunks | **$\le 3$** | Any problem with $\ge 2$ spatial entities or 2D offsets **MUST** provide a diagram. |
| **Grade 7** | 12–13 | Late Concrete / Van Hiele 1–2 | 3 chunks | **$\le 4$** | Multi-point coordinates, composite shapes, or polygon vertex reflections **MUST** provide a diagram. |
| **Grade 8** | 13–14 | Emerging Formal / Van Hiele 2 | 3–4 chunks | **$\le 4$** | Mentally rotating/folding non-rectilinear shapes or tracking $\ge 3$ relative offsets **MUST** provide a diagram. |
| **Grade 9** | 14–15 | Early Formal / Van Hiele 2–3 | 4 chunks | **$\le 5$** | Multi-axis reflections, 3D nets, or non-standard spatial orientations **MUST** provide a diagram. |
| **Grade 10** | 15–16 | Formal Operational (O/L Yr 1) | 4–5 chunks | **$\le 6$** | Can self-sketch standard 1-triangle or rectangle problems; composite solids or circle theorems **MUST** provide a diagram. |
| **Grade 11** | 16–17 | Formal Operational (G.C.E. O/L) | 5 chunks | **$\le 6$** | Complex geometric proofs and multi-stage spatial setups **MUST** provide a diagram unless self-sketching is the explicit rubric task. |
| **Grade 12** | 17–18 | Advanced Formal (G.C.E. A/L) | 5–6 chunks | **$\le 7$** | 3D coordinate frames, compound vector geometry, and multi-body setups **MUST** provide a schematic diagram. |
| **Grade 13** | 18–19 | Formal Rigor (G.C.E. A/L) | 6 chunks | **$\le 8$** | High text abstraction allowed; multi-region calculus, 3D mechanics, and complex physical setups require schematics. |

---

## 3. Remediation & Scaffolding Protocol

When an authored or proposed question exceeds the grade benchmark ($\text{CDS} > \text{Benchmark(Grade)}$):

### Step 1: Externalize with a VDD Diagram
Provide a clean VDD diagram in `diagram_dsl`. The diagram must clearly show:
1. The reference boundaries or geometric outline (e.g. lantern frame, pitch layout, octagon).
2. The axis of symmetry as a distinct dashed line or highlighted centerline.
3. Relevant labeled points, landmarks, or dimensions.
4. **Language-neutral landmarks (bilingual reuse):** Use single uppercase letters or standard mathematical tokens ($A, B, P, Q, H, F, W$) for points, objects, or landmarks instead of English prose words (e.g. avoid `"School"`, `"Home"`, `"Finish"`). In the question stem (`question_text` and `question_text_sinhala`), describe what each letter represents in the student's chosen language. This ensures the single shared diagram serves both English and Sinhala mediums naturally.

### Step 2: Chunk and Linearize the Text
Transform dense, nested paragraphs into structured, readable chunks:
- Use bullet points (`•`) for multiple coordinates or independent features.
- State the coordinate baseline or symmetry axis *first*, before referencing offsets.
- Remove nested prepositions ("between X and the axis, 2 m from X" → "Pillar P is 5 m left. Lamp L is placed between P and the axis, 2 m from P (so it is 3 m from the axis).").

### Step 3: Grade-Appropriate Concrete Metaphors
Avoid domain jargon overload. If using a real-world scenario (e.g. cricket pitch, Sigiriya garden, telescope mirror):
- Define the geometric meaning directly ("a straight centerline running from top to bottom").
- Keep distances intuitive and clearly anchored.

---

## 4. Automation & Tooling

Run the spatial load assessment CLI tool:

```bash
# Assess a single question stem for Grade 7:
python3 tools/assess-spatial-load.py --grade 7 --text "අටපට්ටම් වෙසක් කූඩුවක..."

# Assess an entire staged document:
python3 tools/assess-spatial-load.py --staged wt/staged.json --grade 7

# Display the benchmarks table:
python3 tools/assess-spatial-load.py --benchmarks

# Run the test suite:
python3 tools/assess-spatial-load.py --self-test
```

During authoring (`author-question-text`) and orchestration (`generate`), any stem with $\text{CDS} > \text{Benchmark(Grade)}$ that lacks a diagram is a **BLOCKING defect**.
During critique (`qgen-critic`), any question exceeding the benchmark without visual scaffolding must be flagged as a **MAJOR/BLOCKER** finding.
