import { useCallback, useRef, useState, type ReactElement } from "react";
import ConfirmDialog, { type ConfirmTone } from "../components/ConfirmDialog";

export interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmTone;
}

export interface ConfirmApi {
  // Opens the dialog; resolves true on 確定, false on 取消 / Esc.
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  // Render this once in the page / component that calls confirm().
  dialog: ReactElement;
}

// The usual 「刪除」 question.
export function deleteConfirmOptions(name: string): ConfirmOptions {
  return {
    title: "確認刪除",
    message: `確定要刪除「${name}」嗎？此操作無法復原。`,
    confirmLabel: "刪除",
    tone: "danger",
  };
}

// A drop-in for window.confirm(): the system's own centered ConfirmDialog
// instead of the browser's native box, still awaited like a boolean --
// `if (!(await confirm({ message }))) return;`.
export function useConfirm(): ConfirmApi {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const resolveRef = useRef<((answer: boolean) => void) | null>(null);

  const confirm = useCallback((next: ConfirmOptions): Promise<boolean> => {
    // A confirm still open (shouldn't happen) is answered 取消 first.
    resolveRef.current?.(false);
    setOptions(next);
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  const answer = useCallback((value: boolean): void => {
    resolveRef.current?.(value);
    resolveRef.current = null;
    setOptions(null);
  }, []);

  const handleConfirm = useCallback(() => answer(true), [answer]);
  const handleCancel = useCallback(() => answer(false), [answer]);

  const dialog = (
    <ConfirmDialog
      open={options !== null}
      title={options?.title ?? "請確認"}
      confirmLabel={options?.confirmLabel}
      cancelLabel={options?.cancelLabel}
      tone={options?.tone ?? "primary"}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    >
      <p>{options?.message}</p>
    </ConfirmDialog>
  );

  return { confirm, dialog };
}
