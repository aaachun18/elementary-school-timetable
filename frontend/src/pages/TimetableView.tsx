import { useEffect, useRef, useState, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
import { list as listScheduleVersions } from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listClasses } from "../api/classes";
import { list as listTeachers } from "../api/teachers";
import { list as listRooms } from "../api/rooms";
import ConflictChecklist from "../components/ConflictChecklist";
import { useResource } from "../hooks/useResource";
import { useScheduleCheck } from "../hooks/useScheduleCheck";
import { useTimetableData, timeSlotKey, type EnrichedSchedule } from "../hooks/useTimetableData";
import { isCurrentUserAdmin } from "../utils/auth";
import { getViolationSentence, type NameLookups } from "../utils/failureDiagnostics";
import { formatVersionLabel } from "../utils/scheduleVersionFormat";
import { mergeViolationsBySentence } from "../utils/violationMerge";
import type { ConstraintViolationDetail } from "../types/scheduler";
import { formatWeekday } from "../utils/timeSlotFormat";
import {
  BUTTON_PRIMARY,
  CARD,
  ERROR_TEXT,
  LABEL,
  LOADING_TEXT,
  MUTED_TEXT,
  NOTICE,
  PAGE,
  PAGE_TITLE,
  SECTION,
  SELECT,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_HIGHLIGHT,
  TH,
} from "../styles/ui";

type ViewMode = "class" | "teacher" | "room";

const VIEW_MODES: { key: ViewMode; label: string }[] = [
  { key: "class", label: "依班級" },
  { key: "teacher", label: "依教師" },
  { key: "room", label: "依教室" },
];

const WEEKDAYS = [1, 2, 3, 4, 5];

function targetIdOf(row: EnrichedSchedule, viewMode: ViewMode): number | null {
  if (viewMode === "class") {
    return row.classId;
  }
  if (viewMode === "teacher") {
    return row.teacherId;
  }
  return row.roomId;
}

// What a cell shows besides the subject name -- "the other party" for
// whichever axis isn't the one currently being browsed. Room view shows
// the same pairing as teacher view (subject + class): which class is
// occupying the room is the most room-relevant question; see Task 34's
// report for this being my own reasonable extension, not spelled out in
// the spec.
function cellDetailOf(row: EnrichedSchedule, viewMode: ViewMode): string {
  if (viewMode === "class") {
    return row.teacherName ?? "未指定教師";
  }
  return row.className;
}

// Task 68: where 「在課表中查看」 takes the user -- which view, and whose
// timetable. A class (or, for H7, which only names a requirement, that
// requirement's class) wins over a teacher, which wins over a room. null =
// nothing to show (the button is hidden).
interface LocateTarget {
  viewMode: ViewMode;
  targetId: number;
}

function resolveLocateTarget(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): LocateTarget | null {
  const classId =
    violation.class_id ??
    (violation.class_subject_requirement_id === null
      ? null
      : (lookups.requirementById.get(violation.class_subject_requirement_id)?.class_id ?? null));
  if (classId !== null) {
    return { viewMode: "class", targetId: classId };
  }
  if (violation.teacher_id !== null) {
    return { viewMode: "teacher", targetId: violation.teacher_id };
  }
  if (violation.room_id !== null) {
    return { viewMode: "room", targetId: violation.room_id };
  }
  return null;
}

export default function TimetableView(): ReactElement {
  const [searchParams] = useSearchParams();

  const versionsResource = useResource(() => listScheduleVersions(), []);
  const semesters = useResource(() => listSemesters(), []);
  const academicYears = useResource(() => listAcademicYears(), []);
  const classesResource = useResource(() => listClasses(), []);
  const teachersResource = useResource(() => listTeachers(), []);
  const roomsResource = useResource(() => listRooms(), []);

  // Task 34: arriving from 排課控制台's 「查看課表」 link carries
  // ?scheduleVersionId=<id> in the URL -- a query string rather than
  // react-router's <Link state> because it survives a page reload and can
  // be bookmarked/shared, not just an in-memory navigation.
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(() => {
    const raw = searchParams.get("scheduleVersionId");
    const parsed = raw !== null ? Number(raw) : NaN;
    return Number.isInteger(parsed) ? parsed : null;
  });
  const [viewMode, setViewMode] = useState<ViewMode>("class");
  const [selectedTargetId, setSelectedTargetId] = useState<number | null>(null);

  const timetable = useTimetableData(selectedVersionId);

  // --- Task 68: 檢查衝突 (ADMIN only; the backend would also let a TEACHER
  // check a PUBLISHED version, this is a UI scoping choice). ---
  const isAdmin = isCurrentUserAdmin();
  const scheduleCheck = useScheduleCheck(selectedVersionId);
  // The TimeSlot whose cell 「在課表中查看」 marked. Cleared by any other
  // change of what the grid shows (view, target, version) and by re-checking.
  const [highlightedTimeSlotId, setHighlightedTimeSlotId] = useState<number | null>(null);
  // Bumped on every locate so the grid scrolls into view even when the
  // same line is located twice in a row.
  const [locateRequestCount, setLocateRequestCount] = useState(0);
  const timetableSectionRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (locateRequestCount > 0) {
      timetableSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [locateRequestCount]);

  function handleSelectViewMode(mode: ViewMode): void {
    setViewMode(mode);
    // A classId is meaningless as a teacherId/roomId and vice versa --
    // switching axis always starts the target selection over.
    setSelectedTargetId(null);
    setHighlightedTimeSlotId(null);
  }

  function handleRunCheck(): void {
    setHighlightedTimeSlotId(null);
    scheduleCheck.run();
  }

  // A violation without a time slot (H7/H8, an incomplete row) only
  // switches the view; nothing is highlighted.
  function handleLocate(violation: ConstraintViolationDetail): void {
    if (timetable.data === null) {
      return;
    }
    const target = resolveLocateTarget(violation, timetable.data.lookups);
    if (target === null) {
      return;
    }
    setViewMode(target.viewMode);
    setSelectedTargetId(target.targetId);
    setHighlightedTimeSlotId(violation.time_slot_id);
    setLocateRequestCount((previous) => previous + 1);
  }

  function canLocate(violation: ConstraintViolationDetail): boolean {
    return (
      timetable.data !== null && resolveLocateTarget(violation, timetable.data.lookups) !== null
    );
  }

  const isLoadingLookups =
    versionsResource.isLoading ||
    semesters.isLoading ||
    academicYears.isLoading ||
    classesResource.isLoading ||
    teachersResource.isLoading ||
    roomsResource.isLoading;
  const lookupErrorMessage =
    versionsResource.errorMessage ??
    semesters.errorMessage ??
    academicYears.errorMessage ??
    classesResource.errorMessage ??
    teachersResource.errorMessage ??
    roomsResource.errorMessage;

  if (isLoadingLookups) {
    return (
      <div className={PAGE}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  if (lookupErrorMessage !== null) {
    return (
      <div className={PAGE}>
        <p role="alert" className={ERROR_TEXT}>
          {lookupErrorMessage}
        </p>
      </div>
    );
  }

  const academicYearById = new Map(
    (academicYears.data ?? []).map((academicYear) => [
      academicYear.id,
      academicYear.year,
    ]),
  );
  const semesterById = new Map(
    (semesters.data ?? []).map((semester) => [semester.id, semester]),
  );
  const versions = versionsResource.data ?? [];
  const selectedVersion = versions.find((version) => version.id === selectedVersionId);

  const targetOptions =
    viewMode === "class"
      ? (classesResource.data ?? []).map((item) => ({ id: item.id, label: item.name }))
      : viewMode === "teacher"
        ? (teachersResource.data ?? []).map((item) => ({ id: item.id, label: item.name }))
        : (roomsResource.data ?? []).map((item) => ({ id: item.id, label: item.name }));

  // Task 35: the vertical axis now comes from the school's full, global
  // TimeSlot structure (useTimetableData's `periods`, already sorted)
  // instead of only the periods this version's own results happened to
  // use (Task 34's approach) -- so early study hall, lunch, etc. always
  // show up even when nothing is ever scheduled into them.
  const periods = timetable.data?.periods ?? [];
  const schedules = timetable.data?.schedules ?? [];
  const timeSlotByWeekdayAndPeriod =
    timetable.data?.timeSlotByWeekdayAndPeriod ?? new Map();

  // Task 35.5: teaching/non-teaching status and label are decided per
  // CELL (this exact weekday+period's own TimeSlot), not per row -- the
  // same period can be "早自習" on Monday and "導師時間" on Wednesday, and
  // each cell must show its own name rather than one collapsed row title.
  // A missing TimeSlot record for this exact weekday+period is treated as
  // an ordinary teaching slot, matching TimeSlotBase's own
  // is_teaching_period default of True.
  function cellLabelOf(weekday: number, period: number): string | null {
    const timeSlot = timeSlotByWeekdayAndPeriod.get(timeSlotKey(weekday, period));
    if (timeSlot === undefined || timeSlot.is_teaching_period) {
      return null;
    }
    return timeSlot.label ?? "非教學時段";
  }

  // Task 68: the cell 「在課表中查看」 points at -- matched by TimeSlot id,
  // so it works for non-teaching cells (H11) too.
  function isHighlightedCell(weekday: number, period: number): boolean {
    return (
      highlightedTimeSlotId !== null &&
      timeSlotByWeekdayAndPeriod.get(timeSlotKey(weekday, period))?.id === highlightedTimeSlotId
    );
  }

  // The summary counts lines as the checklist shows them (merged), not raw
  // violation records.
  const checkLookups = timetable.data?.lookups ?? null;
  const checkProblemCount =
    scheduleCheck.result === null || checkLookups === null
      ? 0
      : mergeViolationsBySentence(scheduleCheck.result.violations, (violation) =>
          getViolationSentence(violation, checkLookups),
        ).length;

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>課表檢視</h1>
      {/* Task 67: only ADMIN can ever pick an ARCHIVED version here (a
          TEACHER's version list is PUBLISHED-only, enforced by the
          backend). */}
      {selectedVersion?.status === "ARCHIVED" && (
        <p className={`${NOTICE} mb-4`}>這是已封存的版本，僅供查看。</p>
      )}

      <section className={SECTION}>
        <label htmlFor="timetable-version-select" className={`${LABEL} mb-1 block`}>
          選擇排課版本
        </label>
        {/* Task 43: TEACHER's GET /api/v1/schedule-versions/ already only
            ever returns PUBLISHED versions (backend/app/services/
            schedule_version.py) -- `versions` here is exactly what this
            page is allowed to offer, no extra client-side filtering
            needed. An empty list (no PUBLISHED version exists yet, for
            TEACHER; or genuinely none at all, for ADMIN) gets its own
            message instead of a dropdown with nothing but "請選擇…" in
            it. */}
        {versions.length === 0 ? (
          <p className={MUTED_TEXT}>目前沒有可查看的排課版本。</p>
        ) : (
          <select
            id="timetable-version-select"
            value={selectedVersionId ?? ""}
            onChange={(event) => {
              setSelectedVersionId(
                event.target.value === "" ? null : Number(event.target.value),
              );
              setSelectedTargetId(null);
              setHighlightedTimeSlotId(null);
            }}
            className={SELECT}
          >
            <option value="">請選擇…</option>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {formatVersionLabel(version, semesterById, academicYearById)}
              </option>
            ))}
          </select>
        )}
      </section>

      {/* Task 68: 檢查衝突 -- read-only, any version status. The result
          belongs to the selected version only (useScheduleCheck drops it
          on a version change). Waits for the timetable data, whose lookups
          turn the violations into names. */}
      {isAdmin && selectedVersionId !== null && (
        <section className={SECTION} aria-label="檢查衝突">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleRunCheck}
              disabled={scheduleCheck.isChecking || timetable.isLoading || timetable.data === null}
              className={BUTTON_PRIMARY}
            >
              {scheduleCheck.isChecking
                ? "檢查中…"
                : scheduleCheck.result !== null
                  ? "重新檢查"
                  : "檢查衝突"}
            </button>
            <span className={MUTED_TEXT}>依目前儲存的課表檢查所有排課規則，不會修改任何資料。</span>
          </div>
          {scheduleCheck.errorMessage !== null && (
            <p role="alert" className={ERROR_TEXT}>
              檢查失敗：{scheduleCheck.errorMessage}
            </p>
          )}
          {scheduleCheck.result !== null && checkLookups !== null && (
            <div className={`${CARD} mt-3`} aria-live="polite">
              {checkProblemCount > 0 && (
                <p className="mb-2 text-sm font-semibold text-red-600">
                  共 {checkProblemCount} 項問題
                </p>
              )}
              <ConflictChecklist
                violations={scheduleCheck.result.violations}
                lookups={checkLookups}
                emptyText="沒有發現衝突，這份課表符合所有檢查規則"
                onLocate={handleLocate}
                canLocate={canLocate}
              />
            </div>
          )}
        </section>
      )}

      {selectedVersionId !== null && (
        <section ref={timetableSectionRef} className={`${SECTION} scroll-mt-4`}>
          <nav className="mb-4 flex gap-2">
            {VIEW_MODES.map((mode) => (
              <button
                key={mode.key}
                type="button"
                onClick={() => handleSelectViewMode(mode.key)}
                aria-pressed={viewMode === mode.key}
                className={viewMode === mode.key ? TAB_BUTTON_ACTIVE : TAB_BUTTON}
              >
                {mode.label}
              </button>
            ))}
          </nav>

          <label htmlFor="timetable-target-select" className={`${LABEL} mb-1 block`}>
            {viewMode === "class" ? "選擇班級" : viewMode === "teacher" ? "選擇教師" : "選擇教室"}
          </label>
          <select
            id="timetable-target-select"
            value={selectedTargetId ?? ""}
            onChange={(event) => {
              setSelectedTargetId(
                event.target.value === "" ? null : Number(event.target.value),
              );
              setHighlightedTimeSlotId(null);
            }}
            className={`${SELECT} mb-4`}
          >
            <option value="">請選擇…</option>
            {targetOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>

          {timetable.isLoading && <p className={LOADING_TEXT}>載入中…</p>}
          {timetable.errorMessage !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {timetable.errorMessage}
            </p>
          )}

          {timetable.data !== null && selectedTargetId !== null && (
            <div className={TABLE_WRAPPER}>
              <table className={TABLE}>
                <thead>
                  <tr className={TABLE_HEAD_ROW}>
                    <th className={TH}>節次</th>
                    {WEEKDAYS.map((weekday) => (
                      <th key={weekday} className={TH}>
                        {formatWeekday(weekday)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {periods.map((period) => (
                    <tr key={period} className="hover:bg-gray-50">
                      {/* Task 35.5: the row header is now a plain,
                          weekday-independent period number -- no label is
                          read here, since a single period can have
                          different labels on different weekdays. */}
                      <th scope="row" className={`${TH} bg-white font-medium text-gray-600`}>
                        第 {period} 節
                      </th>
                      {WEEKDAYS.map((weekday) => {
                        const nonTeachingLabel = cellLabelOf(weekday, period);
                        const isHighlighted = isHighlightedCell(weekday, period);
                        // Non-teaching cells show only their own label (or
                        // the generic fallback) -- never any guessed-at
                        // administrative content, and never a schedule
                        // lookup at all.
                        if (nonTeachingLabel !== null) {
                          return (
                            <td
                              key={weekday}
                              className={`${TD} text-gray-400 ${isHighlighted ? TD_HIGHLIGHT : "bg-gray-50"}`}
                            >
                              {nonTeachingLabel}
                            </td>
                          );
                        }
                        const matches = schedules.filter(
                          (schedule) =>
                            schedule.period === period &&
                            schedule.weekday === weekday &&
                            targetIdOf(schedule, viewMode) === selectedTargetId,
                        );
                        const schedule = matches[0];
                        return (
                          <td key={weekday} className={isHighlighted ? `${TD} ${TD_HIGHLIGHT}` : TD}>
                            {schedule !== undefined && (
                              <>
                                {matches.length > 1 && (
                                  <span title="這個時段出現多筆排課結果，顯示第一筆">
                                    ⚠️{" "}
                                  </span>
                                )}
                                <span className="font-medium text-gray-900">
                                  {schedule.subjectName}
                                </span>
                                <br />
                                <span className="text-gray-500">
                                  {cellDetailOf(schedule, viewMode)}
                                </span>
                              </>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
