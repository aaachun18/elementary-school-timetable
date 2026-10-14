import { useCallback, useEffect, useRef, useState } from "react";
import { check as checkScheduleVersion } from "../api/scheduleVersions";
import { extractApiErrorMessage } from "../constants/errorMessages";
import type { ScheduleCheckResult } from "../types/scheduler";

// Every piece of state also remembers which version it belongs to, so a
// response that arrives after the user switched versions can never be shown
// under the new one.
interface ForVersion<T> {
  versionId: number;
  value: T;
}

interface UseScheduleCheckResult {
  result: ScheduleCheckResult | null;
  isChecking: boolean;
  errorMessage: string | null;
  // Runs the check for the current version. Never runs on its own: the
  // check is a deliberate user action (a button), not part of loading.
  run: () => void;
  clear: () => void;
  // Task 69: shows a result obtained elsewhere for the current version --
  // e.g. the `check` a move/swap response already carries -- as if run()
  // had returned it. Supersedes any check still in flight.
  setResult: (result: ScheduleCheckResult) => void;
}

// Task 68: GET /schedule-versions/{id}/check, triggered on demand.
// - A response for a version that is no longer the current one, or from a
//   request superseded by a newer run()/clear(), is dropped.
// - Nothing is set after the component unmounts.
export function useScheduleCheck(scheduleVersionId: number | null): UseScheduleCheckResult {
  const [result, setStoredResult] = useState<ForVersion<ScheduleCheckResult> | null>(null);
  const [error, setError] = useState<ForVersion<string> | null>(null);
  const [checkingVersionId, setCheckingVersionId] = useState<number | null>(null);

  // Switching versions discards the previous result entirely, so coming
  // back to a version shows no result until it is checked again (it may
  // have changed meanwhile). Done during render -- React's recommended way
  // to reset state when a prop changes -- rather than in an effect.
  const [trackedVersionId, setTrackedVersionId] = useState(scheduleVersionId);
  if (trackedVersionId !== scheduleVersionId) {
    setTrackedVersionId(scheduleVersionId);
    setStoredResult(null);
    setError(null);
    setCheckingVersionId(null);
  }

  // Incremented by every run()/clear(); a response only lands if its own
  // request number is still the latest.
  const latestRequestRef = useRef(0);
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const run = useCallback(() => {
    if (scheduleVersionId === null) {
      return;
    }
    const versionId = scheduleVersionId;
    latestRequestRef.current += 1;
    const requestNumber = latestRequestRef.current;
    const isCurrent = (): boolean =>
      isMountedRef.current && requestNumber === latestRequestRef.current;

    setCheckingVersionId(versionId);
    setError(null);
    checkScheduleVersion(versionId)
      .then((data) => {
        if (isCurrent()) {
          setStoredResult({ versionId, value: data });
        }
      })
      .catch((caught: unknown) => {
        if (isCurrent()) {
          setStoredResult(null);
          setError({ versionId, value: extractApiErrorMessage(caught) });
        }
      })
      .finally(() => {
        if (isCurrent()) {
          setCheckingVersionId(null);
        }
      });
  }, [scheduleVersionId]);

  const clear = useCallback(() => {
    latestRequestRef.current += 1;
    setStoredResult(null);
    setError(null);
    setCheckingVersionId(null);
  }, []);

  const setResult = useCallback(
    (value: ScheduleCheckResult) => {
      if (scheduleVersionId === null) {
        return;
      }
      latestRequestRef.current += 1;
      setStoredResult({ versionId: scheduleVersionId, value });
      setError(null);
      setCheckingVersionId(null);
    },
    [scheduleVersionId],
  );

  const isCurrentVersion = (versionId: number): boolean => versionId === scheduleVersionId;

  return {
    result: result !== null && isCurrentVersion(result.versionId) ? result.value : null,
    isChecking: checkingVersionId !== null && isCurrentVersion(checkingVersionId),
    errorMessage: error !== null && isCurrentVersion(error.versionId) ? error.value : null,
    run,
    clear,
    setResult,
  };
}
