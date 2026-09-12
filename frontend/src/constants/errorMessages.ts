// Known backend error message (English, verbatim from `detail`) -> 繁體中文.
// This is a translation, not a rewording: the reason reported to the user
// stays exactly what the backend said, just in Chinese instead of English
// -- it does not weaken the "忠實呈現後端內容" (faithfully show the
// backend's content) principle from docs/FRONTEND_REQUIREMENTS.md 第 6 節.
//
// Only messages the backend is actually known to produce belong here.
// Keying by the exact string is intentionally simple and admittedly
// brittle (a backend wording change silently stops matching), but the
// fallback below means that failure mode is safe: an untranslated message
// still displays, in English, rather than disappearing or being replaced
// by a vague generic string.
const KNOWN_ERROR_MESSAGES: Record<string, string> = {
  // POST /api/v1/auth/login -- backend/app/routers/auth.py's only 401 case.
  "Incorrect username or password": "帳號或密碼錯誤",
};

// Falls back to the original (untranslated) message when it isn't in the
// table above -- never swallowed, never replaced with a generic string.
export function translateErrorMessage(message: string): string {
  return KNOWN_ERROR_MESSAGES[message] ?? message;
}
