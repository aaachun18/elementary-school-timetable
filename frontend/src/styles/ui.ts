// Task 48: the shared design system every page/component pulls from,
// instead of each page inventing its own inline-style colors/spacing (the
// problem this Task exists to fix). Plain Tailwind utility strings, not a
// component library -- every call site still writes <button className=
// {BUTTON_PRIMARY}>, it just imports the class string from here instead
// of typing it out (and getting it slightly different) on every page.
//
// Palette: blue-600 is the one accent color (primary actions, focus
// rings, links); everything else is the gray scale (backgrounds, borders,
// body text) plus the three semantic colors (green = success, red =
// error/danger, gray = loading/muted) -- unchanged in MEANING from what
// every page already did with ad-hoc inline styles, just unified in
// actual values and expressed as Tailwind classes now.

// --- Typography ---
export const PAGE_TITLE = "text-2xl font-semibold text-gray-900 mb-4";
export const SECTION_TITLE = "text-lg font-semibold text-gray-900 mt-6 mb-2";
export const SUBSECTION_TITLE = "text-base font-semibold text-gray-800 mt-3 mb-1";
export const BODY_TEXT = "text-sm text-gray-700";
export const MUTED_TEXT = "text-sm text-gray-500";
export const HELP_TEXT = "text-sm text-gray-500 mb-3";
export const ERROR_TEXT = "text-sm text-red-600 mt-1";
export const SUCCESS_TEXT = "text-sm font-medium text-green-600";
// Task 98 Phase E: a finished flow's message (排課完成) -- the success
// badge colors on a framed panel.
export const SUCCESS_PANEL = "mt-3 rounded-md border border-green-200 bg-badge-success-bg px-4 py-3 text-badge-success-fg";
export const LOADING_TEXT = "text-sm text-gray-500";

// --- Layout ---
export const PAGE = "p-6 max-w-6xl mx-auto";
// Task 100: 學校資料 -- title, tabs, toolbar and table in one centered
// column of at most 880px (+ the page padding), the same for all five tabs,
// so switching tabs never moves the title or the tab row.
export const PAGE_DATA = "p-6 max-w-[58rem] mx-auto";
// Task 98 Phase C: a page's header (components/PageHeader.tsx) -- the
// title with its small tags (學期 · 紀錄 #N, a status badge) and (i) on the
// left, the page's actions on the right; one row, wrapping when narrow.
export const PAGE_HEADER = "mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2";
export const PAGE_HEADER_MAIN = "flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1";
export const PAGE_HEADER_TITLE = "text-2xl font-semibold text-gray-900";
export const PAGE_HEADER_ACTIONS = "flex flex-wrap items-center gap-2";
// A small tag next to a title (「115 學年度第 1 學期 · 紀錄 #1」).
export const META_TAG = "text-sm text-text-muted";
// A card's one title row (components/CardHeader.tsx): the title and its (i).
export const CARD_HEADER = "mb-3 flex flex-wrap items-center gap-2";
export const CARD_TITLE = "text-base font-semibold text-gray-900";
// The one line of a rule that changes the result or avoids a mistake,
// kept visible when the rest of the explanation moved into an (i).
export const RULE_NOTE = "mb-3 text-xs text-text-muted";
// The wizard's step buttons (components/ActionBar.tsx): one row under the
// card, just the buttons (Task 99: no bar, no line, no shadow, not sticky);
// secondary actions left, the primary one right.
export const ACTION_BAR = "mt-4 flex flex-wrap items-center justify-between gap-2";
export const ACTION_BAR_GROUP = "flex flex-wrap items-center gap-2";
export const SECTION = "mb-6";
export const CARD = "rounded-lg border border-gray-200 bg-white p-4 shadow-sm";

// --- Buttons (Task 98, decision 34) ---
// Six variants, colors from the @theme tokens in index.css:
//   Primary   -- the ONE most important action of a screen (下一步, 自動排課,
//                儲存課表). Never two on one screen.
//   Secondary -- everything else (上一步, 取消, 複製, 手動編輯課表...).
//   Success   -- only the last step of a flow (發布此課表).
//   Danger    -- solid red, only on a confirmation dialog's confirm button;
//                lists never show a red button.
//   Ghost     -- no frame, primary text: a setting entry that carries its
//                own content (「設定可排節次」), back links, show-more toggles.
//   Icon      -- 32×32 with a 20px icon; always aria-label + title.
// Every button is at least 32px tall (min-h-8) -- a table row's (ROW)
// 28px -- and gets the global focus-visible ring (index.css). Disabled is
// never just faded: the reason sits next to it (DisabledReason) or in its
// title.
const BUTTON_BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-md font-medium disabled:cursor-not-allowed disabled:opacity-50";
const BUTTON_SIZE = "min-h-8 px-3 py-1.5 text-sm";
// Small size (in-row actions inside a card, 登出, 重試...).
const BUTTON_SIZE_SM = "min-h-8 px-2.5 py-1 text-xs";
// Task 99: the table-row size -- only a table row's actions (帳號管理's
// 重設密碼 / 編輯 / 停用, 學校資料's 編輯 / 確認 / 取消, 換教師's 預覽): 28px
// tall (still the whole click area), 10px side padding, 13px text, 6px
// corners (rounded-md); ROW_ACTIONS / ROW_ACTIONS_END keep 8px between.
const BUTTON_SIZE_ROW = "min-h-7 px-2.5 py-0.5 text-[13px] leading-5";

const PRIMARY_COLORS = "bg-primary text-on-accent shadow-sm hover:bg-primary-hover";
const SECONDARY_COLORS = "bg-secondary text-on-secondary hover:bg-secondary-hover";
const SUCCESS_COLORS = "bg-success text-on-accent shadow-sm hover:bg-success-hover";
const DANGER_COLORS = "bg-danger text-on-accent shadow-sm hover:bg-danger-hover";
const GHOST_COLORS = "text-primary hover:bg-primary-soft hover:text-primary-hover";

export const BUTTON_PRIMARY = `${BUTTON_BASE} ${BUTTON_SIZE} ${PRIMARY_COLORS}`;
export const BUTTON_SECONDARY = `${BUTTON_BASE} ${BUTTON_SIZE} ${SECONDARY_COLORS}`;
export const BUTTON_SUCCESS = `${BUTTON_BASE} ${BUTTON_SIZE} ${SUCCESS_COLORS}`;
export const BUTTON_DANGER = `${BUTTON_BASE} ${BUTTON_SIZE} ${DANGER_COLORS}`;
export const BUTTON_GHOST = `${BUTTON_BASE} min-h-8 px-2 py-1.5 text-sm ${GHOST_COLORS}`;

export const BUTTON_PRIMARY_SM = `${BUTTON_BASE} ${BUTTON_SIZE_SM} ${PRIMARY_COLORS}`;
export const BUTTON_SECONDARY_SM = `${BUTTON_BASE} ${BUTTON_SIZE_SM} ${SECONDARY_COLORS}`;
export const BUTTON_PRIMARY_ROW = `${BUTTON_BASE} ${BUTTON_SIZE_ROW} ${PRIMARY_COLORS}`;
export const BUTTON_SECONDARY_ROW = `${BUTTON_BASE} ${BUTTON_SIZE_ROW} ${SECONDARY_COLORS}`;
export const BUTTON_GHOST_SM = `${BUTTON_BASE} min-h-8 px-2 py-1 text-xs ${GHOST_COLORS}`;

// Neutral gray icon, darker with a light gray square on hover.
const ICON_BUTTON_BASE =
  "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-icon disabled:cursor-not-allowed disabled:opacity-50";
export const ICON_BUTTON = `${ICON_BUTTON_BASE} hover:bg-secondary hover:text-icon-hover`;
// Task 98 Phase B: a row's trash button -- always shown, neutral gray, red
// only under the pointer (a list never shows a red button at rest). A
// disabled one stays gray.
export const ICON_BUTTON_DELETE = `${ICON_BUTTON_BASE} hover:bg-danger-soft hover:text-danger-hover disabled:hover:bg-transparent disabled:hover:text-icon`;

// InfoPopover's panel (components/InfoPopover.tsx); its position, width
// (at most 360px) and max height are set inline from the (i) button.
export const INFO_POPOVER_PANEL =
  "fixed z-50 overflow-y-auto rounded-md border border-gray-200 bg-surface p-3 text-left text-sm font-normal text-gray-700 shadow-lg";

// The one line under (or next to) a disabled button saying why.
export const DISABLED_REASON = "text-xs text-text-muted";

// A row of buttons (e.g. 編輯 / 刪除 in a table cell): never touching each
// other -- every group of buttons sits in this or another gap-* container.
export const ROW_ACTIONS = "flex flex-wrap items-center gap-2";
// Task 98 Phase B: a table's 操作 column -- as narrow as its buttons, at the
// right edge; the buttons stay on one line.
export const TH_ACTIONS = "border-b border-gray-200 px-3 py-2 text-right font-semibold text-gray-700 whitespace-nowrap w-px";
export const TD_ACTIONS = "border-b border-gray-100 px-3 py-2 text-gray-700 w-px";
export const ROW_ACTIONS_END = "flex items-center justify-end gap-2 whitespace-nowrap";
// Task 99 / Task 100: 排課紀錄's 操作 -- the last column, as narrow as its
// buttons. Three fixed slots [檢視課表 72px][檢視排課設定 96px][trash 32px],
// so a row without a timetable keeps an empty first slot instead of
// shifting the others: every link (and the trash at the right edge) has the
// same x on every row. The header's 「操作」 starts where the first link's
// text does (12px cell padding + the Ghost link's 8px).
export const TH_ACTIONS_START = "border-b border-gray-200 py-2 pl-5 pr-3 text-left font-semibold text-gray-700 whitespace-nowrap";
export const RECORD_ACTIONS = "grid grid-cols-[4.5rem_6rem_2rem] items-center gap-2 whitespace-nowrap";
// A slot's link sits at the slot's left edge.
export const RECORD_ACTION_SLOT = "justify-self-start";
// Task 101: 排課紀錄 is a fixed-layout table with set shares (RECORD_COLS):
// 編號 6% | 學期 19% | 狀態 13% | 建立時間 16% | 備註 the rest | 操作 240px (the
// three slots + gaps + padding). At least 960px wide: in a narrower window
// the wrapper (TABLE_WRAPPER) scrolls sideways instead of wrapping cells;
// 學期 / 狀態 / 建立時間 never wrap (TD_NOWRAP), and 備註 keeps >= ~190px.
export const RECORD_TABLE = "w-full min-w-[60rem] table-fixed border-collapse text-sm";
export const RECORD_COLS = {
  number: "w-[6%]",
  semester: "w-[19%]",
  status: "w-[13%]",
  createdAt: "w-[16%]",
  note: "",
  // 216px of slots + the cell's 24px padding: the trash ends at the
  // cell's right padding on every row.
  actions: "w-60",
} as const;
export const TH_NOTE = "border-b border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap";
// Task 99: 排課紀錄's 備註 cell -- the inline field's text (px-2 + its 1px
// border) starts where the header's text does (px-3).
export const TD_NOTE = "border-b border-gray-100 py-2 pl-[3px] pr-3 text-gray-700";
// A row's error line inside that narrow column: wide enough to read.
export const ROW_ERROR_TEXT = "mt-1 min-w-56 text-left text-sm text-red-600";
// Task 101: the same line in a fixed-layout table's 操作 column (DATA_TABLE),
// whose width is set: it wraps inside the column, aligned with the buttons.
export const ROW_ERROR_TEXT_FIXED = "mt-1 text-right text-sm text-red-600";

// --- Form controls ---
// The focus ring comes from index.css (2px primary); the border turns
// primary too.
export const INPUT =
  "rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-900 focus:border-primary disabled:bg-gray-100 disabled:text-gray-500";
export const SELECT = INPUT;
// A picking dropdown whose saved value is 停用 (components/ChoiceSelect.tsx):
// amber frame and text, 「請重新選擇」, and a hint line below.
export const SELECT_RESELECT =
  "rounded-md border border-amber-500 px-2 py-1 text-sm font-medium text-amber-800 focus:border-primary disabled:bg-gray-100 disabled:text-gray-500";
export const CHOICE_HINT = "mt-1 text-xs text-amber-800";
// Task 98 Phase D: a field typed right in a table row (排課紀錄's 備註):
// no frame at rest, the frame shows on hover and focus.
export const INPUT_INLINE =
  "rounded-md border border-transparent bg-transparent px-2 py-1 text-sm text-gray-900 placeholder:text-gray-400 hover:border-gray-300 focus:border-primary focus:bg-surface disabled:text-gray-500";
// Fields stacked in one column are equally wide: in a table cell or a
// dialog's form a field fills its column (`w-full`); the pickers a page
// stacks above its content (年級, 版本, 班級 / 教師 / 教室 ...) share this width.
export const FIELD_PAGE = "w-64 max-w-full";
export const CHECKBOX = "h-4 w-4 rounded border-gray-300 accent-primary";
export const LABEL = "text-sm font-medium text-gray-700";

// --- Task 98 Phase E: 教師設定 ---
// The top toolbar (全選 + how many are in) and one card per teacher: an
// unchecked teacher is quieter (gray, no inputs), a checked one framed.
export const TOOLBAR = "mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md bg-page px-3 py-2";
export const TEACHER_GRID = "grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3";
export const TEACHER_CARD = "rounded-md border border-gray-200 bg-page px-3 py-2 text-gray-500";
export const TEACHER_CARD_CHECKED = "rounded-md border border-gray-300 bg-surface px-3 py-2 text-gray-900 shadow-sm";

// --- Task 98 Phase E: 年級與可排節次 ---
// One row per grade, the columns lined up: 年級 | badge | 預設 (muted) | the
// Ghost 「設定可排節次」 at the right.
export const GRADE_ROW =
  "grid grid-cols-[5rem_minmax(9rem,auto)_1fr_auto] items-center gap-3 border-b border-gray-100 py-2 text-sm last:border-b-0";

// --- Task 98 Phase E: 科目需求 column widths ---
// 連堂 160-180px, 指定老師 at least 120px, 特殊教室 at least 140px, 固定時段
// as narrow as its button -- so no dropdown's text is cut off.
export const REQ_COL_PATTERN = "w-44 min-w-40";
export const REQ_COL_TEACHER = "min-w-32";
export const REQ_COL_ROOM = "min-w-36";
export const REQ_COL_FIXED = "w-px";

// 排課前檢查's problems (wizard step 6): a light red frame above the
// outcome; 自動排課 stays disabled while it shows.
export const PREFLIGHT_PANEL = "mt-3 rounded-md border border-red-200 bg-red-50 px-4 py-3";

// --- Task 98 Phase E: 共同排課's pickers (1 選年級 → 2 選班級 → 3 選科目) ---
export const PICK_STEP_LABEL = "mb-1 text-xs font-semibold text-gray-600";
const PICK_BUTTON_BASE = "inline-flex min-h-8 items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium";
export const PICK_BUTTON = `${PICK_BUTTON_BASE} border border-gray-200 bg-surface text-gray-700 hover:bg-secondary`;
// Selected: tinted background, primary frame and a check mark.
export const PICK_BUTTON_SELECTED = `${PICK_BUTTON_BASE} border border-primary bg-primary-soft text-primary`;

// --- Tables ---
export const TABLE_WRAPPER = "overflow-x-auto rounded-lg border border-gray-200";
// Task 101 (replaces Task 99's as-wide-as-content tables): 學校資料's lists
// (班級 / 科目 / 科目需求 / 教室) fill the page's centered 880px column
// (PAGE_DATA) with a fixed layout: every column gets a set share through a
// <col> (the *_COLS below), so the columns read evenly instead of bunching
// up at the left. Header and cells align alike; 操作 is at the right.
export const DATA_TABLE_WRAPPER = "w-full overflow-x-auto rounded-lg border border-gray-200";
export const DATA_TABLE = "w-full table-fixed border-collapse text-sm";
export const TH_DATA = "border-b border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap";
// 操作's header in such a table: right-aligned, its width from the <col>.
export const TH_DATA_ACTIONS = "border-b border-gray-200 px-3 py-2 text-right font-semibold text-gray-700 whitespace-nowrap";
export const TD_DATA_ACTIONS = "border-b border-gray-100 px-3 py-2 text-gray-700";
// Column shares, in column order (the last one is 操作, only for whoever
// may edit; without it the browser scales the others up).
// 班級: 年級 | 名稱類型 | 班級名稱 | 狀態 | 操作 (停用/啟用 + trash, or the new
// row's 確認 / 取消).
export const CLASS_COLS = ["w-[18%]", "w-[20%]", "w-[26%]", "w-[14%]", "w-[22%]"] as const;
export const SUBJECT_COLS = ["w-[55%]", "w-[25%]", "w-[20%]"] as const;
export const GRADE_REQUIREMENT_COLS = ["w-[45%]", "w-[40%]", "w-[15%]"] as const;
export const ROOM_COLS = ["w-[28%]", "w-[34%]", "w-[20%]", "w-[18%]"] as const;
// 科目需求's 每週節數 dropdown (~140px).
export const WEEKLY_PERIODS_SELECT_WIDTH = "w-35";
// Task 101: 學校資料's 時段 -- the same full width, the five days equally
// wide (fixed layout), every cell centered (TH_CENTER / TD_CENTER).
export const TIME_SLOT_TABLE = "w-full table-fixed border-collapse text-sm";
export const TABLE = "w-full border-collapse text-sm";
export const TABLE_HEAD_ROW = "bg-gray-50";
export const TH = "border-b border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap";
export const TD = "border-b border-gray-100 px-3 py-2 text-gray-700";
export const TR_HOVER = "hover:bg-gray-50";
// Task 99: a timetable-shaped table (學校資料's 時段): every header and
// cell centered. Full constants, so text-left / text-center never compete.
export const TH_CENTER = "border-b border-gray-200 px-3 py-2 text-center font-semibold text-gray-700 whitespace-nowrap";
export const TD_CENTER = "border-b border-gray-100 px-3 py-2 text-center text-gray-700";
// Task 73: a cell of a locked (read-only) row -- TD with lighter text. A
// separate constant, not TD + "text-gray-400", so the two text colors never
// compete.
export const TD_LOCKED = "border-b border-gray-100 px-3 py-2 text-gray-400";
// Task 92A: short values (names, numbers, a semester) that must not wrap
// -- the table wrapper scrolls sideways instead of squeezing them.
export const TD_NOWRAP = `${TD} whitespace-nowrap`;
export const TD_LOCKED_NOWRAP = `${TD_LOCKED} whitespace-nowrap`;
// Task 102: an editable field's text in 學校資料's lists -- a click starts
// editing the row in place (no pencil). Always drawn in a light dashed box,
// so it reads as "可以編輯" at a glance; hover / focus fills it with the
// primary tint. Disabled (busy) keeps the box but drops the hover.
export const INLINE_EDIT_TEXT =
  "-mx-1.5 max-w-full cursor-text truncate rounded border border-dashed border-gray-300 bg-white px-1.5 py-0.5 text-left hover:border-primary hover:bg-primary-soft focus-visible:border-primary focus-visible:bg-primary-soft disabled:cursor-default disabled:hover:border-gray-300 disabled:hover:bg-white";

// --- Nav ---
export const NAV_BAR =
  "flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-gray-200 bg-white px-6 py-3";
export const NAV_LINK = "inline-flex min-h-8 items-center text-sm font-medium text-gray-600 hover:text-primary";
export const NAV_LINK_ACTIVE = "inline-flex min-h-8 items-center text-sm font-medium text-primary";

// --- Tabs (DataBrowser's own secondary nav, and the class / grade lists
// that switch what a page shows) ---
export const TAB_BUTTON =
  "inline-flex min-h-8 items-center rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-secondary hover:text-on-secondary";
export const TAB_BUTTON_ACTIVE =
  "inline-flex min-h-8 items-center rounded-md bg-primary-soft px-3 py-1.5 text-sm font-medium text-primary";

// --- Stepper (components/Stepper.tsx, Task 98 Phase C) ---
// One row at most 48px high: a 24px numbered circle + the label, joined by
// lines. Done = check mark, current = solid primary, not yet = gray. Below
// 900px only the current step keeps its label.
export const STEPPER = "mb-4 flex min-h-12 items-center gap-2 overflow-hidden";
export const STEPPER_ITEM = "flex min-w-0 flex-1 items-center gap-2 last:flex-none";
export const STEPPER_BUTTON =
  "inline-flex min-h-8 shrink-0 cursor-pointer items-center gap-2 rounded-md px-1 text-sm hover:bg-secondary";
// Task 102: a step that isn't a button -- the current or a read-only one,
// and (grayer, not-allowed cursor) a later one still locked.
export const STEPPER_ITEM_STATIC = "inline-flex min-h-8 shrink-0 items-center gap-2 rounded-md px-1 text-sm";
export const STEPPER_ITEM_LOCKED =
  "inline-flex min-h-8 shrink-0 cursor-not-allowed items-center gap-2 rounded-md px-1 text-sm opacity-60";
const STEP_CIRCLE_BASE = "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold";
export const STEP_CIRCLE_DONE = `${STEP_CIRCLE_BASE} bg-primary-soft text-primary`;
export const STEP_CIRCLE_CURRENT = `${STEP_CIRCLE_BASE} bg-primary text-on-accent`;
export const STEP_CIRCLE_TODO = `${STEP_CIRCLE_BASE} bg-gray-200 text-gray-600`;
export const STEP_LABEL_CURRENT = "font-semibold text-gray-900";
export const STEP_LABEL_OTHER = "hidden text-gray-600 min-[900px]:inline";
export const STEP_LINE = "h-px min-w-3 flex-1 bg-gray-300";

// --- Badges / status pills ---
// Task 73: marks a row that can't be edited or deleted (shown with an
// explanation line next to it, not only as a tooltip).
export const LOCK_BADGE =
  "inline-flex items-center gap-1 rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700";
// A 導師's class next to the teacher (教師設定), and the 導師's name on the
// timetable (導師 tag below a class's grid, and on every lesson they teach
// that class).
export const HOMEROOM_TAG =
  "inline-flex items-center rounded-full bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700";
// Task 98: StatusBadge's tones (components/StatusBadge.tsx), light
// background + dark text from the badge tokens. 排課紀錄: 自動排課 = info,
// 手動排課 = manual, 尚未排課 = warning, 已發布 = success, anything else
// neutral. The same tones serve the other status pills (啟用 / 停用,
// 已固定, the 警告 tag in the conflict list).
const BADGE_BASE = "inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium";
export const BADGE_INFO = `${BADGE_BASE} bg-badge-info-bg text-badge-info-fg`;
export const BADGE_MANUAL = `${BADGE_BASE} bg-badge-manual-bg text-badge-manual-fg`;
export const BADGE_WARNING = `${BADGE_BASE} bg-badge-warning-bg text-badge-warning-fg`;
export const BADGE_SUCCESS = `${BADGE_BASE} bg-badge-success-bg text-badge-success-fg`;
export const BADGE_NEUTRAL = `${BADGE_BASE} bg-badge-neutral-bg text-badge-neutral-fg`;
// Task 99: 「N 個錯誤」 on the home page -- the existing danger tokens (light
// red background, dark red text; the pair the trash button's hover uses).
export const BADGE_DANGER = `${BADGE_BASE} bg-danger-soft text-danger-hover`;

// Task 100: the timetable's check result (components/CheckStatusTag.tsx),
// right under the title row in the view and the edit mode alike: 32px
// pills, 14px bold text with an icon, the badge tokens (all >= 4.5:1,
// tokens.test.ts). The tags sit in one button that opens / closes the list.
export const CHECK_TAG_ROW = "mb-3 flex flex-wrap items-center gap-2";
export const CHECK_TAG_BUTTON = "inline-flex flex-wrap items-center gap-2 rounded-full";
const CHECK_TAG_BASE = "inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-sm font-semibold";
export const CHECK_TAG_SUCCESS = `${CHECK_TAG_BASE} bg-badge-success-bg text-badge-success-fg`;
export const CHECK_TAG_DANGER = `${CHECK_TAG_BASE} bg-danger-soft text-danger-hover`;
export const CHECK_TAG_WARNING = `${CHECK_TAG_BASE} bg-badge-warning-bg text-badge-warning-fg`;
export const CHECK_TAG_NEUTRAL = `${CHECK_TAG_BASE} bg-badge-neutral-bg text-badge-neutral-fg`;
export const CHECK_TAG_CHEVRON = "text-sm text-text-muted";
// The check request failed: the message, next to a 重試 button.
export const CHECK_FAILED_TEXT = "text-sm text-red-600";

// --- Notices ---
// Task 67: a short, non-error heads-up shown above content (e.g. "this is
// an archived version, read only").
export const NOTICE = "rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800";

// --- Dialogs ---
// Task 67: native <dialog> opened with showModal(). m-auto restores the
// browser's own centering, which Tailwind's preflight margin reset removes.
export const DIALOG =
  "m-auto w-full max-w-lg rounded-lg border border-gray-200 bg-white p-0 shadow-xl backdrop:bg-black/40";
export const DIALOG_TITLE = "text-lg font-semibold text-gray-900";

// --- Timetable ---
// Task 68: the cell 「在課表中查看」 points at -- an amber inset ring plus a
// light fill: clearly visible, but not the red used for errors.
export const TD_HIGHLIGHT = "bg-amber-50 ring-2 ring-inset ring-amber-400";
// Task 84 / Task 85: candidate marks while a lesson is selected or dragged
// in edit mode -- at most one soft fill per cell plus one small icon in its
// top-right corner. Low-saturation fills, so they read apart from the
// amber locate ring (TD_HIGHLIGHT), the drag-hover outline (DROP_TARGET_OK / DROP_TARGET_BLOCKED) and the
// dark gray non-teaching fill; a cell carrying one of those markers shows
// the marker instead of the fill (its icon stays). Never colour alone: a
// conflict also gets fine diagonal stripes, and the icons differ (✓ / ✕);
// the full description is the icon's title / aria-label.
export const TD_CANDIDATE_SAFE = "bg-emerald-50";
export const TD_CANDIDATE_CONFLICT =
  "bg-rose-50 bg-[repeating-linear-gradient(135deg,rgb(225_29_72/0.12)_0_2px,transparent_2px_8px)]";
const CANDIDATE_ICON_BASE =
  "pointer-events-auto absolute right-1 top-1 inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px] leading-none font-bold text-white";
export const CANDIDATE_ICON_SAFE = `${CANDIDATE_ICON_BASE} bg-emerald-600`;
export const CANDIDATE_ICON_CONFLICT = `${CANDIDATE_ICON_BASE} bg-rose-600`;
// A lesson the selected / dragged one can swap with without adding a
// problem: light blue (cell and lesson alike), icon ⇄.
export const TD_CANDIDATE_SWAP = "bg-sky-100";
export const CANDIDATE_ICON_SWAP = `${CANDIDATE_ICON_BASE} bg-sky-600`;
// Task 90: a target the lesson block (連堂) rules refuse -- gray with a
// "no entry" icon; nothing is sent when dropping there.
export const TD_CANDIDATE_BLOCKED =
  "bg-gray-100 bg-[repeating-linear-gradient(45deg,rgb(107_114_128/0.12)_0_2px,transparent_2px_8px)]";
export const CANDIDATE_ICON_BLOCKED = `${CANDIDATE_ICON_BASE} bg-gray-500`;
// The legend above the grid: 可放 / 衝突 / 可對調, a small swatch with one
// word each.
export const CANDIDATE_LEGEND = "mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600";
const CANDIDATE_SWATCH_BASE = "inline-block h-3 w-3 rounded-sm border";
export const CANDIDATE_LEGEND_SAFE_SWATCH = `${CANDIDATE_SWATCH_BASE} border-emerald-300 ${TD_CANDIDATE_SAFE}`;
export const CANDIDATE_LEGEND_CONFLICT_SWATCH = `${CANDIDATE_SWATCH_BASE} border-rose-300 ${TD_CANDIDATE_CONFLICT}`;
export const CANDIDATE_LEGEND_SWAP_SWATCH = `${CANDIDATE_SWATCH_BASE} border-sky-300 ${TD_CANDIDATE_SWAP}`;

// --- Task 90: lesson blocks (連堂) on the timetable ---
// A thin bar along the left edge of each cell of a block; two adjacent
// lessons of one block share it across the cell border (no text label).
// Low-key indigo, read-only and edit mode alike. The ends of a block are
// rounded and inset, so two different blocks one above the other don't
// look joined.
export const BLOCK_BAR_BASE = "pointer-events-none absolute left-0 w-1 bg-indigo-300";
export const BLOCK_BAR_TOP_JOINED = "top-0";
export const BLOCK_BAR_TOP_END = "top-1.5 rounded-t-full";
export const BLOCK_BAR_BOTTOM_JOINED = "-bottom-px";
export const BLOCK_BAR_BOTTOM_END = "bottom-1.5 rounded-b-full";
// A cell where the dragged block would land (every lesson of it, not only
// the one under the pointer): the same green as DROP_TARGET_OK, dashed.
export const DROP_TARGET_RANGE = "bg-green-50 outline-2 -outline-offset-2 outline-dashed outline-green-500";
// The cell under the pointer when the target is refused by the block rules.
// Task 103: laid over the bottom of the cell (absolute; the cell is
// relative) instead of taking room in it -- so showing it never makes the
// row taller and moves what is under the pointer.
export const DROP_ZONE_BLOCKED =
  "pointer-events-none absolute inset-x-1 bottom-1 z-10 rounded-md border border-dashed border-gray-400 bg-white/90 px-2 py-1 text-center text-xs text-gray-600";

// Task 78: the row header (節次) column. Full constants rather than TH plus
// extra classes, so two background/text colors never compete.
// The weekly grid: fixed layout so Monday-Friday are always equally wide,
// each at least 11rem -- wide enough for 「本土語文／臺灣手語」 on one line in
// a lesson button -- after a 5rem 節次 column.
export const TIMETABLE_TABLE = "w-full min-w-[60rem] table-fixed border-collapse text-sm";
export const TIMETABLE_PERIOD_COLUMN = "w-20";
// Task 99: every header and cell of the timetable is centered.
export const TIMETABLE_ROW_HEADER =
  "border-b border-gray-200 bg-white px-3 py-2 text-center font-medium text-gray-600 whitespace-nowrap";
// Non-teaching rows (早自習/午休/放學): a clearly darker gray than the
// row hover (gray-50) and the table head (gray-50), so they read as "not a
// lesson slot" at a glance. The cell's own background covers the row hover.
export const TIMETABLE_ROW_HEADER_NON_TEACHING =
  "border-b border-gray-300 bg-gray-200 px-3 py-2 text-center font-medium text-gray-600 whitespace-nowrap";
// A non-teaching cell without background, for combining with one marker
// (TD_HIGHLIGHT / DROP_TARGET_BLOCKED), which brings its own.
export const TD_NON_TEACHING_BASE = "border-b border-gray-300 px-3 py-2 text-center text-gray-600";
export const TD_NON_TEACHING = `${TD_NON_TEACHING_BASE} bg-gray-200`;

// --- Timetable edit mode (Task 69) ---
// A lesson in edit mode is a full-width button; the selected one gets a
// thick blue border AND a 「已選取」 text marker (never color alone). All
// variants share one base so border/background never come from two
// competing classes.
const LESSON_BUTTON_BASE =
  "flex w-full flex-col items-center rounded-md px-2 py-1 text-center text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60";
export const LESSON_BUTTON = `${LESSON_BUTTON_BASE} border border-gray-300 bg-white hover:border-blue-400 hover:bg-blue-50`;
export const LESSON_BUTTON_SELECTED = `${LESSON_BUTTON_BASE} border-2 border-blue-600 bg-blue-50`;
// Task 71: drag & drop. The lesson being dragged is faded with a dashed
// border; a lesson under the pointer that it can swap with gets a thick
// green border. (A lesson it can't swap with is always in the dragged
// lesson's own time slot, so the whole cell shows DROP_TARGET_BLOCKED.)
export const LESSON_BUTTON_DRAGGING = `${LESSON_BUTTON_BASE} border border-dashed border-gray-400 bg-gray-100 opacity-50`;
export const LESSON_BUTTON_DROP_OK = `${LESSON_BUTTON_BASE} border-2 border-green-600 bg-green-50`;
// A lesson the selected / dragged one can swap with safely (TD_CANDIDATE_SWAP).
export const LESSON_BUTTON_SWAP_OK = `${LESSON_BUTTON_BASE} border border-sky-300 bg-sky-100 hover:border-blue-400`;
// Task 71: a cell under the pointer while dragging -- solid green ring =
// can move here; dashed red outline = can't (non-teaching period, or the
// dragged lesson's own time slot). Ring vs. dashed outline, not color alone.
export const DROP_TARGET_OK = "bg-green-50 ring-2 ring-inset ring-green-500";
export const DROP_TARGET_BLOCKED = "bg-red-50 outline-2 -outline-offset-2 outline-dashed outline-red-400";
// Task 71: the bottom of a cell a dragged lesson can move to, so "the empty
// part of a cell" is always there to drop on even when the cell's lessons
// fill it. Task 85: shown only while the drag is over that cell, and
// pointer-events-none (so is DROP_STRIP): appearing under the pointer must
// not change which element the drop lands on -- the cell itself handles it.
export const DROP_ZONE =
  "pointer-events-none absolute inset-x-1 bottom-1 z-10 rounded-md border border-dashed border-green-500 bg-green-50/95 px-2 py-1 text-center text-xs text-green-700";
// Task 85: in a cell that has lessons, the drop area under them is a thin
// dashed strip while dragging; it expands to DROP_ZONE (with 「移到這裡」)
// only while the drag is over that cell.
export const DROP_STRIP = "pointer-events-none h-1.5 rounded-sm border border-dashed border-blue-300";
// Task 103: the same room, empty, whenever no strip is shown -- every cell
// with lessons keeps it in edit mode, so starting a drag (or selecting a
// lesson, whose 「移到這裡」 strip takes the same room) never makes the rows
// taller and moves the timetable under the pointer.
export const DROP_STRIP_SPACE = "pointer-events-none h-1.5";
// Task 85: the click flow's move target. In an EMPTY cell the whole cell
// is one button (text only on hover / keyboard focus) ...
export const CELL_MOVE_TARGET =
  "flex min-h-12 w-full items-center justify-center rounded-md text-xs font-medium text-transparent hover:bg-blue-50 hover:text-blue-700 focus:outline-none focus-visible:bg-blue-50 focus-visible:text-blue-700 focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed";
// ... and under a cell's lessons it is a thin dashed strip that expands to
// show 「移到這裡」 on hover / focus.
export const MOVE_TARGET_STRIP =
  "h-1.5 w-full overflow-hidden rounded-sm border border-dashed border-blue-300 text-[0px] text-blue-700 hover:h-auto hover:bg-blue-50 hover:py-1 hover:text-xs focus:outline-none focus-visible:h-auto focus-visible:bg-blue-50 focus-visible:py-1 focus-visible:text-xs focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed";
// The 「已選取：…」 status bar above the grid.
export const SELECTION_BAR =
  "flex flex-wrap items-center gap-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900";

// --- Task 92A: preview dialogs (move/swap/換教師) ---
// A little wider than DIALOG so a typical problem line fits on one line.
export const DIALOG_WIDE =
  "m-auto w-full max-w-xl rounded-lg border border-gray-200 bg-white p-0 shadow-xl backdrop:bg-black/40";
// 「這次會做什麼」.
export const PREVIEW_ACTION_LINE = "text-base font-medium text-gray-900";
// The verdict: green when nothing new is wrong, red otherwise.
export const PREVIEW_VERDICT_OK = "text-sm font-semibold text-green-700";
export const PREVIEW_VERDICT_PROBLEM = "text-sm font-semibold text-red-700";
export const PREVIEW_LIST = "m-0 flex list-none flex-col gap-1 p-0";
export const PREVIEW_LINE = "flex items-baseline gap-2 text-sm text-gray-800";
export const PREVIEW_LINE_LIGHT = "flex items-baseline gap-2 text-sm text-gray-500";
// The small category tag in front of each problem line.
export const PREVIEW_TAG_BASE = "shrink-0 rounded px-1.5 py-0.5 text-xs font-medium";
export const PREVIEW_TAG_ERROR = `${PREVIEW_TAG_BASE} bg-red-50 text-red-700`;
export const PREVIEW_TAG_WARNING = `${PREVIEW_TAG_BASE} bg-amber-50 text-amber-800`;
export const PREVIEW_TAG_UNRESOLVED = `${PREVIEW_TAG_BASE} bg-gray-100 text-gray-600`;
export const PREVIEW_TAG_RESOLVED = `${PREVIEW_TAG_BASE} bg-green-50 text-green-700`;
// The one small footnote line, and 「另有 N 項既有問題…」.
export const PREVIEW_NOTE = "text-xs text-gray-500";
// 「另外 N 項」/「影響範圍」 toggles.
export const PREVIEW_TOGGLE = `${BUTTON_GHOST_SM} self-start`;

// --- Task 93: the 「未排入課程」 panel (edit mode) ---
export const PLACE_PANEL = "mb-4 rounded-lg border border-amber-200 bg-amber-50/40 p-3";
export const PLACE_PANEL_TITLE = "text-sm font-semibold text-gray-900";
export const PLACE_GROUP = "flex flex-wrap items-center gap-2";
export const PLACE_GROUP_LABEL = "w-20 shrink-0 text-xs font-medium text-gray-600";
// One card: the draggable button plus, when no teacher is required, a
// small teacher picker next to it.
export const PLACE_CARD = "inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-1 py-0.5";
const PLACE_CARD_BUTTON_BASE = "rounded px-2 py-1 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";
export const PLACE_CARD_BUTTON = `${PLACE_CARD_BUTTON_BASE} cursor-grab text-gray-900 hover:bg-blue-50`;
export const PLACE_CARD_BUTTON_SELECTED = `${PLACE_CARD_BUTTON_BASE} cursor-grab bg-blue-100 font-medium text-blue-900 ring-2 ring-blue-500`;
export const PLACE_CARD_BUTTON_DRAGGING = `${PLACE_CARD_BUTTON_BASE} cursor-grabbing border border-dashed border-gray-400 bg-gray-100 text-gray-500`;
// No teacher picked yet: looks disabled, but stays focusable so a click or
// a drag can say why (「請先選擇教師」).
export const PLACE_CARD_BUTTON_NEEDS_TEACHER = `${PLACE_CARD_BUTTON_BASE} cursor-not-allowed text-gray-400`;
export const PLACE_TEACHER_SELECT =
  "rounded border border-gray-300 bg-white px-1 py-0.5 text-xs text-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:opacity-50";

// --- Task 94: room type forms ---
// A short help line under a form input.
export const FIELD_HELP = "mt-1 max-w-56 whitespace-normal text-xs text-gray-500";
// A non-blocking heads-up under a form input (e.g. no room has this type).
export const FIELD_HINT_WARNING = "mt-1 max-w-56 whitespace-normal text-xs text-amber-700";
// The small ⚠ next to a table value that has such a problem.
export const INLINE_WARNING_ICON = "ml-1 cursor-help text-amber-600";

// --- Task 98 Phase D: the home page's Action Cards ---
// Three equally wide cards, each one whole link: icon, title, one line.
export const ACTION_CARD_GRID = "mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3";
export const ACTION_CARD =
  "flex h-full items-start gap-3 rounded-lg border border-gray-200 bg-surface p-4 shadow-sm transition-colors hover:border-primary hover:bg-primary-soft";
export const ACTION_CARD_ICON = "flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary";
export const ACTION_CARD_TITLE = "text-base font-semibold text-gray-900";
export const ACTION_CARD_TEXT = "mt-0.5 text-sm text-text-muted";

// --- Task 97: home page dashboard ---
export const DASHBOARD_GRID = "grid grid-cols-1 gap-4 md:grid-cols-2";
export const DASHBOARD_CARD_TITLE = "mb-3 text-base font-semibold text-gray-900";
export const STAT_ROW = "flex flex-wrap gap-6";
export const STAT_VALUE_PROBLEM = "text-2xl font-semibold text-red-600";
export const STAT_VALUE_WARNING = "text-2xl font-semibold text-amber-700";
// Task 99: a count that is 0 -- gray; only a non-zero count is colored.
export const STAT_VALUE_ZERO = "text-2xl font-semibold text-text-muted";
// Task 99: the card's title row with its badge at the right.
export const DASHBOARD_CARD_HEADER = "mb-3 flex flex-wrap items-center justify-between gap-2";
// Task 99: 資料健康度 is shown only when something is missing -- an amber
// reminder card.
export const DASHBOARD_REMINDER_CARD = "rounded-lg border border-amber-200 bg-amber-50 p-4 shadow-sm";
export const DASHBOARD_REMINDER_TITLE = "mb-2 text-base font-semibold text-amber-800";
export const STAT_LABEL = "text-xs text-gray-500";
// A text link inside a sentence (「請到學校資料新增」): the inline form of
// Ghost. A link that stands on its own uses a BUTTON_* class instead.
export const LINK_TEXT = "font-medium text-primary underline-offset-2 hover:text-primary-hover hover:underline";

// --- Task 103: edit-mode notices (課表 手動編輯) ---
// Short-lived notices (saved, 無法放在這裡, 正在預覽…) float at the bottom of
// the window instead of sitting above the timetable: they show wherever
// the page is scrolled, and appearing / disappearing never moves the
// timetable under the pointer.
export const TOAST_REGION =
  "pointer-events-none fixed inset-x-0 bottom-6 z-40 flex flex-col items-center gap-2 px-4 empty:hidden";
export const TOAST = "pointer-events-auto max-w-xl rounded-md border px-4 py-2 text-sm shadow-lg";
export const TOAST_SUCCESS = `${TOAST} border-green-200 bg-green-50 text-green-800`;
export const TOAST_NOTICE = `${TOAST} border-amber-200 bg-amber-50 text-amber-900`;
export const TOAST_LOADING = `${TOAST} border-gray-200 bg-white text-gray-700`;
