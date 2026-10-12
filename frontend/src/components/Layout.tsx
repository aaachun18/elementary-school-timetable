import type { ReactElement } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import { getCurrentUserRole } from "../utils/auth";

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

  return (
    <div>
      <nav>
        {!isRestrictedToTimetable && (
          <>
            <Link to="/">首頁</Link>
            {" | "}
            <Link to="/data">基礎資料</Link>
            {" | "}
            <Link to="/requirements">排課需求總覽</Link>
            {" | "}
            <Link to="/scheduler">排課控制台</Link>
            {" | "}
          </>
        )}
        <Link to="/timetable">課表檢視</Link>
        {" | "}
        <button type="button" onClick={handleLogout}>
          登出
        </button>
      </nav>
      <hr />
      <Outlet />
    </div>
  );
}
