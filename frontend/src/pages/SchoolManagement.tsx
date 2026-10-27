import type { ReactElement } from "react";
import PageHeader from "../components/PageHeader";
import { PAGE } from "../styles/ui";
import { SchoolsTab } from "./DataBrowser";

// Task 98: the 系統管理員's page for schools (moved out of 基礎資料, which
// is now a 教學組長's school data only). Accounts are bound to a school on
// 帳號管理.
export default function SchoolManagement(): ReactElement {
  return (
    <div className={PAGE}>
      <PageHeader
        title="學校管理"
        info={<p>建立學校後，到「帳號管理」建立該校的教學組長帳號；學校的教師、科目、教室與課表由教學組長維護。</p>}
      />
      <SchoolsTab isAdmin />
    </div>
  );
}
