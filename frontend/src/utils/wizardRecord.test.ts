import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  forgetWizardRecord,
  readRememberedWizardRecord,
  readRememberedWizardStep,
  rememberWizardRecord,
  rememberWizardStep,
} from "./wizardRecord";

function memoryStorage(): Storage {
  const items = new Map<string, string>();
  return {
    get length() {
      return items.size;
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => {
      items.delete(key);
    },
    setItem: (key, value) => {
      items.set(key, value);
    },
  };
}

describe("wizardRecord", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("remembers the record and the step it was on", () => {
    rememberWizardRecord(7);
    rememberWizardStep("requirements");

    expect(readRememberedWizardRecord()).toBe(7);
    expect(readRememberedWizardStep()).toBe("requirements");
  });

  it("keeps the step when the same record is remembered again", () => {
    rememberWizardRecord(7);
    rememberWizardStep("grades");
    rememberWizardRecord(7);

    expect(readRememberedWizardStep()).toBe("grades");
  });

  it("drops the step when another record is remembered", () => {
    rememberWizardRecord(7);
    rememberWizardStep("grades");
    rememberWizardRecord(8);

    expect(readRememberedWizardRecord()).toBe(8);
    expect(readRememberedWizardStep()).toBeNull();
  });

  it("forgets both", () => {
    rememberWizardRecord(7);
    rememberWizardStep("run");
    forgetWizardRecord();

    expect(readRememberedWizardRecord()).toBeNull();
    expect(readRememberedWizardStep()).toBeNull();
  });

  it("reads nothing when storage is unavailable", () => {
    vi.stubGlobal("localStorage", undefined);

    rememberWizardRecord(7);

    expect(readRememberedWizardRecord()).toBeNull();
    expect(readRememberedWizardStep()).toBeNull();
  });
});
