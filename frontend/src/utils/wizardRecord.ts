// v3: the 排課紀錄 the wizard is filling, and the step it was on -- so
// leaving 開始排課 for another page and coming back resumes right there,
// and a link straight to one step (?step=teachers, from a failed run's
// diagnostics) can open it. Forgotten once the record is scheduled or a new
// one is started. A per-browser convenience only: without it the wizard
// just starts at step one. Storage that is unavailable (private mode ...)
// is simply skipped.

import { isWizardStep, type WizardStepKey } from "./wizard";

const REMEMBERED_RECORD_KEY = "wizard.record";
const REMEMBERED_STEP_KEY = "wizard.step";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, value);
    }
  } catch {
    // Resuming just starts over.
  }
}

export function readRememberedWizardRecord(): number | null {
  const raw = read(REMEMBERED_RECORD_KEY);
  const parsed = raw === null ? NaN : Number(raw);
  return Number.isInteger(parsed) ? parsed : null;
}

export function readRememberedWizardStep(): WizardStepKey | null {
  const raw = read(REMEMBERED_STEP_KEY);
  return isWizardStep(raw) ? raw : null;
}

// A different record than the one remembered starts from no step.
export function rememberWizardRecord(recordId: number): void {
  if (readRememberedWizardRecord() !== recordId) {
    write(REMEMBERED_STEP_KEY, null);
  }
  write(REMEMBERED_RECORD_KEY, String(recordId));
}

export function rememberWizardStep(step: WizardStepKey): void {
  write(REMEMBERED_STEP_KEY, step);
}

export function forgetWizardRecord(): void {
  write(REMEMBERED_RECORD_KEY, null);
  write(REMEMBERED_STEP_KEY, null);
}
