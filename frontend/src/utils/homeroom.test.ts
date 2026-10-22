import { describe, expect, it } from "vitest";
import { classesWithoutHomeroom, missingHomeroomMessage, sortClassesByGrade } from "./homeroom";

const levels = new Map([
  [10, 1],
  [20, 2],
]);
const classes = [
  { id: 3, grade_id: 20, name: "二年甲班" },
  { id: 2, grade_id: 10, name: "一年乙班" },
  { id: 1, grade_id: 10, name: "一年甲班" },
];

describe("sortClassesByGrade", () => {
  it("orders by grade level, then by id", () => {
    expect(sortClassesByGrade(classes, levels).map((item) => item.name)).toEqual([
      "一年甲班",
      "一年乙班",
      "二年甲班",
    ]);
  });
});

describe("classesWithoutHomeroom", () => {
  it("leaves out the classes that already have a 導師", () => {
    expect(classesWithoutHomeroom(classes, new Set([2])).map((item) => item.id)).toEqual([3, 1]);
  });
});

describe("missingHomeroomMessage", () => {
  it("names every class without a 導師", () => {
    const sorted = sortClassesByGrade(classes, levels);
    expect(missingHomeroomMessage(sorted, new Set([2]))).toBe(
      "一年甲班、二年甲班未被指派導師，修正後方可進入下一步。",
    );
  });

  it("is null once every class has one", () => {
    expect(missingHomeroomMessage(classes, new Set([1, 2, 3]))).toBeNull();
  });
});
