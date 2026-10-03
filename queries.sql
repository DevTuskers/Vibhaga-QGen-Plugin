-- vibhaga-qgen — ready-made read-only queries (W5).
--
-- Run with psql variables, e.g.
--   psql "$CONTENT_DB_URL" -v lesson_id=<uuid> -f queries.sql          (then pick the block you need)
-- or paste one block into a SQL console, replacing each :'name' / :name placeholder by hand.
-- Every block is a single SELECT: nothing here writes, and nothing selects a secret or a token value.
-- Column names checked against information_schema on 2026-09-30 (questions.lesson_ids is uuid[],
-- sub_questions.sub_question_id is the part key, auth.refresh_tokens.user_id is varchar).
-- Q4 columns checked 2026-10-02 (lessons.sort_order, sub_answers.sub_question_id, answers/sub_answers.diagram_dsl).
-- Which database each block targets is stated in its header. Hosts and project refs are NOT in this
-- public file: see Vibhaga-Docs AGENTS.md § "Onboarding-tool verification" for the two projects.
-- Blocks Q2 and Q3 are run non-interactively by `tools/sql-proof.py` (read-only; exits on the `ok` column).


-- ============================================================================================
-- Q1 — Dedup by lesson                                              DATABASE: content
-- Variables: lesson_id (uuid).
-- Every question tagged with the lesson: drafts and published, flagged or not, papered or
-- paperless. Read the excerpt, then the full row, before judging a planned question a duplicate.
-- Zero rows is a real answer (the lesson has no questions yet), not an error — but check the
-- lesson id first: Q1a returns 1 when the lesson exists.
-- ============================================================================================

-- Q1a — the lesson exists (expect 1)
SELECT count(*) AS lesson_exists FROM lessons WHERE lesson_id = :'lesson_id'::uuid;

-- Q1b — the questions tagged with it
SELECT q.question_id,
       q.status,
       q.needs_human_review,
       q.source_paper_id IS NULL                         AS paperless,
       q.source_batch_id,
       q.question_number,
       cardinality(q.lesson_ids)                         AS lesson_count,
       (SELECT count(*) FROM sub_questions s WHERE s.question_id = q.question_id) AS parts,
       left(q.question_text, 240)                        AS stem_excerpt
FROM questions q
WHERE :'lesson_id'::uuid = ANY (q.lesson_ids)
ORDER BY q.source_paper_id NULLS FIRST, q.source_batch_id, q.question_number, q.question_id;


-- ============================================================================================
-- Q2 — Post-publish proof for a playground session                  DATABASE: content
-- Variables: batch_id (uuid — the session id), expected (int — how many questions you published,
-- from your ledger).
-- One row. `ok` is true only when ALL of these hold:
--   * the session row exists and `questions` equals :expected (a count of 0 never passes, and a
--     partial landing never passes);
--   * every question is flagged (needs_human_review), status 'published', paperless
--     (source_paper_id IS NULL), and has the session's grade/exam/subject/medium;
--   * no answer and no sub-answer of any of its parts (nested parts included — every
--     sub_questions row carries question_id) has verified_by or verified_at set;
--   * every leaf has an answer: a question with no parts has an `answers` row, and every part with
--     no child part has a `sub_answers` row (unanswered_leaves = 0).
-- Every failing count is returned so a false `ok` says which invariant broke.
-- ============================================================================================

WITH b  AS (SELECT * FROM question_batches WHERE batch_id = :'batch_id'::uuid),
     q  AS (SELECT q.* FROM questions q WHERE q.source_batch_id = :'batch_id'::uuid),
     sq AS (SELECT s.* FROM sub_questions s JOIN q USING (question_id)),
     a  AS (SELECT a.* FROM answers a JOIN q USING (question_id)),
     sa AS (SELECT x.* FROM sub_answers x JOIN sq USING (sub_question_id)),
     r  AS (
       SELECT (SELECT count(*) FROM b)                                                    AS session_exists,
              (SELECT count(*) FROM q)                                                    AS questions,
              (SELECT count(*) FROM q WHERE q.needs_human_review IS NOT TRUE)             AS not_flagged,
              (SELECT count(*) FROM q WHERE q.status IS DISTINCT FROM 'published')        AS not_published,
              (SELECT count(*) FROM q WHERE q.source_paper_id IS NOT NULL)                AS papered,
              (SELECT count(*) FROM q CROSS JOIN b
                WHERE q.grade   IS DISTINCT FROM b.grade   OR q.exam   IS DISTINCT FROM b.exam
                   OR q.subject IS DISTINCT FROM b.subject OR q.medium IS DISTINCT FROM b.medium) AS scope_mismatch,
              (SELECT count(*) FROM sq)                                                   AS parts,
              (SELECT count(*) FROM a)                                                    AS answers,
              (SELECT count(*) FROM a  WHERE a.verified_by  IS NOT NULL OR a.verified_at  IS NOT NULL) AS signed_answers,
              (SELECT count(*) FROM sa)                                                   AS sub_answers,
              (SELECT count(*) FROM sa WHERE sa.verified_by IS NOT NULL OR sa.verified_at IS NOT NULL) AS signed_sub_answers,
              (SELECT count(*) FROM q
                WHERE NOT EXISTS (SELECT 1 FROM sq WHERE sq.question_id = q.question_id)
                  AND NOT EXISTS (SELECT 1 FROM a  WHERE a.question_id  = q.question_id))
            + (SELECT count(*) FROM sq
                WHERE NOT EXISTS (SELECT 1 FROM sq c WHERE c.parent_sub_question_id = sq.sub_question_id)
                  AND NOT EXISTS (SELECT 1 FROM sa WHERE sa.sub_question_id = sq.sub_question_id)) AS unanswered_leaves
     )
SELECT r.*,
       (r.session_exists = 1 AND r.questions = :expected AND r.questions > 0
        AND r.not_flagged = 0 AND r.not_published = 0 AND r.papered = 0 AND r.scope_mismatch = 0
        AND r.signed_answers = 0 AND r.signed_sub_answers = 0 AND r.unanswered_leaves = 0) AS ok
FROM r;


-- ============================================================================================
-- Q3 — Admin Auth revocation proof for the actor                    DATABASE: Admin Auth project
-- Variables: actor_id (uuid — the user id the tool signed in as; it prints it on logout).
-- ⚠️ Runs on the ADMIN AUTH project, never the content project: zero sessions for a user that
-- does not exist there proves nothing. `ok` therefore demands actor_exists = 1, and refuses a
-- database that has the content schema (public.question_batches present = wrong project).
-- The counts come from qgen.q3(actor uuid) — a counts-only SECURITY DEFINER function owned by
-- postgres, installed once per skills/generate/SKILL.md step 11: RLS is enabled on auth.users /
-- auth.sessions / auth.refresh_tokens with NO policies, so a reader role (never BYPASSRLS) sees
-- zero rows and a direct count would lie "revoked". On the content project the function does not
-- exist — this query errors, which reads as NOT ok.
-- Counts only — no token, no email, no row is returned. `sessions` deliberately counts EVERY row,
-- expired ones included: a global logout deletes them all, so any surviving row means "not revoked".
-- ============================================================================================

SELECT f.actor_exists, f.sessions, f.active_refresh_tokens, w.wrong_project,
       (f.actor_exists = 1 AND f.sessions = 0 AND f.active_refresh_tokens = 0 AND NOT w.wrong_project) AS ok
FROM qgen.q3(:'actor_id'::uuid) f,
     (SELECT to_regclass('public.question_batches') IS NOT NULL AS wrong_project) w;

-- ============================================================================================
-- Q4 — The critic's read of a playground batch                       DATABASE: content
-- Variables: batch_id (uuid — the session id).
-- Read-only input for agents/qgen-critic.md. Q4a is the session row (it plays the paper's role:
-- grade XOR exam, subject, medium) with its intended lessons resolved. Q4b is one row per question
-- in question_number order, every level nested as JSON: the question's own answers, and each part
-- with its parent id (rebuild the tree from parent_sub_question_id; depth ≤ 2) and its sub-answers;
-- diagram_dsl at every level; lesson_ids resolved to (sort_order = lesson number, name). Q4c lists
-- every OTHER question sharing a lesson with the batch — full stems plus part texts — for the
-- "not a copy" check. Each block emits ONE JSON object per line (newlines inside text are escaped),
-- so run it with `psql -X -A -t -v ON_ERROR_STOP=1` and parse line by line. For G6, a lesson's
-- sort_order is its lesson number × 10 (70 = lesson 07) — match the scope card by number AND name. All statuses are returned: a row unpublished back to draft is still shown,
-- with its status, so read the status column before judging.
-- ============================================================================================

-- Q4a — the session row (expect exactly 1 line)
SELECT to_jsonb(r) FROM (
SELECT b.batch_id, b.name, b.status, b.grade, b.exam, b.subject, b.medium, b.question_count,
       (SELECT jsonb_agg(jsonb_build_object('lesson_id', l.lesson_id, 'sort_order', l.sort_order,
                                            'name', l.name, 'name_sinhala', l.name_sinhala)
                         ORDER BY l.sort_order)
          FROM lessons l WHERE l.lesson_id = ANY (b.lesson_ids))       AS session_lessons
FROM question_batches b
WHERE b.batch_id = :'batch_id'::uuid) r;

-- Q4b — the batch, one JSON line per question, parts/answers nested
SELECT to_jsonb(r) FROM (
SELECT q.question_number, q.question_id, q.status, q.needs_human_review, q.is_multipart,
       q.grade, q.exam, q.subject, q.medium,
       (SELECT jsonb_agg(jsonb_build_object('lesson_id', l.lesson_id, 'sort_order', l.sort_order,
                                            'name', l.name, 'grade', l.grade, 'exam', l.exam)
                         ORDER BY l.sort_order)
          FROM lessons l WHERE l.lesson_id = ANY (q.lesson_ids))       AS lessons,
       cardinality(q.lesson_ids)                                        AS lesson_id_count,
       q.question_text, q.question_text_sinhala, q.diagram_dsl,
       (SELECT jsonb_agg(jsonb_build_object('answer_id', a.answer_id, 'approach', a.approach,
                                            'final_answer_latex', a.final_answer_latex,
                                            'diagram_dsl', a.diagram_dsl,
                                            'verified_by', a.verified_by, 'verified_at', a.verified_at)
                         ORDER BY a.created_at, a.answer_id)
          FROM answers a WHERE a.question_id = q.question_id)           AS answers,
       (SELECT jsonb_agg(jsonb_build_object(
                 'sub_question_id', s.sub_question_id, 'parent_sub_question_id', s.parent_sub_question_id,
                 'label', s.label, 'sort_order', s.sort_order, 'text', s.text,
                 'text_sinhala', s.text_sinhala, 'diagram_dsl', s.diagram_dsl,
                 'sub_answers', (SELECT jsonb_agg(jsonb_build_object(
                                          'sub_answer_id', x.sub_answer_id, 'approach', x.approach,
                                          'final_answer_latex', x.final_answer_latex,
                                          'diagram_dsl', x.diagram_dsl,
                                          'verified_by', x.verified_by, 'verified_at', x.verified_at)
                                        ORDER BY x.created_at, x.sub_answer_id)
                                   FROM sub_answers x WHERE x.sub_question_id = s.sub_question_id))
                         ORDER BY s.parent_sub_question_id NULLS FIRST, s.sort_order, s.label)
          FROM sub_questions s WHERE s.question_id = q.question_id)     AS parts
FROM questions q
WHERE q.source_batch_id = :'batch_id'::uuid) r
ORDER BY r.question_number, r.question_id;

-- Q4c — every other question tagged with a lesson the batch uses (dedup / not-a-copy), one JSON line each
SELECT to_jsonb(r) FROM (
SELECT q.question_id, q.source_batch_id, q.source_paper_id, q.status, q.question_number,
       q.question_text,
       (SELECT string_agg(s.label || ') ' || s.text, ' | ' ORDER BY s.parent_sub_question_id NULLS FIRST, s.sort_order)
          FROM sub_questions s WHERE s.question_id = q.question_id)     AS part_texts
FROM questions q
WHERE q.source_batch_id IS DISTINCT FROM :'batch_id'::uuid
  AND q.lesson_ids && (SELECT coalesce(array_agg(DISTINCT t), '{}'::uuid[])
                         FROM questions x CROSS JOIN LATERAL unnest(x.lesson_ids) AS t
                        WHERE x.source_batch_id = :'batch_id'::uuid)
ORDER BY q.source_paper_id NULLS FIRST, q.source_batch_id, q.question_number, q.question_id) r;
