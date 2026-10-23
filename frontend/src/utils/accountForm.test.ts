import { describe, expect, it } from "vitest";
import {
  creatableRoles,
  getMissingFieldMessage,
  getNationalIdError,
  NATIONAL_ID_FORMAT_MESSAGE,
  needsSchoolChoice,
  toUserCreate,
  type NewAccountDraft,
} from "./accountForm";

const COMPLETE_TEACHER: NewAccountDraft = {
  username: " wang ",
  password: "s3cret-pass",
  role: "TEACHER",
  schoolId: 3,
  teacherName: " 王老師 ",
  nationalId: "",
};

describe("creatableRoles", () => {
  it("lets the 系統管理員 create every role", () => {
    expect(creatableRoles("ADMIN")).toEqual(["TEACHER", "COORDINATOR", "ADMIN"]);
  });

  it("limits a 教學組長 to 一般老師 accounts", () => {
    expect(creatableRoles("COORDINATOR")).toEqual(["TEACHER"]);
  });
});

describe("needsSchoolChoice", () => {
  it("is only for the 系統管理員 creating a school-bound account", () => {
    expect(needsSchoolChoice("ADMIN", "TEACHER")).toBe(true);
    expect(needsSchoolChoice("ADMIN", "COORDINATOR")).toBe(true);
    expect(needsSchoolChoice("ADMIN", "ADMIN")).toBe(false);
    expect(needsSchoolChoice("COORDINATOR", "TEACHER")).toBe(false);
  });
});

describe("getMissingFieldMessage", () => {
  it("accepts a complete draft", () => {
    expect(getMissingFieldMessage(COMPLETE_TEACHER, "ADMIN")).toBeNull();
  });

  it("requires a teacher name for an 一般老師", () => {
    expect(getMissingFieldMessage({ ...COMPLETE_TEACHER, teacherName: "  " }, "ADMIN")).toBe(
      "請輸入教師姓名",
    );
  });

  it("requires a school only when the 系統管理員 must choose one", () => {
    const withoutSchool = { ...COMPLETE_TEACHER, schoolId: null };
    expect(getMissingFieldMessage(withoutSchool, "ADMIN")).toBe("請選擇所屬學校");
    expect(getMissingFieldMessage(withoutSchool, "COORDINATOR")).toBeNull();
  });
});

describe("toUserCreate", () => {
  it("trims and includes school and teacher name for the 系統管理員", () => {
    expect(toUserCreate(COMPLETE_TEACHER, "ADMIN")).toEqual({
      username: "wang",
      password: "s3cret-pass",
      role: "TEACHER",
      school_id: 3,
      teacher_name: "王老師",
    });
  });

  it("leaves the school out for a 教學組長 (their own school is used)", () => {
    expect(toUserCreate(COMPLETE_TEACHER, "COORDINATOR").school_id).toBeUndefined();
  });

  it("sends neither school nor teacher name for a 系統管理員 account", () => {
    const body = toUserCreate({ ...COMPLETE_TEACHER, role: "ADMIN" }, "ADMIN");
    expect(body.school_id).toBeUndefined();
    expect(body.teacher_name).toBeUndefined();
  });
});

describe("身分證字號", () => {
  it("is sent upper-cased only when filled in", () => {
    expect(toUserCreate(COMPLETE_TEACHER, "ADMIN").teacher_national_id).toBeUndefined();
    expect(toUserCreate({ ...COMPLETE_TEACHER, nationalId: " a123456789 " }, "ADMIN").teacher_national_id).toBe(
      "A123456789",
    );
  });

  it("is never sent for a non-teacher account", () => {
    const body = toUserCreate({ ...COMPLETE_TEACHER, role: "COORDINATOR", nationalId: "A123456789" }, "ADMIN");
    expect(body.teacher_national_id).toBeUndefined();
  });

  it("accepts an ID card or resident certificate number", () => {
    expect(getNationalIdError("A123456789")).toBeNull();
    expect(getNationalIdError("a823456789")).toBeNull();
    expect(getNationalIdError("AB12345678")).toBeNull();
  });

  it("explains a missing or malformed number", () => {
    expect(getNationalIdError("  ")).toBe("請輸入身分證字號");
    expect(getNationalIdError("123456789")).toBe(NATIONAL_ID_FORMAT_MESSAGE);
    expect(getNationalIdError("A12345678")).toBe(NATIONAL_ID_FORMAT_MESSAGE);
  });
});
