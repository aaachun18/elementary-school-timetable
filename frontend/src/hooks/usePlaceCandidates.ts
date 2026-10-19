import { useEffect, useState } from "react";
import { placeCandidates } from "../api/scheduleVersions";
import { placeCandidateCacheKey } from "../utils/placement";
import type { PlaceCandidatesResult } from "../types/scheduler";

type PlaceCandidateResult = { ok: true; data: PlaceCandidatesResult } | { ok: false };

export type PlaceCandidateState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: PlaceCandidatesResult }
  | { status: "failed" };

// Task 93: the place-candidates (backend Task 92) of the unscheduled card
// currently selected or dragged -- the same caching as useMoveCandidates
// (Task 84): one request per key (version, anchor lesson, teacher, room,
// revision); a request whose key is no longer the current one is aborted,
// and a response that slips through is stored under its own key and never
// shown for another card. Pass null as lessonId or teacherId when nothing
// should be shown (no card, or no teacher picked yet).
export function usePlaceCandidates(
  versionId: number | null,
  lessonId: number | null,
  teacherId: number | null,
  roomId: number | null,
  revision: number,
): PlaceCandidateState {
  const key = placeCandidateCacheKey(versionId, lessonId, teacherId, roomId, revision);
  const [results, setResults] = useState<ReadonlyMap<string, PlaceCandidateResult>>(() => new Map());
  const isCached = key !== null && results.has(key);

  useEffect(() => {
    if (key === null || isCached || versionId === null || lessonId === null) {
      return;
    }
    const controller = new AbortController();
    const store = (result: PlaceCandidateResult): void => {
      setResults((previous) => {
        // Keep this revision's entries only: anything older is stale
        // (keys are "place:{version}:{lesson}:{revision}:t…:r…").
        const next = new Map<string, PlaceCandidateResult>();
        for (const [cachedKey, cached] of previous) {
          if (cachedKey.split(":")[3] === String(revision)) {
            next.set(cachedKey, cached);
          }
        }
        next.set(key, result);
        return next;
      });
    };
    placeCandidates(versionId, lessonId, teacherId, roomId, controller.signal)
      .then((data) => store({ ok: true, data }))
      .catch(() => {
        // Aborted: the card changed, nothing to record. Any other failure
        // (409 TEACHER_REQUIRED, network...): marks are simply not shown,
        // and a drop still goes through the preview.
        if (!controller.signal.aborted) {
          store({ ok: false });
        }
      });
    return () => controller.abort();
  }, [key, isCached, versionId, lessonId, teacherId, roomId, revision]);

  if (key === null) {
    return { status: "idle" };
  }
  const result = results.get(key);
  if (result === undefined) {
    return { status: "loading" };
  }
  return result.ok ? { status: "ready", data: result.data } : { status: "failed" };
}
