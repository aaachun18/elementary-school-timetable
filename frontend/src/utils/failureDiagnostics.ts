// Task 36: turns one ConstraintViolationDetail into a Chinese sentence, by
// combining VIOLATION_TYPE_TEMPLATES (constants/errorMessages.ts) with the
// id->entity lookups FailureDiagnostics.tsx builds from the same list()
// calls Task 30/31 already established (RequirementsOverview.tsx, DataBrowser.tsx).

import { LESSON_FAILURE_REASON_TEMPLATES, VIOLATION_TYPE_TEMPLATES } from "../constants/errorMessages";
import { formatTimeSlotLabel } from "./timeSlotFormat";
import type { ConstraintViolationDetail, LessonFailureDetail } from "../types/scheduler";
import type { Teacher } from "../types/teacher";
import type { Class } from "../types/class";
import type { Subject } from "../types/subject";
import type { Room } from "../types/room";
import type { TimeSlot } from "../types/timeSlot";
import type { ClassSubjectRequirement } from "../types/classSubjectRequirement";

export interface NameLookups {
  teacherById: Map<number, Teacher>;
  classById: Map<number, Class>;
  subjectById: Map<number, Subject>;
  roomById: Map<number, Room>;
  timeSlotById: Map<number, TimeSlot>;
  requirementById: Map<number, ClassSubjectRequirement>;
}

// Every resolver returns "" for a null id (never the literal text "null"),
// per Task 36's spec: a template's placeholder for a missing id disappears
// from the rendered sentence instead of showing anything.

export function resolveTeacherName(id: number | null, lookups: NameLookups): string {
  if (id === null) {
    return "";
  }
  return lookups.teacherById.get(id)?.name ?? `教師 ID ${id}`;
}

export function resolveClassName(id: number | null, lookups: NameLookups): string {
  if (id === null) {
    return "";
  }
  return lookups.classById.get(id)?.name ?? `班級 ID ${id}`;
}

export function resolveSubjectName(id: number | null, lookups: NameLookups): string {
  if (id === null) {
    return "";
  }
  return lookups.subjectById.get(id)?.name ?? `科目 ID ${id}`;
}

export function resolveRoomName(id: number | null, lookups: NameLookups): string {
  if (id === null) {
    return "";
  }
  return lookups.roomById.get(id)?.name ?? `教室 ID ${id}`;
}

export function resolveTimeSlotLabel(id: number | null, lookups: NameLookups): string {
  if (id === null) {
    return "";
  }
  const timeSlot = lookups.timeSlotById.get(id);
  return timeSlot === undefined ? `時段 ID ${id}` : formatTimeSlotLabel(timeSlot);
}

// class_subject_requirement_id is deliberately NOT rendered as a form
// (per Task 36's scope note) -- just the 班級+科目 combination, which is
// the only piece every consumer of this id (H7/NO_CANDIDATE_TEACHER/
// H6_REQUIRED_TEACHER_NOT_QUALIFIED/STATIC_INACTIVE_ENTITY_CONFLICT) needs
// to identify which requirement is at fault.
export function resolveRequirementLabel(
  requirementId: number | null,
  lookups: NameLookups,
): string {
  if (requirementId === null) {
    return "";
  }
  const requirement = lookups.requirementById.get(requirementId);
  if (requirement === undefined) {
    return `需求 ID ${requirementId}`;
  }
  return `${resolveClassName(requirement.class_id, lookups)}的${resolveSubjectName(
    requirement.subject_id,
    lookups,
  )}`;
}

// The DataBrowser.tsx tab a given inactive entity lives on -- shared by both
// resolveInactiveEntities() below (the {inactiveEntities} sentence text) and
// constants/violationPageMapping.ts (which page/tab "請至...修正" points at),
// so the two can never name a different entity than they link to.
export type InactiveEntityTab = "teachers" | "classes" | "subjects" | "rooms";

export interface InactiveEntity {
  tab: InactiveEntityTab;
  label: string;
}

const INACTIVE_ENTITY_TAB_PREFIX: Record<InactiveEntityTab, string> = {
  teachers: "教師",
  classes: "班級",
  subjects: "科目",
  rooms: "教室",
};

// H12_ACTIVE_STATUS always carries class_id/subject_id (ActiveStatusConstraint
// checks them unconditionally -- see its docstring), so their presence on the
// violation does NOT by itself mean they're the inactive one; this checks
// each populated id against the same Teacher/Class/Subject/Room.is_active
// flag the backend's own ActiveStatusConstraint/check_static_feasibility
// compare against, and only lists the ones that are actually inactive.
// STATIC_INACTIVE_ENTITY_CONFLICT has no such ambiguity -- static_feasibility.py
// sets exactly one of teacher_id/class_id/subject_id per violation, and only
// ever for an id it already confirmed is inactive -- so every populated id is
// included as-is, without re-checking is_active (an extra check that could
// only ever agree, never disagree, with what the backend already decided).
//
// Returned in teacher -> class -> subject -> room order; a violation can
// legitimately name more than one (H12 can flag several entities at once).
export function resolveInactiveEntities(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): InactiveEntity[] {
  const verifyInactive = violation.type === "H12_ACTIVE_STATUS";
  const entities: InactiveEntity[] = [];

  if (violation.teacher_id !== null) {
    const teacher = lookups.teacherById.get(violation.teacher_id);
    if (!verifyInactive || teacher?.is_active === false) {
      entities.push({ tab: "teachers", label: teacher?.name ?? `ID ${violation.teacher_id}` });
    }
  }
  if (violation.class_id !== null) {
    const classItem = lookups.classById.get(violation.class_id);
    if (!verifyInactive || classItem?.is_active === false) {
      entities.push({ tab: "classes", label: classItem?.name ?? `ID ${violation.class_id}` });
    }
  }
  if (violation.subject_id !== null) {
    const subject = lookups.subjectById.get(violation.subject_id);
    if (!verifyInactive || subject?.is_active === false) {
      entities.push({ tab: "subjects", label: subject?.name ?? `ID ${violation.subject_id}` });
    }
  }
  if (violation.room_id !== null) {
    const room = lookups.roomById.get(violation.room_id);
    if (!verifyInactive || room?.is_active === false) {
      entities.push({ tab: "rooms", label: room?.name ?? `ID ${violation.room_id}` });
    }
  }

  return entities;
}

function formatInactiveEntities(entities: InactiveEntity[]): string {
  return entities
    .map((entity) => `${INACTIVE_ENTITY_TAB_PREFIX[entity.tab]} ${entity.label}`)
    .join("、");
}

function applyTemplate(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) => values[key] ?? "");
}

// Shared by getViolationSentence() and getGroupedLessonFailureSentence()
// below -- both substitute the same placeholder set, just into different
// templates (a full sentence vs. a bare reason clause).
function buildTemplateValues(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): Record<string, string> {
  return {
    teacherName: resolveTeacherName(violation.teacher_id, lookups),
    className: resolveClassName(violation.class_id, lookups),
    subjectName: resolveSubjectName(violation.subject_id, lookups),
    roomName: resolveRoomName(violation.room_id, lookups),
    timeSlotLabel: resolveTimeSlotLabel(violation.time_slot_id, lookups),
    requirementLabel: resolveRequirementLabel(
      violation.class_subject_requirement_id,
      lookups,
    ),
    inactiveEntities: formatInactiveEntities(resolveInactiveEntities(violation, lookups)),
  };
}

// Falls back to the violation's own English `message` when its `type` has no
// entry in VIOLATION_TYPE_TEMPLATES -- same "never blank, never swallowed"
// fallback stance as translateErrorMessage/translateFailureType.
export function getViolationSentence(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): string {
  const template = VIOLATION_TYPE_TEMPLATES[violation.type];
  if (template === undefined) {
    return violation.message;
  }
  return applyTemplate(template, buildTemplateValues(violation, lookups));
}

// --- Task 39: merging lesson_failures entries that fail for the same
// reason into one message, instead of one repeated-looking message per
// lesson_id. ---

// "Same reason" per Task 39's spec: same class_subject_requirement_id (so
// same class+subject -- a LessonFailureDetail's own field, not derived) +
// same violation `type` + every id field on the violation matching too
// (teacher_id/class_id/subject_id/room_id/time_slot_id). Deliberately
// excludes lesson_id (the one thing that's SUPPOSED to vary within a group)
// and message/suggested_action (English text that can embed a specific
// lesson_id -- e.g. "No teacher is qualified/assignable for lesson 162" --
// which would wrongly split an otherwise-identical group if compared
// as strings). JSON.stringify of a fixed-shape tuple is a simple, exact
// equality key -- no risk of two different reasons hashing the same, which
// matters here since a bad merge silently hides a distinct failure reason.
function lessonFailureGroupKey(
  classSubjectRequirementId: number,
  violation: ConstraintViolationDetail,
): string {
  return JSON.stringify([
    classSubjectRequirementId,
    violation.type,
    violation.teacher_id,
    violation.class_id,
    violation.subject_id,
    violation.room_id,
    violation.time_slot_id,
  ]);
}

export interface LessonFailureGroup {
  key: string;
  classSubjectRequirementId: number;
  lessonIds: number[];
  // Any member of the group works as the representative: every member is
  // guaranteed identical type + id fields by construction (that's what
  // defines the group), so resolving text/a page link from any one of them
  // produces the same result as any other.
  representative: ConstraintViolationDetail;
}

// Flattens every (lesson, reason) pair across all LessonFailureDetail
// entries and regroups them by lessonFailureGroupKey(). A single Lesson
// with multiple DISTINCT reasons (theoretically possible -- see
// scheduling_engine/algorithms/greedy.py's explain path, even though the
// live API today only ever produces one reason per Lesson) correctly ends
// up contributing to multiple different groups, one per distinct reason --
// it is never dropped or force-merged into just one.
export function groupLessonFailures(
  lessonFailures: LessonFailureDetail[],
): LessonFailureGroup[] {
  const groups = new Map<string, LessonFailureGroup>();
  for (const failure of lessonFailures) {
    for (const reason of failure.reasons) {
      const key = lessonFailureGroupKey(failure.class_subject_requirement_id, reason);
      const existing = groups.get(key);
      if (existing === undefined) {
        groups.set(key, {
          key,
          classSubjectRequirementId: failure.class_subject_requirement_id,
          lessonIds: [failure.lesson_id],
          representative: reason,
        });
      } else if (!existing.lessonIds.includes(failure.lesson_id)) {
        existing.lessonIds.push(failure.lesson_id);
      }
    }
  }
  return [...groups.values()];
}

// "{班級}的{科目}(共 N 堂課):{reason},這些課無法排定!" for a group of 2+
// lessons; "{班級}的{科目}:{reason},這堂課無法排定!" for exactly 1 -- no
// "(共 1 堂課)" (a redundant thing to say about a single lesson) and
// "這堂課" instead of "這些課" so the sentence still reads as natural
// Chinese instead of grammatically implying a group of one.
export function getGroupedLessonFailureSentence(
  group: LessonFailureGroup,
  lookups: NameLookups,
): string {
  const requirementLabel = resolveRequirementLabel(
    group.classSubjectRequirementId,
    lookups,
  );
  const reasonTemplate = LESSON_FAILURE_REASON_TEMPLATES[group.representative.type];
  const values = buildTemplateValues(group.representative, lookups);
  const reason =
    reasonTemplate !== undefined
      ? applyTemplate(reasonTemplate, values)
      : getViolationSentence(group.representative, lookups).replace(/!$/, "");

  const count = group.lessonIds.length;
  if (count === 1) {
    return `${requirementLabel}:${reason},這堂課無法排定!`;
  }
  return `${requirementLabel}(共 ${count} 堂課):${reason},這些課無法排定!`;
}
