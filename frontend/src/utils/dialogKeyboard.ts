// Task 85 / Task 86: what a key press means while a ConfirmDialog is open.
// Pure, so the rules are tested without a browser; components/
// ConfirmDialog.tsx applies the result to the DOM -- including whether the
// event's default action is prevented.
//
// Task 85: the modal <dialog> trapped nothing itself -- Tab from its last
// button left the page, after which Enter / Esc did nothing. Every key is
// now decided here, whatever element has focus.
//
// Task 86: Enter on a focused button must keep the browser's own
// activation (never preventDefault). But Chromium activates a button on the
// Enter KEYPRESS, and an Enter an IME (e.g. Microsoft Bopomofo) processed
// arrives as keydown key "Process" / keyCode 229 with no keypress at all --
// the button was never pressed, while Esc and Tab (not processed) worked.
// So Enter is recognised by `code` too, and if no click reached the focused
// button by the time Enter is released, it is pressed then, once.

export interface DialogKeyInput {
  key: string;
  // The physical key: still "Enter" / "NumpadEnter" when an IME processed
  // the press and `key` is "Process".
  code: string;
  shiftKey: boolean;
  // A key held down auto-repeats; a repeated Enter is never a deliberate
  // choice inside the dialog (it is the Enter that OPENED it, still held).
  repeat: boolean;
  // Text is being composed (e.g. typing Chinese in an input): the IME owns
  // the key.
  isComposing: boolean;
  // Index of the focused element among the dialog's focusable elements, or
  // -1 when focus is outside the dialog (e.g. <body>).
  focusIndex: number;
  focusableCount: number;
  // Index of the 取消/返回 button among the focusable elements.
  cancelIndex: number;
  // The focused element is a <button> (only buttons are activated by Enter).
  focusIsButton: boolean;
  // An action is in flight: Esc must not abandon it.
  busy: boolean;
}

export type DialogKeyEffect =
  | { type: "none" }
  // Same as pressing 取消/返回.
  | { type: "cancel" }
  // Move focus to this focusable element.
  | { type: "focus"; index: number };

export interface DialogKeyAction {
  effect: DialogKeyEffect;
  // Cancel the browser's default action for the key. NEVER true for an
  // Enter on a focused button: the browser's own activation must run.
  preventDefault: boolean;
  // Keep the key from the page's own handlers (e.g. the timetable's Esc).
  stopPropagation: boolean;
  // This is an Enter on a focused button: watch whether a click reaches
  // it, and press it on keyup if none did (see enterKeyUpShouldActivate).
  watchActivation: boolean;
}

const LEAVE_TO_BROWSER: DialogKeyAction = {
  effect: { type: "none" },
  preventDefault: false,
  stopPropagation: false,
  watchActivation: false,
};

const SWALLOW: DialogKeyAction = {
  effect: { type: "none" },
  preventDefault: true,
  stopPropagation: true,
  watchActivation: false,
};

export function isEnterKey(key: string, code: string): boolean {
  return key === "Enter" || code === "Enter" || code === "NumpadEnter";
}

function isEscapeKey(key: string, code: string): boolean {
  return key === "Escape" || code === "Escape";
}

export function dialogKeyAction(input: DialogKeyInput): DialogKeyAction {
  const { key, code, shiftKey, repeat, isComposing, focusIndex, focusableCount, cancelIndex } =
    input;

  if (isComposing) {
    return LEAVE_TO_BROWSER;
  }

  if (isEscapeKey(key, code)) {
    return input.busy
      ? SWALLOW
      : { effect: { type: "cancel" }, preventDefault: true, stopPropagation: true, watchActivation: false };
  }

  if (isEnterKey(key, code)) {
    if (repeat) {
      return SWALLOW;
    }
    // Focus somewhere outside: Enter must not do anything by accident --
    // bring focus back to the safe button instead.
    if (focusIndex === -1) {
      return focusableCount > 0
        ? { effect: { type: "focus", index: cancelIndex }, preventDefault: true, stopPropagation: true, watchActivation: false }
        : SWALLOW;
    }
    // On a focused element inside the dialog: the browser activates it.
    return { ...LEAVE_TO_BROWSER, watchActivation: input.focusIsButton };
  }

  if (key === "Tab") {
    if (focusableCount === 0) {
      return SWALLOW;
    }
    const last = focusableCount - 1;
    let target: number | null = null;
    if (focusIndex === -1) {
      target = shiftKey ? last : 0;
    } else if (shiftKey && focusIndex === 0) {
      target = last;
    } else if (!shiftKey && focusIndex === last) {
      target = 0;
    }
    return target === null
      ? { ...LEAVE_TO_BROWSER, stopPropagation: true }
      : { effect: { type: "focus", index: target }, preventDefault: true, stopPropagation: true, watchActivation: false };
  }

  return LEAVE_TO_BROWSER;
}

// On releasing the watched Enter: press the button ourselves only if the
// browser never did (no click reached it) and it can still be pressed.
// Never twice: a normal Enter's native click already counts.
export function enterKeyUpShouldActivate(watch: {
  clicked: boolean;
  stillInDialog: boolean;
  disabled: boolean;
}): boolean {
  return !watch.clicked && watch.stillInDialog && !watch.disabled;
}
