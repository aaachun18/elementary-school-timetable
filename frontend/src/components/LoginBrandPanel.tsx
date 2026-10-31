import type { ReactElement, ReactNode } from "react";
import { Link } from "react-router-dom";
import { CalendarPlusIcon, CheckIcon, PencilIcon } from "./icons";
import { SYSTEM_NAME } from "../constants/systemName";

// 登入頁's left half (768px and wider; Login hides it below): the system's
// name, one line, three points, and a small drawn timetable. The
// background -- the brand gradient, a faint timetable grid and a glow in
// the top-right corner -- is .login-brand-panel in index.css; the
// contrast of the text on it is checked in styles/tokens.test.ts.

const HIGHLIGHTS: readonly { icon: ReactNode; text: string }[] = [
  { icon: <CalendarPlusIcon />, text: "六步驟排課精靈，設定好就能自動排課" },
  { icon: <CheckIcon />, text: "自動檢查衝突，排不出來時說明原因" },
  { icon: <PencilIcon />, text: "手動拖曳微調，排課紀錄與發布一目了然" },
];

export default function LoginBrandPanel(): ReactElement {
  return (
    <aside className="login-brand-panel relative hidden flex-col justify-center px-10 py-16 text-on-accent md:flex md:w-3/7 lg:px-16">
      <div className="flex flex-col">
        <p className="text-[44px] leading-tight font-extrabold tracking-[0.02em]">{SYSTEM_NAME}</p>
        <span className="mt-4 h-1 w-12 rounded-full bg-on-accent/60" aria-hidden="true" />
        <p className="mt-6 text-xl text-on-accent/85">提高排課效率、節省您的時間。</p>
        <ul className="mt-10 flex flex-col gap-5">
          {HIGHLIGHTS.map((highlight) => (
            <li key={highlight.text} className="flex items-center gap-3 text-base font-medium">
              <span className="shrink-0" aria-hidden="true">
                {highlight.icon}
              </span>
              {highlight.text}
            </li>
          ))}
        </ul>
        <MiniTimetable />
      </div>
      <Link
        to="/"
        className="absolute bottom-8 left-10 text-sm font-medium underline-offset-2 hover:underline lg:left-16"
      >
        ← 返回首頁
      </Link>
    </aside>
  );
}

// The drawn timetable: 5 days × 4 periods of rounded cells, a few
// "scheduled" (brighter) and one with the amber frame the timetable uses
// for a lesson being moved. Decoration only.
const COLUMNS = 5;
const ROWS = 4;
const CELL_WIDTH = 64;
const CELL_HEIGHT = 40;
const GAP = 8;
const BRIGHT_CELLS: ReadonlySet<string> = new Set(["0-0", "2-0", "1-1", "4-1", "3-2", "0-3"]);
const MOVING_CELL = "2-2";

function MiniTimetable(): ReactElement {
  const width = COLUMNS * CELL_WIDTH + (COLUMNS - 1) * GAP;
  const height = ROWS * CELL_HEIGHT + (ROWS - 1) * GAP;
  const cells: ReactElement[] = [];
  for (let row = 0; row < ROWS; row += 1) {
    for (let column = 0; column < COLUMNS; column += 1) {
      const key = `${column}-${row}`;
      const isMoving = key === MOVING_CELL;
      cells.push(
        <rect
          key={key}
          x={column * (CELL_WIDTH + GAP)}
          y={row * (CELL_HEIGHT + GAP)}
          width={CELL_WIDTH}
          height={CELL_HEIGHT}
          rx={8}
          fill="#ffffff"
          fillOpacity={BRIGHT_CELLS.has(key) ? 0.35 : 0.16}
          stroke={isMoving ? "#fbbf24" : "none"}
          strokeWidth={isMoving ? 2.5 : 0}
        />,
      );
    }
  }
  return (
    <svg
      viewBox={`-4 -4 ${width + 8} ${height + 8}`}
      className="mt-12 w-[360px] max-w-full -rotate-2 drop-shadow-xl"
      aria-hidden="true"
      focusable="false"
    >
      {cells}
    </svg>
  );
}
