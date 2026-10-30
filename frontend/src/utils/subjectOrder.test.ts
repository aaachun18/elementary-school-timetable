import { describe, expect, it } from "vitest";
import { compareSubjectNames, sortBySubject, subjectRank } from "./subjectOrder";

describe("subjectRank", () => {
  it("treats every name of 國語 as 國語", () => {
    expect(subjectRank("國語文")).toBe(0);
    expect(subjectRank("國語")).toBe(0);
    expect(subjectRank("國文")).toBe(0);
  });

  it("goes by the first listed word a name contains", () => {
    // 健康與體育 contains 健康 (before 體育).
    expect(subjectRank("健康與體育")).toBeLessThan(subjectRank("體育"));
    expect(subjectRank("藝術與人文")).toBe(subjectRank("藝術"));
  });

  it("puts a subject with none of the words after all of them", () => {
    expect(subjectRank("本土語文／臺灣手語")).toBeGreaterThan(subjectRank("綜合活動"));
  });
});

describe("sortBySubject", () => {
  it("lists subjects in the school order", () => {
    const names = [
      "綜合活動",
      "體育",
      "健康",
      "音樂",
      "藝術",
      "社會",
      "自然科學",
      "美勞",
      "生活課程",
      "數學",
      "英語文",
      "國語文",
      "國際視野",
    ];

    expect(sortBySubject(names, (name) => name)).toEqual([
      "國語文",
      "英語文",
      "數學",
      "生活課程",
      "美勞",
      "自然科學",
      "社會",
      "藝術",
      "音樂",
      "健康",
      "體育",
      "綜合活動",
      "國際視野",
    ]);
  });

  it("orders subjects of the same place by name and never changes the input", () => {
    const names = ["英文", "英語文"];
    const sorted = sortBySubject(names, (name) => name);

    expect(compareSubjectNames("英文", "英語文")).not.toBe(0);
    expect(sorted).toHaveLength(2);
    expect(names).toEqual(["英文", "英語文"]);
  });
});
