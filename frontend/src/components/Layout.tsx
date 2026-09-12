import type { ReactElement } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";

// Shared shell for every protected page (see App.tsx: this is combined
// with ProtectedRoute as one parent layout route, wrapping Home/DataBrowser
// as nested <Outlet /> children) -- so logout only needs to be written
// once, here, instead of duplicated per page.
export default function Layout(): ReactElement {
  const navigate = useNavigate();

  function handleLogout(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    navigate("/login");
  }

  return (
    <div>
      <nav>
        <Link to="/">首頁</Link>
        {" | "}
        <Link to="/data">基礎資料</Link>
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
