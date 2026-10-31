import { describe, expect, it } from "vitest";
import { filterByRole, ROLE_FILTER_OPTIONS, searchResultText, serialNumber, sortAccounts } from "./accountList";

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

describe("filterByRole", () => {
  const accounts = [
    { username: "admin", role: "ADMIN" as const },
    { username: "coordinator", role: "COORDINATOR" as const },
    { username: "t1", role: "TEACHER" as const },
    { username: "t2", role: "TEACHER" as const },
  ];

  it("keeps every account for 所有角色", () => {
    expect(filterByRole(accounts, "ALL")).toEqual(accounts);
  });

  it("keeps only the chosen role", () => {
    expect(filterByRole(accounts, "TEACHER").map((account) => account.username)).toEqual(["t1", "t2"]);
    expect(filterByRole(accounts, "COORDINATOR").map((account) => account.username)).toEqual(["coordinator"]);
  });

  it("offers the roles in the asked order", () => {
    expect(ROLE_FILTER_OPTIONS.map((option) => option.label)).toEqual(["所有角色", "教師", "系統管理員", "教學組長"]);
  });
});

describe("searchResultText", () => {
  it("says what was searched and how many were found", () => {
    expect(searchResultText("王", null, 2)).toBe("搜尋「王」：共 2 個帳號");
    expect(searchResultText("李", null, 0)).toBe("找不到包含「李」的帳號");
  });

  it("names the chosen role", () => {
    expect(searchResultText(null, "教師", 5)).toBe("教師：共 5 個帳號");
    expect(searchResultText(null, "教學組長", 0)).toBe("沒有教學組長帳號");
    expect(searchResultText("王", "教師", 1)).toBe("教師中搜尋「王」：共 1 個帳號");
    expect(searchResultText("王", "教師", 0)).toBe("找不到包含「王」的教師帳號");
  });
});
