import type { ReactElement } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import { getCurrentUserRole, isCurrentUserManager } from "../utils/auth";
import { BUTTON_SECONDARY_SM, NAV_BAR, NAV_LINK, NAV_LINK_ACTIVE } from "../styles/ui";

// Shared shell for every protected page (see App.tsx: this is combined
// with ProtectedRoute as one parent layout route, wrapping Home/DataBrowser
// as nested <Outlet /> children) -- so logout only needs to be written
// once, here, instead of duplicated per page.
export default function Layout(): ReactElement {
  const navigate = useNavigate();
  // Task 43 / 98: each role only gets the links to pages it may open (the
  // rest also bounce back via RoleRoute, see App.tsx, if typed directly)
  // -- left out of the nav entirely rather than shown disabled:
  // - 系統管理員: 學校管理, 帳號管理;
  // - 一般老師: 首頁 (a simplified dashboard, Task 97), 課表;
  // - 教學組長: 首頁, 開始排課, 排課紀錄, 學校資料, 帳號管理. An unknown
  //   role (null) sees this nav too, same "only block a CONFIRMED role"
  //   stance RoleRoute takes.
  const role = getCurrentUserRole();
  const isAdmin = role === "ADMIN";
  const isTeacher = role === "TEACHER";
  const canManageAccounts = isCurrentUserManager();

  function handleLogout(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    navigate("/login");
  }

  // Task 48: NavLink (not plain Link) only to pick up its automatic
  // isActive -> styling -- purely presentational (which page is
  // highlighted), no change to where any link actually goes or what
  // RoleRoute/ProtectedRoute decide.
  function navLinkClassName({ isActive }: { isActive: boolean }): string {
    return isActive ? NAV_LINK_ACTIVE : NAV_LINK;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className={NAV_BAR}>
        {isAdmin ? (
          <NavLink to="/schools" className={navLinkClassName}>
            學校管理
          </NavLink>
        ) : (
          <NavLink to="/" end className={navLinkClassName}>
            首頁
          </NavLink>
        )}
        {!isAdmin && !isTeacher && (
          <>
            <NavLink to="/wizard" className={navLinkClassName}>
              開始排課
            </NavLink>
            <NavLink to="/records" className={navLinkClassName}>
              排課紀錄
            </NavLink>
            <NavLink to="/data" className={navLinkClassName}>
              學校資料
            </NavLink>
          </>
        )}
        {/* Task 59: unlike the links above, 帳號管理 is shown only to a
            CONFIRMED manager (Task 98: 系統管理員 or 教學組長) -- an unknown
            role (null) does not see it. Kept after the scheduling links: an
            administrative page, not part of the scheduling flow. */}
        {canManageAccounts && (
          <NavLink to="/users" className={navLinkClassName}>
            帳號管理
          </NavLink>
        )}
        {/* Task 98: a 教學組長 opens timetables from 排課紀錄; a 一般老師
            goes straight to the published one. */}
        {isTeacher && (
          <NavLink to="/timetable" className={navLinkClassName}>
            課表
          </NavLink>
        )}
        <button type="button" onClick={handleLogout} className={`${BUTTON_SECONDARY_SM} ml-auto`}>
          登出
        </button>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
