import { type ReactElement } from "react";
import { Link } from "react-router-dom";

// Temporary placeholder -- a future Task replaces this with the real
// Dashboard (see docs/FRONTEND_REQUIREMENTS.md 流程 A). Nav bar and logout
// are provided by the shared Layout (components/Layout.tsx) that wraps
// this page, not repeated here.
export default function Home(): ReactElement {
  return (
    <div>
      <p>登入成功,歡迎回來。系統功能建置中,更多頁面即將上線。</p>
      <p>
        <Link to="/data">查看基礎資料(老師/班級/科目/教室/時段)</Link>
      </p>
    </div>
  );
}
