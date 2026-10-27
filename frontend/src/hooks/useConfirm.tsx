import { useCallback, useRef, useState, type ReactElement } from "react";
import ConfirmDialog from "../components/ConfirmDialog";
import type { ConfirmText } from "../utils/confirmText";

// Task 98 Phase B: every confirmation names its title and both buttons
// (utils/confirmText.ts has the 「刪除…」 ones).
export type ConfirmOptions = ConfirmText;

export interface ConfirmApi {
  // Opens the dialog; resolves true on the confirm button, false on the
  // cancel button / Esc.
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  // Render this once in the page / component that calls confirm().
  dialog: ReactElement;
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
      title={options?.title ?? ""}
      confirmLabel={options?.confirmLabel ?? ""}
      cancelLabel={options?.cancelLabel ?? ""}
      tone={options?.tone ?? "primary"}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    >
      <p>{options?.message}</p>
    </ConfirmDialog>
  );

  return { confirm, dialog };
}
