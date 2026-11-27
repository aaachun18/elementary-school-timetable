import { useState } from "react";
import axios from "axios";
import { generateLessons, runScheduler } from "../api/scheduleVersions";
import { extractApiErrorMessage } from "../constants/errorMessages";
import type { RunSchedulerFailureResponse, RunSchedulerSuccessResponse } from "../types/scheduler";

export interface AutoScheduleState {
  isRunning: boolean;
  result: RunSchedulerSuccessResponse | null;
  // run-scheduler's 422: why no complete timetable was found (the record
  // stays 尚未排課, nothing partial is saved).
  failure: RunSchedulerFailureResponse | null;
  error: string | null;
}

// v3: 自動排課 of one 尚未排課 record -- its lessons generated from its
// requirements, then the scheduler run on it (success: the record becomes
// 自動排課). Shared by the wizard's last step and 檢視排課設定.
export function useAutoSchedule(versionId: number): AutoScheduleState & {
  run: () => Promise<boolean>;
} {
  const [state, setState] = useState<AutoScheduleState>({
    isRunning: false,
    result: null,
    failure: null,
    error: null,
  });

  // Resolves true when a timetable was made.
  async function run(): Promise<boolean> {
    setState({ isRunning: true, result: null, failure: null, error: null });
    try {
      await generateLessons(versionId);
      const result = await runScheduler(versionId);
      setState({ isRunning: false, result, failure: null, error: null });
      return true;
    } catch (caught) {
      // Only run-scheduler's 422 carries the structured failure shape.
      if (
        axios.isAxiosError<RunSchedulerFailureResponse>(caught) &&
        caught.response?.status === 422 &&
        "failure_type" in (caught.response.data ?? {})
      ) {
        setState({ isRunning: false, result: null, failure: caught.response.data, error: null });
      } else {
        setState({ isRunning: false, result: null, failure: null, error: extractApiErrorMessage(caught) });
      }
      return false;
    }
  }

  return { ...state, run };
}
