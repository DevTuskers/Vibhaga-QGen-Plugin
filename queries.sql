-- vibhaga-qgen — ready-made read-only queries (W5).
--
-- Run with psql variables, e.g.
--   psql "$CONTENT_DB_URL" -v lesson_id=<uuid> -f queries.sql          (then pick the block you need)
-- or paste one block into a SQL console, replacing each :'name' / :name placeholder by hand.
-- Every block is a single SELECT: nothing here writes, and nothing selects a secret or a token value.
-- Column names checked against information_schema on 2026-09-30 (questions.lesson_ids is uuid[],
-- sub_questions.sub_question_id is the part key, auth.refresh_tokens.user_id is varchar).
-- Which database each block targets is stated in its header. Hosts and project refs are NOT in this
-- public file: see Vibhaga-Docs AGENTS.md § "Onboarding-tool verification" for the two projects.


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
-- Counts only — no token, no email, no row is selected. `sessions` deliberately counts EVERY row,
-- expired ones included: a global logout deletes them all, so any surviving row means "not revoked".
-- ============================================================================================

SELECT u.actor_exists, s.sessions, t.active_refresh_tokens, w.wrong_project,
       (u.actor_exists = 1 AND s.sessions = 0 AND t.active_refresh_tokens = 0 AND NOT w.wrong_project) AS ok
FROM (SELECT count(*) AS actor_exists FROM auth.users WHERE id = :'actor_id'::uuid) u,
     (SELECT count(*) AS sessions FROM auth.sessions WHERE user_id = :'actor_id'::uuid) s,
     (SELECT count(*) AS active_refresh_tokens FROM auth.refresh_tokens
       WHERE user_id = (:'actor_id')::uuid::text AND revoked IS NOT TRUE) t,
     (SELECT to_regclass('public.question_batches') IS NOT NULL AS wrong_project) w;
