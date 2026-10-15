-- add_demo_rooms.sql
--
-- Purpose: give every lesson of the demo semester a room, so the timetable's
-- "by room" view has content. The scheduler never assigns a room to a
-- requirement without required_room_type ("taught in the class's own
-- room"), so the demo versions have room_id NULL everywhere. This one-off
-- script:
--   1. creates one homeroom per [SEED] class of semester 13 that has none,
--      named after the class plus the Chinese word for "classroom"
--      (class name || U+6559 U+5BA4), with the existing ordinary-classroom
--      room_type, and sets it as that class's homeroom
--      (classes.homeroom_room_id);
--   2. aborts if filling the rooms would put two lessons in the same room
--      at the same time slot within one version (H3);
--   3. sets room_id = the class's homeroom on every schedule row of every
--      semester 13 version whose room_id is NULL.
-- Requirements (required_room_type stays NULL), teachers, time slots and
-- version status are untouched. Rows that already have a room keep it.
--
-- Hard-coded: semester_id = 13; classes whose name starts with "[SEED]".
-- Only for this demo dataset -- NOT a general-purpose tool.
--
-- Idempotent: a class that already has a homeroom gets no new room, and an
-- existing room with the same name is reused instead of duplicated; rows
-- that already have a room are skipped. A second run reports INSERT 0 0,
-- UPDATE 0, UPDATE 0.
--
-- Note: semester 13's versions are ARCHIVED/PUBLISHED, which the API
-- refuses to modify; this script writes their schedule rows directly on
-- purpose (one-off demo data fix, see docs/SYSTEM_DESIGN.md section 10).
--
-- Chinese text is written as U&'...' Unicode escapes so this file stays
-- ASCII-only:
--   U&'\666E\901A\6559\5BA4' = ordinary classroom (the room_type value
--                              already used by existing rooms)
--   U&'\6559\5BA4'           = "classroom" suffix of the new room names
--
-- Usage: do not run this file directly. scripts/add_demo_rooms.ps1 appends
-- ROLLBACK (dry run, default) or COMMIT (-Commit) after it.

BEGIN;

-- [1] BEFORE: per version -- schedule rows, rows with a room
SELECT v.id AS version_id, v.version_number AS v, v.status,
       count(s.id) AS schedule_rows, count(s.room_id) AS rows_with_room
FROM schedule_versions v
LEFT JOIN schedules s ON s.schedule_version_id = v.id
WHERE v.semester_id = 13
GROUP BY v.id, v.version_number, v.status
ORDER BY v.id;

-- [1b] BEFORE: semester 13 [SEED] classes and their homerooms
SELECT c.id AS class_id, c.name AS class_name, c.homeroom_room_id, r.name AS homeroom
FROM classes c
LEFT JOIN rooms r ON r.id = c.homeroom_room_id
WHERE c.id IN (SELECT class_id FROM class_subject_requirements WHERE semester_id = 13)
  AND left(c.name, 6) = '[SEED]'
ORDER BY c.id;

-- [2] Create the missing homerooms (psql prints "INSERT 0 n")
INSERT INTO rooms (name, room_type, capacity, is_active)
SELECT c.name || U&'\6559\5BA4', U&'\666E\901A\6559\5BA4', NULL, TRUE
FROM classes c
WHERE c.id IN (SELECT class_id FROM class_subject_requirements WHERE semester_id = 13)
  AND left(c.name, 6) = '[SEED]'
  AND c.homeroom_room_id IS NULL
  AND NOT EXISTS (SELECT 1 FROM rooms r WHERE r.name = c.name || U&'\6559\5BA4')
ORDER BY c.id
RETURNING id AS new_room_id, name AS new_room_name, room_type;

-- [3] Set them as the classes' homerooms (first "UPDATE n")
UPDATE classes c
SET homeroom_room_id = (
    SELECT min(r.id) FROM rooms r WHERE r.name = c.name || U&'\6559\5BA4'
)
WHERE c.id IN (SELECT class_id FROM class_subject_requirements WHERE semester_id = 13)
  AND left(c.name, 6) = '[SEED]'
  AND c.homeroom_room_id IS NULL
  AND EXISTS (SELECT 1 FROM rooms r WHERE r.name = c.name || U&'\6559\5BA4')
RETURNING c.id AS class_id, c.name AS class_name, c.homeroom_room_id;

-- [4] Guard: after filling, no (room, time slot) may repeat within a version
DO $$
DECLARE
    clash_count integer;
BEGIN
    SELECT count(*) INTO clash_count
    FROM (
        SELECT s.schedule_version_id,
               coalesce(s.room_id, c.homeroom_room_id) AS room_id,
               s.time_slot_id
        FROM schedules s
        JOIN schedule_versions v ON v.id = s.schedule_version_id
        JOIN lessons l ON l.id = s.lesson_id
        JOIN class_subject_requirements r ON r.id = l.class_subject_requirement_id
        JOIN classes c ON c.id = r.class_id
        WHERE v.semester_id = 13
          AND s.time_slot_id IS NOT NULL
          AND coalesce(s.room_id, c.homeroom_room_id) IS NOT NULL
        GROUP BY 1, 2, 3
        HAVING count(*) > 1
    ) AS clashes;
    IF clash_count > 0 THEN
        RAISE EXCEPTION 'aborted: % (version, room, time slot) combinations would hold more than one lesson', clash_count;
    END IF;
END
$$;

-- [5] Fill the empty rooms with the class's homeroom (second "UPDATE n")
UPDATE schedules s
SET room_id = c.homeroom_room_id
FROM schedule_versions v, lessons l, class_subject_requirements r, classes c
WHERE v.id = s.schedule_version_id
  AND l.id = s.lesson_id
  AND r.id = l.class_subject_requirement_id
  AND c.id = r.class_id
  AND v.semester_id = 13
  AND s.room_id IS NULL
  AND c.homeroom_room_id IS NOT NULL;

-- [6] AFTER: per version -- schedule rows, rows with a room
SELECT v.id AS version_id, v.version_number AS v, v.status,
       count(s.id) AS schedule_rows, count(s.room_id) AS rows_with_room
FROM schedule_versions v
LEFT JOIN schedules s ON s.schedule_version_id = v.id
WHERE v.semester_id = 13
GROUP BY v.id, v.version_number, v.status
ORDER BY v.id;

-- [7] AFTER: room usage per version
SELECT s.schedule_version_id AS version_id, rm.id AS room_id, rm.name AS room_name,
       count(*) AS lessons
FROM schedules s
JOIN schedule_versions v ON v.id = s.schedule_version_id
JOIN rooms rm ON rm.id = s.room_id
WHERE v.semester_id = 13
GROUP BY s.schedule_version_id, rm.id, rm.name
ORDER BY s.schedule_version_id, rm.id;

-- ROLLBACK or COMMIT is appended by scripts/add_demo_rooms.ps1
