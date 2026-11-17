import { describe, expect, it } from "vitest";
import {
  ACCOUNT_FILTER_OPTIONS,
  filterAccounts,
  searchResultText,
  serialNumber,
  sortAccounts,
} from "./accountList";

const teacher = (username: string, name: string | null) => ({
  username,
  role: "TEACHER" as const,
  teacher_name: name,
});

describe("sortAccounts", () => {
  it("orders teachers by the strokes of their name, surname first", () => {
    const sorted = sortAccounts([
      teacher("t1", "陳美玲"),
      teacher("t2", "王小明"),
      teacher("t3", "丁一"),
      teacher("t4", "李大同"),
      teacher("t5", "林志明"),
    ]);

    expect(sorted.map((account) => account.teacher_name)).toEqual(["丁一", "王小明", "李大同", "林志明", "陳美玲"]);
  });

  it("puts 教學組長 first, then same names by account, then no name", () => {
    const sorted = sortAccounts([
      teacher("wang2", "王小明"),
      teacher("noname", null),
      { username: "coordinator", role: "COORDINATOR" as const, teacher_name: "陳組長" },
      teacher("wang1", "王小明"),
    ]);

    expect(sorted.map((account) => account.username)).toEqual(["coordinator", "wang1", "wang2", "noname"]);
  });
});

describe("serialNumber", () => {
  it("counts on across pages", () => {
    expect(serialNumber(1, 10, 0)).toBe(1);
    expect(serialNumber(2, 10, 3)).toBe(14);
  });
});

describe("filterAccounts", () => {
  const accounts = [
    { username: "coordinator", role: "COORDINATOR" as const, school_id: 1 },
    { username: "t1", role: "TEACHER" as const, school_id: 1 },
    { username: "t2", role: "TEACHER" as const, school_id: null },
  ];

  it("keeps every account for 所有帳號", () => {
    expect(filterAccounts(accounts, "ALL")).toEqual(accounts);
  });

  it("keeps only the chosen role", () => {
    expect(filterAccounts(accounts, "TEACHER").map((account) => account.username)).toEqual(["t1", "t2"]);
    expect(filterAccounts(accounts, "COORDINATOR").map((account) => account.username)).toEqual(["coordinator"]);
  });

  it("keeps the 無所屬學校 teachers", () => {
    expect(filterAccounts(accounts, "NO_SCHOOL").map((account) => account.username)).toEqual(["t2"]);
  });

  it("offers no 系統管理員 filter", () => {
    expect(ACCOUNT_FILTER_OPTIONS.map((option) => option.label)).toEqual([
      "所有帳號",
      "教學組長",
      "一般老師",
      "無所屬學校",
    ]);
  });
});

describe("searchResultText", () => {
  it("says what was searched and how many were found", () => {
    expect(searchResultText("王", null, 2)).toBe("搜尋「王」：共 2 個帳號");
    expect(searchResultText("李", null, 0)).toBe("找不到包含「李」的帳號");
  });

  it("names the chosen group", () => {
    expect(searchResultText(null, "一般老師", 5)).toBe("一般老師：共 5 個帳號");
    expect(searchResultText(null, "無所屬學校", 0)).toBe("沒有無所屬學校帳號");
    expect(searchResultText("王", "一般老師", 1)).toBe("一般老師中搜尋「王」：共 1 個帳號");
    expect(searchResultText("王", "一般老師", 0)).toBe("找不到包含「王」的一般老師帳號");
  });
});
