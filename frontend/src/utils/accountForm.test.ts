import { describe, expect, it } from "vitest";
import {
  EMAIL_FORMAT_MESSAGE,
  getMissingFieldMessage,
  isValidEmail,
  needsSchoolChoice,
  needsTeacherName,
  newAccountRole,
  toAccountCreate,
  type NewAccountDraft,
} from "./accountForm";

const COMPLETE: NewAccountDraft = {
  email: " Wang@Example.com ",
  schoolId: 3,
  teacherName: " 王老師 ",
};

describe("newAccountRole", () => {
  it("lets the 系統管理員 create only 教學組長 accounts", () => {
    expect(newAccountRole("ADMIN")).toBe("COORDINATOR");
  });

  it("lets a 教學組長 create only 一般老師 accounts", () => {
    expect(newAccountRole("COORDINATOR")).toBe("TEACHER");
  });
});

describe("which fields the dialog asks for", () => {
  it("asks the 系統管理員 for a school and no name", () => {
    expect(needsSchoolChoice("ADMIN")).toBe(true);
    expect(needsTeacherName("ADMIN")).toBe(false);
  });

  it("asks a 教學組長 for a name and no school", () => {
    expect(needsSchoolChoice("COORDINATOR")).toBe(false);
    expect(needsTeacherName("COORDINATOR")).toBe(true);
  });
});

describe("isValidEmail", () => {
  it("accepts an address and rejects anything else", () => {
    expect(isValidEmail("a@b.tw")).toBe(true);
    expect(isValidEmail("  A@B.TW ")).toBe(true);
    expect(isValidEmail("ab.tw")).toBe(false);
    expect(isValidEmail("a@b")).toBe(false);
    expect(isValidEmail("a b@c.tw")).toBe(false);
  });
});

describe("getMissingFieldMessage", () => {
  it("is null for a complete draft", () => {
    expect(getMissingFieldMessage(COMPLETE, "ADMIN")).toBeNull();
    expect(getMissingFieldMessage(COMPLETE, "COORDINATOR")).toBeNull();
  });

  it("names the missing field", () => {
    expect(getMissingFieldMessage({ ...COMPLETE, schoolId: null }, "ADMIN")).toBe("請選擇所屬學校");
    expect(getMissingFieldMessage({ ...COMPLETE, email: " " }, "ADMIN")).toBe("請輸入 Email");
    expect(getMissingFieldMessage({ ...COMPLETE, email: "wang" }, "COORDINATOR")).toBe(EMAIL_FORMAT_MESSAGE);
    expect(getMissingFieldMessage({ ...COMPLETE, teacherName: " " }, "COORDINATOR")).toBe("請輸入教師姓名");
  });

  it("does not need what the actor's dialog doesn't show", () => {
    expect(getMissingFieldMessage({ ...COMPLETE, teacherName: "" }, "ADMIN")).toBeNull();
    expect(getMissingFieldMessage({ ...COMPLETE, schoolId: null }, "COORDINATOR")).toBeNull();
  });
});

describe("toAccountCreate", () => {
  it("sends the 系統管理員's school and email", () => {
    expect(toAccountCreate(COMPLETE, "ADMIN")).toEqual({ email: "wang@example.com", school_id: 3 });
  });

  it("sends the 教學組長's email and teacher name", () => {
    expect(toAccountCreate(COMPLETE, "COORDINATOR")).toEqual({
      email: "wang@example.com",
      teacher_name: "王老師",
    });
  });
});
