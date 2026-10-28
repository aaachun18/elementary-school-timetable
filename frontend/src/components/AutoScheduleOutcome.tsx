import type { ReactElement } from "react";
import { Link } from "react-router-dom";
import FailureDiagnostics from "./FailureDiagnostics";
import type { AutoScheduleState } from "../hooks/useAutoSchedule";
import { BUTTON_PRIMARY, BUTTON_SECONDARY, ERROR_TEXT, MUTED_TEXT, SUCCESS_PANEL } from "../styles/ui";

// v3: what 自動排課 (hooks/useAutoSchedule.ts) came back with -- the
// timetable's link on success, the reasons on failure (the record stays
// 尚未排課, so its settings can be fixed and the run tried again). A
// scheduled record becomes the school's newest, so its 編號 is then 1.
const NEWEST_DISPLAY_NUMBER = 1;

export default function AutoScheduleOutcome({
  versionId,
  state,
  showLinks = true,
}: {
  versionId: number;
  state: AutoScheduleState;
  // false where the page itself already offers 檢視課表 (排課設定's header),
  // so a screen never has two Primary buttons.
  showLinks?: boolean;
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
      <div className={SUCCESS_PANEL} role="status">
        <p className="text-sm font-semibold">
          排課完成：排定 {state.result.scheduled_count} 堂課（排課紀錄編號 {NEWEST_DISPLAY_NUMBER}）
        </p>
        {showLinks && (
          <div className="mt-3 flex flex-wrap justify-end gap-2">
            <Link to="/records" className={BUTTON_SECONDARY}>
              排課紀錄
            </Link>
            <Link to={`/timetable?scheduleVersionId=${versionId}`} className={BUTTON_PRIMARY}>
              檢視課表
            </Link>
          </div>
        )}
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
