import { describe, expect, it } from "vitest";
import { inlineEditKeyAction } from "./inlineEdit";

describe("inlineEditKeyAction", () => {
  it("saves on Enter and cancels on Esc in a field", () => {
    expect(inlineEditKeyAction("Enter", "Enter", "INPUT", false)).toBe("save");
    expect(inlineEditKeyAction("Enter", "NumpadEnter", "SELECT", false)).toBe("save");
    expect(inlineEditKeyAction("Escape", "Escape", "INPUT", false)).toBe("cancel");
    expect(inlineEditKeyAction("a", "KeyA", "INPUT", false)).toBeNull();
  });

  it("knows an IME-processed Enter by its code", () => {
    expect(inlineEditKeyAction("Process", "Enter", "INPUT", false)).toBe("save");
  });

  it("ignores the Enter that ends an IME composition", () => {
    expect(inlineEditKeyAction("Process", "Enter", "INPUT", true)).toBeNull();
    expect(inlineEditKeyAction("Enter", "Enter", "INPUT", true)).toBeNull();
  });

  it("leaves the row's buttons alone", () => {
    expect(inlineEditKeyAction("Enter", "Enter", "BUTTON", false)).toBeNull();
    expect(inlineEditKeyAction("Escape", "Escape", "BUTTON", false)).toBeNull();
  });
});
