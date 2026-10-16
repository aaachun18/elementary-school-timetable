import { describe, expect, it } from "vitest";
import {
  dialogKeyAction,
  enterKeyUpShouldActivate,
  isEnterKey,
  type DialogKeyInput,
} from "./dialogKeyboard";

// Task 85 / Task 86: ConfirmDialog's keyboard rules. Two focusable
// buttons, as in the move/swap preview: 返回 (index 0) and 確認 (index 1).
function input(fields: Partial<DialogKeyInput>): DialogKeyInput {
  return {
    key: "Enter",
    code: "Enter",
    shiftKey: false,
    repeat: false,
    isComposing: false,
    focusIndex: 0,
    focusableCount: 2,
    cancelIndex: 0,
    focusIsButton: true,
    busy: false,
    ...fields,
  };
}

describe("Enter on a focused button", () => {
  it("is never prevented: the browser activates the button itself", () => {
    for (const focusIndex of [0, 1]) {
      expect(dialogKeyAction(input({ key: "Enter", focusIndex }))).toEqual({
        effect: { type: "none" },
        preventDefault: false,
        stopPropagation: false,
        watchActivation: true,
      });
    }
  });

  it("is recognised by its physical key when an IME processed it (key \"Process\")", () => {
    const action = dialogKeyAction(input({ key: "Process", code: "Enter" }));

    expect(action.preventDefault).toBe(false);
    // No keypress follows an IME-processed Enter, so the press is watched
    // and the button is pressed on keyup if the browser didn't.
    expect(action.watchActivation).toBe(true);
  });

  it("treats the numpad Enter the same way", () => {
    expect(dialogKeyAction(input({ key: "Enter", code: "NumpadEnter" })).watchActivation).toBe(true);
  });

  it("isn't watched on a focused element that isn't a button (e.g. a radio)", () => {
    expect(dialogKeyAction(input({ focusIsButton: false }))).toEqual({
      effect: { type: "none" },
      preventDefault: false,
      stopPropagation: false,
      watchActivation: false,
    });
  });
});

describe("Enter that must not act", () => {
  it("ignores an auto-repeating Enter (the one that opened the dialog, still held)", () => {
    for (const focusIndex of [0, -1]) {
      expect(dialogKeyAction(input({ repeat: true, focusIndex }))).toEqual({
        effect: { type: "none" },
        preventDefault: true,
        stopPropagation: true,
        watchActivation: false,
      });
    }
  });

  it("with focus outside the dialog only brings focus back to 返回 (and is prevented)", () => {
    expect(dialogKeyAction(input({ focusIndex: -1, focusIsButton: false }))).toEqual({
      effect: { type: "focus", index: 0 },
      preventDefault: true,
      stopPropagation: true,
      watchActivation: false,
    });
    // 返回 isn't always first (e.g. a dialog whose content has a radio group).
    expect(dialogKeyAction(input({ focusIndex: -1, focusableCount: 4, cancelIndex: 2 })).effect).toEqual({
      type: "focus",
      index: 2,
    });
  });

  it("does nothing when nothing in the dialog can take focus", () => {
    expect(dialogKeyAction(input({ focusIndex: -1, focusableCount: 0 }))).toMatchObject({
      effect: { type: "none" },
      preventDefault: true,
    });
  });

  it("leaves a key to the IME while text is being composed", () => {
    expect(dialogKeyAction(input({ isComposing: true }))).toEqual({
      effect: { type: "none" },
      preventDefault: false,
      stopPropagation: false,
      watchActivation: false,
    });
  });
});

describe("enterKeyUpShouldActivate (pressing the button on keyup)", () => {
  it("presses it only when no click reached it", () => {
    expect(enterKeyUpShouldActivate({ clicked: false, stillInDialog: true, disabled: false })).toBe(true);
    // A normal Enter: the browser already clicked -- never twice.
    expect(enterKeyUpShouldActivate({ clicked: true, stillInDialog: true, disabled: false })).toBe(false);
  });

  it("doesn't press a button that is gone or disabled", () => {
    expect(enterKeyUpShouldActivate({ clicked: false, stillInDialog: false, disabled: false })).toBe(false);
    expect(enterKeyUpShouldActivate({ clicked: false, stillInDialog: true, disabled: true })).toBe(false);
  });
});

describe("Esc", () => {
  it("is 返回 wherever focus is, and stops at the dialog", () => {
    for (const focusIndex of [0, 1, -1]) {
      expect(dialogKeyAction(input({ key: "Escape", code: "Escape", focusIndex }))).toEqual({
        effect: { type: "cancel" },
        preventDefault: true,
        stopPropagation: true,
        watchActivation: false,
      });
    }
  });

  it("is swallowed while an action is in flight", () => {
    expect(dialogKeyAction(input({ key: "Escape", code: "Escape", busy: true }))).toEqual({
      effect: { type: "none" },
      preventDefault: true,
      stopPropagation: true,
      watchActivation: false,
    });
  });
});

describe("Tab / Shift+Tab stay inside the dialog", () => {
  const tab = (fields: Partial<DialogKeyInput>) =>
    dialogKeyAction(input({ key: "Tab", code: "Tab", ...fields }));

  it("wraps from the last element to the first", () => {
    expect(tab({ focusIndex: 1 })).toEqual({
      effect: { type: "focus", index: 0 },
      preventDefault: true,
      stopPropagation: true,
      watchActivation: false,
    });
  });

  it("wraps from the first element to the last with Shift", () => {
    expect(tab({ shiftKey: true, focusIndex: 0 }).effect).toEqual({ type: "focus", index: 1 });
  });

  it("moves natively between elements in the middle (not prevented)", () => {
    expect(tab({ focusIndex: 0 })).toEqual({
      effect: { type: "none" },
      preventDefault: false,
      stopPropagation: true,
      watchActivation: false,
    });
    expect(tab({ shiftKey: true, focusIndex: 2, focusableCount: 4 }).preventDefault).toBe(false);
  });

  it("brings focus back in from outside", () => {
    expect(tab({ focusIndex: -1 }).effect).toEqual({ type: "focus", index: 0 });
    expect(tab({ shiftKey: true, focusIndex: -1 }).effect).toEqual({ type: "focus", index: 1 });
  });

  it("is swallowed when nothing can take focus (e.g. both buttons disabled while busy)", () => {
    expect(tab({ focusIndex: -1, focusableCount: 0, busy: true })).toMatchObject({
      effect: { type: "none" },
      preventDefault: true,
    });
  });
});

describe("other keys", () => {
  it("are left alone (e.g. Space activates the focused button natively on keyup)", () => {
    for (const [key, code] of [[" ", "Space"], ["ArrowDown", "ArrowDown"]]) {
      expect(dialogKeyAction(input({ key, code }))).toEqual({
        effect: { type: "none" },
        preventDefault: false,
        stopPropagation: false,
        watchActivation: false,
      });
    }
  });

  it("isEnterKey matches Enter by key or by physical key", () => {
    expect(isEnterKey("Enter", "Enter")).toBe(true);
    expect(isEnterKey("Process", "Enter")).toBe(true);
    expect(isEnterKey("Enter", "NumpadEnter")).toBe(true);
    expect(isEnterKey("Process", "KeyA")).toBe(false);
    expect(isEnterKey(" ", "Space")).toBe(false);
  });
});
