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
export const LOADING_TEXT = "text-sm text-gray-500";

// --- Layout ---
export const PAGE = "p-6 max-w-6xl mx-auto";
export const SECTION = "mb-6";
export const CARD = "rounded-lg border border-gray-200 bg-white p-4 shadow-sm";

// --- Buttons ---
// Normal size (page-level actions: 新增/登入/開始自動排課/展開課程清單...).
export const BUTTON_PRIMARY =
  "inline-flex items-center justify-center rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50";
export const BUTTON_SECONDARY =
  "inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50";
export const BUTTON_DANGER =
  "inline-flex items-center justify-center rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-600 shadow-sm hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50";

// Small size (in-row actions: 編輯/刪除/確認/取消/移除 inside a table row).
export const BUTTON_PRIMARY_SM =
  "inline-flex items-center justify-center rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50";
export const BUTTON_SECONDARY_SM =
  "inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50";
export const BUTTON_DANGER_SM =
  "inline-flex items-center justify-center rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-600 shadow-sm hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50";

// Plain text-link-styled button, e.g. toggling a collapsible section.
export const BUTTON_LINK =
  "text-sm font-medium text-blue-600 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50";

// --- Form controls ---
export const INPUT =
  "rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500";
export const SELECT = INPUT;
export const CHECKBOX = "h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500";
export const LABEL = "text-sm font-medium text-gray-700";

// --- Tables ---
export const TABLE_WRAPPER = "overflow-x-auto rounded-lg border border-gray-200";
export const TABLE = "w-full border-collapse text-sm";
export const TABLE_HEAD_ROW = "bg-gray-50";
export const TH = "border-b border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap";
export const TD = "border-b border-gray-100 px-3 py-2 text-gray-700";
export const TR_HOVER = "hover:bg-gray-50";
// Task 73: a cell of a locked (read-only) row -- TD with lighter text. A
// separate constant, not TD + "text-gray-400", so the two text colors never
// compete.
export const TD_LOCKED = "border-b border-gray-100 px-3 py-2 text-gray-400";
// Task 92A: short values (names, numbers, a semester) that must not wrap
// -- the table wrapper scrolls sideways instead of squeezing them.
export const TD_NOWRAP = `${TD} whitespace-nowrap`;
export const TD_LOCKED_NOWRAP = `${TD_LOCKED} whitespace-nowrap`;

// --- Nav ---
export const NAV_BAR =
  "flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-gray-200 bg-white px-6 py-3";
export const NAV_LINK = "text-sm font-medium text-gray-600 hover:text-blue-600";
export const NAV_LINK_ACTIVE = "text-sm font-medium text-blue-600";

// --- Tabs (DataBrowser's own secondary nav) ---
export const TAB_BUTTON =
  "rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100";
export const TAB_BUTTON_ACTIVE = "rounded-md bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700";

// --- Badges / status pills ---
// Task 73: marks a row that can't be edited or deleted (shown with an
// explanation line next to it, not only as a tooltip).
export const LOCK_BADGE =
  "inline-flex items-center gap-1 rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700";
export const BADGE_SUCCESS = "inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700";
export const BADGE_NEUTRAL = "inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600";
// Task 67: version status pills -- DRAFT uses the accent blue (BADGE_INFO),
// PUBLISHED reuses BADGE_SUCCESS, ARCHIVED reuses BADGE_NEUTRAL.
export const BADGE_INFO = "inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700";
// Task 90: a WARNING (e.g. a teacher below the minimum weekly periods) --
// amber like NOTICE, never the red of an error.
export const BADGE_WARNING = "inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800";

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
// Task 71 fix: the cell a just-saved move/swap landed in (edit mode only).
// Deliberately not TD_HIGHLIGHT: that one belongs to 「在課表中查看」 and
// has its own lifetime.
export const TD_ADJUSTED = "bg-sky-50 ring-2 ring-inset ring-sky-500";
// Task 84 / Task 85: candidate marks while a lesson is selected or dragged
// in edit mode -- at most one soft fill per cell plus one small icon in its
// top-right corner. Low-saturation fills, so they read apart from the
// amber locate ring (TD_HIGHLIGHT), the sky 「剛調整」 ring (TD_ADJUSTED),
// the drag-hover outline (DROP_TARGET_OK / DROP_TARGET_BLOCKED) and the
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
// Task 90: a target the lesson block (連堂) rules refuse -- gray with a
// "no entry" icon; nothing is sent when dropping there.
export const TD_CANDIDATE_BLOCKED =
  "bg-gray-100 bg-[repeating-linear-gradient(45deg,rgb(107_114_128/0.12)_0_2px,transparent_2px_8px)]";
export const CANDIDATE_ICON_BLOCKED = `${CANDIDATE_ICON_BASE} bg-gray-500`;
// The legend above the grid: small swatches with one word each (Task 90
// added the fourth, 「不可放」).
export const CANDIDATE_LEGEND = "mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600";
const CANDIDATE_SWATCH_BASE = "inline-block h-3 w-3 rounded-sm border";
export const CANDIDATE_LEGEND_SAFE_SWATCH = `${CANDIDATE_SWATCH_BASE} border-emerald-300 ${TD_CANDIDATE_SAFE}`;
export const CANDIDATE_LEGEND_CONFLICT_SWATCH = `${CANDIDATE_SWATCH_BASE} border-rose-300 ${TD_CANDIDATE_CONFLICT}`;
export const CANDIDATE_LEGEND_UNAVAILABLE_SWATCH = `${CANDIDATE_SWATCH_BASE} border-gray-300 bg-gray-200`;
export const CANDIDATE_LEGEND_BLOCKED_SWATCH = `${CANDIDATE_SWATCH_BASE} border-gray-400 ${TD_CANDIDATE_BLOCKED}`;

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
export const DROP_ZONE_BLOCKED =
  "pointer-events-none rounded-md border border-dashed border-gray-400 bg-white/80 px-2 py-1 text-center text-xs text-gray-600";

// Task 78: the row header (節次) column. Full constants rather than TH plus
// extra classes, so two background/text colors never compete.
export const TIMETABLE_ROW_HEADER =
  "border-b border-gray-200 bg-white px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap";
// Non-teaching rows (早自習/午休/放學): a clearly darker gray than the
// row hover (gray-50) and the table head (gray-50), so they read as "not a
// lesson slot" at a glance. The cell's own background covers the row hover.
export const TIMETABLE_ROW_HEADER_NON_TEACHING =
  "border-b border-gray-300 bg-gray-200 px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap";
// A non-teaching cell without background, for combining with one marker
// (TD_HIGHLIGHT / TD_ADJUSTED / DROP_TARGET_BLOCKED), which brings its own.
export const TD_NON_TEACHING_BASE = "border-b border-gray-300 px-3 py-2 text-gray-600";
export const TD_NON_TEACHING = `${TD_NON_TEACHING_BASE} bg-gray-200`;

// --- Timetable edit mode (Task 69) ---
// A lesson in edit mode is a full-width button; the selected one gets a
// thick blue border AND a 「已選取」 text marker (never color alone). All
// variants share one base so border/background never come from two
// competing classes.
const LESSON_BUTTON_BASE =
  "flex w-full flex-col items-start rounded-md px-2 py-1 text-left text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60";
export const LESSON_BUTTON = `${LESSON_BUTTON_BASE} border border-gray-300 bg-white hover:border-blue-400 hover:bg-blue-50`;
export const LESSON_BUTTON_SELECTED = `${LESSON_BUTTON_BASE} border-2 border-blue-600 bg-blue-50`;
// Task 71: drag & drop. The lesson being dragged is faded with a dashed
// border; a lesson under the pointer that it can swap with gets a thick
// green border. (A lesson it can't swap with is always in the dragged
// lesson's own time slot, so the whole cell shows DROP_TARGET_BLOCKED.)
export const LESSON_BUTTON_DRAGGING = `${LESSON_BUTTON_BASE} border border-dashed border-gray-400 bg-gray-100 opacity-50`;
export const LESSON_BUTTON_DROP_OK = `${LESSON_BUTTON_BASE} border-2 border-green-600 bg-green-50`;
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
  "pointer-events-none rounded-md border border-dashed border-green-500 px-2 py-1 text-center text-xs text-green-700";
// Task 85: in a cell that has lessons, the drop area under them is a thin
// dashed strip while dragging; it expands to DROP_ZONE (with 「移到這裡」)
// only while the drag is over that cell.
export const DROP_STRIP = "pointer-events-none h-1.5 rounded-sm border border-dashed border-blue-300";
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
export const PREVIEW_TOGGLE = "self-start text-xs font-medium text-blue-600 hover:text-blue-700";
