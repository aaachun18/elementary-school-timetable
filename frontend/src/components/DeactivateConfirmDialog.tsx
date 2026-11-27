import { useEffect, useState, type ReactElement } from "react";
import ConfirmDialog from "./ConfirmDialog";
import {
  deactivateDialogText,
  type DeactivationImpact,
  type DeactivationKind,
  type ImpactState,
} from "../utils/deactivation";
import { CANCEL_LABEL } from "../utils/confirmText";
import { MUTED_TEXT } from "../styles/ui";

// 停用 of an account, a subject, a room or a class -- one dialog for all
// four: the rule, then at most two lines from loadImpact()'s counts
// (utils/deactivation.ts deactivateDialogText; 計算中… while they load,
// 無法取得影響範圍 if they can't be read -- 停用 still works). Buttons
// [取消][停用]. 啟用 never asks.
export default function DeactivateConfirmDialog({
  kind,
  name,
  loadImpact,
  busy = false,
  onConfirm,
  onCancel,
}: {
  kind: DeactivationKind;
  name: string;
  loadImpact: () => Promise<DeactivationImpact>;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}): ReactElement {
  const [state, setState] = useState<ImpactState>({ status: "loading" });

  useEffect(() => {
    let isCurrent = true;
    loadImpact()
      .then((impact) => {
        if (isCurrent) {
          setState({ status: "ready", impact });
        }
      })
      .catch(() => {
        if (isCurrent) {
          setState({ status: "failed" });
        }
      });
    return () => {
      isCurrent = false;
    };
    // Loaded once per opened dialog (the caller mounts it to open it).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const text = deactivateDialogText(kind, name, state);
  return (
    <ConfirmDialog
      open
      title={text.title}
      confirmLabel={text.confirmLabel}
      cancelLabel={CANCEL_LABEL}
      tone="danger"
      busy={busy}
      busyLabel="停用中…"
      onConfirm={onConfirm}
      onCancel={onCancel}
    >
      {text.lines.map((line, index) => (
        <p key={line} className={index === 0 ? undefined : `${MUTED_TEXT} mt-1`}>
          {line}
        </p>
      ))}
    </ConfirmDialog>
  );
}
