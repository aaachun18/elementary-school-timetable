// Task 98: why a button is disabled, in one short line shown next to it
// (components/DisabledReason.tsx) -- a disabled button is never just faded.
// null = the button is enabled, or its own label already says why (e.g.
// 「排課中…」 while the request runs).

// 「自動排課」 (wizard step 6 and 排課設定).
export function autoScheduleDisabledReason({
  isRunning,
  isDone,
  teacherCount,
  requirementCount,
}: {
  isRunning: boolean;
  isDone: boolean;
  teacherCount: number;
  requirementCount: number;
}): string | null {
  if (isRunning) {
    return null;
  }
  if (isDone) {
    return "這筆紀錄已經排好課了";
  }
  if (teacherCount === 0) {
    return "還沒設定參與教師";
  }
  if (requirementCount === 0) {
    return "還沒有任何科目需求";
  }
  return null;
}

// Wizard step 2's 「儲存並下一步」.
export function saveTeachersDisabledReason({
  isSaving,
  checkedCount,
  hasRangeError,
}: {
  isSaving: boolean;
  checkedCount: number;
  hasRangeError: boolean;
}): string | null {
  if (isSaving) {
    return null;
  }
  if (checkedCount === 0) {
    return "請先勾選至少一位老師";
  }
  if (hasRangeError) {
    return "請先修正每週節數的錯誤";
  }
  return null;
}
