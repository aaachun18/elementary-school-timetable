import type { ReactElement } from "react";
import { PencilIcon } from "./icons";
import { ICON_BUTTON } from "../styles/ui";

// Task 100: a row's 「編輯」 -- a pencil IconButton, neutral gray (darker
// with a light gray square under the pointer), the sibling of
// DeleteIconButton. `label` names the row (「編輯國語文」「編輯 teacher01」)
// and is both the accessible name and the tooltip.
export default function EditIconButton({
  label,
  onClick,
  disabled = false,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}): ReactElement {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={label} title={label} className={ICON_BUTTON}>
      <PencilIcon />
    </button>
  );
}
