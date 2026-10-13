// Task 59: frontend copy of the backend's password rule
// (backend/app/schemas/user.py's validate_password) -- 8 characters to 72
// UTF-8 bytes, bcrypt's own input limit. The backend still enforces it
// independently; this exists so the 帳號管理 forms can show the reason in
// Chinese BEFORE submitting. A backend 422 carries a validation-error
// array rather than a `detail` string, which extractApiErrorMessage()
// cannot turn into a readable message.
export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_BYTES = 72;

const PASSWORD_LENGTH_MESSAGE = "密碼長度必須為 8 到 72 個字元";
const PASSWORD_BYTES_MESSAGE =
  "密碼長度必須為 8 到 72 個字元，中文等非英數字元每字會佔用 2 到 4 個字元的長度";

// Returns null when the password satisfies the rule, or the message to
// show otherwise. Same two messages, in the same order, as the backend.
export function getPasswordRuleError(password: string): string | null {
  // Array.from() counts code points, matching Python's len() on a str
  // (password.length would count an emoji as 2).
  const characterCount = Array.from(password).length;
  if (characterCount < PASSWORD_MIN_LENGTH || characterCount > PASSWORD_MAX_BYTES) {
    return PASSWORD_LENGTH_MESSAGE;
  }
  if (new TextEncoder().encode(password).length > PASSWORD_MAX_BYTES) {
    return PASSWORD_BYTES_MESSAGE;
  }
  return null;
}
