// Idle logout (閒置自動登出): someone who does nothing for IDLE_TIMEOUT_MINUTES
// is logged out; someone working never is -- while they are active the
// token is renewed (POST /auth/refresh, at most every REFRESH_INTERVAL_MS).
// Before this the token simply ran out a fixed hour after logging in, in the
// middle of whatever was being edited. Pure, no React (session.test.ts);
// hooks/useIdleSession.ts runs it.

// Mirrors the backend's IDLE_TIMEOUT_MINUTES (app/core/security.py), whose
// tokens last a little longer, so this timer is what logs out on time.
export const IDLE_TIMEOUT_MINUTES = 30;
export const IDLE_TIMEOUT_MS = IDLE_TIMEOUT_MINUTES * 60 * 1000;
// Renew no more often than this while active (a request per move would be
// pointless); well inside the token's lifetime.
export const REFRESH_INTERVAL_MS = 5 * 60 * 1000;
// How often the timer looks.
export const SESSION_CHECK_INTERVAL_MS = 30 * 1000;

export type SessionAction = "logout" | "refresh" | "none";

export function sessionAction({
  now,
  lastActivityAt,
  lastRefreshAt,
}: {
  now: number;
  // The last mouse, keyboard, touch, scroll or drag.
  lastActivityAt: number;
  // When the token in use was issued (renewed).
  lastRefreshAt: number;
}): SessionAction {
  if (now - lastActivityAt >= IDLE_TIMEOUT_MS) {
    return "logout";
  }
  // Only for someone active since the last renewal: an idle person's token
  // is left to run out with the idle timer.
  if (lastActivityAt > lastRefreshAt && now - lastRefreshAt >= REFRESH_INTERVAL_MS) {
    return "refresh";
  }
  return "none";
}

// Why the login page was opened, kept for that page only (sessionStorage).
export type LogoutReason = "idle" | "expired";

const LOGOUT_REASON_KEY = "auth.logoutReason";

export const LOGOUT_REASON_MESSAGES: Record<LogoutReason, string> = {
  idle: `閒置超過 ${IDLE_TIMEOUT_MINUTES} 分鐘，已自動登出，請重新登入。`,
  expired: "登入已逾時，請重新登入。",
};

export function rememberLogoutReason(reason: LogoutReason): void {
  try {
    sessionStorage.setItem(LOGOUT_REASON_KEY, reason);
  } catch {
    // The login page then just shows no reason.
  }
}

export function readLogoutReason(): LogoutReason | null {
  try {
    const reason = sessionStorage.getItem(LOGOUT_REASON_KEY);
    return reason === "idle" || reason === "expired" ? reason : null;
  } catch {
    return null;
  }
}

// After the login page has read it: shown on that page only.
export function clearLogoutReason(): void {
  try {
    sessionStorage.removeItem(LOGOUT_REASON_KEY);
  } catch {
    // Nothing to clear then.
  }
}
