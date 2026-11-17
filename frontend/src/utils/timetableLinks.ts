// 帳號改版: the 教學組長's 「課表」 link opens TimetableView with
// ?view=published -- the published timetables only, read-only, the way a
// 一般老師 sees them (their 排課紀錄 still opens any record for editing).
export const PUBLISHED_VIEW = "published";

export const PUBLISHED_TIMETABLE_PATH = `/timetable?view=${PUBLISHED_VIEW}`;
