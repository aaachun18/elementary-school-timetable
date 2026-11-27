import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";
import { getCurrentUserRole, homePathFor, type UserRole } from "../utils/auth";

// Task 98 (replaces Task 43's AdminOnlyRoute): a page only the listed roles
// may open. A CONFIRMED role outside the list is sent to its own landing
// page instead (homePathFor: the 系統管理員 to 學校管理, everyone else
// to 首頁); a TEACHER asking for an admin page still lands on
// /timetable, as before Task 98.
//
// This is a navigation/UX restriction, not a security boundary by itself:
// the backend's require_coordinator / require_manager / require_admin and
// its per-school scoping are the real lock regardless of this component.
//
// A role that can't be determined (null -- no token, or one that can't be
// decoded) is let through rather than redirected: this only ever blocks a
// CONFIRMED role, never an ambiguous case.
export default function RoleRoute({
  allow,
  children,
}: {
  allow: readonly UserRole[];
  children: ReactElement;
}): ReactElement {
  const role = getCurrentUserRole();
  if (role !== null && !allow.includes(role)) {
    return <Navigate to={role === "TEACHER" ? "/timetable" : homePathFor(role)} replace />;
  }
  return children;
}
