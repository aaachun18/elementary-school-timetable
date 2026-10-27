import type { ReactElement } from "react";
import { TrashIcon } from "./icons";
import { ICON_BUTTON_DELETE } from "../styles/ui";

// Task 98 Phase B: a row's 「刪除」 -- a trash IconButton, always shown,
// neutral gray (red only under the pointer). `label` names the row
// (「刪除班級「一年甲班」」, utils/confirmText.ts) and is both the accessible
// name and the tooltip. When the row can't be deleted, `disabledReason`
// says why: the tooltip shows it and the accessible name carries it.
// The click only opens the confirmation; the caller asks first.
export default function DeleteIconButton({
  label,
  onClick,
  disabled = false,
  disabledReason = null,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  disabledReason?: string | null;
}): ReactElement {
  const text = disabledReason === null ? label : `${label}（${disabledReason}）`;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || disabledReason !== null}
      aria-label={text}
      title={disabledReason ?? label}
      className={ICON_BUTTON_DELETE}
    >
      <TrashIcon />
    </button>
  );
}
