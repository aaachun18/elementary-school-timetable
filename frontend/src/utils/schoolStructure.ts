// The fixed structure a school gets from its type -- the same rules as
// backend/app/services/school_structure.py (the backend checks them again):
// grade names, and the class names a grade may use in each name style.
// No React, no requests.

export type SchoolType = "ELEMENTARY" | "JUNIOR_HIGH" | "SENIOR_HIGH";

export const SCHOOL_TYPES: readonly SchoolType[] = ["ELEMENTARY", "JUNIOR_HIGH", "SENIOR_HIGH"];

export const SCHOOL_TYPE_LABELS: Record<SchoolType, string> = {
  ELEMENTARY: "國小",
  JUNIOR_HIGH: "國中",
  SENIOR_HIGH: "高中",
};

// Grade levels: 國小 1-6, 國中 7-9, 高中 10-12 (shown as 一到三年級).
const SENIOR_HIGH_FIRST_LEVEL = 10;

const CHINESE_DIGITS = ["一", "二", "三", "四", "五", "六", "七", "八", "九"];

// 1 -> 一, 10 -> 十, 12 -> 十二, 20 -> 二十, 30 -> 三十 (1-99).
export function chineseNumber(value: number): string {
  const tens = Math.floor(value / 10);
  const ones = value % 10;
  if (tens === 0) {
    return CHINESE_DIGITS[ones - 1] ?? String(value);
  }
  const tensText = tens === 1 ? "" : (CHINESE_DIGITS[tens - 1] ?? "");
  const onesText = ones === 0 ? "" : (CHINESE_DIGITS[ones - 1] ?? "");
  return `${tensText}十${onesText}`;
}

// The year shown to people: 高中 10-12 -> 1-3, every other level as is.
function displayedYear(level: number): number {
  return level >= SENIOR_HIGH_FIRST_LEVEL ? level - SENIOR_HIGH_FIRST_LEVEL + 1 : level;
}

// 1 -> 「一年級」, 7 -> 「七年級」, 10 -> 「一年級」(高中).
export function gradeName(level: number): string {
  return `${chineseNumber(displayedYear(level))}年級`;
}

// --- Class names ---

export type ClassNameStyle = "NUMBER" | "HEAVENLY_STEM" | "VIRTUE";

export const CLASS_NAME_STYLES: readonly ClassNameStyle[] = ["NUMBER", "HEAVENLY_STEM", "VIRTUE"];

export const CLASS_NAME_STYLE_LABELS: Record<ClassNameStyle, string> = {
  NUMBER: "一二三…",
  HEAVENLY_STEM: "甲乙丙…",
  VIRTUE: "忠孝仁愛…",
};

const CLASS_NUMBER_COUNT = 30;
const HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"];
const VIRTUES = ["忠", "孝", "仁", "愛", "信", "義", "和", "平"];

function classNameTokens(style: ClassNameStyle): string[] {
  if (style === "NUMBER") {
    return Array.from({ length: CLASS_NUMBER_COUNT }, (_, index) => chineseNumber(index + 1));
  }
  return style === "HEAVENLY_STEM" ? HEAVENLY_STEMS : VIRTUES;
}

// Every name a class of this grade may take in this style, expanded from
// the grade: 一年級 + 甲乙丙 -> 一年甲班, 一年乙班 ...
export function classNameOptions(level: number, style: ClassNameStyle): string[] {
  const prefix = `${chineseNumber(displayedYear(level))}年`;
  return classNameTokens(style).map((token) => `${prefix}${token}班`);
}

// --- A grade's default open periods (開始排課 > 年級與可排節次) ---

// The same defaults the backend applies (app/services/grade_levels.py), in
// the words people use: only teaching periods are counted, so 國小's
// afternoon is 第 5-7 節.
export function defaultOpenPeriodsText(level: number): string {
  if (level <= 2) {
    return "星期二第 1–7 節，其他天第 1–4 節";
  }
  if (level <= 4) {
    return "星期三、五第 1–4 節，其他天第 1–7 節";
  }
  if (level <= 6) {
    return "星期三第 1–4 節，其他天第 1–7 節";
  }
  return "每天第 1–8 節";
}
