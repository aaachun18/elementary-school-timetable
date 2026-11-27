import { useEffect, useState } from "react";
import { isUsernameAvailable } from "../api/users";

// Wait this long after the last keystroke before asking the backend.
const CHECK_DELAY_MS = 300;

export const USERNAME_TAKEN_MESSAGE = "這個 Email 已經有帳號，請更換";

// 新增帳號: whether the 帳號名稱 being typed is already taken, checked a
// moment after typing stops. true = taken, false = free, null = not known
// (empty, still checking, or the check itself failed -- then 儲存 is still
// allowed and the backend's own 409 「這個 Email 已經有帳號，請更換」 reports it).
export function useUsernameTaken(username: string): boolean | null {
  const [result, setResult] = useState<{ username: string; taken: boolean } | null>(null);
  const trimmed = username.trim();

  useEffect(() => {
    if (trimmed === "") {
      return undefined;
    }
    let isCurrent = true;
    const timer = window.setTimeout(() => {
      isUsernameAvailable(trimmed)
        .then((available) => {
          if (isCurrent) {
            setResult({ username: trimmed, taken: !available });
          }
        })
        .catch(() => {
          // Not swallowed for good: an unknown answer just doesn't warn
          // early; the register call reports a taken name itself.
          if (isCurrent) {
            setResult(null);
          }
        });
    }, CHECK_DELAY_MS);
    return () => {
      isCurrent = false;
      window.clearTimeout(timer);
    };
  }, [trimmed]);

  // An answer for an earlier spelling says nothing about this one.
  return result !== null && result.username === trimmed ? result.taken : null;
}
