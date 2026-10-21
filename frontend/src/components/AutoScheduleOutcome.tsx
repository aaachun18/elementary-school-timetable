import type { ReactElement } from "react";
import { Link } from "react-router-dom";
import FailureDiagnostics from "./FailureDiagnostics";
import type { AutoScheduleState } from "../hooks/useAutoSchedule";
import { ERROR_TEXT, LINK_TEXT, MUTED_TEXT, SUCCESS_TEXT } from "../styles/ui";

// v3: what 自動排課 (hooks/useAutoSchedule.ts) came back with -- the
// timetable's link on success, the reasons on failure (the record stays
// 尚未排課, so its settings can be fixed and the run tried again).
export default function AutoScheduleOutcome({
  versionId,
  versionNumber,
  state,
}: {
  versionId: number;
  versionNumber: number | null;
  state: AutoScheduleState;
}): ReactElement | null {
  if (state.isRunning) {
    return <p className={`${MUTED_TEXT} mt-2`}>排課可能需要一點時間，請耐心等候。</p>;
  }
  if (state.error !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {state.error}
      </p>
    );
  }
  if (state.result !== null) {
    return (
      <div className="mt-3">
        <p className={SUCCESS_TEXT}>
          ✓ 排課完成：排定 {state.result.scheduled_count} 堂課（排課紀錄編號 {versionNumber}，自動排課）
        </p>
        <p className="mt-1 flex flex-wrap gap-4 text-sm">
          <Link to={`/timetable?scheduleVersionId=${versionId}`} className={LINK_TEXT}>
            檢視課表
          </Link>
          <Link to="/records" className={LINK_TEXT}>
            回到排課紀錄
          </Link>
        </p>
      </div>
    );
  }
  if (state.failure !== null) {
    return (
      <div className="mt-3">
        <p className="text-sm text-gray-700">
          這次沒有排出完整課表（不會留下部分結果），這筆排課紀錄維持「尚未排課」。依下面的說明修改設定後，可以再按一次「自動排課」。
        </p>
        <FailureDiagnostics response={state.failure} versionId={versionId} />
      </div>
    );
  }
  return null;
}
