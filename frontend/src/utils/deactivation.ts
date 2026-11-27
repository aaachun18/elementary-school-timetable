// 停用 of an account (its teacher), a subject, a room or a class -- the
// one confirmation dialog's text (components/DeactivateConfirmDialog.tsx),
// 學校資料's lists' 狀態 badge and 「顯示已停用」 filter, and the 「改為停用」
// offer when a class in use can't be deleted. Pure, no React
// (deactivation.test.ts).

import type { BadgeTone } from "./badgeTone";

export type DeactivationKind = "account" | "subject" | "room" | "class";

// GET .../deactivation-impact (backend app/services/deactivation.py).
export interface DeactivationImpact {
  published_records: number;
  other_records: number;
  not_scheduled_records: number;
  grade_requirements: number;
}

export type ImpactState =
  | { status: "loading" }
  | { status: "failed" }
  | { status: "ready"; impact: DeactivationImpact };

export const DEACTIVATE_FIRST_LINE = "停用後，新的排課不能再使用。";
export const IMPACT_LOADING_TEXT = "計算中…";
export const IMPACT_FAILED_TEXT = "無法取得影響範圍";

export interface DeactivateDialogText {
  title: string;
  lines: string[];
  confirmLabel: string;
}

// The 排課紀錄 whose timetable uses it, 已發布 included -- the ones that
// need another one before they can be published.
export function recordsInUse(impact: DeactivationImpact): number {
  return impact.published_records + impact.other_records;
}

// Task 102: at most three lines -- the rule, then (only when non-zero) how
// many 排課紀錄 use it and, for a subject, how many 年級科目需求 hide. An
// account adds that it can't log in any more. A class never gets the
// 排課紀錄 line: it is not under H12 (決策 37), so a timetable using a 停用
// class can still be published as it is.
export function deactivateDialogText(
  kind: DeactivationKind,
  name: string,
  state: ImpactState,
): DeactivateDialogText {
  const lines = [DEACTIVATE_FIRST_LINE];
  if (state.status === "loading") {
    lines.push(IMPACT_LOADING_TEXT);
  } else if (state.status === "failed") {
    lines.push(IMPACT_FAILED_TEXT);
  } else {
    const { impact } = state;
    const recordCount = recordsInUse(impact);
    if (kind !== "class" && recordCount > 0) {
      lines.push(`已有 ${recordCount} 筆排課紀錄使用，需換成其他項目才能發布。`);
    }
    if (kind === "subject" && impact.grade_requirements > 0) {
      lines.push(`各年級需求 ${impact.grade_requirements} 筆將隱藏，重新啟用後恢復。`);
    }
  }
  if (kind === "account") {
    lines.push("對應的教師資料會一併停用，且該帳號無法再登入。");
  }
  return { title: `停用「${name}」？`, lines, confirmLabel: "停用" };
}

// --- 學校資料's lists (班級 / 科目 / 教室) ---

export const SHOW_INACTIVE_LABEL = "顯示已停用";

export interface ActiveStatusBadge {
  tone: BadgeTone;
  label: string;
}

export function activeStatusBadge(isActive: boolean): ActiveStatusBadge {
  return isActive ? { tone: "success", label: "啟用中" } : { tone: "neutral", label: "已停用" };
}

// The rows shown: 已停用 ones only when 「顯示已停用」 is on.
export function visibleItems<T extends { is_active: boolean }>(items: readonly T[], showInactive: boolean): T[] {
  return items.filter((item) => showInactive || item.is_active);
}

// 班級: the grade picked (or every grade), then visibleItems().
export function visibleClasses<T extends { grade_id: number; is_active: boolean }>(
  classes: readonly T[],
  gradeId: number | null,
  showInactive: boolean,
): T[] {
  return visibleItems(
    classes.filter((item) => gradeId === null || item.grade_id === gradeId),
    showInactive,
  );
}

// A refused delete of a class in use (409 CLASS_IN_USE): why, and 停用
// offered instead.
export function classInUseText(name: string, recordCount: number): { title: string; message: string } {
  return {
    title: `無法刪除「${name}」`,
    message: `「${name}」已被 ${recordCount} 筆排課紀錄使用，無法刪除。可改為停用：停用後不會出現在新的排課中，舊紀錄仍保留。`,
  };
}
