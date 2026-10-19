import { useEffect, useId, useRef, type ReactElement, type ReactNode, type SyntheticEvent } from "react";
import { dialogKeyAction, enterKeyUpShouldActivate, isEnterKey } from "../utils/dialogKeyboard";
import {
  BUTTON_DANGER,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  DIALOG,
  DIALOG_TITLE,
  DIALOG_WIDE,
} from "../styles/ui";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  // The explanation, and any extra inputs (e.g. the copy dialog's target
  // semester choice) or an error message -- the dialog itself stays generic.
  children: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  // Red confirm button for an action the user should think twice about.
  danger?: boolean;
  // An action is in flight: both buttons are disabled and Esc does nothing,
  // so the same request can't be sent twice or abandoned half way.
  busy?: boolean;
  busyLabel?: string;
  // e.g. a required choice inside `children` hasn't been made yet.
  confirmDisabled?: boolean;
  // false = an information-only dialog: just the cancel button (label it
  // e.g. 「關閉」), nothing to confirm.
  showConfirm?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  // Task 85: where focus goes after closing when the element focused before
  // opening is gone or can't take focus (e.g. a button that was disabled
  // while the dialog's request ran). Without it focus stays where the
  // browser leaves it.
  restoreFocusFallback?: () => void;
  // Task 92A: the preview dialogs use a slightly wider dialog.
  wide?: boolean;
}

// Task 85: everything inside the dialog that Tab can reach, in order.
const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "a[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

// Back to the element focused before the dialog opened, if it still exists
// and can take focus; otherwise the caller's fallback.
function restoreFocus(previous: HTMLElement | null, fallback: (() => void) | undefined): void {
  if (previous !== null && previous !== document.body && previous.isConnected) {
    previous.focus();
    if (document.activeElement === previous) {
      return;
    }
  }
  fallback?.();
}

// Task 67: the shared confirmation dialog, replacing window.confirm() for
// the version-management actions (publish/unpublish/copy) -- unlike a
// native confirm it can stay open on failure, show the error inside, and
// hold form controls. Built on the browser's own <dialog> + showModal()
// (focus trapping, Esc, backdrop) rather than a UI library. Fully
// controlled: `open` is the only source of truth; Esc or 取消 just asks
// the parent to close it via onCancel.
export default function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = "確定",
  cancelLabel = "取消",
  danger = false,
  busy = false,
  busyLabel = "處理中…",
  confirmDisabled = false,
  showConfirm = true,
  onConfirm,
  onCancel,
  restoreFocusFallback,
  wide = false,
}: ConfirmDialogProps): ReactElement {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  // Task 85: the element focused just before opening, to return to.
  const previousFocusRef = useRef<HTMLElement | null>(null);
  // Read when the dialog closes, which may be renders after it opened.
  const restoreFocusFallbackRef = useRef(restoreFocusFallback);
  useEffect(() => {
    restoreFocusFallbackRef.current = restoreFocusFallback;
  }, [restoreFocusFallback]);
  // Several dialogs can be mounted on one page at once.
  const titleId = useId();

  // Task 70 fix: focus always starts on the safe 取消/返回 button, set
  // explicitly rather than left to showModal()'s "first focusable element"
  // (which is a radio button in the copy dialog, and would be any button a
  // dialog's content happens to contain). Enter then only ever activates
  // the button the user has focused; 確認 needs a click or Tab + Enter.
  //
  // Task 85: the element focused before opening is remembered and focused
  // again on close (or the caller's fallback). One tick after opening,
  // focus is checked again and pulled back to 取消/返回 if anything moved it
  // out of the dialog meanwhile (e.g. a browser settling focus after a drag
  // and drop) -- the dialog never opens with focus outside it.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) {
      return;
    }
    if (open && !dialog.open) {
      previousFocusRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
      cancelButtonRef.current?.focus();
      const timer = window.setTimeout(() => {
        if (dialog.open && !dialog.contains(document.activeElement)) {
          cancelButtonRef.current?.focus();
        }
      }, 0);
      return () => window.clearTimeout(timer);
    }
    if (!open && dialog.open) {
      dialog.close();
      restoreFocus(previousFocusRef.current, restoreFocusFallbackRef.current);
      previousFocusRef.current = null;
    }
    return undefined;
  }, [open]);

  // Task 86: a parent may unmount the dialog while it is still open instead
  // of closing it first (e.g. deleting a version removes the version card
  // that holds its dialogs). Focus is returned the same way then.
  useEffect(() => {
    const previousFocus = previousFocusRef;
    const fallback = restoreFocusFallbackRef;
    return () => {
      if (previousFocus.current !== null) {
        restoreFocus(previousFocus.current, fallback.current);
        previousFocus.current = null;
      }
    };
  }, []);

  // Task 85: every key while open is decided by dialogKeyAction(), whatever
  // has focus -- Esc is 取消/返回 (and never reaches the page's own Esc
  // handling, e.g. the timetable's "deselect"), Enter only ever activates
  // the focused button (a held, auto-repeating Enter is ignored), and Tab /
  // Shift+Tab cycle inside the dialog instead of leaving it. Listening on
  // window in the capture phase so nothing on the page sees these keys
  // first.
  //
  // Task 86: an Enter on a focused button is never prevented -- the
  // browser's own activation runs. Since an IME-processed Enter produces no
  // keypress (so no activation), the press is watched: if no click reached
  // that button by keyup, it is pressed then, once. The Enter that OPENED
  // the dialog went down before these listeners existed, so it is never
  // watched and its keyup does nothing.
  useEffect(() => {
    if (!open) {
      return undefined;
    }
    let watched: { button: HTMLButtonElement; clicked: boolean } | null = null;

    function handleKeyDown(event: KeyboardEvent): void {
      const dialog = dialogRef.current;
      if (dialog === null || !dialog.open) {
        return;
      }
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      const active = document.activeElement;
      const action = dialogKeyAction({
        key: event.key,
        code: event.code,
        shiftKey: event.shiftKey,
        repeat: event.repeat,
        isComposing: event.isComposing,
        focusIndex: focusable.findIndex((element) => element === active),
        focusableCount: focusable.length,
        cancelIndex: Math.max(
          0,
          focusable.findIndex((element) => element === cancelButtonRef.current),
        ),
        focusIsButton: active instanceof HTMLButtonElement,
        busy,
      });
      if (action.preventDefault) {
        event.preventDefault();
      }
      if (action.stopPropagation) {
        event.stopPropagation();
      }
      if (action.watchActivation && active instanceof HTMLButtonElement) {
        watched = { button: active, clicked: false };
      }
      if (action.effect.type === "cancel") {
        onCancel();
      } else if (action.effect.type === "focus") {
        focusable[action.effect.index]?.focus();
      }
    }

    function handleClick(event: MouseEvent): void {
      if (watched !== null && event.target instanceof Node && watched.button.contains(event.target)) {
        watched.clicked = true;
      }
    }

    function handleKeyUp(event: KeyboardEvent): void {
      if (watched === null || !isEnterKey(event.key, event.code)) {
        return;
      }
      const { button, clicked } = watched;
      watched = null;
      const dialog = dialogRef.current;
      if (
        enterKeyUpShouldActivate({
          clicked,
          stillInDialog: dialog !== null && dialog.open && dialog.contains(button),
          disabled: button.disabled,
        })
      ) {
        button.click();
      }
    }

    window.addEventListener("keydown", handleKeyDown, true);
    window.addEventListener("click", handleClick, true);
    window.addEventListener("keyup", handleKeyUp, true);
    return () => {
      window.removeEventListener("keydown", handleKeyDown, true);
      window.removeEventListener("click", handleClick, true);
      window.removeEventListener("keyup", handleKeyUp, true);
    };
  }, [open, busy, onCancel]);

  // While busy both buttons are disabled, which drops focus to <body>. If
  // the action then fails and the dialog stays open, put focus back on the
  // safe button instead of leaving it outside the dialog's content.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null || !open || busy || !dialog.open) {
      return;
    }
    if (!dialog.contains(document.activeElement)) {
      cancelButtonRef.current?.focus();
    }
  }, [open, busy]);

  // (Task 70 fix, now part of dialogKeyAction(): an Enter held down from the
  // button that OPENED this dialog keeps auto-repeating, and the first
  // repeat would hit the freshly focused 取消/返回 -- so a repeated Enter is
  // ignored; a fresh Enter press works as usual.)

  // Esc normally never gets here any more (the keydown handler above takes
  // it first), but the browser can still raise "cancel" on its own (e.g. a
  // close request from the OS). Prevent that
  // close so `open` stays the only thing that decides visibility, then hand
  // the decision to the parent.
  function handleCancelEvent(event: SyntheticEvent<HTMLDialogElement>): void {
    event.preventDefault();
    if (!busy) {
      onCancel();
    }
  }

  // Some browsers close the dialog on a repeated Esc even when "cancel" was
  // prevented. If that happens while the parent still has it open, keep the
  // two in sync: reopen during a busy action, otherwise treat it as 取消.
  function handleCloseEvent(): void {
    if (!open) {
      return;
    }
    if (busy) {
      dialogRef.current?.showModal();
    } else {
      onCancel();
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onCancel={handleCancelEvent}
      onClose={handleCloseEvent}
      aria-labelledby={titleId}
      className={wide ? DIALOG_WIDE : DIALOG}
    >
      {/* Content only while open: a closed <dialog> is hidden anyway, and
          this keeps its inputs out of the page's tab order and DOM. */}
      {open && (
        <div className="flex flex-col gap-4 p-5">
          <h2 id={titleId} className={DIALOG_TITLE}>
            {title}
          </h2>
          <div className="flex flex-col gap-2 text-sm text-gray-700">{children}</div>
          <div className="flex justify-end gap-2">
            <button
              ref={cancelButtonRef}
              type="button"
              onClick={onCancel}
              disabled={busy}
              className={BUTTON_SECONDARY}
            >
              {cancelLabel}
            </button>
            {showConfirm && (
              <button
                type="button"
                onClick={onConfirm}
                disabled={busy || confirmDisabled}
                className={danger ? BUTTON_DANGER : BUTTON_PRIMARY}
              >
                {busy ? busyLabel : confirmLabel}
              </button>
            )}
          </div>
        </div>
      )}
    </dialog>
  );
}
