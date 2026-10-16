import { useEffect, useState } from "react";
import { moveCandidates } from "../api/scheduleVersions";
import {
  candidateCacheKey,
  candidateStateFor,
  type CandidateResult,
  type CandidateState,
} from "../utils/moveCandidates";

// Task 84: the move-candidates (Task 83) of the lesson currently selected
// or dragged in the timetable's edit mode.
// - Fetched once per (version, lesson, revision); selecting the same lesson
//   again reads the cache. `revision` goes up after every saved change, so
//   older entries are never read again (and are dropped on the next store).
// - A request whose lesson is no longer the current one is aborted; even a
//   response that slips through is stored under its own key and never
//   shown for another lesson (candidateStateFor()).
// - State is only set from the request's own callbacks, never
//   synchronously inside the effect.
// Pass null as versionId or scheduleId when nothing should be shown.
export function useMoveCandidates(
  versionId: number | null,
  scheduleId: number | null,
  revision: number,
): CandidateState {
  const key = candidateCacheKey(versionId, scheduleId, revision);
  const [results, setResults] = useState<ReadonlyMap<string, CandidateResult>>(
    () => new Map(),
  );
  const isCached = key !== null && results.has(key);

  useEffect(() => {
    if (key === null || isCached || versionId === null || scheduleId === null) {
      return;
    }
    const controller = new AbortController();
    const store = (result: CandidateResult): void => {
      setResults((previous) => {
        const next = new Map<string, CandidateResult>();
        // Keep this revision's entries only: anything older is stale.
        const revisionSuffix = `:${revision}`;
        for (const [cachedKey, cached] of previous) {
          if (cachedKey.endsWith(revisionSuffix)) {
            next.set(cachedKey, cached);
          }
        }
        next.set(key, result);
        return next;
      });
    };
    moveCandidates(versionId, scheduleId, controller.signal)
      .then((data) => store({ ok: true, data }))
      .catch(() => {
        // Aborted: the lesson changed, nothing to record. Any other
        // failure (403/404/409/network): marks are simply not shown.
        if (!controller.signal.aborted) {
          store({ ok: false });
        }
      });
    return () => controller.abort();
  }, [key, isCached, versionId, scheduleId, revision]);

  return candidateStateFor(results, key);
}
