// Task 104: how long 自動排課 took -- one decimal under 10 seconds ("2.4"),
// whole seconds from there ("37").
export function formatSeconds(seconds: number): string {
  return seconds < 10 ? seconds.toFixed(1) : String(Math.round(seconds));
}
