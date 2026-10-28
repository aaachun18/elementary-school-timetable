import type { ReactElement } from "react";
import { RESELECT_LABEL, selectableChoices, storedChoice, type Choice } from "../utils/choiceSelect";
import { CHOICE_HINT, SELECT, SELECT_RESELECT } from "../styles/ui";

const RESELECT_VALUE = "__reselect__";

// A picking dropdown that never offers a 停用 teacher / room
// (utils/choiceSelect.ts). A saved 停用 value shows 「請重新選擇」 in amber,
// with 「原指定的「X」已停用」 below, until something else is picked.
export default function ChoiceSelect({
  value,
  choices,
  noneLabel,
  onChange,
  ariaLabel,
  disabled = false,
}: {
  value: number | null;
  choices: readonly Choice[];
  // The first option, meaning "nothing picked" (不指定, 原班教室...).
  noneLabel: string;
  onChange: (id: number | null) => void;
  ariaLabel: string;
  disabled?: boolean;
}): ReactElement {
  const stored = storedChoice(value, choices);
  const isReselect = stored.kind === "reselect";
  const selectValue = stored.kind === "active" ? String(stored.id) : isReselect ? RESELECT_VALUE : "";
  return (
    <div>
      <select
        value={selectValue}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-invalid={isReselect || undefined}
        className={`${isReselect ? SELECT_RESELECT : SELECT} w-full`}
      >
        {isReselect && (
          <option value={RESELECT_VALUE} disabled>
            {RESELECT_LABEL}
          </option>
        )}
        <option value="">{noneLabel}</option>
        {selectableChoices(choices).map((choice) => (
          <option key={choice.id} value={choice.id}>
            {choice.label}
          </option>
        ))}
      </select>
      {stored.kind === "reselect" && <p className={CHOICE_HINT}>{stored.hint}</p>}
    </div>
  );
}
