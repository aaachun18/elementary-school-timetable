// A picking dropdown (精靈 科目需求's 指定老師 / 特殊教室, 共同排課's 教室):
// 停用 teachers and rooms are never offered. When the value already saved
// is a 停用 one, the closed dropdown says 「請重新選擇」 (amber) with one
// line below naming what was saved -- until another choice (or none) is
// made. Pure, no React (choiceSelect.test.ts; components/ChoiceSelect.tsx).

export interface Choice {
  id: number;
  label: string;
  isActive: boolean;
}

export const RESELECT_LABEL = "請重新選擇";

export type StoredChoice =
  | { kind: "none" }
  | { kind: "active"; id: number }
  // The saved one is 停用 (or no longer exists): pick again.
  | { kind: "reselect"; hint: string };

// The options shown: 啟用 ones only, in the given order.
export function selectableChoices(choices: readonly Choice[]): Choice[] {
  return choices.filter((choice) => choice.isActive);
}

export function storedChoice(storedId: number | null, choices: readonly Choice[]): StoredChoice {
  if (storedId === null) {
    return { kind: "none" };
  }
  const stored = choices.find((choice) => choice.id === storedId);
  if (stored !== undefined && stored.isActive) {
    return { kind: "active", id: storedId };
  }
  const name = stored === undefined ? "" : `「${stored.label}」`;
  return { kind: "reselect", hint: `原指定的${name === "" ? "項目" : name}已停用` };
}

// Task 102: the timetable's 依班級 / 依教師 / 依教室 pickers only show a
// record, they pick nothing: a 停用 one is listed only when this record's
// timetable uses it, marked 「（已停用）」, so an old timetable can still be
// seen from its side. Other 停用 ones are left out.
export const INACTIVE_MARK = "（已停用）";

export function viewableChoices(
  choices: readonly Choice[],
  usedIds: ReadonlySet<number>,
): { id: number; label: string }[] {
  return choices
    .filter((choice) => choice.isActive || usedIds.has(choice.id))
    .map((choice) => ({ id: choice.id, label: choice.isActive ? choice.label : `${choice.label}${INACTIVE_MARK}` }));
}
