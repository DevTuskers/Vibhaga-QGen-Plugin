#!/usr/bin/env bash
# run-gate.sh — the ONE offline gate over a generated staged doc (vibhaga-qgen).
# Moved from Vibhaga-Docs `.devin/skills/_maths-onboarding/run-gate.sh`; the paper-side checks
# (S7 manifest ↔ staged, quarantine ↔ verdicts join, split-PDF sha, paper_metadata scope) are gone —
# there is no source paper. What remains is everything that applies to a generated staged doc
# `{"questions":[...]}` (as produced by tools/build-staged.py) before a playground publish:
#
#   structure: question_number is a JSON number · is_multipart == (parts > 0) · nonempty label/text
#     per part · depth ≤ 2 · sort_order == index · uuid ids, no duplicates, no duplicate question_numbers
#   answers: every question has an answer · answer ids at the right level (answer_id on whole answers,
#     sub_answer_id inside sub-question nodes — `sub_answer` object or `answers[]`) · no verified_by/at,
#     no steps, no fully-empty answers · needs_human_review flag true on every question · artefact
#     answers carry a figure · approach paragraphs ≤ 180 chars
#   lessons: every question carries ≥ 1 lesson uuid (a mixed-lesson question may carry several — no cap)
#   scope: no `exam` key anywhere in the doc (playground items carry no exam — decision 0018 PD-6)
#   figures: whole-doc diagram_dsl ↔ figures/*.json canonical content equality (reuse allowed,
#     duplicate-content aliases WARN)
#   text: markdown gate 0 BLOCKED · odd-$ parity · KaTeX strict compile of every $…$ run · no Sinhala
#     inside \text{} · measured inline width (CLIP 0) when the Chromium measurer can run
#
# Usage:
#   run-gate.sh <run-dir> [--tools DIR] [--katex DIR] [--allow-skip-width] [--log gate-output.txt]
#   run-gate.sh --self-test [--allow-skip-width]   # clean fixture passes; planted fixture fires EVERY check
#
# <run-dir> holds: questions-<sub>.json (one or more) or staged.json/questions.json · optional
#   figures/*.json (`*.anchors.json` ignored). The gate writes fields-<sub>.json beside them — the
#   [{id, field, text}] list the markdown gate and the measurer read.
#
# Output: one line per check, `FAIL` at the end of a failing line, `WARN` for skipped optional inputs
# or figure aliases, then `N checks · M failed`. The measured-width check prints `SKIPPED (reason)
# FAIL` when the measurer cannot run; --allow-skip-width downgrades that to a WARN (say so in the ledger).
# Exit: 0 clean · 1 any FAIL · 2 usage / missing input.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
TOOLS=$HERE; KATEX=""; ALLOW_SKIP=0; SELF=0; RUN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tools) TOOLS=$2; shift 2;; --katex) KATEX=$2; shift 2;; --allow-skip-width) ALLOW_SKIP=1; shift;; --log) LOG=$2; shift 2;;
    --self-test) SELF=1; shift;; -h|--help) sed -n '2,32p' "$0"; exit 0;; *) RUN=$1; shift;;
  esac
done
for b in jq node python3; do command -v $b >/dev/null || { echo "run-gate: $b not found" >&2; exit 2; }; done
# Locate the Admin app (KaTeX + the renderer the measurer bundles): --katex, $VIBHAGA_ADMIN, or the
# sibling <plugin>/../Vibhaga-Admin — walk up from TOOLS so a moved checkout still finds it.
if [ -z "$KATEX" ]; then
  if [ -n "${VIBHAGA_ADMIN:-}" ]; then KATEX=$VIBHAGA_ADMIN/node_modules/katex
  else d=$TOOLS; while [ "$d" != / ]; do [ -d "$d/Vibhaga-Admin/node_modules/katex" ] && { KATEX=$d/Vibhaga-Admin/node_modules/katex; break; }; d=$(dirname "$d"); done; fi
fi
[ -d "$KATEX" ] || { echo "run-gate: KaTeX not found (pass --katex <Vibhaga-Admin>/node_modules/katex)" >&2; exit 2; }
KATEX=$(cd "$KATEX" && pwd); ADMIN=$(cd "$KATEX/../.." && pwd); UMB=$(dirname "$ADMIN")
export VIBHAGA_ADMIN=$ADMIN VIBHAGA_WEB=${VIBHAGA_WEB:-$UMB/Vibhaga-Web} VIBHAGA_ROOT=${VIBHAGA_ROOT:-$UMB}

N=0; F=0
ok()   { N=$((N+1)); echo "$1"; }
fail() { N=$((N+1)); F=$((F+1)); echo "$1  FAIL"; }
# check <id> <label> <actual> <wanted>
check() { if [ "$3" = "$4" ]; then ok "[$1] $2: $3"; else fail "[$1] $2: $3 (want $4)"; fi; }
warn() { echo "[$1] $2  WARN"; }

fields_py() { # $1 staged.json → fields json on stdout ([{id, field, text}] for markdown gate + measurer)
python3 - "$1" <<'PY'
import json, sys
s = json.load(open(sys.argv[1])); out = []
def add(i, f, t):
    if isinstance(t, str) and t.strip(): out.append({"id": i, "field": f, "text": t})
def answers(node):
    # the staged schema carries whole answers in `answers[]` and per-node sub-answers in BOTH
    # `sub_answer` (object) and `answers[]` (Vibhaga-API onboarding/publish.ts collectSubAnswers)
    yield from node.get("answers") or []
    sa = node.get("sub_answer")
    if isinstance(sa, dict): yield sa
for q in s["questions"]:
    qn = f"Q{q.get('question_number')}"
    add(qn, "question_text", q.get("question_text")); add(qn, "question_text_sinhala", q.get("question_text_sinhala"))
    for a in answers(q):
        add(qn, f"a:{a.get('answer_id') or a.get('sub_answer_id')}:approach", a.get("approach")); add(qn, f"a:{a.get('answer_id') or a.get('sub_answer_id')}:final", a.get("final_answer_latex"))
    def parts(lst, path, depth):
        sq, sa = ("sq", "sa") if depth == 1 else ("sq2", "sa2")
        for p in lst or []:
            pid = f"{path}/{p.get('label')}"
            add(pid, f"{sq}:{p.get('sub_question_id')}:text", p.get("text")); add(pid, f"{sq}:{p.get('sub_question_id')}:text_sinhala", p.get("text_sinhala"))
            for a in answers(p):
                add(pid, f"{sa}:{a.get('sub_answer_id') or a.get('answer_id')}:approach", a.get("approach")); add(pid, f"{sa}:{a.get('sub_answer_id') or a.get('answer_id')}:final", a.get("final_answer_latex"))
            parts(p.get("sub_questions"), pid, depth + 1)
    parts(q.get("sub_questions"), qn, 1)
print(json.dumps(out, ensure_ascii=False, indent=1))
PY
}

s8_s5_checks() { # $1 staged.json  $2 sub — structure + answers over the WHOLE doc (every staged question)
  local S=$1 P=$2 r
  r=$(jq -c '[.questions[] | select([.. | objects | select(has("answer_id") or has("sub_answer_id"))] | length == 0) | .question_number]' "$S"); check "$P/S8#1" "no answer anywhere" "$r" "[]"
  r=$(jq '[.questions[] | .. | objects | select(has("sub_question_id")) | ((.answers // [])[]?, (if .sub_answer == null then empty else .sub_answer end)) | select(type != "object" or (has("sub_answer_id") | not))] | length' "$S"); check "$P/S8#2a" "sub-answer keyed answer_id" "$r" 0
  r=$(jq '[.questions[].answers[]? | select(type != "object" or (has("answer_id") | not))] | length' "$S"); check "$P/S8#2b" "whole answer keyed sub_answer_id" "$r" 0
  r=$(jq '[.. | objects | select(has("verified_by") or has("verified_at"))] | length' "$S"); check "$P/S8#3" "verified_by/verified_at anywhere (whole doc)" "$r" 0
  r=$(jq '[.questions[] | .. | objects | select((.steps // [] | length) > 0 or .kind == "steps")] | length' "$S"); check "$P/S8#4" "steps / kind steps" "$r" 0
  r=$(jq '[.questions[] | .. | objects | select(has("answer_id") or has("sub_answer_id")) | select(((.approach // "")|gsub("^\\s+|\\s+$";"")) == "" and ((.final_answer_latex // "")|gsub("^\\s+|\\s+$";"")) == "" and (.diagram_dsl // null) == null)] | length' "$S"); check "$P/S8#5" "fully empty answers" "$r" 0
  r=$(jq -c '[.questions[] | select(.ingestion_metadata.needs_human_review != true) | .question_number]' "$S"); check "$P/S8#7" "unflagged questions" "$r" "[]"
  r=$(jq -c '[.questions[] | .. | objects | select(has("answer_id") or has("sub_answer_id")) | select((.diagram_dsl // null) == null) | select((.final_answer_latex // "") | test("draw|shade|mark|plot|sketch|figure|diagram|අඳින්න|ඇඳ|ලකුණු කර";"i")) | (.answer_id // .sub_answer_id)]' "$S"); check "$P/S8#8" "artefact answer without figure" "$r" "[]"
  r=$(jq -c '[.questions[] | .. | objects | select(has("answer_id") or has("sub_answer_id")) | select([ (.approach // "") | split("\n\n")[] | select(test("^\\s*[|*-]") | not) | length ] | max > 180) | (.answer_id // .sub_answer_id)]' "$S"); check "$P/S8#9" "prose paragraph > 180" "$r" "[]"
  r=$(jq -c '[.questions[] | select((.question_number|type) != "number") | .question_id]' "$S"); check "$P/S5#1" "question_number not a number" "$r" "[]"
  r=$(jq -c '[.questions[] | select((.is_multipart == true) != ((.sub_questions // [] | length) > 0)) | .question_number]' "$S"); check "$P/S5#2" "is_multipart mismatch" "$r" "[]"
  r=$(jq -c '[.. | objects | select(has("sub_question_id")) | select(((.label // "")|gsub("^\\s+|\\s+$";"")|length) == 0 or ((.text // "")|gsub("^\\s+|\\s+$";"")|length) == 0) | .sub_question_id]' "$S"); check "$P/S5#3" "empty label/text in parts" "$r" "[]"
  r=$(jq '[.questions[].sub_questions[]?.sub_questions[]?.sub_questions[]?] | length' "$S"); check "$P/S5#4" "depth-3 parts" "$r" 0
  r=$(jq '[.. | objects | select((.sub_questions|type) == "array") | .sub_questions | to_entries[] | select(.value.sort_order != .key)] | length' "$S"); check "$P/S5#5a" "sort_order != index (parts)" "$r" 0
  r=$(jq '[.questions | to_entries[] | select(.value.sort_order != .key)] | length' "$S"); check "$P/S5#5b" "sort_order != index (questions)" "$r" 0
  r=$(jq '[.. | objects | to_entries[] | select(.key | test("^(question|sub_question|answer|sub_answer)_id$")) | select((.value|type) != "string" or ((.value|test("^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$";"i")) | not))] | length' "$S"); check "$P/S5#6" "non-uuid ids" "$r" 0
  r=$(jq '[.. | objects | to_entries[] | select(.key | test("^(question|sub_question|answer|sub_answer)_id$")) | .value] | (length) - (unique | length)' "$S"); check "$P/S5#7" "duplicate ids" "$r" 0
  r=$(jq -c '[.questions[].question_number] | group_by(.) | map(select(length > 1) | .[0])' "$S"); check "$P/S5#qn" "duplicate question_numbers" "$r" "[]"
  r=$(jq -c '[.questions[] | select((.lesson_ids | type) != "array" or (.lesson_ids | length) == 0 or ([.lesson_ids[] | select(type == "string" and test("^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$";"i") | not)] | length) > 0) | .question_number]' "$S"); check "$P/lessons" "every question ≥1 lesson uuid" "$r" "[]"
  r=$(jq '[.. | objects | select(has("exam"))] | length' "$S"); check "$P/exam" "exam key anywhere (playground items carry no exam)" "$r" 0
  echo "[$P/info] question_text_sinhala non-null: $(jq '[.questions[] | select(.question_text_sinhala != null)] | length' "$S")"
}

figure_check() { # $1 staged  $2 sub  $3 run-dir — every diagram_dsl == some figures/*.json, every file used
  local S=$1 sub=$2 R=$3 r rc aliases
  r=$(python3 - "$S" "$sub" "$R" <<'PY'
import json, sys
from pathlib import Path

def normalize(value):
    if isinstance(value, dict):
        return {key: normalize(child) for key, child in value.items()}
    if isinstance(value, list):
        return [normalize(child) for child in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value

def canonical(value):
    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

def walk(value, path=()):
    if isinstance(value, dict):
        if value.get("diagram_dsl") is not None:
            yield path, canonical(value["diagram_dsl"])
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))

try:
    staged = json.loads(Path(sys.argv[1]).read_text())
    assets = {}
    for file in sorted((Path(sys.argv[3]) / "figures").glob("*.json")):
        if not file.name.endswith(".anchors.json"):
            assets[file.name] = canonical(json.loads(file.read_text()))
    names_by_content = {}
    for name, content in assets.items():
        names_by_content.setdefault(content, []).append(name)
    aliases = [names for names in names_by_content.values() if len(names) > 1]
    occurrences = list(walk(staged))
    declared, used = set(assets.values()), {value for _, value in occurrences}
    unmatched = ["/".join(map(str, path)) + "/diagram_dsl" for path, value in occurrences if value not in declared]
    unused = [name for name, value in assets.items() if value not in used]
    levels = dict.fromkeys(("q", "sq", "sq2", "a", "sa", "sa2", "other"), 0)
    for path, _ in occurrences:
        depth = path.count("sub_questions")
        level = ("sa" if depth else "a") if "answers" in path or "sub_answer" in path else ("sq" if depth else "q")
        if depth > 1:
            level += str(depth)
        levels[level if "questions" in path and level in levels else "other"] += 1
    print(json.dumps({"placements": len(occurrences), "files": len(assets), "by_level": levels,
                      "unmatched": unmatched, "unused": unused, "aliases": aliases}, ensure_ascii=False))
    sys.exit(bool(unmatched or unused))
except (OSError, ValueError, TypeError) as exc:
    print(f"figure coverage error: {exc}")
    sys.exit(1)
PY
); rc=$?
  aliases=$(printf '%s' "$r" | jq -c '.aliases // []' 2>/dev/null)
  if [ -n "$aliases" ] && [ "$aliases" != '[]' ]; then
    warn "$sub/figures#aliases" "duplicate-content aliases (content equality only; unique file use not proven): $aliases"
  fi
  if [ "$rc" -eq 0 ]; then ok "[$sub/figures] canonical JSON content equality (whole staged document): $r"
  else fail "[$sub/figures] canonical JSON content equality (whole staged document): $r"; fi
}

text_gates() { # $1 staged  $2 fields.json  $3 IDS  $4 sub
  local S=$1 Fj=$2 IDS=$3 P=$4 r est meas rc md
  fields_py "$S" > "$Fj"; echo "[$P/fields] $(jq length "$Fj") text fields → $Fj"
  est=$(python3 "$TOOLS/check-inline-math-width.py" "$S" --ids "$(echo "$IDS" | jq -r 'join(",")')" 2>&1 | tail -1); echo "[$P/info] S8#10 estimate: $est"
  meas=$(node "$TOOLS/measure-inline-math-width.mjs" --fields "$Fj" --min 0 2>&1); rc=$?
  echo "$meas" | grep -E "^(CLIP|TIGHT|NORENDER)" | sed 's/^/    /'
  if echo "$meas" | grep -q "run(s) rendered"; then
    r=$(echo "$meas" | grep -E "run\(s\) rendered" | tail -1 | sed -E 's/.*rendered · ([0-9]+) CLIP.*/\1/')
    check "$P/S8#10" "MEASURED inline width, CLIP count ($(echo "$meas" | grep -oE '[0-9]+ run\(s\)' | tail -1))" "$r" 0
  else
    r="SKIPPED ($(echo "$meas" | tail -1 | cut -c1-120))"
    if [ $ALLOW_SKIP -eq 1 ]; then warn "$P/S8#10" "MEASURED inline width: $r — --allow-skip-width"; else fail "[$P/S8#10] MEASURED inline width: $r"; fi
  fi
  md=$(node "$TOOLS/markdown-gate.mjs" --fields "$Fj" 2>&1); rc=$?
  echo "$md" | grep -E "^\s+\[(block|advice)\]" | sed 's/^/    /'
  r=$(echo "$md" | grep -E "fields · " | tail -1 | sed -E 's/.*· ([0-9]+) BLOCKED.*/\1/'); [ $rc -ne 0 ] && [ -z "$r" ] && r="rc=$rc"
  check "$P/md" "markdown gate BLOCKED ($(echo "$md" | grep -E 'fields · ' | tail -1))" "$r" 0
  r=$(python3 -c "
import re,json,sys; fs=json.load(open(sys.argv[1])); print(json.dumps([f['id']+' '+f['field'] for f in fs if re.search(r'\\\\text\{[^}]*[\u0D80-\u0DFF]', f['text'])]))" "$Fj"); check "$P/D7" "Sinhala inside \\text{}" "$r" "[]"
  r=$(jq -c '[.[] | select((.text | [scan("\\$")] | length) % 2 == 1) | .id + " " + .field]' "$Fj"); check "$P/G4" "odd \$ parity fields" "$r" "[]"
  r=$(node -e '
    const k=require(process.argv[1]); const fs=JSON.parse(require("fs").readFileSync(process.argv[2],"utf8"));
    let n=0, bad=[]; const RX=/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/gs;
    for (const f of fs) for (const m of String(f.text).replace(/\$\$[\s\S]*?\$\$/g," ").matchAll(RX)) { n++; try { k.renderToString(m[1],{throwOnError:true,strict:true}); } catch(e) { bad.push(f.id+" "+f.field+": "+m[1].slice(0,60)); } }
    console.log(JSON.stringify({runs:n, failed:bad}));' "$KATEX" "$Fj")
  check "$P/G4b" "KaTeX strict compile failures ($(echo "$r" | jq .runs) runs)" "$(echo "$r" | jq -c .failed)" "[]"
}

gate() { # $1 run-dir — every questions-<sub>.json, or staged.json / questions.json
  local R=$1 subs S sub IDS
  [ -d "$R" ] || { echo "run-gate: no such run dir $R" >&2; exit 2; }
  subs=$(find "$R" -maxdepth 1 -name 'questions-*.json' -exec basename {} \; | sed -nE 's/^questions-([A-Za-z0-9]+)\.json$/\1/p' | sort)
  [ -z "$subs" ] && [ -f "$R/staged.json" ] && subs=staged
  [ -z "$subs" ] && [ -f "$R/questions.json" ] && subs=_
  [ -z "$subs" ] && { echo "run-gate: no staged doc in $R (want questions-<sub>.json, staged.json or questions.json)" >&2; exit 2; }
  for sub in $subs; do
    if [ "$sub" = _ ]; then S=$R/questions.json; else S=$R/questions-$sub.json; fi
    [ "$sub" = staged ] && S=$R/staged.json
    IDS=$(jq -c '[.questions[].question_id]' "$S" 2>/dev/null) || { fail "[$sub/parse] staged doc is not valid JSON"; continue; }
    echo "===== Staged doc $sub  ($S)  $(echo "$IDS" | jq length) question(s)"
    s8_s5_checks "$S" "$sub"
    figure_check "$S" "$sub" "$R"
    text_gates "$S" "$R/fields-$sub.json" "$IDS" "$sub"
  done
  echo "===== $N checks · $F failed"
  [ "$F" -eq 0 ]
}

self_test() {
  local T FX BX out clean_rc fired=0 want=0 id
  T=$(mktemp -d /tmp/run-gate-selftest.XXXX); FX=$T/clean; mkdir -p "$FX/figures"
  python3 - "$FX" <<'PY'
import json, sys
from pathlib import Path

FX = Path(sys.argv[1])
U = lambda n: f"00000000-0000-4000-8000-0000000000{n:02d}"
FIG = {"schema": "vibhaga.diagram", "schemaVersion": 1, "canvas": {"width": 200, "height": 100},
       "defaults": {"strokeWidth": 2, "fontSize": 18},
       "a11y": {"title": "Synthetic rectangle ABCD", "description": "A rectangle with vertices A, B, C, D."},
       "elements": [{"id": "AB", "type": "line", "points": [[20, 20], [180, 20]]},
                    {"id": "BC", "type": "line", "points": [[180, 20], [180, 80]]},
                    {"id": "CD", "type": "line", "points": [[180, 80], [20, 80]]},
                    {"id": "DA", "type": "line", "points": [[20, 80], [20, 20]]}]}
ANS = lambda i, approach, final: {"answer_id": U(i), "approach": approach, "final_answer_latex": final}
staged = {"questions": [
    {"question_id": U(1), "question_number": 1, "sort_order": 0, "is_multipart": False,
     "question_text": "A cuboid face is $5\\,\\text{cm}$ by $2\\,\\text{cm}$. Find its area.",
     "question_text_sinhala": None, "lesson_ids": [U(11)], "diagram_dsl": None,
     "answers": [ANS(2, "Area $=$ length $\\times$ width.\n\n- $5 \\times 2$", "$10\\,\\text{cm}^2$")],
     "ingestion_metadata": {"needs_human_review": True}},
    {"question_id": U(3), "question_number": 2, "sort_order": 1, "is_multipart": True,
     "question_text": "A rectangle is $10$ cm by $4$ cm.", "lesson_ids": [U(11), U(12)],
     "sub_questions": [
        {"sub_question_id": U(4), "label": "a", "sort_order": 0, "text": "Find the perimeter.",
         "sub_answer": {"sub_answer_id": U(5), "approach": "$2(10+4)$", "final_answer_latex": "28"}},
        {"sub_question_id": U(6), "label": "b", "sort_order": 1, "text": "Find the area.",
         "sub_answer": {"sub_answer_id": U(7), "approach": "$10 \\times 4$", "final_answer_latex": "40"}}],
     "ingestion_metadata": {"needs_human_review": True}},
    {"question_id": U(8), "question_number": 3, "sort_order": 2, "is_multipart": False,
     "question_text": "The rectangle in the figure has sides in the ratio $9:4$.", "lesson_ids": [U(12)],
     "diagram_dsl": FIG, "answers": [ANS(9, "Count the units.", "9:4")],
     "ingestion_metadata": {"needs_human_review": True}}]}
(FX / "questions-I.json").write_text(json.dumps(staged, ensure_ascii=False))
(FX / "figures" / "q3.json").write_text(json.dumps(FIG))
PY
  echo "===== self-test 1/2: clean fixture ($FX) must pass"
  out=$(gate "$FX"); clean_rc=$?
  if [ $clean_rc -ne 0 ]; then echo "$out" | grep -E "FAIL$"; echo "self-test: CLEAN FIXTURE FAILED"; exit 1; fi
  echo "  PASS clean fixture: $(echo "$out" | tail -1 | sed 's/^===== //')"
  # Broken fixture: one planted defect per check (T13 — every check must be SEEN to fire).
  BX=$T/broken; mkdir -p "$BX/figures"; cp "$FX"/questions-I.json "$BX/"; cp "$FX"/figures/*.json "$BX/figures/"
  python3 - "$BX" <<'PY'
import json, sys
from pathlib import Path

BX = Path(sys.argv[1])
U = lambda n: f"00000000-0000-4000-8000-0000000000{n:02d}"
s = json.loads((BX / "questions-I.json").read_text())
q0, q1, q2 = s["questions"]
q0["question_number"] = "1"                                            # S5#1
q0["is_multipart"] = True                                              # S5#2 (has no parts)
q0["ingestion_metadata"]["needs_human_review"] = False                 # S8#7
q0["answers"][0]["final_answer_latex"] = "draw the rectangle"          # S8#8 (diagram_dsl is null)
q0["answers"][0]["verified_by"] = "someone"                            # S8#3
q0["answers"][0]["steps"] = ["a"]                                      # S8#4
q0["answers"].append({"answer_id": U(20), "approach": "", "final_answer_latex": "", "diagram_dsl": None})  # S8#5
q0["answers"].append({"sub_answer_id": U(21), "approach": "x", "final_answer_latex": "y"})              # S8#2b
q0["answers"].append({"answer_id": U(26), "approach": "a", "final_answer_latex": "$\\sum fx = 96 + 180 + 400 + 396 + 144 + 1000 + 2000 + 3000 = 1216$"})  # S8#10 CLIP (measured)
q0["answers"][0]["approach"] = "x" * 200                               # S8#9
q0["question_text"] = "Find $x$ if $y$ is $3"                          # G4 odd $
q0["exam"] = "ol"                                                      # exam key
q0["lesson_ids"] = ["not-a-uuid"]                                      # lessons
q1["sub_questions"][0]["label"] = ""                                   # S5#3
q1["sub_questions"][0]["answers"] = [{"answer_id": U(22), "approach": "a", "final_answer_latex": "b"}]  # S8#2a
q1["sub_questions"][1]["sub_questions"] = [{"sub_question_id": U(23), "label": "i", "sort_order": 0, "text": "t",
    "sub_questions": [{"sub_question_id": U(24), "label": "x", "sort_order": 0, "text": "t"}]}]         # S5#4 depth-3
q1["sub_questions"][1]["sort_order"] = 7                               # S5#5a
q2["sort_order"] = 99                                                  # S5#5b
q2["answers"][0]["answer_id"] = "not-a-uuid"                           # S5#6 (+#1b below)
q2["question_number"] = 2                                              # S5#qn duplicate
q2["lesson_ids"] = []                                                  # lessons (empty)
q2["question_text"] = "$5\\text{ සෙ.මී.}$ and $\\fract{1}{2}$"           # D7 + G4b
q1["question_text"] = "a <script>x</script> b"                         # markdown BLOCKED
s["questions"].append({"question_id": U(8), "question_number": 4, "sort_order": 3, "is_multipart": False,
    "question_text": "Orphan question with no answer.", "lesson_ids": [U(11)],
    "answers": [], "ingestion_metadata": {"needs_human_review": True}})                                  # S8#1 (+S5#7 dup id)
q2["diagram_dsl"] = {"changed": "not the file content"}                # figures (unmatched placement)
(BX / "questions-I.json").write_text(json.dumps(s, ensure_ascii=False))
PY
  echo '{"different": true}' > "$BX/figures/extra.json"                                                # figures (unused file)
  echo "===== self-test 2/2: broken fixture ($BX) must fire EVERY check"
  out=$(gate "$BX"); echo "$out" | grep -E "FAIL$" | sed 's/^/  FIRED  /'
  local ids="I/S8#1 I/S8#2a I/S8#2b I/S8#3 I/S8#4 I/S8#5 I/S8#7 I/S8#8 I/S8#9 I/S8#10 I/S5#1 I/S5#2 I/S5#3 I/S5#4 I/S5#5a I/S5#5b I/S5#6 I/S5#7 I/S5#qn I/lessons I/exam I/figures I/md I/D7 I/G4 I/G4b"
  for id in $ids; do
    want=$((want+1))
    if echo "$out" | grep -F -e "[$id]" | grep -qE "FAIL$"; then fired=$((fired+1)); else echo "  silent [$id] (expected to fire!)"; fi
  done
  echo "fixture: $fired/$want checks fired"
  rm -rf "$T"
  [ "$fired" -eq "$want" ] || { echo "self-test: FAILED"; exit 1; }
  echo "self-test: PASS"; exit 0
}

if [ $SELF -eq 1 ]; then self_test; fi
[ -n "$RUN" ] || { echo "usage: run-gate.sh <run-dir> [--tools DIR] [--katex DIR] [--allow-skip-width] [--log FILE] | --self-test" >&2; exit 2; }
if [ -n "${LOG:-}" ]; then
  gate "$RUN" 2>&1 | tee "$LOG"; rc=${PIPESTATUS[0]}; exit "$rc"
fi
gate "$RUN"
