import { describe, expect, it } from "vitest";
import { selectableChoices, storedChoice, viewableChoices, type Choice } from "./choiceSelect";

const choices: Choice[] = [
  { id: 1, label: "王老師", isActive: true },
  { id: 2, label: "林老師", isActive: false },
  { id: 3, label: "陳老師", isActive: true },
];

describe("selectableChoices", () => {
  it("never offers a 停用 one", () => {
    expect(selectableChoices(choices).map((choice) => choice.id)).toEqual([1, 3]);
  });
});

describe("storedChoice", () => {
  it("is none without a saved value", () => {
    expect(storedChoice(null, choices)).toEqual({ kind: "none" });
  });

  it("keeps a saved 啟用 one", () => {
    expect(storedChoice(3, choices)).toEqual({ kind: "active", id: 3 });
  });

  it("asks to pick again when the saved one is 停用, naming it", () => {
    expect(storedChoice(2, choices)).toEqual({ kind: "reselect", hint: "原指定的「林老師」已停用" });
  });

  it("asks to pick again when the saved one is unknown", () => {
    expect(storedChoice(9, choices)).toEqual({ kind: "reselect", hint: "原指定的項目已停用" });
  });
});

describe("viewableChoices", () => {
  it("lists a 停用 one only when the record uses it, marked", () => {
    expect(viewableChoices(choices, new Set([2]))).toEqual([
      { id: 1, label: "王老師" },
      { id: 2, label: "林老師（已停用）" },
      { id: 3, label: "陳老師" },
    ]);
    expect(viewableChoices(choices, new Set()).map((choice) => choice.id)).toEqual([1, 3]);
  });
});
