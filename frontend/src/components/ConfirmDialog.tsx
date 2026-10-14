import { useEffect, useId, useRef, type ReactElement, type ReactNode, type SyntheticEvent } from "react";
import {
  BUTTON_DANGER,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  DIALOG,
  DIALOG_TITLE,
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
  onConfirm: () => void;
  onCancel: () => void;
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
  onConfirm,
  onCancel,
}: ConfirmDialogProps): ReactElement {
  const dialogRef = useRef<HTMLDialogElement>(null);
  // Several dialogs can be mounted on one page at once.
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  // Esc fires "cancel" before the browser closes the dialog. Prevent that
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
      className={DIALOG}
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
            <button type="button" onClick={onCancel} disabled={busy} className={BUTTON_SECONDARY}>
              {cancelLabel}
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={busy || confirmDisabled}
              className={danger ? BUTTON_DANGER : BUTTON_PRIMARY}
            >
              {busy ? busyLabel : confirmLabel}
            </button>
          </div>
        </div>
      )}
    </dialog>
  );
}
