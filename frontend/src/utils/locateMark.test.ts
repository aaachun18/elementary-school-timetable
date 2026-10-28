import { describe, expect, it } from "vitest";
import { visibleLocateSlot, type LocateContext, type LocateMark } from "./locateMark";
import { violationIdentityKey } from "./violationMerge";
import type { ConstraintViolationDetail } from "../types/scheduler";

const KEY = "TEACHER_CONFLICT:30:31";

function violation(identityKey: string): ConstraintViolationDetail {
  return {
    type: "TEACHER_CONFLICT",
    severity: "ERROR",
    lesson_id: 30,
    teacher_id: 6,
    class_id: 1,
    subject_id: 5,
    time_slot_id: 12,
    message: "",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: 9,
    identity_key: identityKey,
  };
}

// Located while editing working copy 50, class 1's grid, cell 12.
const mark: LocateMark = {
  timeSlotId: 12,
  // As the page stores it (handleLocate).
  problemKey: violationIdentityKey(violation(KEY)),
  versionId: 50,
  isEditing: true,
  viewMode: "class",
  targetId: 1,
};
const editing: LocateContext = { versionId: 50, isEditing: true, viewMode: "class", targetId: 1 };

describe("visibleLocateSlot", () => {
  it("marks the cell while the problem is still there", () => {
    expect(visibleLocateSlot(mark, editing, [violation(KEY)])).toBe(12);
  });

  it("keeps the mark while there is no check result yet (same view)", () => {
    expect(visibleLocateSlot(mark, editing, null)).toBe(12);
  });

  it("hides it once a newer check no longer has the problem", () => {
    expect(visibleLocateSlot(mark, editing, [])).toBeNull();
    expect(visibleLocateSlot(mark, editing, [violation("ROOM_CONFLICT:7")])).toBeNull();
  });

  it("hides it after saving: another record, no longer editing, no result yet", () => {
    expect(visibleLocateSlot(mark, { ...editing, versionId: 42, isEditing: false }, null)).toBeNull();
  });

  it("hides it after saving over the same record (manual overwrite)", () => {
    // The working copy (50) is gone; the page shows the saved record (42).
    expect(visibleLocateSlot(mark, { ...editing, versionId: 42, isEditing: false }, [violation(KEY)])).toBeNull();
  });

  it("hides it on switching record", () => {
    expect(visibleLocateSlot(mark, { ...editing, versionId: 51 }, null)).toBeNull();
  });

  it("hides it on leaving edit mode, even with the problem still listed", () => {
    expect(visibleLocateSlot(mark, { ...editing, isEditing: false }, [violation(KEY)])).toBeNull();
  });

  it("hides it on switching class, teacher or room", () => {
    expect(visibleLocateSlot(mark, { ...editing, targetId: 2 }, [violation(KEY)])).toBeNull();
    expect(visibleLocateSlot(mark, { ...editing, viewMode: "teacher", targetId: 1 }, null)).toBeNull();
    expect(visibleLocateSlot(mark, { ...editing, targetId: null }, null)).toBeNull();
  });

  it("works the same in the view mode", () => {
    const viewMark: LocateMark = { ...mark, versionId: 42, isEditing: false };
    const viewing: LocateContext = { ...editing, versionId: 42, isEditing: false };
    expect(visibleLocateSlot(viewMark, viewing, [violation(KEY)])).toBe(12);
    expect(visibleLocateSlot(viewMark, viewing, [])).toBeNull();
  });

  it("shows nothing without a mark", () => {
    expect(visibleLocateSlot(null, editing, [violation(KEY)])).toBeNull();
  });
});
