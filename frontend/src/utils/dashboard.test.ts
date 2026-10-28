import { describe, expect, it } from "vitest";
import {
  draftHealthAction,
  draftHealthBadge,
  formatDateTime,
  pickCurrentSemester,
  pickLatestUnpublished,
  summarizeDataHealth,
  summarizeDraftHealth,
  summarizeVersions,
  statTone,
} from "./dashboard";
import type { Class } from "../types/class";
import type { Room } from "../types/room";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { ScheduleVersion, ScheduleVersionStatus } from "../types/scheduleVersion";

type RecordState = ScheduleVersionStatus | "PUBLISHED";
import type { Semester } from "../types/semester";
import type { Subject } from "../types/subject";
import type { Teacher } from "../types/teacher";

function semester(id: number, academicYearId: number, number: number, isActive: boolean): Semester {
  return { id, academic_year_id: academicYearId, number, is_active: isActive, created_at: "", updated_at: "" };
}

// "PUBLISHED": a published 自動排課 record.
function version(id: number, semesterId: number, versionNumber: number, state: RecordState): ScheduleVersion {
  return {
    id,
    semester_id: semesterId,
    version_number: versionNumber,
    display_number: versionNumber,
    status: state === "PUBLISHED" ? "AUTO" : state,
    is_published: state === "PUBLISHED",
    copied_from_number: state === "COPIED" ? 1 : null,
    copied_from_display_number: state === "COPIED" ? 1 : null,
    editing_source_id: null,
    note: null,
    created_at: "",
    updated_at: "2026-10-19T06:03:00Z",
  };
}

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "H1_TEACHER_CONFLICT",
    severity: "ERROR",
    lesson_id: null,
    teacher_id: 1,
    class_id: null,
    subject_id: null,
    time_slot_id: 5,
    message: "",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: null,
    ...fields,
  };
}

const YEARS = new Map([
  [1, 113],
  [2, 114],
]);

describe("pickCurrentSemester", () => {
  it("is the latest active semester", () => {
    const semesters = [semester(1, 1, 2, true), semester(2, 2, 1, true), semester(3, 2, 2, false)];
    expect(pickCurrentSemester(semesters, YEARS)?.id).toBe(2);
  });

  it("prefers the latest active semester whose timetable is published (the next one may be in preparation)", () => {
    const semesters = [semester(13, 1, 1, true), semester(17, 1, 2, true)];
    const versions = [version(1, 13, 11, "PUBLISHED"), version(2, 17, 3, "AUTO")];
    expect(pickCurrentSemester(semesters, YEARS, versions)?.id).toBe(13);
    expect(pickCurrentSemester(semesters, YEARS, [version(2, 17, 3, "AUTO")])?.id).toBe(17);
  });

  it("falls back to the latest semester when none is active, and to null without any", () => {
    expect(pickCurrentSemester([semester(1, 1, 1, false), semester(2, 2, 1, false)], YEARS)?.id).toBe(2);
    expect(pickCurrentSemester([], YEARS)).toBeNull();
  });
});

describe("summarizeVersions", () => {
  const versions = [
    version(1, 13, 4, "AUTO"),
    version(2, 13, 11, "PUBLISHED"),
    version(3, 13, 12, "MANUAL"),
    version(4, 13, 13, "NOT_SCHEDULED"),
    version(5, 14, 14, "COPIED"),
    version(6, 14, 15, "NOT_SCHEDULED"),
  ];

  it("finds the published record and counts the others, for this semester only", () => {
    const summary = summarizeVersions(versions, 13);
    expect(summary.published?.id).toBe(2);
    expect(summary.otherCount).toBe(3);
  });

  it("is empty without records or without a semester", () => {
    expect(summarizeVersions([], 13)).toEqual({ published: null, otherCount: 0 });
    expect(summarizeVersions(versions, null)).toEqual({ published: null, otherCount: 0 });
  });

  it("picks the newest unpublished record that has a timetable, of any semester", () => {
    expect(pickLatestUnpublished(versions)?.id).toBe(5);
    expect(pickLatestUnpublished(versions.filter((v) => v.id !== 5))?.id).toBe(3);
    expect(pickLatestUnpublished([version(2, 13, 11, "PUBLISHED"), version(4, 13, 13, "NOT_SCHEDULED")])).toBeNull();
    expect(pickLatestUnpublished([])).toBeNull();
  });
});

describe("formatDateTime", () => {
  it("reads the backend's zone-less timestamps as UTC and shows local time", () => {
    const utc = new Date(Date.UTC(2026, 9, 19, 6, 3));
    const pad = (value: number): string => String(value).padStart(2, "0");
    const local = `${utc.getFullYear()}/${pad(utc.getMonth() + 1)}/${pad(utc.getDate())} ${pad(utc.getHours())}:${pad(utc.getMinutes())}`;
    expect(formatDateTime("2026-10-19T06:03:00.123456")).toBe(local);
    expect(formatDateTime("2026-10-19T06:03:00Z")).toBe(local);
    expect(formatDateTime("2026-10-19T14:03:00+08:00")).toBe(local);
  });

  it("never shows NaN", () => {
    expect(formatDateTime("not a date")).toBe("—");
    expect(formatDateTime("")).toBe("—");
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
  });
});

describe("summarizeDraftHealth", () => {
  it("counts distinct problems: one clash reported for two lessons is one", () => {
    const health = summarizeDraftHealth(
      [
        violation({ lesson_id: 1 }),
        violation({ lesson_id: 2 }),
        violation({ type: "FIXED_TIME_SLOT_MISMATCH", lesson_id: 3 }),
        violation({ type: "REQUIRED_ROOM_MISSING", severity: "WARNING", lesson_id: 4, identity_key: "REQUIRED_ROOM_MISSING:4" }),
      ],
      2,
    );
    expect(health).toEqual({ errorCount: 2, warningCount: 1, unscheduledCount: 2, isHealthy: false });
  });

  it("is healthy with nothing wrong", () => {
    expect(summarizeDraftHealth([], 0)).toEqual({ errorCount: 0, warningCount: 0, unscheduledCount: 0, isHealthy: true });
  });

  it("is not healthy with only unscheduled lessons or only a warning", () => {
    expect(summarizeDraftHealth([], 1).isHealthy).toBe(false);
    expect(summarizeDraftHealth([violation({ severity: "WARNING", identity_key: "W:1" })], 0).isHealthy).toBe(false);
  });
});

describe("summarizeDataHealth", () => {
  const teacher = (id: number, active = true): Teacher => ({ id, name: `T${id}`, is_active: active }) as Teacher;
  const klass = (id: number): Class => ({ id, name: `${id}班` }) as Class;
  const subject = (id: number): Subject => ({ id, name: `S${id}`, is_active: true }) as Subject;
  const room = (id: number, active = true): Room => ({ id, name: `R${id}`, is_active: active }) as Room;

  it("counts active records (every class counts: classes are always active)", () => {
    const health = summarizeDataHealth({
      teachers: [teacher(1), teacher(2, false)],
      classes: [klass(1), klass(2)],
      subjects: [subject(1)],
      rooms: [room(10), room(11, false)],
    });
    expect([health.teacherCount, health.classCount, health.subjectCount, health.roomCount]).toEqual([1, 2, 1, 1]);
    expect(health.issues).toEqual([]);
  });

  it("says what is missing when there is nothing at all", () => {
    const health = summarizeDataHealth({ teachers: [], classes: [], subjects: [], rooms: [] });
    expect([health.teacherCount, health.classCount, health.subjectCount, health.roomCount]).toEqual([0, 0, 0, 0]);
    expect(health.issues.map((issue) => issue.path)).toEqual([
      "/users",
      "/data?tab=classes",
      "/data?tab=subjects",
      "/data?tab=rooms",
    ]);
  });

  it("has no issue when everything is set", () => {
    expect(
      summarizeDataHealth({ teachers: [teacher(1)], classes: [klass(1)], subjects: [subject(1)], rooms: [room(10)] }).issues,
    ).toEqual([]);
  });
});

describe("draftHealthBadge", () => {
  it("is green 可發布 with no error and no warning", () => {
    expect(draftHealthBadge({ errorCount: 0, warningCount: 0 })).toEqual({ tone: "success", label: "可發布" });
  });

  it("is amber with warnings only", () => {
    expect(draftHealthBadge({ errorCount: 0, warningCount: 3 })).toEqual({ tone: "warning", label: "3 個警告" });
  });

  it("is red as soon as there is an error, warnings or not", () => {
    expect(draftHealthBadge({ errorCount: 2, warningCount: 0 })).toEqual({ tone: "danger", label: "2 個錯誤" });
    expect(draftHealthBadge({ errorCount: 1, warningCount: 4 })).toEqual({ tone: "danger", label: "1 個錯誤" });
  });
});

describe("draftHealthAction", () => {
  it("says 前往修正 with errors, else 檢視並發布", () => {
    expect(draftHealthAction({ errorCount: 1 })).toBe("前往修正");
    expect(draftHealthAction({ errorCount: 0 })).toBe("檢視並發布");
  });
});

describe("statTone", () => {
  it("is gray for 0 and the given color otherwise", () => {
    expect(statTone(0, "problem")).toBe("zero");
    expect(statTone(0, "warning")).toBe("zero");
    expect(statTone(2, "problem")).toBe("problem");
    expect(statTone(1, "warning")).toBe("warning");
  });
});
