import { useState, type FormEvent, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { list as listAcademicYears } from "../api/academicYears";
import {
  list as listScheduleVersions,
  remove as removeScheduleVersion,
  update as updateScheduleVersion,
} from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import ConfirmDialog from "../components/ConfirmDialog";
import { extractApiErrorMessage } from "../constants/errorMessages";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useResource } from "../hooks/useResource";
import { formatDateTime } from "../utils/dashboard";
import { sortRecords } from "../utils/scheduleRecords";
import {
  formatRecordStatus,
  formatVersionLabel,
  hasTimetable,
  recordStatusBadgeClass,
  semesterLabelOf,
} from "../utils/scheduleVersionFormat";
import { DELETE_WARNING, PUBLISHED_DELETE_HINT, canDeleteRecord } from "../utils/versionDelete";
import type { ScheduleVersion } from "../types/scheduleVersion";
import {
  BUTTON_DANGER_SM,
  BUTTON_LINK,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LINK_TEXT,
  LOADING_TEXT,
  MUTED_TEXT,
  PAGE,
  PAGE_TITLE,
  SUCCESS_TEXT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
  TR_HOVER,
} from "../styles/ui";

const ALL = 1000;
const NOTE_MAX_LENGTH = 200;

// v3 (items 9, 11, 15): 排課紀錄 -- every record of the school, newest 編號
// first. Each row: its semester, status (尚未排課 / 自動排課 / 手動排課 /
// 複製自編號 x / 已發布), creation time, 備註 (typed right in the row) and
// its actions: 檢視課表 and 檢視排課設定 (each its own page, with a way
// back here) and 刪除. Publishing, copying and manual editing happen on
// those pages.
export default function ScheduleRecords(): ReactElement {
  const data = useResource(
    () => Promise.all([listScheduleVersions(0, ALL), listSemesters(0, ALL), listAcademicYears(0, ALL)]),
    [],
  );
  const [deleting, setDeleting] = useState<ScheduleVersion | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const flash = useFlashMessage();

  if (data.errorMessage !== null) {
    return (
      <div className={PAGE}>
        <h1 className={PAGE_TITLE}>排課紀錄</h1>
        <p role="alert" className={ERROR_TEXT}>
          {data.errorMessage}
        </p>
      </div>
    );
  }
  if (data.data === null) {
    return (
      <div className={PAGE}>
        <h1 className={PAGE_TITLE}>排課紀錄</h1>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  const [versions, semesters, academicYears] = data.data;
  const semesterById = new Map(semesters.map((item) => [item.id, item]));
  const academicYearById = new Map(academicYears.map((item) => [item.id, item.year]));

  async function handleConfirmDelete(): Promise<void> {
    if (deleting === null) {
      return;
    }
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await removeScheduleVersion(deleting.id);
      flash.showFlash(`已刪除排課紀錄編號 ${deleting.version_number}`);
      setDeleting(null);
      data.reload();
    } catch (caught) {
      setDeleteError(extractApiErrorMessage(caught));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>排課紀錄</h1>
      <p className={HELP_TEXT}>
        每次「開始排課」或複製都會留下一筆排課紀錄，依編號由新到舊排列。「檢視課表」可以手動編輯、複製與發布課表；「檢視排課設定」可以查看這次排課用的設定，或複製設定重新排課。備註直接在欄位裡輸入，離開欄位就會儲存。
      </p>
      {flash.message !== null && <p className={`${SUCCESS_TEXT} mb-2`}>✓ {flash.message}</p>}

      {versions.length === 0 ? (
        <div className={CARD}>
          <p className={MUTED_TEXT}>
            還沒有排課紀錄。到「
            <Link to="/wizard" className={LINK_TEXT}>
              開始排課
            </Link>
            」完成設定並排課後，紀錄就會出現在這裡。
          </p>
        </div>
      ) : (
        <div className={TABLE_WRAPPER}>
          <table className={TABLE}>
            <thead>
              <tr className={TABLE_HEAD_ROW}>
                <th className={TH}>編號</th>
                <th className={TH}>學期</th>
                <th className={TH}>狀態</th>
                <th className={TH}>建立時間</th>
                <th className={TH}>操作</th>
                <th className={TH}>備註</th>
              </tr>
            </thead>
            <tbody>
              {sortRecords(versions).map((version) => (
                <tr key={version.id} className={TR_HOVER}>
                  <td className={`${TD} font-medium`}>{version.version_number}</td>
                  <td className={TD}>{semesterLabelOf(version, semesterById, academicYearById)}</td>
                  <td className={TD}>
                    <span className={recordStatusBadgeClass(version)}>{formatRecordStatus(version)}</span>
                  </td>
                  <td className={`${TD} whitespace-nowrap`}>{formatDateTime(version.created_at)}</td>
                  <td className={TD}>
                    <div className="flex flex-col items-start gap-1">
                      {hasTimetable(version.status) && (
                        <Link to={`/timetable?scheduleVersionId=${version.id}`} className={LINK_TEXT}>
                          檢視課表
                        </Link>
                      )}
                      <Link to={`/records/${version.id}/settings`} className={LINK_TEXT}>
                        檢視排課設定
                      </Link>
                      {canDeleteRecord(version) ? (
                        <button
                          type="button"
                          onClick={() => {
                            setDeleteError(null);
                            setDeleting(version);
                          }}
                          className={BUTTON_DANGER_SM}
                        >
                          刪除
                        </button>
                      ) : (
                        <span className={MUTED_TEXT} title={PUBLISHED_DELETE_HINT}>
                          不可刪除
                        </span>
                      )}
                    </div>
                  </td>
                  <td className={TD}>
                    <NoteCell key={`${version.id}-${version.note ?? ""}`} record={version} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleting !== null}
        title="刪除這筆排課紀錄？"
        confirmLabel="刪除"
        danger
        busy={isDeleting}
        busyLabel="刪除中…"
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => setDeleting(null)}
      >
        {deleting !== null && (
          <p>
            將刪除「{formatVersionLabel(deleting, semesterById, academicYearById)}」。{DELETE_WARNING}
          </p>
        )}
        {deleteError !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {deleteError}
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}

// 備註: typed in place, saved when the field loses focus or on Enter
// (only when it actually changed). Keyed by the saved note, so a reload
// starts it over from what is stored.
function NoteCell({ record }: { record: ScheduleVersion }): ReactElement {
  const [text, setText] = useState(record.note ?? "");
  const [saved, setSaved] = useState(record.note ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  async function save(): Promise<void> {
    if (text.trim() === saved.trim()) {
      return;
    }
    setIsSaving(true);
    setError(null);
    setJustSaved(false);
    try {
      const updated = await updateScheduleVersion(record.id, { note: text.trim() === "" ? null : text.trim() });
      setSaved(updated.note ?? "");
      setText(updated.note ?? "");
      setJustSaved(true);
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void save();
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-w-48 flex-col gap-1">
      <input
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setJustSaved(false);
        }}
        onBlur={() => void save()}
        maxLength={NOTE_MAX_LENGTH}
        disabled={isSaving}
        placeholder="例如：王老師上三年級自然課版"
        aria-label={`編號 ${record.version_number} 的備註`}
        className={`${INPUT} w-full`}
      />
      {isSaving && <span className={MUTED_TEXT}>儲存中…</span>}
      {justSaved && !isSaving && <span className="text-xs text-green-600">已儲存</span>}
      {error !== null && (
        <span role="alert" className={ERROR_TEXT}>
          {error}
        </span>
      )}
      {/* Enter submits the form (no visible button needed). */}
      <button type="submit" className={`${BUTTON_LINK} sr-only`} tabIndex={-1}>
        儲存備註
      </button>
    </form>
  );
}
