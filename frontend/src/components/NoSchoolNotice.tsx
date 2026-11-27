import type { ReactElement } from "react";
import { Link } from "react-router-dom";
import { CARD, LINK_TEXT, PAGE } from "../styles/ui";

// 帳號改版: what an 一般老師 with no school (after 離校) sees instead of
// any page but 個人資料 -- there is no school's data to show them.
export default function NoSchoolNotice(): ReactElement {
  return (
    <div className={PAGE}>
      <div role="status" className={`${CARD} max-w-xl`}>
        <h1 className="mb-2 text-xl font-semibold text-gray-900">目前無所屬學校</h1>
        <p className="text-sm text-gray-700">
          你的帳號目前沒有所屬學校，因此無法查看課表。請聯絡系統管理員，將你分配到任教的學校。
        </p>
        <p className="mt-3 text-sm text-gray-700">
          仍可以到
          <Link to="/profile" className={LINK_TEXT}>
            個人資料
          </Link>
          修改密碼。
        </p>
      </div>
    </div>
  );
}
