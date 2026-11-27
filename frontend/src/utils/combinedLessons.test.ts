import { describe, expect, it } from "vitest";
import {
  blockChoiceLabel,
  blockChoices,
  canMergeWith,
  combinedForDisplay,
  combinedLessonOf,
  combinedTeacherText,
  partnerLessonsOf,
  nameLines,
} from "./combinedLessons";
import type { CombinedLesson } from "../types/combinedLesson";

const host = { id: 1, class_id: 10, weekly_periods: 2, lesson_pattern: null };

describe("canMergeWith", () => {
  it("needs another class with the same weekly periods and pattern", () => {
    expect(canMergeWith(host, { id: 2, class_id: 20, weekly_periods: 2 }, new Set())).toBe(true);
    expect(canMergeWith(host, { id: 2, class_id: 10, weekly_periods: 2 }, new Set())).toBe(false);
    expect(canMergeWith(host, { id: 2, class_id: 20, weekly_periods: 3 }, new Set())).toBe(false);
    expect(
      canMergeWith(host, { id: 2, class_id: 20, weekly_periods: 2, lesson_pattern: "2" }, new Set()),
    ).toBe(false);
  });

  it("leaves out requirements already combined", () => {
    expect(canMergeWith(host, { id: 2, class_id: 20, weekly_periods: 2 }, new Set([2]))).toBe(false);
  });
});

describe("blockChoices", () => {
  it("lists a pattern's blocks, or null without one", () => {
    expect(blockChoices("2+1")).toEqual([
      { blockNo: 1, size: 2 },
      { blockNo: 2, size: 1 },
    ]);
    expect(blockChoices(null)).toBeNull();
    expect(blockChoiceLabel({ blockNo: 1, size: 2 })).toBe("第 1 組（2 節連堂）");
  });
});

const combined: CombinedLesson = {
  id: 5,
  schedule_version_id: 1,
  requirement_ids: [1, 2],
  merged_count: 1,
  block_nos: null,
  room_id: null,
  homeroom_class_id: 10,
  instances: [{ key: "5:1", member_lesson_ids: [[100], [200]] }],
  created_at: "",
  updated_at: "",
};

describe("partnerLessonsOf / combinedLessonOf", () => {
  it("pairs the lessons that share a slot", () => {
    const partners = partnerLessonsOf([combined]);
    expect(partners.get(100)).toEqual([200]);
    expect(partners.get(200)).toEqual([100]);
    expect(partners.get(300)).toBeUndefined();
    expect(combinedLessonOf([combined]).get(200)?.id).toBe(5);
  });
});

describe("combinedTeacherText", () => {
  it("lists every teacher once and marks the class's own with *", () => {
    const own = { lessonId: 100, teacherId: 1, teacherName: "王老師" };
    const other = { lessonId: 200, teacherId: 2, teacherName: "李老師" };
    expect(combinedTeacherText(own, [other])).toBe("王老師*、李老師");
    expect(combinedTeacherText(other, [own])).toBe("李老師*、王老師");
  });

  it("shows one teacher teaching every member once", () => {
    const own = { lessonId: 100, teacherId: 1, teacherName: "王老師" };
    expect(combinedTeacherText(own, [{ lessonId: 200, teacherId: 1, teacherName: "王老師" }])).toBe("王老師*");
    expect(combinedTeacherText(own, [])).toBe("王老師");
  });
});

describe("combinedForDisplay", () => {
  const rowA = {
    scheduleId: 1,
    lessonId: 100,
    classId: 10,
    className: "一年甲班",
    teacherId: 1,
    teacherName: "王老師",
    roomId: null,
    specialRoomName: null,
  };
  const rowB = { ...rowA, scheduleId: 2, lessonId: 200, classId: 20, className: "二年甲班", teacherId: 2, teacherName: "李老師" };
  const single = { ...rowA, scheduleId: 3, lessonId: 300 };

  it("class view: lists every teacher and names another class's room", () => {
    const [a, b, other] = combinedForDisplay([rowA, rowB, single], [combined], "class");
    expect(a.teacherName).toBe("王老師*、李老師");
    expect(a.specialRoomName).toBeNull();
    expect(b.teacherName).toBe("李老師*、王老師");
    expect(b.specialRoomName).toBe("一年甲班");
    expect(other).toEqual(single);
  });

  it("room view: one row in the homeroom class's room, naming both classes", () => {
    const shown = combinedForDisplay([rowA, rowB], [combined], "room");
    expect(shown.map((row) => [row.scheduleId, row.className])).toEqual([[1, "一年甲班、二年甲班"]]);
  });

  it("teacher view: one row per teacher", () => {
    const sameTeacher = { ...rowB, teacherId: 1, teacherName: "王老師" };
    expect(combinedForDisplay([rowA, sameTeacher], [combined], "teacher")).toHaveLength(1);
    expect(combinedForDisplay([rowA, rowB], [combined], "teacher")).toHaveLength(2);
  });
});

describe("nameLines", () => {
  it("keeps up to three names on one line", () => {
    expect(nameLines("王老師*、李老師、陳老師")).toEqual(["王老師*、李老師、陳老師"]);
  });

  it("starts a new line after every three names", () => {
    expect(nameLines("甲*、乙、丙、丁、戊、己、庚")).toEqual(["甲*、乙、丙", "丁、戊、己", "庚"]);
  });

  it("has no lines without names", () => {
    expect(nameLines(null)).toEqual([]);
    expect(nameLines("")).toEqual([]);
  });
});
