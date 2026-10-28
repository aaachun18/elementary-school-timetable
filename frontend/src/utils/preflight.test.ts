import { describe, expect, it } from "vitest";
import { preflightIssues } from "./preflight";
import type { NameLookups } from "./failureDiagnostics";
import type { Class } from "../types/class";
import type { ClassSubjectRequirement } from "../types/classSubjectRequirement";
import type { Room } from "../types/room";
import type { ConstraintViolationDetail, PreflightResult } from "../types/scheduler";
import type { Subject } from "../types/subject";
import type { Teacher } from "../types/teacher";

const lookups: NameLookups = {
  teacherById: new Map([[7, { id: 7, name: "王老師", is_active: false } as Teacher]]),
  classById: new Map([
    [1, { id: 1, name: "一年甲班" } as Class],
    [2, { id: 2, name: "一年乙班" } as Class],
  ]),
  subjectById: new Map([[5, { id: 5, name: "國語文" } as Subject]]),
  roomById: new Map([[9, { id: 9, name: "音樂教室" } as Room]]),
  timeSlotById: new Map(),
  requirementById: new Map([[30, { id: 30, class_id: 1, subject_id: 5 } as ClassSubjectRequirement]]),
};

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "STATIC_INACTIVE_ENTITY_CONFLICT",
    severity: "ERROR",
    lesson_id: null,
    teacher_id: null,
    class_id: null,
    subject_id: null,
    time_slot_id: null,
    message: "",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: 30,
    ...fields,
  };
}

function result(violations: ConstraintViolationDetail[]): PreflightResult {
  return { can_schedule: violations.length === 0, violations, lesson_failures: [] };
}

describe("preflightIssues", () => {
  it("names a 停用 required teacher, linking back to 科目需求", () => {
    expect(preflightIssues(result([violation({ teacher_id: 7 })]), lookups)).toEqual([
      {
        text: "一年甲班 國語文：指定老師「王老師」已停用",
        link: { label: "回到科目需求", path: "/wizard?step=requirements" },
      },
    ]);
  });

  it("names a 停用 special room and a 停用 subject", () => {
    const texts = preflightIssues(result([violation({ room_id: 9 }), violation({ subject_id: 5 })]), lookups).map(
      (issue) => issue.text,
    );
    expect(texts).toEqual(["一年甲班 國語文：特殊教室「音樂教室」已停用", "一年甲班 國語文：科目已停用"]);
  });

  it("says a 停用 class still in the record leaves on going back to 科目需求", () => {
    const [issue] = preflightIssues(
      result([violation({ type: "INACTIVE_CLASS_IN_RECORD", class_id: 2, class_subject_requirement_id: null })]),
      lookups,
    );
    expect(issue.text).toBe("一年乙班已停用，回到科目需求後會自動移出這次排課");
    expect(issue.link?.path).toBe("/wizard?step=requirements");
  });

  it("lists one line once, and lesson failures too", () => {
    const same = violation({ teacher_id: 7 });
    const issues = preflightIssues(
      {
        can_schedule: false,
        violations: [same],
        lesson_failures: [{ lesson_id: null, class_subject_requirement_id: 30, reasons: [same] }],
      },
      lookups,
    );
    expect(issues).toHaveLength(1);
  });

  it("has nothing to list when scheduling can go ahead", () => {
    expect(preflightIssues(result([]), lookups)).toEqual([]);
  });
});
