// Task 98 Phase B: the wording of every 「刪除…」 confirmation (decision 34's
// risk grading: deleting data always asks first). The confirm button says
// the action (「刪除班級」), never a bare 「確定」; the negative option is
// always 「取消」 (Task 99). The
// message says what the backend will actually do -- what goes with it, and
// that it refuses while other records still use it (the row then shows the
// steps to take first, DeleteStepsHint).

import type { ConfirmTone } from "../components/ConfirmDialog";
import { DELETE_WARNING } from "./versionDelete";

export interface ConfirmText {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  tone: ConfirmTone;
}

export type DeletableKind = "class" | "subject" | "room" | "gradeRequirement" | "school" | "account";

// Task 99: every dialog's negative option (ConfirmDialog's default).
export const CANCEL_LABEL = "取消";

const NOT_UNDOABLE = "刪除後無法復原。";

interface KindText {
  noun: string;
  // After 「刪除後無法復原。」: what goes with it / when it is refused.
  consequence: string;
}

// Mirrors the backend's delete_xxx() in services/ (class_.py, subject.py,
// room.py, grade_subject_requirement.py, school.py, user.py) and the steps
// services/delete_guidance.py lists when a delete is refused.
const KIND_TEXT: Record<DeletableKind, KindText> = {
  class: {
    noun: "班級",
    consequence: "如果還有排課紀錄用到這個班級（科目需求、導師或共同排課），系統會擋下刪除，並列出要先處理的紀錄。",
  },
  subject: {
    noun: "科目",
    consequence: "如果年級科目需求或排課紀錄還用到這個科目，系統會擋下刪除，並列出要先處理的步驟。",
  },
  room: {
    noun: "教室",
    consequence: "如果還有排課紀錄用到這間教室（指定教室、已排入的課或共同排課），系統會擋下刪除，並列出要先處理的紀錄。",
  },
  gradeRequirement: {
    noun: "科目需求",
    consequence: "之後開始排課時不會再自動帶入這項需求；已經建立的排課紀錄不受影響。",
  },
  school: {
    noun: "學校",
    consequence:
      "這所學校的年級、時段、科目與年級科目需求會一併刪除。如果還有班級、教室、帳號、教師資料或排課紀錄，系統會擋下刪除，並列出要先處理的步驟。",
  },
  account: {
    noun: "帳號",
    consequence: "這個帳號將無法再登入。一般老師的帳號連著教師資料，系統會擋下刪除，請改用「停用」。",
  },
};

// `name` is what the row shows (一年甲班, 國語, 一年級的國語, the username).
export function deleteConfirmText(kind: DeletableKind, name: string): ConfirmText {
  const { noun, consequence } = KIND_TEXT[kind];
  return {
    title: `刪除「${name}」？`,
    message: `${NOT_UNDOABLE}${consequence}`,
    confirmLabel: `刪除${noun}`,
    cancelLabel: CANCEL_LABEL,
    tone: "danger",
  };
}

// The trash button's accessible name: says which row it deletes.
export function deleteButtonLabel(kind: DeletableKind, name: string): string {
  return `刪除${KIND_TEXT[kind].noun}「${name}」`;
}

// Task 100: the pencil button's accessible name and tooltip: says which
// row it edits (「編輯國語文」); a name in Latin letters or digits gets a
// space (「編輯 teacher01」).
export function editButtonLabel(name: string): string {
  return /^[!-~]/.test(name) ? `編輯 ${name}` : `編輯${name}`;
}

// 排課紀錄: the label (formatVersionLabel) already carries 編號 and status.
export function deleteRecordConfirmText(displayNumber: number | null, recordLabel: string): ConfirmText {
  return {
    title: displayNumber === null ? "刪除這筆排課紀錄？" : `刪除排課紀錄編號 ${displayNumber}？`,
    message: `將刪除「${recordLabel}」。${DELETE_WARNING}`,
    confirmLabel: "刪除紀錄",
    cancelLabel: CANCEL_LABEL,
    tone: "danger",
  };
}
