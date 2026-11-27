import type { Profile } from "../types/me";
import { getPasswordRuleError } from "./passwordRule";

// 個人資料維護's rules, pure (no React). The backend checks the same.

// An 一般老師 after 離校: logged in, but no school's data to show.
export function isUnassignedTeacher(profile: Profile | null): boolean {
  return profile !== null && profile.role === "TEACHER" && profile.school_id === null;
}

// The 系統管理員 has only an account name; everyone else also a name.
export function hasEditableName(profile: Profile): boolean {
  return profile.role !== "ADMIN" && profile.school_id !== null;
}

export interface PasswordChangeDraft {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

// The first problem with the draft, or null when it can be saved.
export function getPasswordChangeError(draft: PasswordChangeDraft): string | null {
  if (draft.currentPassword === "") {
    return "請輸入目前密碼";
  }
  if (draft.newPassword === "") {
    return "請輸入新密碼";
  }
  const ruleError = getPasswordRuleError(draft.newPassword);
  if (ruleError !== null) {
    return ruleError;
  }
  if (draft.newPassword !== draft.confirmPassword) {
    return "兩次輸入的新密碼不一致";
  }
  return null;
}
