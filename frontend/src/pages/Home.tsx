import { type ReactElement } from "react";
import { useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";

// Temporary placeholder -- a future Task replaces this with the real
// Dashboard (see docs/FRONTEND_REQUIREMENTS.md 流程 A). It exists purely to
// prove the login/logout round trip works end to end.
export default function Home(): ReactElement {
  const navigate = useNavigate();

  function handleLogout(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    navigate("/login");
  }

  return (
    <div>
      <p>登入成功,歡迎回來。系統功能建置中,更多頁面即將上線。</p>
      <button type="button" onClick={handleLogout}>
        登出
      </button>
    </div>
  );
}
