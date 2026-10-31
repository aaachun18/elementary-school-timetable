import type { ReactElement, ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import timetableScreenshot from "../assets/landing-timetable.png";
import { CalendarPlusIcon, CheckIcon, ClipboardListIcon, PencilIcon } from "../components/icons";
import { SYSTEM_NAME } from "../constants/systemName";
import { getCurrentUserRole, homePathFor } from "../utils/auth";
import {
  ACTION_CARD_ICON,
  ACTION_CARD_TEXT,
  ACTION_CARD_TITLE,
  BODY_TEXT,
  BUTTON_PRIMARY,
  CARD,
  MUTED_TEXT,
} from "../styles/ui";

// The public home page (`/`), seen before logging in. Someone already
// logged in goes straight to their own landing page (homePathFor) -- the
// same synchronous token check ProtectedRoute does, so this page never
// flashes for them.

const FEATURES: readonly { icon: ReactNode; title: string; text: string }[] = [
  {
    icon: <CalendarPlusIcon />,
    title: "排課精靈",
    text: "6 個步驟依序設定學期、教師、年級節次、科目需求與共同排課。",
  },
  {
    icon: <CheckIcon />,
    title: "自動排課與衝突檢查",
    text: "一鍵產生符合所有硬性限制的課表，排不出來時說明原因。",
  },
  {
    icon: <PencilIcon />,
    title: "手動調整與即時重新檢查",
    text: "拖曳課程即可移動或對調，每次調整後自動重新檢查衝突。",
  },
  {
    icon: <ClipboardListIcon />,
    title: "排課紀錄與發布",
    text: "每次排課都留下紀錄，確認無誤後發布給全校老師查看。",
  },
];

export default function Landing(): ReactElement {
  if (sessionStorage.getItem(TOKEN_KEY)) {
    return <Navigate to={homePathFor(getCurrentUserRole())} replace />;
  }

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <header className="flex items-center justify-between gap-4 border-b border-gray-200 bg-surface px-4 py-3 md:px-8">
        <span className="text-lg font-semibold text-gray-900">{SYSTEM_NAME}</span>
        <Link to="/login" className={BUTTON_PRIMARY}>
          登入
        </Link>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-4 py-10 md:px-8 md:py-16">
        <section className="flex flex-col items-center gap-8 md:flex-row md:gap-12">
          <div className="flex flex-col items-start gap-4 md:w-5/12">
            <h1 className="text-3xl font-bold text-gray-900 md:text-4xl">節省排課時間與心力</h1>
            <p className={BODY_TEXT}>自動排課、衝突檢查、手動微調與排課紀錄管理，
              <br />幫助您完成整學期的課表。
            </p>
            <Link to="/login" className={`${BUTTON_PRIMARY} mt-2`}>
              登入系統
            </Link>
          </div>
          <img
            src={timetableScreenshot}
            alt="課表畫面截圖：依班級檢視一週課表"
            className="w-full rounded-lg border border-gray-200 shadow-sm md:w-7/12"
          />
        </section>

        <section aria-label="主要功能" className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature) => (
            <div key={feature.title} className={`${CARD} flex flex-col gap-3`}>
              <span className={ACTION_CARD_ICON} aria-hidden="true">
                {feature.icon}
              </span>
              <div>
                <h2 className={ACTION_CARD_TITLE}>{feature.title}</h2>
                <p className={ACTION_CARD_TEXT}>{feature.text}</p>
              </div>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-gray-200 bg-surface px-4 py-4 text-center">
        <p className={MUTED_TEXT}>
          {SYSTEM_NAME} · {new Date().getFullYear()} 年版
        </p>
      </footer>
    </div>
  );
}
