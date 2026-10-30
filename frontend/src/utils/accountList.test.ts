import { describe, expect, it } from "vitest";
import { searchResultText, serialNumber, sortAccounts } from "./accountList";

const teacher = (username: string, name: string) => ({ username, role: "TEACHER" as const, teacher_name: name });

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

  it("puts accounts without a teacher first, and same names by account", () => {
    const sorted = sortAccounts([
      teacher("wang2", "王小明"),
      { username: "coordinator", role: "COORDINATOR" as const, teacher_name: null },
      teacher("wang1", "王小明"),
      { username: "admin", role: "ADMIN" as const, teacher_name: null },
    ]);

    expect(sorted.map((account) => account.username)).toEqual(["admin", "coordinator", "wang1", "wang2"]);
  });
});

describe("serialNumber", () => {
  it("counts on across pages", () => {
    expect(serialNumber(1, 10, 0)).toBe(1);
    expect(serialNumber(2, 10, 3)).toBe(14);
  });
});

describe("searchResultText", () => {
  it("says what was searched and how many were found", () => {
    expect(searchResultText("王", 2)).toBe("搜尋「王」：共 2 個帳號");
    expect(searchResultText("李", 0)).toBe("找不到包含「李」的帳號");
  });
});
