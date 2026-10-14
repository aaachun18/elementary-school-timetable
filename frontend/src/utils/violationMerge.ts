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

// --- Task 69: before/after comparison for a move/swap preview ---

export interface ViolationDiff {
  // In `after` only: problems this change would introduce.
  added: MergedViolation[];
  // In `before` only: problems this change would fix.
  resolved: MergedViolation[];
  // In both: problems the change doesn't touch (as they look after it).
  unchanged: MergedViolation[];
}

// Compares two checks of the same version by merged Chinese sentence -- the
// same key the checklist shows, so "added" means "a line the user would
// newly see". A line present in both counts as unchanged even if its ×N
// changed. Each list keeps its source's merged order (`after` for added and
// unchanged, `before` for resolved).
export function diffViolations(
  before: ConstraintViolationDetail[],
  after: ConstraintViolationDetail[],
  sentenceOf: (violation: ConstraintViolationDetail) => string,
): ViolationDiff {
  const beforeItems = mergeViolationsBySentence(before, sentenceOf);
  const afterItems = mergeViolationsBySentence(after, sentenceOf);
  const beforeSentences = new Set(beforeItems.map((item) => item.sentence));
  const afterSentences = new Set(afterItems.map((item) => item.sentence));
  return {
    added: afterItems.filter((item) => !beforeSentences.has(item.sentence)),
    resolved: beforeItems.filter((item) => !afterSentences.has(item.sentence)),
    unchanged: afterItems.filter((item) => beforeSentences.has(item.sentence)),
  };
}
