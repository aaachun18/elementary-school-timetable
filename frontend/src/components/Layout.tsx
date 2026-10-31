import type { ReactElement } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import { useConfirm } from "../hooks/useConfirm";
import { useIdleSession } from "../hooks/useIdleSession";
import { CANCEL_LABEL } from "../utils/confirmText";
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
  // - 教學組長: 首頁, 學校資料, 開始排課, 排課紀錄, 帳號管理. An unknown
  //   role (null) sees this nav too, same "only block a CONFIRMED role"
  //   stance RoleRoute takes.
  const role = getCurrentUserRole();
  const isAdmin = role === "ADMIN";
  const isTeacher = role === "TEACHER";
  const canManageAccounts = isCurrentUserManager();
  const { confirm, dialog: confirmDialog } = useConfirm();
  // Logged out only after IDLE_TIMEOUT_MINUTES without any activity -- never
  // in the middle of working (utils/session.ts).
  useIdleSession();

  // Asked first in the middle of the screen: 登出 or 取消.
  async function handleLogout(): Promise<void> {
    const confirmed = await confirm({
      title: "要登出嗎？",
      message: "登出後要重新輸入帳號密碼才能使用。",
      confirmLabel: "登出",
      cancelLabel: CANCEL_LABEL,
      tone: "primary",
    });
    if (!confirmed) {
      return;
    }
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
          <NavLink to="/home" end className={navLinkClassName}>
            首頁
          </NavLink>
        )}
        {!isAdmin && !isTeacher && (
          <>
            <NavLink to="/data" className={navLinkClassName}>
              學校資料
            </NavLink>
            <NavLink to="/wizard" className={navLinkClassName}>
              開始排課
            </NavLink>
            <NavLink to="/records" className={navLinkClassName}>
              排課紀錄
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
        <button type="button" onClick={() => void handleLogout()} className={`${BUTTON_SECONDARY_SM} ml-auto`}>
          登出
        </button>
      </nav>
      <main>
        <Outlet />
      </main>
      {confirmDialog}
    </div>
  );
}
