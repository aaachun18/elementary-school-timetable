import { describe, expect, it } from "vitest";
import { filterOptions, selectedLabel } from "./searchableSelect";

const options = [
  { value: 1, label: "王小明" },
  { value: 2, label: "王大同" },
  { value: 3, label: "陳美玲" },
  { value: 4, label: "六年甲班" },
];

describe("filterOptions", () => {
  it("keeps every option whose label contains the query", () => {
    expect(filterOptions(options, "王").map((option) => option.value)).toEqual([1, 2]);
    expect(filterOptions(options, "甲").map((option) => option.value)).toEqual([4]);
  });

  it("keeps everything for an empty or blank query", () => {
    expect(filterOptions(options, "")).toEqual(options);
    expect(filterOptions(options, "  ")).toEqual(options);
  });

  it("ignores spaces around the query and letter case", () => {
    expect(filterOptions([{ value: 9, label: "Teacher Lin" }], " lin ").map((option) => option.value)).toEqual([9]);
  });

  it("finds nothing when no label matches", () => {
    expect(filterOptions(options, "李")).toEqual([]);
  });
});

describe("selectedLabel", () => {
  it("shows the picked option, or the none choice when nothing is picked", () => {
    expect(selectedLabel(options, 3, null)).toBe("陳美玲");
    expect(selectedLabel(options, null, "不指定")).toBe("不指定");
    expect(selectedLabel(options, null, null)).toBe("");
  });
});
