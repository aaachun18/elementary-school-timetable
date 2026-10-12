import { TOKEN_KEY } from "../api/client";

// Mirrors the two values backend/app/models/user.py's CheckConstraint
// allows for User.role.
export type UserRole = "ADMIN" | "TEACHER";

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
// role claim isn't one of the two known roles -- every call site treats
// null the same as "not an admin" (fail closed: an unrecognized token
// never unlocks the write buttons).
export function getCurrentUserRole(): UserRole | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token === null) {
    return null;
  }
  const payload = decodeAccessTokenPayload(token);
  if (payload?.role === "ADMIN" || payload?.role === "TEACHER") {
    return payload.role;
  }
  return null;
}

export function isCurrentUserAdmin(): boolean {
  return getCurrentUserRole() === "ADMIN";
}
