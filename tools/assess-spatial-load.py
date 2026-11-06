#!/usr/bin/env python3
"""assess-spatial-load.py — Assess cognitive decoding and spatial imagery load for question descriptions.

Implements the Cognitive Decoding & Spatial Imagery Index (CDS Index) across Grades 6 to 13,
grounded in Cognitive Load Theory (Sweller), Visuospatial Working Memory capacity (Baddeley, Cowan),
and Van Hiele geometric levels.

Usage:
  assess-spatial-load.py --text "..." --grade 7
  assess-spatial-load.py --staged staged.json [--grade 7]
  assess-spatial-load.py --benchmarks
  assess-spatial-load.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Grade benchmarks: Maximum allowable text-only CDS score before visual scaffolding
# (diagram or diagrammatic layout) becomes developmentally mandatory.
GRADE_BENCHMARKS: Dict[int, Dict[str, Any]] = {
    6: {
        "age": "11–12",
        "stage": "Concrete Operational / Van Hiele 1 (Visualization)",
        "vswm_chunks": "2–3 spatial elements",
        "max_text_cds": 3,
        "rule": "Mandatory diagram for any problem with >=2 spatial entities or 2D relative offsets."
    },
    7: {
        "age": "12–13",
        "stage": "Late Concrete Operational / Van Hiele 1–2",
        "vswm_chunks": "3 spatial elements",
        "max_text_cds": 4,
        "rule": "Mandatory diagram for multi-point coordinates, 2D composite shapes, or polygon vertex reflections."
    },
    8: {
        "age": "13–14",
        "stage": "Emerging Formal Operational / Van Hiele 2 (Analysis)",
        "vswm_chunks": "3–4 spatial elements",
        "max_text_cds": 4,
        "rule": "Mandatory diagram for >=3 relative offsets, non-rectilinear shapes, or internal geometric partitions."
    },
    9: {
        "age": "14–15",
        "stage": "Early Formal Operational / Van Hiele 2–3",
        "vswm_chunks": "4 spatial elements",
        "max_text_cds": 5,
        "rule": "Mandatory diagram for multi-axis reflections, 3D nets, or non-standard orientations."
    },
    10: {
        "age": "15–16",
        "stage": "Formal Operational (O/L) / Van Hiele 3 (Informal Deduction)",
        "vswm_chunks": "4–5 spatial elements",
        "max_text_cds": 6,
        "rule": "Can mentally construct standard 1-triangle or simple rectangle narratives; diagram required for composite solids or circle theorems."
    },
    11: {
        "age": "16–17",
        "stage": "Formal Operational (O/L Exit) / Van Hiele 3",
        "vswm_chunks": "5 spatial elements",
        "max_text_cds": 6,
        "rule": "Diagram mandatory for complex geometric proofs or multi-stage physical setups unless sketching is the explicit task."
    },
    12: {
        "age": "17–18",
        "stage": "Advanced Formal Operational (A/L) / Van Hiele 3–4",
        "vswm_chunks": "5–6 spatial elements",
        "max_text_cds": 7,
        "rule": "Diagram mandatory for 3D coordinate systems, multi-body mechanics, or compound vector geometries."
    },
    13: {
        "age": "18–19",
        "stage": "Rigor (A/L Exit) / Van Hiele 4",
        "vswm_chunks": "6 spatial elements",
        "max_text_cds": 8,
        "rule": "Text abstraction permitted for standard mathematical formulations; diagrams required for multi-region calculus or complex physical systems."
    },
}

# Regex cues for spatial entities and landmarks (English and Sinhala)
SPATIAL_ENTITY_CUES = [
    # English
    r"\b(axis|line of symmetry|perpendicular|crease|stump|pitch|fountain|wall|pond|pool|pavilion|pillar|lamp|cross|flag|mirror|telescope|lantern|tassel|rampart|gate|watchtower|corner|vertex|vertices|edge|face|hexagon|octagon|pentagon|rectangle|triangle|circle)\b",
    # Sinhala
    r"(සමමිති\s*අක්ෂ|අක්ෂය|රේඛාව|කඩුලු\s*කණුව|තණතීරුව|රිටර්න්\s*ක්‍රීස්|බෝලිං\s*ක්‍රීස්|දිය\s*උල්පත|තාප්පය|පොකුණ|පත්තිරිප්පුව|මණ්ඩපය|කණුව|පහන|කුරුසය|කොඩිය|දර්පණය|දුරේක්ෂය|කූඩුව|පඬි|ප්‍රාකාරය|දොරටුව|මුරකොටුව|කොන|ශීර්ෂ|දාරය|පැත්ත|ෂඩස්‍ර|අෂ්ටාස්‍ර|පංචාස්‍ර|සෘජුකෝණාස්‍ර|ත්‍රිකෝණ|වෘත්ත)",
]

# Coordinate offset and spatial preposition cues
TRANSFORMATION_CUES = [
    # English
    r"\b(left|right|above|below|north|south|east|west|northeast|northwest|southeast|southwest|midpoint|center|centre|opposite|between|distance|apart|reflect|reflected|fold|folded|coincide|symmetric|corresponding)\b",
    # Sinhala
    r"(වමින්|දකුණින්|ඉහළින්|පහළින්|උතුර|දකුණ|නැගෙනහිර|බටහිර|ඊසාන|වයඹ|ගිනිකොන|නිරිත|මධ්‍ය\s*ලක්ෂ්‍ය|මැද|හරි\s*මැද|සම්මුඛ|අතර|දුරින්|පරතරය|නැමූ|සම්පාත|අනුරූප|සමමිතික)",
]

# Multi-coordinate or nested spatial markers (points labeled A, B, C... or offsets)
COORDINATE_GRID_CUES = [
    r"[A-H]\s*,\s*(අක්ෂයට|to the axis)",
    r"\d+\s*(cm|mm|m|km)\s*(වමින්|දකුණින්|left|right)",
    r"\d+\s*(cm|mm|m|km)\s*(පහළින්|ඉහළින්|below|above)",
    r"(ශීර්ෂ|vertices)\s*[,:]?\s*[A-Z]",
]


def score_entity_count(text: str) -> int:
    """Component 1: Spatial Entity & Layout Count (E, 0-3 points)."""
    matches = set()
    for pattern in SPATIAL_ENTITY_CUES:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            matches.add(m.group(0).lower())
    count = len(matches)
    if count == 0:
        return 0
    elif count <= 2:
        return 1
    elif count <= 4:
        return 2
    else:
        return 3


def score_transformation_complexity(text: str) -> int:
    """Component 2: Mental Coordinate / Transformation Demands (T, 0-4 points)."""
    # Check for heavy multi-coordinate grid patterns (e.g. A at x,y; B at x,y; C at x,y)
    grid_matches = 0
    for pat in COORDINATE_GRID_CUES:
        grid_matches += len(re.findall(pat, text, re.IGNORECASE))

    # Check for compass direction networks
    compass_cues = len(re.findall(r"(උතුර|දකුණ|නැගෙනහිර|බටහිර|ඊසාන|වයඹ|ගිනිකොන|නිරිත|north|south|east|west|northeast|northwest)", text, re.IGNORECASE))

    # Check for folding / reflection / diagonal mappings
    fold_cues = len(re.findall(r"(නැමූ|සම්පාත|විකර්ණ|diagonal|fold|coincide|reflection|අනුරූප)", text, re.IGNORECASE))

    score = 0
    if grid_matches >= 3 or compass_cues >= 4:
        score = 4
    elif grid_matches >= 1 or fold_cues >= 2 or compass_cues >= 2:
        score = 3
    elif fold_cues >= 1:
        score = 2
    else:
        # Standard 1D distance checks
        has_transform = False
        for pattern in TRANSFORMATION_CUES:
            if re.search(pattern, text, re.IGNORECASE):
                has_transform = True
                break
        score = 1 if has_transform else 0

    return min(4, score)


def score_text_density(text: str) -> int:
    """Component 3: Text Density & Relational Juggling (D, 0-3 points)."""
    # Count words / words roughly
    words = re.findall(r"\S+", text)
    word_count = len(words)

    # Check for nested preposition phrases
    prep_count = len(re.findall(r"(අතර|සිට|දක්වා|මත|ඔස්සේ|between|from|to|along|across)", text, re.IGNORECASE))

    if word_count > 60 or prep_count >= 5:
        return 3
    elif word_count > 35 or prep_count >= 3:
        return 2
    elif word_count > 15:
        return 1
    return 0


def assess_question_text(text: str, grade: int = 7, has_diagram: bool = False) -> Dict[str, Any]:
    """Calculate the Cognitive Decoding & Spatial Imagery (CDS) score of a stem."""
    if not text.strip():
        return {
            "score": 0,
            "components": {"E": 0, "T": 0, "D": 0},
            "grade": grade,
            "benchmark": GRADE_BENCHMARKS.get(grade, GRADE_BENCHMARKS[7])["max_text_cds"],
            "has_diagram": has_diagram,
            "status": "PASS",
            "action": "Text is empty.",
            "recommendations": []
        }

    e_score = score_entity_count(text)
    t_score = score_transformation_complexity(text)
    d_score = score_text_density(text)
    raw_cds = e_score + t_score + d_score

    # A provided diagram externally scaffolds entities and transformations, reducing extraneous mental load by ~4 points
    effective_cds = max(1, raw_cds - 4) if has_diagram else raw_cds

    benchmark_info = GRADE_BENCHMARKS.get(grade, GRADE_BENCHMARKS[7])
    max_cds = benchmark_info["max_text_cds"]

    recs: List[str] = []
    if not has_diagram:
        if raw_cds > max_cds:
            status = "FAIL"
            recs.append(f"Cognitive load score ({raw_cds}/10) exceeds Grade {grade} benchmark ({max_cds}/10).")
            recs.append("MANDATORY: Provide a visual VDD diagram to externalize the spatial configuration.")
            if t_score >= 3:
                recs.append("Simplify coordinate descriptions: avoid presenting multi-point offsets (x,y) purely in prose.")
            if d_score >= 2:
                recs.append("Chunk text: use bullet points or separate sentences for distinct spatial features.")
        elif raw_cds == max_cds:
            status = "WARN"
            recs.append(f"Cognitive load score ({raw_cds}/10) is at the maximum threshold for Grade {grade}.")
            recs.append("RECOMMENDED: Add a supporting diagram or clarify spatial landmarks with bulleted chunking.")
        else:
            status = "PASS"
            recs.append(f"Cognitive load score ({raw_cds}/10) is within Grade {grade} benchmark ({max_cds}/10).")
    else:
        status = "PASS"
        recs.append(f"Scaffolded with visual diagram: effective cognitive load reduced to {effective_cds}/10 (raw: {raw_cds}/10).")

    return {
        "raw_cds": raw_cds,
        "effective_cds": effective_cds,
        "components": {
            "E_entities": e_score,
            "T_transformations": t_score,
            "D_density": d_score,
        },
        "grade": grade,
        "benchmark": max_cds,
        "grade_details": benchmark_info,
        "has_diagram": has_diagram,
        "status": status,
        "recommendations": recs,
    }


def assess_staged_doc(staged_path: Path, grade: Optional[int] = None) -> List[Dict[str, Any]]:
    """Assess all questions in a staged document."""
    data = json.loads(staged_path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    session_grade = grade or data.get("session", {}).get("grade") or 7

    results = []
    for q in questions:
        q_num = q.get("question_number")
        text = q.get("question_text_sinhala") or q.get("question_text") or ""
        has_diagram = bool(q.get("diagram_dsl"))
        assessment = assess_question_text(text, grade=session_grade, has_diagram=has_diagram)
        results.append({
            "question_number": q_num,
            "question_id": q.get("question_id"),
            "text_preview": text[:80].replace("\n", " "),
            "has_diagram": has_diagram,
            "assessment": assessment,
        })
    return results


def run_self_test() -> int:
    """Run internal tests verifying the scoring model against grade benchmarks."""
    # Test 1: Simple 1D line question (low load)
    q_low = "රේඛාවක දිග $10$ cm වේ. එහි හරි මැද ලක්ෂ්‍යය $M$ නම්, එක් කෙළවරක සිට $M$ ට ඇති දුර සොයන්න."
    res_low = assess_question_text(q_low, grade=7)
    assert res_low["raw_cds"] <= 3, f"Expected low CDS, got {res_low['raw_cds']}"
    assert res_low["status"] == "PASS"

    # Test 2: Multi-point coordinates in text without diagram (overload for G7/8)
    q_high = (
        "අටපට්ටම් වෙසක් කූඩුවක ඉදිරිපසට සිරස් සමමිති අක්ෂයක් ඇත.\n"
        "එහි පහත ස්ථානවල කඩදාසි පඬි එල්ලා ඇත:\n"
        "A, අක්ෂයට 6 cm වමින් සහ ඉහළ කෙළවරට 10 cm පහළින්.\n"
        "B, අක්ෂයට 6 cm දකුණින් සහ ඉහළ කෙළවරට 10 cm පහළින්.\n"
        "C, අක්ෂයට 4 cm වමින් සහ ඉහළ කෙළවරට 12 cm පහළින්.\n"
        "D, අක්ෂයට 4 cm දකුණින් සහ ඉහළ කෙළවරට 12 cm පහළින්.\n"
        "E, අක්ෂයට 6 cm දකුණින් සහ ඉහළ කෙළවරට 12 cm පහළින්."
    )
    res_high = assess_question_text(q_high, grade=7, has_diagram=False)
    assert res_high["raw_cds"] >= 7, f"Expected high CDS >= 7, got {res_high['raw_cds']}"
    assert res_high["status"] == "FAIL", f"Expected FAIL for G7 without diagram, got {res_high['status']}"

    # Test 3: Same question WITH diagram scaffolds cognitive load
    res_scaffolded = assess_question_text(q_high, grade=7, has_diagram=True)
    assert res_scaffolded["status"] == "PASS", "Diagram scaffolding must pass"
    assert res_scaffolded["effective_cds"] < res_scaffolded["raw_cds"]

    # Test 4: Grade progression bounds
    for g in range(6, 14):
        assert g in GRADE_BENCHMARKS
        assert GRADE_BENCHMARKS[g]["max_text_cds"] >= 3

    print("assess-spatial-load --self-test: PASS — 4 checks ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess cognitive decoding and spatial imagery load.")
    parser.add_argument("--text", help="Question text to assess")
    parser.add_argument("--staged", type=Path, help="Staged questions JSON file")
    parser.add_argument("--grade", type=int, default=7, help="Student grade (6 to 13, default: 7)")
    parser.add_argument("--diagram", action="store_true", help="Whether a supporting diagram is provided")
    parser.add_argument("--benchmarks", action="store_true", help="Print benchmarks across Grades 6 to 13")
    parser.add_argument("--self-test", action="store_true", help="Run internal tests")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.benchmarks:
        print("=== Cognitive Decoding & Spatial Imagery (CDS) Grade Benchmarks ===")
        print("Grade | Age   | Max Text CDS | VSWM Chunks | Developmental Stage")
        print("------|-------|--------------|-------------|--------------------")
        for g, b in GRADE_BENCHMARKS.items():
            print(f"G{g:<4} | {b['age']:<5} | {b['max_text_cds']:<12} | {b['vswm_chunks']:<11} | {b['stage']}")
        return 0

    if args.text:
        res = assess_question_text(args.text, grade=args.grade, has_diagram=args.diagram)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["status"] == "PASS" else 1

    if args.staged:
        results = assess_staged_doc(args.staged, grade=args.grade)
        print(f"Assessed {len(results)} question(s) from {args.staged} for Grade {args.grade}:")
        fails = 0
        for r in results:
            a = r["assessment"]
            diag_flag = " [VDD Diagram]" if r["has_diagram"] else " [NO Diagram]"
            status_str = a["status"]
            print(f"Q{r['question_number']}: CDS {a['raw_cds']}/10 (effective: {a['effective_cds']}/10){diag_flag} -> {status_str}")
            if status_str != "PASS":
                fails += 1
                for rec in a["recommendations"]:
                    print(f"    * {rec}")
        return 1 if fails > 0 else 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
