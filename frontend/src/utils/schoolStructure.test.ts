import { describe, expect, it } from "vitest";
import { chineseNumber, classNameOptions, defaultOpenPeriodsText, gradeName } from "./schoolStructure";

describe("chineseNumber", () => {
  it("writes 1-30 the way class names use them", () => {
    expect([1, 9, 10, 11, 20, 21, 30].map(chineseNumber)).toEqual([
      "一",
      "九",
      "十",
      "十一",
      "二十",
      "二十一",
      "三十",
    ]);
  });
});

describe("gradeName", () => {
  it("names 國小 and 國中 grades by their level", () => {
    expect([1, 6, 7, 9].map(gradeName)).toEqual(["一年級", "六年級", "七年級", "九年級"]);
  });

  it("names 高中 levels 10-12 as 一到三年級", () => {
    expect([10, 11, 12].map(gradeName)).toEqual(["一年級", "二年級", "三年級"]);
  });
});

describe("classNameOptions", () => {
  it("expands 一二三… to 三十 from the grade", () => {
    const names = classNameOptions(1, "NUMBER");
    expect(names).toHaveLength(30);
    expect(names[0]).toBe("一年一班");
    expect(names[29]).toBe("一年三十班");
  });

  it("expands 甲乙丙… to 癸", () => {
    const names = classNameOptions(2, "HEAVENLY_STEM");
    expect(names).toHaveLength(10);
    expect(names[0]).toBe("二年甲班");
    expect(names[9]).toBe("二年癸班");
  });

  it("expands 忠孝仁愛… to 平", () => {
    const names = classNameOptions(7, "VIRTUE");
    expect(names).toEqual([
      "七年忠班",
      "七年孝班",
      "七年仁班",
      "七年愛班",
      "七年信班",
      "七年義班",
      "七年和班",
      "七年平班",
    ]);
  });

  it("uses 一到三年 for 高中", () => {
    expect(classNameOptions(10, "HEAVENLY_STEM")[0]).toBe("一年甲班");
  });
});

describe("defaultOpenPeriodsText", () => {
  it("describes each band's default open periods", () => {
    expect(defaultOpenPeriodsText(1)).toBe("星期二第 1–7 節，其他天第 1–4 節");
    expect(defaultOpenPeriodsText(4)).toBe("星期三、五第 1–4 節，其他天第 1–7 節");
    expect(defaultOpenPeriodsText(6)).toBe("星期三第 1–4 節，其他天第 1–7 節");
    expect(defaultOpenPeriodsText(8)).toBe("每天第 1–8 節");
    expect(defaultOpenPeriodsText(11)).toBe("每天第 1–8 節");
  });
});
