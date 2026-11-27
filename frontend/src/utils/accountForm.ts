import type { AccountCreate } from "../types/user";
import type { UserRole } from "./auth";

// 帳號改版: the 新增帳號 dialog's rules, mirroring what
// backend/app/services/user.py enforces (the backend is still the final
// authority -- this only keeps 儲存 disabled and explains why).
//
// - 系統管理員: creates a 教學組長 -- 所屬學校 + Email.
// - 教學組長: creates an 一般老師 of their own school -- Email + 教師姓名.
// The password is generated and mailed by the backend.

// The role the new account gets.
export function newAccountRole(actorRole: UserRole | null): UserRole {
  return actorRole === "ADMIN" ? "COORDINATOR" : "TEACHER";
}

export function needsSchoolChoice(actorRole: UserRole | null): boolean {
  return actorRole === "ADMIN";
}

export function needsTeacherName(actorRole: UserRole | null): boolean {
  return actorRole !== "ADMIN";
}

// Same shape check as backend/app/schemas/user.py EMAIL_PATTERN.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const EMAIL_FORMAT_MESSAGE = "Email 格式不正確";

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

export function isValidEmail(value: string): boolean {
  return EMAIL_PATTERN.test(normalizeEmail(value));
}

export interface NewAccountDraft {
  email: string;
  schoolId: number | null;
  teacherName: string;
}

// The first missing / invalid field, as a short Chinese hint, or null
// when the draft can be saved.
export function getMissingFieldMessage(draft: NewAccountDraft, actorRole: UserRole | null): string | null {
  if (needsSchoolChoice(actorRole) && draft.schoolId === null) {
    return "請選擇所屬學校";
  }
  if (draft.email.trim() === "") {
    return "請輸入 Email";
  }
  if (!isValidEmail(draft.email)) {
    return EMAIL_FORMAT_MESSAGE;
  }
  if (needsTeacherName(actorRole) && draft.teacherName.trim() === "") {
    return "請輸入教師姓名";
  }
  return null;
}

export function toAccountCreate(draft: NewAccountDraft, actorRole: UserRole | null): AccountCreate {
  const body: AccountCreate = { email: normalizeEmail(draft.email) };
  if (needsSchoolChoice(actorRole) && draft.schoolId !== null) {
    body.school_id = draft.schoolId;
  }
  if (needsTeacherName(actorRole)) {
    body.teacher_name = draft.teacherName.trim();
  }
  return body;
}
