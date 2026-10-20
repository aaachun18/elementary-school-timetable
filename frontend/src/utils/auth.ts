import { TOKEN_KEY } from "../api/client";

// Mirrors the values backend/app/models/user.py's CheckConstraint allows
// for User.role. Task 98: ADMIN = 系統管理員, COORDINATOR = 教學組長,
// TEACHER = 一般老師.
export type UserRole = "ADMIN" | "COORDINATOR" | "TEACHER";

export const ROLE_LABELS: Record<UserRole, string> = {
  ADMIN: "系統管理員",
  COORDINATOR: "教學組長",
  TEACHER: "一般老師",
};

interface AccessTokenPayload {
  sub?: string;
  role?: string;
  exp?: number;
}

// Decodes the JWT's payload segment only -- this is NOT a signature
// verification, and isn't meant to be one. The frontend has no way to (and
// no need to) verify a JWT's signature: every write endpoint independently
// enforces role server-side via require_admin
// (backend/app/core/dependencies.py) regardless of what this reads. This
// exists purely so the UI can decide which buttons are even worth showing
// -- a tampered/forged token would just make some buttons appear that
// still 403 the moment they're used, same as a TEACHER token always has.
function decodeAccessTokenPayload(token: string): AccessTokenPayload | null {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  try {
    // JWT uses base64url, not plain base64 -- swap the two characters that
    // differ before handing it to atob().
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, "0")}`)
        .join(""),
    );
    return JSON.parse(json) as AccessTokenPayload;
  } catch {
    return null;
  }
}

// Returns null when there is no token, or it can't be decoded, or its
// role claim isn't one of the known roles -- every call site treats
// null the same as "not an admin" (fail closed: an unrecognized token
// never unlocks the write buttons).
export function getCurrentUserRole(): UserRole | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token === null) {
    return null;
  }
  const payload = decodeAccessTokenPayload(token);
  if (payload?.role === "ADMIN" || payload?.role === "COORDINATOR" || payload?.role === "TEACHER") {
    return payload.role;
  }
  return null;
}

// Task 59: the logged-in account's username -- the JWT's `sub` claim
// (backend/app/routers/auth.py's login() puts the username there). Used
// only to disable the 帳號管理 page's delete button on the user's own row;
// the backend independently refuses self-deletion regardless.
export function getCurrentUsername(): string | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token === null) {
    return null;
  }
  const sub = decodeAccessTokenPayload(token)?.sub;
  return typeof sub === "string" ? sub : null;
}

// Only the 系統管理員 -- schools, and deleting / binding accounts.
export function isCurrentUserAdmin(): boolean {
  return getCurrentUserRole() === "ADMIN";
}

// Task 98: the 系統管理員 or a 教學組長 -- whoever may manage accounts
// (backend require_manager).
export function isCurrentUserManager(): boolean {
  const role = getCurrentUserRole();
  return role === "ADMIN" || role === "COORDINATOR";
}

// Task 98: only a 教學組長 changes scheduling data (backend
// require_coordinator); the 系統管理員 has no scheduling data at all.
export function isCurrentUserCoordinator(): boolean {
  return getCurrentUserRole() === "COORDINATOR";
}

// Task 98: where each role lands -- and where a page the role may not
// open sends it instead. An unknown role (null) is treated like a 教學組長
// (the page itself then fails closed on its own requests).
export function homePathFor(role: UserRole | null): string {
  if (role === "ADMIN") {
    return "/schools";
  }
  return "/";
}
