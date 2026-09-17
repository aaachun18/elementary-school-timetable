import type { ReactElement } from "react";
import { Link } from "react-router-dom";
import { list as listTeachers } from "../api/teachers";
import { list as listClasses } from "../api/classes";
import { list as listSubjects } from "../api/subjects";
import { list as listRooms } from "../api/rooms";
import { list as listTimeSlots } from "../api/timeSlots";
import { list as listRequirements } from "../api/classSubjectRequirements";
import { useResource } from "../hooks/useResource";
import { translateFailureType } from "../constants/errorMessages";
import { resolveViolationPageTarget } from "../constants/violationPageMapping";
import {
  getGroupedLessonFailureSentence,
  getViolationSentence,
  groupLessonFailures,
  type LessonFailureGroup,
  type NameLookups,
} from "../utils/failureDiagnostics";
import type {
  ConstraintViolationDetail,
  RunSchedulerFailureResponse,
} from "../types/scheduler";

interface FailureDiagnosticsProps {
  response: RunSchedulerFailureResponse;
}

// Shared by both <ul> lists below: listStyle "none" drops the browser's
// default bullet (•), and padding/margin go with it -- that padding exists
// specifically to make room for the bullet marker, so leaving it in place
// after removing the marker would strand each item in the same indented
// position with nothing there to justify it. marginBottom on each <li>
// replaces the visual separation the bullet+indent used to imply, so
// consecutive failure entries don't run together now that there's no
// marker/indent to set them apart.
const FAILURE_LIST_STYLE = { listStyle: "none", padding: 0, margin: 0 } as const;
const FAILURE_LIST_ITEM_STYLE = { marginBottom: "1em" } as const;

// Second line of every violation/group (Task 37): "請至 {頁面} 修正" with
// {頁面} as a clickable react-router Link to whichever page/tab
// constants/violationPageMapping.ts resolves for this violation's type --
// or, for the 4 types that resolve to no usable page at all, a fixed line
// explaining why instead of a link. Factored out of ViolationItem so
// GroupedLessonFailureItem (Task 39) can render the identical second line
// for a group's representative violation without duplicating this
// link-vs-text branch.
function PageTargetLine({
  violation,
  lookups,
}: {
  violation: ConstraintViolationDetail;
  lookups: NameLookups;
}): ReactElement {
  const target = resolveViolationPageTarget(violation, lookups);
  return (
    <p style={{ color: "#555", fontSize: "0.9em" }}>
      {target.kind === "link" ? (
        <>
          請至 <Link to={target.path}>{target.label}</Link> 修正
        </>
      ) : (
        target.message
      )}
    </p>
  );
}

// One post_hoc_violations entry -> exactly two lines (Task 37): the Chinese
// violation sentence (ends in "!"), then PageTargetLine. Task 39's merging
// is scoped to lesson_failures only (see GroupedLessonFailureItem below) --
// post_hoc_violations are already whole-batch, one-per-problem entries with
// nothing lesson-shaped to merge, so this keeps rendering them exactly as
// Task 37 left it.
function ViolationItem({
  violation,
  lookups,
}: {
  violation: ConstraintViolationDetail;
  lookups: NameLookups;
}): ReactElement {
  return (
    <li style={FAILURE_LIST_ITEM_STYLE}>
      <p>{getViolationSentence(violation, lookups)}</p>
      <PageTargetLine violation={violation} lookups={lookups} />
    </li>
  );
}

// Task 39: one GROUP of lesson_failures (every Lesson that failed for the
// exact same reason, per groupLessonFailures()) -> exactly two lines, same
// shape as ViolationItem but with the merged "{班級}的{科目}(共 N 堂課):
// {reason},這些課無法排定!" sentence instead of one line per lesson_id --
// no lesson_id/#數字 shown anywhere (per Task 39's spec, an internal id
// that means nothing to a 教務人員 looking at this screen).
function GroupedLessonFailureItem({
  group,
  lookups,
}: {
  group: LessonFailureGroup;
  lookups: NameLookups;
}): ReactElement {
  return (
    <li style={FAILURE_LIST_ITEM_STYLE}>
      <p>{getGroupedLessonFailureSentence(group, lookups)}</p>
      <PageTargetLine violation={group.representative} lookups={lookups} />
    </li>
  );
}

// Renders a RunSchedulerFailureResponse (Task 32's raw-JSON placeholder,
// replaced here) as Chinese sentences a 教務人員 can act on, with every
// teacher_id/class_id/subject_id/room_id/time_slot_id/
// class_subject_requirement_id resolved to its name via the same
// list()-then-Map join pattern RequirementsOverview.tsx (Task 31) already
// established.
//
// lesson_failures and post_hoc_violations are shown as two separate
// sections rather than merged into one flat list: post_hoc_violations is a
// flat list of whole-batch problems (H7, or the three STATIC_* checks) that
// aren't about any single lesson, while lesson_failures is about specific
// Lessons -- and (Task 39) grouped by identical failure reason via
// groupLessonFailures(), since multiple Lessons failing for the exact same
// reason (e.g. every lesson generated for one over-subscribed requirement)
// used to render as that many near-identical, lesson_id-numbered entries.
// Merging the two sections together would either lose that per-lesson
// grouping or force a fake one onto the batch-level entries, so they still
// get their own headings.
export default function FailureDiagnostics({
  response,
}: FailureDiagnosticsProps): ReactElement {
  const teachers = useResource(() => listTeachers(), []);
  const classes = useResource(() => listClasses(), []);
  const subjects = useResource(() => listSubjects(), []);
  const rooms = useResource(() => listRooms(), []);
  const timeSlots = useResource(() => listTimeSlots(), []);
  const requirements = useResource(() => listRequirements(), []);

  const isLoading =
    teachers.isLoading ||
    classes.isLoading ||
    subjects.isLoading ||
    rooms.isLoading ||
    timeSlots.isLoading ||
    requirements.isLoading;
  const errorMessage =
    teachers.errorMessage ??
    classes.errorMessage ??
    subjects.errorMessage ??
    rooms.errorMessage ??
    timeSlots.errorMessage ??
    requirements.errorMessage;

  if (isLoading) {
    return <p>診斷資料載入中…</p>;
  }
  if (errorMessage !== null) {
    return <p role="alert">{errorMessage}</p>;
  }

  const lookups: NameLookups = {
    teacherById: new Map((teachers.data ?? []).map((teacher) => [teacher.id, teacher])),
    classById: new Map((classes.data ?? []).map((classItem) => [classItem.id, classItem])),
    subjectById: new Map((subjects.data ?? []).map((subject) => [subject.id, subject])),
    roomById: new Map((rooms.data ?? []).map((room) => [room.id, room])),
    timeSlotById: new Map((timeSlots.data ?? []).map((timeSlot) => [timeSlot.id, timeSlot])),
    requirementById: new Map(
      (requirements.data ?? []).map((requirement) => [requirement.id, requirement]),
    ),
  };

  return (
    <div>
      <p role="alert" style={{ color: "#b00020", fontWeight: "bold" }}>
        ✗ 排課失敗:{translateFailureType(response.failure_type)}
      </p>

      {response.lesson_failures.length > 0 && (
        <section>
          <h3>各課程排課失敗原因</h3>
          <ul style={FAILURE_LIST_STYLE}>
            {groupLessonFailures(response.lesson_failures).map((group) => (
              <GroupedLessonFailureItem key={group.key} group={group} lookups={lookups} />
            ))}
          </ul>
        </section>
      )}

      {response.post_hoc_violations.length > 0 && (
        <section>
          <h3>整體排課檢查未通過項目</h3>
          <ul style={FAILURE_LIST_STYLE}>
            {response.post_hoc_violations.map((violation, index) => (
              <ViolationItem key={`post-hoc-${index}`} violation={violation} lookups={lookups} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
