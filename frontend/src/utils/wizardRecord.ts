// v3: the 排課紀錄 the wizard is filling, so a link straight to one step
// (?step=teachers, from a failed run's diagnostics) can open it. A per-
// browser convenience only: without it the wizard just starts at step one.
// Storage that is unavailable (private mode ...) is simply skipped.

const REMEMBERED_RECORD_KEY = "wizard.record";

export function readRememberedWizardRecord(): number | null {
  try {
    const raw = sessionStorage.getItem(REMEMBERED_RECORD_KEY);
    const parsed = raw === null ? NaN : Number(raw);
    return Number.isInteger(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function rememberWizardRecord(recordId: number): void {
  try {
    sessionStorage.setItem(REMEMBERED_RECORD_KEY, String(recordId));
  } catch {
    // Deep links just start over.
  }
}
