// The wizard's 「複製此教室設定至所有同年級班級」 (科目需求 step), beside
// 「複製此連堂設定」 (utils/lessonPatternCopy.ts): the class on screen is the
// source; for each of its subjects, the other classes of the same grade that
// have that subject get its 特殊教室 (or 原班教室). Only the room is copied.
// Pure, no React; the backend checks every item again and saves them in one
// transaction.

import type { RequiredRoomItem } from "../types/classSubjectRequirement";
import { CANCEL_LABEL, type ConfirmText } from "./confirmText";

export interface RoomCopyRequirement {
  id: number;
  class_id: number;
  subject_id: number;
  required_room_id?: number | null;
  is_locked: boolean;
}

export interface RoomCopyPlan {
  // What to send; unchanged ones included (the backend leaves them as they are).
  items: RequiredRoomItem[];
  // The classes that get at least one subject's room.
  copiedClassIds: number[];
  // Target subjects left alone (no such subject, or locked), and source
  // subjects whose room is 停用 (it can't be picked any more).
  skippedCount: number;
}

export function planRequiredRoomCopy({
  sourceClassId,
  gradeClassIds,
  requirements,
  activeRoomIds,
}: {
  sourceClassId: number;
  // Every class of the source's grade (the source included).
  gradeClassIds: readonly number[];
  requirements: readonly RoomCopyRequirement[];
  activeRoomIds: ReadonlySet<number>;
}): RoomCopyPlan {
  const sources = requirements.filter((item) => item.class_id === sourceClassId);
  const targetClassIds = gradeClassIds.filter((id) => id !== sourceClassId);
  const items: RequiredRoomItem[] = [];
  const copied = new Set<number>();
  let skippedCount = 0;
  for (const source of sources) {
    const roomId = source.required_room_id ?? null;
    for (const classId of targetClassIds) {
      const target = requirements.find((item) => item.class_id === classId && item.subject_id === source.subject_id);
      if (target === undefined || target.is_locked || (roomId !== null && !activeRoomIds.has(roomId))) {
        skippedCount += 1;
        continue;
      }
      items.push({ id: target.id, required_room_id: roomId });
      copied.add(classId);
    }
  }
  return { items, copiedClassIds: [...copied], skippedCount };
}

export const COPY_ROOMS_LABEL = "複製此教室設定至所有同年級班級";

export const COPY_ROOMS_CONFIRM: ConfirmText = {
  title: "複製教室設定？",
  message: "同年級其他班級各科目的特殊教室設定會被覆蓋。",
  confirmLabel: "複製",
  cancelLabel: CANCEL_LABEL,
  tone: "primary",
};

// 「已複製到 2 個班級，略過 1 項（無此科目或教室已停用）」.
export function copyRoomsResultText(copiedClassCount: number, skippedCount: number): string {
  const copied = `已複製到 ${copiedClassCount} 個班級`;
  return skippedCount > 0 ? `${copied}，略過 ${skippedCount} 項（無此科目或教室已停用）` : copied;
}
