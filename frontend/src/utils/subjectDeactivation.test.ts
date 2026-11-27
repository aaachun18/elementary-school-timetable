import { describe, expect, it } from "vitest";
import { hiddenRequirementsNote, skippedSubjectsNote, splitBySubjectActive } from "./subjectDeactivation";

describe("splitBySubjectActive", () => {
  it("hides the requirements of 停用 subjects", () => {
    const requirements = [
      { id: 1, subject_id: 10 },
      { id: 2, subject_id: 11 },
      { id: 3, subject_id: 12 },
    ];
    const { shown, hidden } = splitBySubjectActive(requirements, new Set([10, 12]));
    expect(shown.map((item) => item.id)).toEqual([1, 3]);
    expect(hidden.map((item) => item.id)).toEqual([2]);
  });
});

describe("hiddenRequirementsNote", () => {
  it("counts the hidden ones, and says nothing when there are none", () => {
    expect(hiddenRequirementsNote(2)).toBe("另有 2 筆已停用科目的需求已隱藏");
    expect(hiddenRequirementsNote(0)).toBeNull();
  });
});

describe("skippedSubjectsNote", () => {
  it("counts the 停用 subjects left out of this scheduling", () => {
    expect(skippedSubjectsNote(1)).toBe("有 1 個已停用科目的需求未納入本次排課");
    expect(skippedSubjectsNote(0)).toBeNull();
  });
});
