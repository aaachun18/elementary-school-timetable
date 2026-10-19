// Task 92A: what the move/swap and 換教師 preview dialogs show, as plain
// data -- one line saying what the change does, one verdict line (does it
// add problems), and a short list of one-line problems. Pure functions, no
// React, so every case can be unit-tested (previewSummary.test.ts).

import {
  UNKNOWN_VIOLATION_TYPE_HEADING,
  VIOLATION_TYPE_HEADINGS,
  VIOLATION_TYPE_SUGGESTIONS,
} from "../constants/errorMessages";
import { splitBySeverity, type MergedViolation, type ViolationDiff } from "./violationMerge";

// How many problem lines / changed rows show before 「另外 N 項／列」.
export const PREVIEW_VISIBLE_LINES = 3;
export const PREVIEW_VISIBLE_CHANGES = 4;

// error: a new problem (red). warning: a new WARNING (light, Task 90).
// unresolved: an existing problem that now reads differently (Task 71).
// resolved: a problem this change fixes (green).
export type PreviewLineKind = "error" | "warning" | "unresolved" | "resolved";

export interface PreviewLine {
  key: string;
  kind: PreviewLineKind;
  // The small tag in front, e.g. 「老師衝堂」.
  category: string;
  // The sentence without its closing 「！」.
  text: string;
  // 「（2 堂）」 when one problem was reported for several lessons, else null.
  countLabel: string | null;
  // The type's Chinese suggestion, or null -- shown only in `fullText`
  // (the line's title and aria-label), never as a line of its own.
  suggestion: string | null;
  // Everything about the line in one string, for title and aria-label.
  fullText: string;
}

export interface PreviewVerdict {
  // ok: no new ERROR (green ✓). problem: at least one (red).
  tone: "ok" | "problem";
  text: string;
}

export interface PreviewSummary {
  verdict: PreviewVerdict;
  // New errors, then new warnings, then still-unresolved, then resolved.
  lines: PreviewLine[];
  // Existing problems the change leaves alone and describes the same way.
  untouchedCount: number;
  // Only new ERRORs make a change 「仍要…」.
  addsProblems: boolean;
}

const KIND_CATEGORY: Partial<Record<PreviewLineKind, string>> = {
  warning: "警告",
  unresolved: "仍未解決",
  resolved: "已解決",
};

export function shortSentence(sentence: string): string {
  return sentence.replace(/[！。!.]+$/u, "");
}

export function previewVerdict(addedErrorCount: number, resolvedCount: number): PreviewVerdict {
  const resolved = resolvedCount > 0 ? `，解決 ${resolvedCount} 項` : "";
  if (addedErrorCount === 0) {
    return { tone: "ok", text: `✓ 沒有新增問題${resolved}` };
  }
  return { tone: "problem", text: `會新增 ${addedErrorCount} 項問題${resolved}` };
}

export function previewLine(item: MergedViolation, kind: PreviewLineKind): PreviewLine {
  const category =
    KIND_CATEGORY[kind] ?? VIOLATION_TYPE_HEADINGS[item.type] ?? UNKNOWN_VIOLATION_TYPE_HEADING;
  const text = shortSentence(item.sentence);
  const countLabel = item.count > 1 ? `（${item.count} 堂）` : null;
  // A resolved problem needs no advice.
  const suggestion = kind === "resolved" ? null : (VIOLATION_TYPE_SUGGESTIONS[item.type] ?? null);
  const fullText = `${category}：${text}${countLabel ?? ""}${suggestion === null ? "" : `。建議：${suggestion}`}`;
  return { key: `${kind}:${item.sentence}`, kind, category, text, countLabel, suggestion, fullText };
}

export function buildPreviewSummary(diff: ViolationDiff): PreviewSummary {
  const added = splitBySeverity(diff.added);
  const stillUnresolved = diff.unchanged.filter((item) => item.descriptionChanged);
  return {
    verdict: previewVerdict(added.errors.length, diff.resolved.length),
    lines: [
      ...added.errors.map((item) => previewLine(item, "error")),
      ...added.warnings.map((item) => previewLine(item, "warning")),
      ...stillUnresolved.map((item) => previewLine(item, "unresolved")),
      ...diff.resolved.map((item) => previewLine(item, "resolved")),
    ],
    untouchedCount: diff.unchanged.length - stillUnresolved.length,
    addsProblems: added.errors.length > 0,
  };
}

// The first `limit` items (all of them once expanded) and how many are
// left for 「另外 N 項」.
export function visibleItems<T>(
  items: readonly T[],
  limit: number,
  expanded: boolean,
): { shown: T[]; hiddenCount: number } {
  if (expanded || items.length <= limit) {
    return { shown: [...items], hiddenCount: 0 };
  }
  return { shown: items.slice(0, limit), hiddenCount: items.length - limit };
}

// --- The 「這次會做什麼」 line ---

// 「四年甲班 國語：星期一第 2 節 → 星期二第 2 節（整組 2 節一起移動）」.
export function describeMoveLine(
  lessonName: string,
  fromSlot: string,
  toSlot: string,
  changedRowCount: number,
): string {
  const block = changedRowCount > 1 ? `（整組 ${changedRowCount} 節一起移動）` : "";
  return `${lessonName}：${fromSlot} → ${toSlot}${block}`;
}

// 「四年甲班 國語：星期一第 2 節 ↔ 四年甲班 數學：星期二第 2 節」.
export function describeSwapLine(
  lessonName: string,
  slot: string,
  otherName: string,
  otherSlot: string,
  changedRowCount: number,
): string {
  const block = changedRowCount > 2 ? `（兩組連堂整組對調，共 ${changedRowCount} 節）` : "";
  return `${lessonName}：${slot} ↔ ${otherName}：${otherSlot}${block}`;
}

// 「四年甲班 國語：王老師 → 李老師（3 堂課）」.
export function describeReassignLine(
  courseName: string,
  previousTeacher: string | null,
  newTeacher: string,
  changedLessonCount: number,
): string {
  const count =
    changedLessonCount > 0 ? `（${changedLessonCount} 堂課）` : "（這個版本沒有要換的課，只更新指定教師）";
  return `${courseName}：${previousTeacher ?? "未指定教師"} → ${newTeacher}${count}`;
}
