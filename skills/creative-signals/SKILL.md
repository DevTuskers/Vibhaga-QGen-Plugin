---
name: creative-signals
description: >-
  Gather real-world "creative signals" by web search before a generate plan is sketched — Sri Lankan
  and international news (current and past), historical facts and anniversaries, sports statistics
  (cricket, Olympics), science and space events, Sri Lankan geography, environment and culture
  (festivals, landmarks, agriculture, economy), and technology or everyday-life data — then keep only
  the signals that fit the lesson's maths, the grade and a school audience, and write them to
  signals.md. Every plan line in generate is anchored to one signal and carries a short creativity
  rubric. Use at generate step 2b, or whenever plan lines keep colliding with existing questions.
argument-hint: "[grade] [lesson number] [how many questions]"
---

# Creative signals — real-world anchors for a plan (generate step 2b)

**Why this exists.** Plans written from the lesson alone drift to the lesson's own stories and task chains,
and the plan critic then replaces 4–6 lines in ten (logbook, 2026-10 runs). A question built on a real fact
gets a context nobody has used, and — if the task comes from the data's own shape — a task chain nobody has
used. The dedup step ([generate §Copy check](../generate/SKILL.md#copy-check)) is unchanged: signals make a
collision rare, they never excuse one.

**Who does it.** The writer, after reading the scope card's teaching text (step 2) and before sketching
`plan-items.yaml` (step 3). Signals are outside the corpus, so they do not break the blind-writer rule.
Never paste card examples, exercises or live rows into a search.

## 1. Budget (lean runs)

- About **6 web searches and 4 page reads** for a 10-question batch, one pass, no re-searching later rounds.
- Collect **12–15 candidates**, keep **at least one per planned question** (a signal may feed two questions
  only if their task chains differ).
- **No two lines in a batch share a task chain.** Reusing one signal for two lines is the commonest way to repeat a chain ("halve the span, then mirror a distance" told in two stories). Before running `similar`, write each line's abstract operation chain beside it and compare the lines pairwise.
- Spread a batch across **at least 3 categories** and use **at least 3 Sri Lankan signals** in ten.

## 2. Signal categories

Start from the lesson's maths, then ask which real situation naturally contains that maths.

| Category | Look for (examples, not a list to copy) |
|---|---|
| News — Sri Lankan and international, current and past | infrastructure openings (expressways, bridges, ports), school and exam calendars, weather and monsoon rainfall, new bus or train services, world records |
| History and anniversaries | events falling in this month or term (today's date, Asia/Colombo), ancient Sri Lankan engineering (tanks, stupas, Sigiriya), inventions, famous journeys |
| Sports statistics | cricket (Sri Lanka scorecards, run rates, overs, World Cup records), Olympics and Asian Games results, athletics times, netball, volleyball |
| Science and space | launches and missions, eclipses and meteor showers visible from Sri Lanka, planet facts, animal speeds, the human body, scientific records |
| Sri Lankan geography, environment and culture | festivals (Avurudu, Vesak, Poson, Esala Perahera, Deepavali, Christmas, Ramazan), landmarks (Sigiriya, Sri Pada, Ruwanweliseya, Galle Fort), rivers and mountains, rainforests and wildlife (Sinharaja, Yala, elephants, turtles), agriculture (tea, paddy, coconut, rubber, cinnamon), economy (exports, tourism, fishing) |
| Technology and everyday life | mobile data packs, electricity units on a bill, bus and train fares, cooking and recipes, phone battery and screen time, solar panels, recycling |

## 3. Keep a signal only if it passes all four

1. **Maths fit.** The lesson's section concept appears in the data itself (a Mass lesson → tea leaves weighed
   at a factory; a Time lesson → a train timetable or a launch countdown). A signal that only decorates the
   story fails.
2. **Grade fit.** The numbers can be made friendly for the grade without lying (§4), the reading level fits, and
   the data does not need anything on the card's `not_taught` list (negative numbers, percentages, large
   numbers, decimals — whatever the card refuses).
3. **School-appropriate.** Neutral and safe for a 10–17-year-old and their teacher. Drop: deaths, injuries and
   casualty counts; war, terror, crime; party politics, elections and politicians; claims that compare religions or
   ethnic groups (a festival as a cultural event is fine); gambling and betting; alcohol and tobacco; brand
   advertising; private people's data. Named living people only for neutral sports or science achievements.
4. **Verifiable.** You read the number on a source page (news site, official body, encyclopaedia) and record the
   URL and its date. No source → not a signal.

## 4. Honest numbers

- A stem stays **self-contained**: every number the student needs is in the stem. The signal gives the context,
  never required outside knowledge.
- State a real figure as fact only when it is the sourced value, or a clearly rounded one ("about 2 200 m high").
- When the arithmetic needs other numbers, change the framing, not the facts: "A school group visits
  Sigiriya …", "Suppose a shop sells …". Never present an invented statistic as real. ([T155](../../docs/TRAPS.md))
- "Current" news: check the event date against the run date; do not use an event whose result is still open.
- Sinhala names of places and festivals are the everyday Sinhala ones (සීගිරිය, පොසොන්); units stay English
  symbols after numbers (T150).

## 5. Write `$A/signals.md`

One table, written before any plan line:

```
| S# | category | fact (one line, with its numbers) | source URL · date read | lesson section fit | grade fit / not_taught check | safe |
```

Then a line `searches: N · page reads: M · kept: K of C`.

## 6. Anchor each plan line, and add the creativity rubric

- **Let the data choose the task, not only the story.** Ask what a person in that situation would really need
  to work out (a scorer: overs left at the required rate; a tea factory: how many bags from a day's plucking;
  a launch team: the time in Sri Lanka). A lesson exercise retold with a cricket story is still a copy
  (Copy check), so the chain must come from the signal.
- Every plan line in `notes.md` carries `signal: S<k>` and the rubric:
  `· students: <why it is interesting to a student> · teachers: <what it adds for a teacher — a link to
  another subject, a real-world habit, a common misconception>`.
- Every item in `plan-items.yaml` carries `signal: S<k>` (the `similar` tool and `dedup-sheet.py` ignore it; the
  plan critic reads it).
- A line with no fitting signal is not filled with a generic context: drop it, or take the next thin lesson
  ([Room left and stop rule](../generate/SKILL.md#room-left-and-stop-rule)).

## 7. What the plan critic checks

The plan critic reads `signals.md` with the plan ([`qgen-critic` §8](../../agents/qgen-critic.md)): every line
cites a kept signal, the plan uses the fact honestly (§4), the signal is school-appropriate (§3.3) and in scope
(§3.2). A missing, misused or unsafe signal is a REPLACE, like a copied chain.
