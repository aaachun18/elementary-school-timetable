// Task 59: frontend copy of the backend's password rule
// (backend/app/schemas/user.py's validate_password) -- 8 characters to 72
// UTF-8 bytes, bcrypt's own input limit. The backend still enforces it
// independently; this exists so the 帳號管理 forms can show the reason in
// Chinese BEFORE submitting. (Task 60: a backend 422 now also shows the
// same Chinese message, via extractApiErrorMessage(), if it ever gets
// past this check.)
export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_BYTES = 72;

const PASSWORD_TOO_SHORT_MESSAGE = "密碼至少需要 8 個字元";
const PASSWORD_TOO_LONG_MESSAGE = "密碼太長，請縮短（中文等非英數字元每字會佔用較多長度）";

// Returns null when the password satisfies the rule, or the message to
// show otherwise. Same two messages, checked in the same order, as the backend.
export function getPasswordRuleError(password: string): string | null {
  // Array.from() counts code points, matching Python's len() on a str
  // (password.length would count an emoji as 2).
  const characterCount = Array.from(password).length;
  if (characterCount < PASSWORD_MIN_LENGTH) {
    return PASSWORD_TOO_SHORT_MESSAGE;
  }
  if (
    characterCount > PASSWORD_MAX_BYTES ||
    new TextEncoder().encode(password).length > PASSWORD_MAX_BYTES
  ) {
    return PASSWORD_TOO_LONG_MESSAGE;
  }
  return null;
}
