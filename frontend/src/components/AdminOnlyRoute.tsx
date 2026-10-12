import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";
import { getCurrentUserRole } from "../utils/auth";

// Task 43: a TEACHER's whole experience is limited to 課表檢視 -- every
// other page (首頁/基礎資料/排課需求總覽/排課控制台) redirects a TEACHER
// straight to /timetable instead of rendering at all. Wrap each of those
// routes' element with this in App.tsx.
//
// This is a navigation/UX restriction, not a security boundary by itself:
// the pages behind it don't expose anything the backend wouldn't already
// let a TEACHER GET directly -- their write buttons are separately gated
// by isCurrentUserAdmin() (Task 42) and backend require_admin enforces the
// real write lock regardless of this component. The one piece of this
// Task that IS a real backend-enforced boundary (TEACHER only ever seeing
// PUBLISHED ScheduleVersions/Schedules) lives in
// backend/app/services/schedule_version.py and schedule.py, not here.
//
// A role that can't be determined (null -- no token, or one that can't be
// decoded) is let through rather than redirected: this only ever blocks a
// CONFIRMED TEACHER, never an ambiguous case.
export default function AdminOnlyRoute({
  children,
}: {
  children: ReactElement;
}): ReactElement {
  if (getCurrentUserRole() === "TEACHER") {
    return <Navigate to="/timetable" replace />;
  }
  return children;
}
