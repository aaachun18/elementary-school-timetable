-- reset_demo_requirements.sql
--
-- Purpose: restore the demo data's shared requirements after a demo run.
-- Reassigning a teacher in a DRAFT version (demo step e) also rewrites
-- class_subject_requirements.required_teacher_id, which is shared by every
-- version of the semester (known trade-off, docs/SYSTEM_DESIGN.md section
-- 10). Afterwards the ARCHIVED v4 and the PUBLISHED v11 report
-- H6_REQUIRED_TEACHER. This script sets each mismatching requirement's
-- required_teacher_id back to the teacher on v4's schedule rows.
--
-- Hard-coded ids (this demo dataset only -- NOT a general-purpose tool):
--   semester_id         = 13  (academic year 1, semester 1)
--   schedule_version_id = 24  (v4, ARCHIVED; its teachers are the reference)
--
-- What it changes: ONLY class_subject_requirements.required_teacher_id, and
-- only for semester 13 rows whose v4 lessons all have one single teacher
-- and whose current required teacher is a different teacher. Requirements
-- with no required teacher are left alone. Schedule rows, version status
-- and every other column are untouched (updated_at is not bumped either).
-- Running it again when everything is consistent is a no-op (UPDATE 0).
--
-- Usage: do not run this file directly. scripts/reset_demo_requirements.ps1
-- appends ROLLBACK (dry run, default) or COMMIT (-Commit) after it.

BEGIN;

-- [1] BEFORE: semester 13 requirements vs. the single teacher on v4 rows
SELECT r.id AS req_id, c.name AS class_name, sj.name AS subject_name,
       r.required_teacher_id AS req_tid, rt.name AS required_teacher,
       v4.teacher_id AS v4_tid, vt.name AS v4_teacher,
       CASE WHEN r.required_teacher_id IS NOT NULL
             AND r.required_teacher_id <> v4.teacher_id THEN 'MISMATCH' ELSE 'ok' END AS status
FROM class_subject_requirements r
JOIN classes c ON c.id = r.class_id
JOIN subjects sj ON sj.id = r.subject_id
LEFT JOIN teachers rt ON rt.id = r.required_teacher_id
LEFT JOIN (
    SELECT l.class_subject_requirement_id AS requirement_id, MIN(s.teacher_id) AS teacher_id
    FROM schedules s JOIN lessons l ON l.id = s.lesson_id
    WHERE s.schedule_version_id = 24
    GROUP BY l.class_subject_requirement_id
    HAVING COUNT(DISTINCT s.teacher_id) = 1 AND COUNT(s.teacher_id) = COUNT(*)
) v4 ON v4.requirement_id = r.id
LEFT JOIN teachers vt ON vt.id = v4.teacher_id
WHERE r.semester_id = 13
ORDER BY r.id;

-- [2] REPAIR (psql prints "UPDATE n" = number of repaired requirements)
UPDATE class_subject_requirements AS r
SET required_teacher_id = v4.teacher_id
FROM (
    SELECT l.class_subject_requirement_id AS requirement_id, MIN(s.teacher_id) AS teacher_id
    FROM schedules s JOIN lessons l ON l.id = s.lesson_id
    WHERE s.schedule_version_id = 24
    GROUP BY l.class_subject_requirement_id
    HAVING COUNT(DISTINCT s.teacher_id) = 1 AND COUNT(s.teacher_id) = COUNT(*)
) AS v4
WHERE r.id = v4.requirement_id
  AND r.semester_id = 13
  AND r.required_teacher_id IS NOT NULL
  AND r.required_teacher_id <> v4.teacher_id
RETURNING r.id AS repaired_req_id, r.required_teacher_id AS new_required_teacher_id;

-- [3] AFTER: same query as [1]; every row should now be 'ok'
SELECT r.id AS req_id, c.name AS class_name, sj.name AS subject_name,
       r.required_teacher_id AS req_tid, rt.name AS required_teacher,
       v4.teacher_id AS v4_tid, vt.name AS v4_teacher,
       CASE WHEN r.required_teacher_id IS NOT NULL
             AND r.required_teacher_id <> v4.teacher_id THEN 'MISMATCH' ELSE 'ok' END AS status
FROM class_subject_requirements r
JOIN classes c ON c.id = r.class_id
JOIN subjects sj ON sj.id = r.subject_id
LEFT JOIN teachers rt ON rt.id = r.required_teacher_id
LEFT JOIN (
    SELECT l.class_subject_requirement_id AS requirement_id, MIN(s.teacher_id) AS teacher_id
    FROM schedules s JOIN lessons l ON l.id = s.lesson_id
    WHERE s.schedule_version_id = 24
    GROUP BY l.class_subject_requirement_id
    HAVING COUNT(DISTINCT s.teacher_id) = 1 AND COUNT(s.teacher_id) = COUNT(*)
) v4 ON v4.requirement_id = r.id
LEFT JOIN teachers vt ON vt.id = v4.teacher_id
WHERE r.semester_id = 13
ORDER BY r.id;

-- ROLLBACK or COMMIT is appended by scripts/reset_demo_requirements.ps1
