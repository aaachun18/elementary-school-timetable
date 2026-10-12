import type { ReactElement } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import { getCurrentUserRole } from "../utils/auth";
import { BUTTON_SECONDARY_SM, NAV_BAR, NAV_LINK, NAV_LINK_ACTIVE } from "../styles/ui";

// Shared shell for every protected page (see App.tsx: this is combined
// with ProtectedRoute as one parent layout route, wrapping Home/DataBrowser
// as nested <Outlet /> children) -- so logout only needs to be written
// once, here, instead of duplicated per page.
export default function Layout(): ReactElement {
  const navigate = useNavigate();
  // Task 43: a confirmed TEACHER only gets the 課表檢視 link + 登出 -- every
  // other link (which also bounces back via AdminOnlyRoute, see App.tsx,
  // if typed directly) is left out of the nav entirely rather than shown
  // disabled. An unknown role (null) sees the full nav, same "only block a
  // CONFIRMED TEACHER" stance AdminOnlyRoute takes.
  const isRestrictedToTimetable = getCurrentUserRole() === "TEACHER";

  function handleLogout(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    navigate("/login");
  }

  // Task 48: NavLink (not plain Link) only to pick up its automatic
  // isActive -> styling -- purely presentational (which page is
  // highlighted), no change to where any link actually goes or what
  // AdminOnlyRoute/ProtectedRoute decide.
  function navLinkClassName({ isActive }: { isActive: boolean }): string {
    return isActive ? NAV_LINK_ACTIVE : NAV_LINK;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className={NAV_BAR}>
        {!isRestrictedToTimetable && (
          <>
            <NavLink to="/" className={navLinkClassName}>
              首頁
            </NavLink>
            <NavLink to="/data" className={navLinkClassName}>
              基礎資料
            </NavLink>
            <NavLink to="/requirements" className={navLinkClassName}>
              排課需求總覽
            </NavLink>
            <NavLink to="/scheduler" className={navLinkClassName}>
              排課控制台
            </NavLink>
          </>
        )}
        <NavLink to="/timetable" className={navLinkClassName}>
          課表檢視
        </NavLink>
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
