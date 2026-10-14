// Task 68: merging and grouping for the conflict checklist
// (components/ConflictChecklist.tsx). Pure functions -- no React, no API --
// so the rules can be unit-tested on their own.

import type { ConstraintViolationDetail } from "../types/scheduler";

// One line of the checklist: every violation whose final Chinese sentence
// is identical, shown once with how many times it was reported.
export interface MergedViolation {
  sentence: string;
  // The first violation's type -- identical sentences come from the same
  // template, so in practice every member shares it.
  type: string;
  count: number;
  // In their original order; violations[0] is the representative used for
  // anything that needs ids (e.g. locating it on the timetable).
  violations: ConstraintViolationDetail[];
}

export interface ViolationTypeGroup {
  type: string;
  items: MergedViolation[];
}

// Why the sentence (not the ids) is the key: one conflict is often reported
// once per lesson involved -- two lessons of one teacher in the same slot
// give two H1 violations with different lesson_id/class_id but the same
// "{老師}在{時段}被同時排定兩堂課！". Those are one problem to the user. Two
// violations whose sentences differ in any name or slot stay separate.
// Order: by each sentence's first appearance in `violations`.
export function mergeViolationsBySentence(
  violations: ConstraintViolationDetail[],
  sentenceOf: (violation: ConstraintViolationDetail) => string,
): MergedViolation[] {
  const bySentence = new Map<string, MergedViolation>();
  for (const violation of violations) {
    const sentence = sentenceOf(violation);
    const existing = bySentence.get(sentence);
    if (existing === undefined) {
      bySentence.set(sentence, {
        sentence,
        type: violation.type,
        count: 1,
        violations: [violation],
      });
    } else {
      existing.count += 1;
      existing.violations.push(violation);
    }
  }
  return Array.from(bySentence.values());
}

// Groups merged lines by type: groups follow `typeOrder`, then any type not
// in it (alphabetically, so the order is still stable); lines inside a
// group keep their merged order.
export function groupMergedViolationsByType(
  items: MergedViolation[],
  typeOrder: readonly string[],
): ViolationTypeGroup[] {
  const byType = new Map<string, MergedViolation[]>();
  for (const item of items) {
    const group = byType.get(item.type);
    if (group === undefined) {
      byType.set(item.type, [item]);
    } else {
      group.push(item);
    }
  }
  const rank = (type: string): number => {
    const index = typeOrder.indexOf(type);
    return index === -1 ? typeOrder.length : index;
  };
  return Array.from(byType.entries())
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .map(([type, groupItems]) => ({ type, items: groupItems }));
}

// --- Task 69: before/after comparison for a move/swap/reassign preview ---

// Task 71 fix: which fields make one violation "the same problem" before and
// after a change. The sentence can't be the key: several sentences describe
// where a lesson CURRENTLY is (e.g. 「被固定在星期五第 8 節，但目前排在…」),
// so moving the lesson to another wrong slot used to show as one problem
// resolved plus one added. Fields per type (as the backend fills them -- see
// scheduling_engine/constraints/ and services/schedule_check.py):
// - the time slot IS the problem (a clash or an unavailability at that slot):
//   H1 teacher+slot, H2 class+slot, H3 room+slot, H4 teacher+slot;
// - the slot only describes where the lesson is now: left out --
//   H11 and FIXED_TIME_SLOT_MISMATCH and INCOMPLETE_SCHEDULE_ROW are about
//   one lesson (lesson_id);
// - no slot involved at all: H5 teacher+subject, H6 class+subject+teacher,
//   H7 requirement, H8 teacher, H9 class+subject+room,
//   H12 teacher+class+subject+room (which of them is inactive).
// A type not listed (a future one) uses every id, slot included -- i.e. it
// behaves as before this fix.
const IDENTITY_FIELDS_BY_TYPE: Record<string, readonly (keyof ConstraintViolationDetail)[]> = {
  H1_TEACHER_CONFLICT: ["teacher_id", "time_slot_id"],
  H2_CLASS_CONFLICT: ["class_id", "time_slot_id"],
  H3_ROOM_CONFLICT: ["room_id", "time_slot_id"],
  H4_TEACHER_AVAILABILITY: ["teacher_id", "time_slot_id"],
  H5_TEACHER_QUALIFICATION: ["teacher_id", "subject_id"],
  H6_REQUIRED_TEACHER: ["class_id", "subject_id", "teacher_id"],
  H7_WEEKLY_PERIODS: ["class_subject_requirement_id"],
  H8_TEACHER_MAX_WORKLOAD: ["teacher_id"],
  H9_ROOM_TYPE: ["class_id", "subject_id", "room_id"],
  H11_NON_TEACHING_PERIOD: ["lesson_id"],
  H12_ACTIVE_STATUS: ["teacher_id", "class_id", "subject_id", "room_id"],
  INCOMPLETE_SCHEDULE_ROW: ["lesson_id"],
  FIXED_TIME_SLOT_MISMATCH: ["lesson_id"],
};

const ALL_ID_FIELDS: readonly (keyof ConstraintViolationDetail)[] = [
  "lesson_id",
  "teacher_id",
  "class_id",
  "subject_id",
  "room_id",
  "time_slot_id",
  "class_subject_requirement_id",
];

export function violationIdentityKey(violation: ConstraintViolationDetail): string {
  const fields = IDENTITY_FIELDS_BY_TYPE[violation.type] ?? ALL_ID_FIELDS;
  return JSON.stringify([violation.type, ...fields.map((field) => violation[field])]);
}

// A line that existed before and still exists after the change.
export interface UnchangedViolation extends MergedViolation {
  // The problem is the same, but its sentence reads differently now (e.g.
  // the lesson is still off its fixed slot, just in another wrong slot) --
  // shown as 「仍未解決：…」 so the new position is visible.
  descriptionChanged: boolean;
}

export interface ViolationDiff {
  // Problems only in `after`: this change would introduce them.
  added: MergedViolation[];
  // Problems only in `before`: this change would fix them.
  resolved: MergedViolation[];
  // Problems in both (as they read after the change).
  unchanged: UnchangedViolation[];
}

// Compares two checks of the same version problem by problem
// (violationIdentityKey), then merges each group by sentence for display
// (×N, same as the checklist). Each list keeps its source's order (`after`
// for added and unchanged, `before` for resolved).
export function diffViolations(
  before: ConstraintViolationDetail[],
  after: ConstraintViolationDetail[],
  sentenceOf: (violation: ConstraintViolationDetail) => string,
  identityOf: (violation: ConstraintViolationDetail) => string = violationIdentityKey,
): ViolationDiff {
  // identity -> every sentence it had before
  const beforeSentencesByIdentity = new Map<string, Set<string>>();
  for (const violation of before) {
    const identity = identityOf(violation);
    const sentences = beforeSentencesByIdentity.get(identity) ?? new Set<string>();
    sentences.add(sentenceOf(violation));
    beforeSentencesByIdentity.set(identity, sentences);
  }
  const afterIdentities = new Set(after.map(identityOf));

  const added = after.filter((violation) => !beforeSentencesByIdentity.has(identityOf(violation)));
  const resolved = before.filter((violation) => !afterIdentities.has(identityOf(violation)));
  const unchangedViolations = after.filter((violation) =>
    beforeSentencesByIdentity.has(identityOf(violation)),
  );

  const unchanged = mergeViolationsBySentence(unchangedViolations, sentenceOf).map((item) => ({
    ...item,
    descriptionChanged: item.violations.some(
      (violation) => !beforeSentencesByIdentity.get(identityOf(violation))?.has(item.sentence),
    ),
  }));

  return {
    added: mergeViolationsBySentence(added, sentenceOf),
    resolved: mergeViolationsBySentence(resolved, sentenceOf),
    unchanged,
  };
}
