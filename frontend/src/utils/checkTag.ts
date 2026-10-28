// Task 99 (item 9) / Task 100 (item 5): the conflict check of a timetable
// as its status tags (components/CheckStatusTag.tsx) -- which tags, their
// text, tone and icon -- and whether the full list under them is open.
// The same for the view and the edit mode. Pure, no React
// (checkTag.test.ts).

import type { BadgeTone } from "./badgeTone";

export interface CheckTagInput {
  isChecking: boolean;
  // The check request failed (its message is shown separately).
  hasFailed: boolean;
  // A result is there (and can be turned into sentences).
  hasResult: boolean;
  // Distinct problems / warnings, as the checklist counts them.
  errorCount: number;
  warningCount: number;
}

// "check" = a check mark (無衝突), "alert" = a warning triangle, null = none.
export type CheckTagIcon = "check" | "alert" | null;

export interface CheckTag {
  tone: BadgeTone;
  label: string;
  icon: CheckTagIcon;
}

// What the tag row shows:
//   checking -- one gray 「檢查中…」 (the previous result is not shown)
//   failed   -- nothing to toggle; the page shows the message and 重試
//   idle     -- no result yet: nothing
//   result   -- green 「無衝突」, or red 「N 個錯誤」 and / or amber
//               「N 個警告」 side by side
export type CheckTagState =
  | { kind: "checking"; tags: CheckTag[] }
  | { kind: "failed"; tags: CheckTag[] }
  | { kind: "idle"; tags: CheckTag[] }
  | { kind: "result"; tags: CheckTag[] };

export function checkTags(input: CheckTagInput): CheckTagState {
  if (input.isChecking) {
    return { kind: "checking", tags: [{ tone: "neutral", label: "檢查中…", icon: null }] };
  }
  if (input.hasFailed) {
    return { kind: "failed", tags: [] };
  }
  if (!input.hasResult) {
    return { kind: "idle", tags: [] };
  }
  const tags: CheckTag[] = [];
  if (input.errorCount > 0) {
    tags.push({ tone: "danger", label: `${input.errorCount} 個錯誤`, icon: "alert" });
  }
  if (input.warningCount > 0) {
    tags.push({ tone: "warning", label: `${input.warningCount} 個警告`, icon: "alert" });
  }
  if (tags.length === 0) {
    tags.push({ tone: "success", label: "無衝突", icon: "check" });
  }
  return { kind: "result", tags };
}

// The list opens by itself when there is something in it; a click on the
// tag overrides that (true / false) until the next result (null again).
export function isCheckListOpen(
  input: Pick<CheckTagInput, "hasResult" | "errorCount" | "warningCount">,
  override: boolean | null,
): boolean {
  if (!input.hasResult) {
    return false;
  }
  return override ?? (input.errorCount > 0 || input.warningCount > 0);
}

// Task 100: the check is a 教學組長's tool -- GET /check answers 403 to a
// 一般老師 for every record, published ones included -- so a teacher never
// sees the tags and the page never asks.
export function canSeeCheckTags(isCoordinator: boolean): boolean {
  return isCoordinator;
}
