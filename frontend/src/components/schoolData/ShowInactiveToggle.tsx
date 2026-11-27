import type { ReactElement } from "react";
import { SHOW_INACTIVE_LABEL } from "../../utils/deactivation";
import { CHECKBOX } from "../../styles/ui";

// Task 102: 學校資料's 班級 / 科目 / 教室 lists' one filter -- 「顯示已停用」
// plus the list's own noun (「顯示已停用班級」), in the toolbar above the
// table, off by default (已停用 rows hidden).
export default function ShowInactiveToggle({
  checked,
  onChange,
  noun,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  // What the list holds: 班級, 科目 or 教室.
  noun: string;
}): ReactElement {
  return (
    <label className="flex min-h-8 items-center gap-2 text-sm text-gray-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className={CHECKBOX}
      />
      {SHOW_INACTIVE_LABEL}
      {noun}
    </label>
  );
}
