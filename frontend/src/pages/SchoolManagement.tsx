import type { ReactElement } from "react";
import { HELP_TEXT, PAGE, PAGE_TITLE } from "../styles/ui";
import { SchoolsTab } from "./DataBrowser";

// Task 98: the 系統管理員's page for schools (moved out of 基礎資料, which
// is now a 教學組長's school data only). Accounts are bound to a school on
// 帳號管理.
export default function SchoolManagement(): ReactElement {
  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>學校管理</h1>
      <p className={HELP_TEXT}>
        建立學校後，到「帳號管理」建立該校的教學組長帳號；學校的教師、科目、教室與課表由教學組長維護。
      </p>
      <SchoolsTab isAdmin />
    </div>
  );
}
