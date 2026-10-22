import { describe, expect, it } from "vitest";
import { findSubjectByName, normalizeSubjectName } from "./subjectName";

const subjects = [
  { id: 1, name: "國語文" },
  { id: 2, name: "數學" },
];

describe("findSubjectByName", () => {
  it("finds the school's subject of that name, spaces ignored", () => {
    expect(findSubjectByName(subjects, "數學")?.id).toBe(2);
    expect(findSubjectByName(subjects, "  國語文 ")?.id).toBe(1);
  });

  it("finds nothing for a new name", () => {
    expect(findSubjectByName(subjects, "書法")).toBeUndefined();
  });
});

describe("normalizeSubjectName", () => {
  it("trims the name", () => {
    expect(normalizeSubjectName(" 書法 ")).toBe("書法");
  });
});
