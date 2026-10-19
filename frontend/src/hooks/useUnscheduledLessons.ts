import { unscheduledLessons } from "../api/scheduleVersions";
import { useResource } from "./useResource";
import type { UnscheduledLesson } from "../types/scheduler";

interface UseUnscheduledLessonsResult {
  // [] while nothing is loaded for this version (or the version is null).
  lessons: UnscheduledLesson[];
  isLoading: boolean;
  errorMessage: string | null;
  reload: () => void;
}

// Task 93: the lessons of the version's semester that have no row in the
// version (backend Task 92). Pass null when the panel isn't shown (not in
// edit mode) -- nothing is fetched then. A result for another version
// (still on screen while the new one loads) is never returned.
export function useUnscheduledLessons(versionId: number | null): UseUnscheduledLessonsResult {
  const resource = useResource(
    () => (versionId === null ? Promise.resolve(null) : unscheduledLessons(versionId)),
    [versionId],
  );
  const data = resource.data;
  const lessons =
    data !== null && versionId !== null && data.schedule_version_id === versionId ? data.lessons : [];
  return {
    lessons,
    isLoading: resource.isLoading,
    errorMessage: versionId === null ? null : resource.errorMessage,
    reload: resource.reload,
  };
}
