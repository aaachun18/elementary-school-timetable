// Task 98 Phase D: the one dynamic line under each of the home page's
// three Action Cards (開始排課 / 排課紀錄 / 學校資料). Pure, no React.

import type { ScheduleVersion } from "../types/scheduleVersion";
import { formatRecordStatus } from "./scheduleVersionFormat";

type RecordSource = Pick<
  ScheduleVersion,
  "display_number" | "status" | "is_published" | "copied_from_display_number"
>;

// Records the 排課紀錄 page lists (a working copy being edited has no 編號).
function listedRecords<T extends RecordSource>(records: readonly T[]): T[] {
  return records.filter((record) => record.display_number !== null);
}

// 開始排課: how many records are still 尚未排課 (settings not finished or
// not yet scheduled), else what the wizard does.
export function wizardCardText(records: readonly RecordSource[]): string {
  const notScheduled = listedRecords(records).filter((record) => record.status === "NOT_SCHEDULED").length;
  return notScheduled > 0 ? `${notScheduled} 筆尚未排課的紀錄` : "設定老師與科目需求，自動排出課表";
}

// 排課紀錄: 「3 筆未發布紀錄 · 最近一筆：手動排課」 (編號 1 is the newest).
export function recordsCardText(records: readonly RecordSource[]): string {
  const listed = listedRecords(records);
  if (listed.length === 0) {
    return "還沒有排課紀錄";
  }
  const unpublished = listed.filter((record) => !record.is_published).length;
  const latest = listed.reduce((newest, record) =>
    (record.display_number ?? Infinity) < (newest.display_number ?? Infinity) ? record : newest,
  );
  return `${unpublished} 筆未發布紀錄 · 最近一筆：${formatRecordStatus(latest)}`;
}

// 學校資料: 「10 位老師 · 6 個班級」.
export function schoolDataCardText(teacherCount: number, classCount: number): string {
  return `${teacherCount} 位老師 · ${classCount} 個班級`;
}
