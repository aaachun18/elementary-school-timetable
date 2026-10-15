import { describe, expect, it } from "vitest";
import { coursesOfTeacher, currentTeacherIdsOf, teacherIdsWithCourses } from "./teacherReassignment";
import type { ClassSubjectRequirement } from "../types/classSubjectRequirement";

function requirement(id: number, requiredTeacherId: number | null): ClassSubjectRequirement {
  return {
    id,
    semester_id: 1,
    class_id: 10,
    subject_id: 20,
    weekly_periods: 3,
    required_teacher_id: requiredTeacherId,
    required_room_type: null,
    consecutive_limit: null,
    created_at: "",
    updated_at: "",
    is_locked: false,
  };
}

// 1: rows taught by 5 (required teacher 7 is ignored -- the rows win)
// 2: rows have no teacher -> required teacher 7
// 3: no rows, no required teacher -> nobody
// 4: lessons split between 5 and 6
const requirements = [requirement(1, 7), requirement(2, 7), requirement(3, null), requirement(4, 9)];
const rowTeachers = new Map<number, number[]>([
  [1, [5]],
  [4, [5, 6]],
]);

describe("currentTeacherIdsOf", () => {
  it("prefers the teachers on the version's Schedule rows", () => {
    expect(currentTeacherIdsOf(requirements[0], rowTeachers.get(1))).toEqual([5]);
  });

  it("falls back to the required teacher when no row has a teacher", () => {
    expect(currentTeacherIdsOf(requirements[1], undefined)).toEqual([7]);
    expect(currentTeacherIdsOf(requirements[1], [])).toEqual([7]);
  });

  it("is empty with neither rows nor a required teacher", () => {
    expect(currentTeacherIdsOf(requirements[2], undefined)).toEqual([]);
  });

  it("lists every teacher when the lessons are split", () => {
    expect(currentTeacherIdsOf(requirements[3], rowTeachers.get(4))).toEqual([5, 6]);
  });
});

describe("teacherIdsWithCourses", () => {
  it("collects every current teacher once", () => {
    expect([...teacherIdsWithCourses(requirements, rowTeachers)].sort()).toEqual([5, 6, 7]);
  });
});

describe("coursesOfTeacher", () => {
  const idsOf = (list: ClassSubjectRequirement[]) => list.map((item) => item.id);

  it("lists the courses a teacher currently holds, by id", () => {
    expect(idsOf(coursesOfTeacher(5, requirements, rowTeachers, new Set()))).toEqual([1, 4]);
  });

  it("does not list a course only because the teacher is its (overridden) required teacher", () => {
    expect(idsOf(coursesOfTeacher(7, requirements, rowTeachers, new Set()))).toEqual([2]);
  });

  it("keeps courses just handed away (alsoInclude) in the list", () => {
    expect(idsOf(coursesOfTeacher(7, requirements, rowTeachers, new Set([1])))).toEqual([1, 2]);
  });

  it("is empty for a teacher without courses", () => {
    expect(coursesOfTeacher(99, requirements, rowTeachers, new Set())).toEqual([]);
  });
});
