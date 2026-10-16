// Task 84: turning the move-candidates response (Task 83) into a mark per
// timetable cell / lesson while a lesson is selected or dragged in edit
// mode. Pure functions, no React.
//
// A mark uses exactly the preview dialog's rule (AdjustmentPreviewDialog:
// diffViolations(), "adds problems" = diff.added is not empty) and the same
// sentences, so a red cell is precisely a drop whose preview would say
// 「這次異動會新增的問題」. Marks are only a hint: a red cell can still be
// dropped on, and the preview decides.

import type {
  ConstraintViolationDetail,
  MoveCandidatesResult,
  ScheduleCheckResult,
} from "../types/scheduler";
import { diffViolations } from "./violationMerge";

// safe: the change adds no problem (it may solve some, or leave existing
// ones as they are). conflict: it adds at least one, with the sentences.
// unavailable: not a target at all (non-teaching slot / current slot) --
// shown with the cell's ordinary style, no mark. none: no data for this
// target (e.g. a lesson the backend didn't list as a swap partner) -- no
// hint either way.
export type CandidateMark =
  | { status: "safe" }
  | { status: "conflict"; reasons: string[] }
  | { status: "unavailable" }
  | { status: "none" };

export const NO_MARK: CandidateMark = { status: "none" };

// How many reasons a conflict mark spells out before 「…等 N 項」.
export const MAX_LISTED_REASONS = 3;

export type SentenceOf = (violation: ConstraintViolationDetail) => string;

// The cache key for one lesson's candidates: the version, the lesson
// (Schedule row) and the timetable's edit revision, which goes up after
// every saved move / swap / reassignment -- so a saved change makes every
// earlier entry unreachable. null when there is nothing to fetch.
export function candidateCacheKey(
  versionId: number | null,
  scheduleId: number | null,
  revision: number,
): string | null {
  if (versionId === null || scheduleId === null) {
    return null;
  }
  return `${versionId}:${scheduleId}:${revision}`;
}

// baseline vs. the check after one change, by the preview dialog's rule.
export function assessCandidate(
  baseline: ScheduleCheckResult,
  after: ScheduleCheckResult,
  sentenceOf: SentenceOf,
): CandidateMark {
  const diff = diffViolations(baseline.violations, after.violations, sentenceOf);
  if (diff.added.length === 0) {
    return { status: "safe" };
  }
  return {
    status: "conflict",
    reasons: diff.added.map((item) => (item.count > 1 ? `${item.sentence} ×${item.count}` : item.sentence)),
  };
}

// Dropping on the empty part of the cell for this time slot: a move.
export function markForCell(
  data: MoveCandidatesResult,
  timeSlotId: number,
  sentenceOf: SentenceOf,
): CandidateMark {
  const candidate = data.candidates.find((item) => item.time_slot_id === timeSlotId);
  if (candidate === undefined) {
    return NO_MARK;
  }
  if (!candidate.available || candidate.move === null) {
    return { status: "unavailable" };
  }
  return assessCandidate(data.baseline, candidate.move, sentenceOf);
}

// Dropping on another lesson in this time slot: a swap with it.
export function markForSwap(
  data: MoveCandidatesResult,
  timeSlotId: number,
  otherScheduleId: number,
  sentenceOf: SentenceOf,
): CandidateMark {
  const swap = data.candidates
    .find((item) => item.time_slot_id === timeSlotId)
    ?.swaps.find((item) => item.swap_with_schedule_id === otherScheduleId);
  if (swap === undefined) {
    return NO_MARK;
  }
  return assessCandidate(data.baseline, swap.check, sentenceOf);
}

// The short visible label -- never colour alone. A cell's mark is about
// moving there ("可放"), a lesson's about swapping with it ("可對調").
export function candidateLabel(mark: CandidateMark, action: "move" | "swap"): string | null {
  if (mark.status === "safe") {
    return action === "move" ? "可放" : "可對調";
  }
  if (mark.status === "conflict") {
    return "衝突";
  }
  return null;
}

// title / aria-label text: what dropping here would do, with at most
// MAX_LISTED_REASONS reasons.
export function candidateDescription(mark: CandidateMark, action: "move" | "swap"): string | null {
  const verb = action === "move" ? "移到這裡" : "與這堂課對調";
  if (mark.status === "safe") {
    return `${verb}不會新增問題`;
  }
  if (mark.status !== "conflict") {
    return null;
  }
  const listed = mark.reasons.slice(0, MAX_LISTED_REASONS).join("；");
  const more = mark.reasons.length > MAX_LISTED_REASONS ? `…等 ${mark.reasons.length} 項` : "";
  return `${verb}會新增問題：${listed}${more}`;
}

// Which state the page is in for the current key. Results are stored per
// cache key, so a response for a lesson that is no longer selected or
// dragged lands under its own key and is simply never read -- it can't
// overwrite the current lesson's marks.
export type CandidateResult =
  | { ok: true; data: MoveCandidatesResult }
  | { ok: false };

export type CandidateState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: MoveCandidatesResult }
  | { status: "failed" };

export function candidateStateFor(
  results: ReadonlyMap<string, CandidateResult>,
  key: string | null,
): CandidateState {
  if (key === null) {
    return { status: "idle" };
  }
  const result = results.get(key);
  if (result === undefined) {
    return { status: "loading" };
  }
  return result.ok ? { status: "ready", data: result.data } : { status: "failed" };
}

// Every mark of one response, computed once (not per render: the grid
// re-renders on every dragover change). cells: time slot id -> move mark;
// swaps: swapMarkKey(time slot id, schedule id) -> swap mark. Targets
// missing from the maps get no hint.
export interface CandidateMarks {
  cells: ReadonlyMap<number, CandidateMark>;
  swaps: ReadonlyMap<string, CandidateMark>;
}

export function swapMarkKey(timeSlotId: number, scheduleId: number): string {
  return `${timeSlotId}:${scheduleId}`;
}

export function buildCandidateMarks(
  data: MoveCandidatesResult,
  sentenceOf: SentenceOf,
): CandidateMarks {
  const cells = new Map<number, CandidateMark>();
  const swaps = new Map<string, CandidateMark>();
  for (const candidate of data.candidates) {
    cells.set(candidate.time_slot_id, markForCell(data, candidate.time_slot_id, sentenceOf));
    for (const swap of candidate.swaps) {
      swaps.set(
        swapMarkKey(candidate.time_slot_id, swap.swap_with_schedule_id),
        assessCandidate(data.baseline, swap.check, sentenceOf),
      );
    }
  }
  return { cells, swaps };
}
