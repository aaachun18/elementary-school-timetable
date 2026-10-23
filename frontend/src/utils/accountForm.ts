import type { UserCreate } from "../types/user";
import type { UserRole } from "./auth";

// Task 98: the 帳號管理 add-row's rules, mirroring what
// backend/app/services/user.py enforces (the backend is still the final
// authority -- this only keeps 確認 disabled and explains why).

// Which roles the logged-in account may create.
export function creatableRoles(actorRole: UserRole | null): UserRole[] {
  if (actorRole === "ADMIN") {
    return ["TEACHER", "COORDINATOR", "ADMIN"];
  }
  return ["TEACHER"];
}

// Only the 系統管理員 picks a school; a 教學組長's accounts always go to
// their own school, and a 系統管理員 account has none.
export function needsSchoolChoice(actorRole: UserRole | null, role: UserRole): boolean {
  return actorRole === "ADMIN" && role !== "ADMIN";
}

export interface NewAccountDraft {
  username: string;
  password: string;
  role: UserRole;
  schoolId: number | null;
  teacherName: string;
  // 身分證字號: asked for only when the name is already taken (else "").
  nationalId: string;
}

// The first missing field, as a short Chinese hint, or null when the draft
// is complete. (The password's own rule is checked separately.)
export function getMissingFieldMessage(
  draft: NewAccountDraft,
  actorRole: UserRole | null,
): string | null {
  if (draft.username.trim() === "") {
    return "請輸入帳號名稱";
  }
  if (draft.password === "") {
    return "請輸入密碼";
  }
  if (draft.role === "TEACHER" && draft.teacherName.trim() === "") {
    return "請輸入教師姓名";
  }
  if (needsSchoolChoice(actorRole, draft.role) && draft.schoolId === null) {
    return "請選擇所屬學校";
  }
  return null;
}

export function toUserCreate(draft: NewAccountDraft, actorRole: UserRole | null): UserCreate {
  const body: UserCreate = {
    username: draft.username.trim(),
    password: draft.password,
    role: draft.role,
  };
  if (needsSchoolChoice(actorRole, draft.role) && draft.schoolId !== null) {
    body.school_id = draft.schoolId;
  }
  if (draft.role === "TEACHER") {
    body.teacher_name = draft.teacherName.trim();
    if (draft.nationalId.trim() !== "") {
      body.teacher_national_id = normalizeNationalId(draft.nationalId);
    }
  }
  return body;
}

// --- 身分證字號 (same rule as backend/app/schemas/user.py) ---

const NATIONAL_ID_PATTERN = /^[A-Z][A-Z0-9][0-9]{8}$/;

export const NATIONAL_ID_FORMAT_MESSAGE = "身分證字號格式不正確，應為 1 個英文字母加 9 碼（例：A123456789）";

export function normalizeNationalId(value: string): string {
  return value.trim().toUpperCase();
}

// null when valid, otherwise the message to show.
export function getNationalIdError(value: string): string | null {
  if (value.trim() === "") {
    return "請輸入身分證字號";
  }
  return NATIONAL_ID_PATTERN.test(normalizeNationalId(value)) ? null : NATIONAL_ID_FORMAT_MESSAGE;
}
