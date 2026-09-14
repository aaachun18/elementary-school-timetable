import { useState, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
import { list as listScheduleVersions } from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listClasses } from "../api/classes";
import { list as listTeachers } from "../api/teachers";
import { list as listRooms } from "../api/rooms";
import { useResource } from "../hooks/useResource";
import { useTimetableData, timeSlotKey, type EnrichedSchedule } from "../hooks/useTimetableData";
import { formatVersionLabel } from "../utils/scheduleVersionFormat";
import { formatWeekday } from "../utils/timeSlotFormat";

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

  function handleSelectViewMode(mode: ViewMode): void {
    setViewMode(mode);
    // A classId is meaningless as a teacherId/roomId and vice versa --
    // switching axis always starts the target selection over.
    setSelectedTargetId(null);
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
    return <p>載入中…</p>;
  }
  if (lookupErrorMessage !== null) {
    return <p role="alert">{lookupErrorMessage}</p>;
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

  return (
    <div>
      <h1>課表檢視</h1>

      <section>
        <label htmlFor="timetable-version-select">選擇排課版本</label>
        <br />
        <select
          id="timetable-version-select"
          value={selectedVersionId ?? ""}
          onChange={(event) => {
            setSelectedVersionId(
              event.target.value === "" ? null : Number(event.target.value),
            );
            setSelectedTargetId(null);
          }}
        >
          <option value="">請選擇…</option>
          {versions.map((version) => (
            <option key={version.id} value={version.id}>
              {formatVersionLabel(version, semesterById, academicYearById)}
            </option>
          ))}
        </select>
      </section>

      {selectedVersionId !== null && (
        <section>
          <nav>
            {VIEW_MODES.map((mode) => (
              <button
                key={mode.key}
                type="button"
                onClick={() => handleSelectViewMode(mode.key)}
                aria-pressed={viewMode === mode.key}
              >
                {mode.label}
              </button>
            ))}
          </nav>

          <label htmlFor="timetable-target-select">
            {viewMode === "class" ? "選擇班級" : viewMode === "teacher" ? "選擇教師" : "選擇教室"}
          </label>
          <br />
          <select
            id="timetable-target-select"
            value={selectedTargetId ?? ""}
            onChange={(event) =>
              setSelectedTargetId(
                event.target.value === "" ? null : Number(event.target.value),
              )
            }
          >
            <option value="">請選擇…</option>
            {targetOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>

          {timetable.isLoading && <p>載入中…</p>}
          {timetable.errorMessage !== null && (
            <p role="alert">{timetable.errorMessage}</p>
          )}

          {timetable.data !== null && selectedTargetId !== null && (
            <table>
              <thead>
                <tr>
                  <th>節次</th>
                  {WEEKDAYS.map((weekday) => (
                    <th key={weekday}>{formatWeekday(weekday)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => (
                  <tr key={period}>
                    {/* Task 35.5: the row header is now a plain,
                        weekday-independent period number -- no label is
                        read here, since a single period can have
                        different labels on different weekdays. */}
                    <th scope="row">第 {period} 節</th>
                    {WEEKDAYS.map((weekday) => {
                      const nonTeachingLabel = cellLabelOf(weekday, period);
                      // Non-teaching cells show only their own label (or
                      // the generic fallback) -- never any guessed-at
                      // administrative content, and never a schedule
                      // lookup at all.
                      if (nonTeachingLabel !== null) {
                        return <td key={weekday}>{nonTeachingLabel}</td>;
                      }
                      const matches = schedules.filter(
                        (schedule) =>
                          schedule.period === period &&
                          schedule.weekday === weekday &&
                          targetIdOf(schedule, viewMode) === selectedTargetId,
                      );
                      const schedule = matches[0];
                      return (
                        <td key={weekday}>
                          {schedule !== undefined && (
                            <>
                              {matches.length > 1 && (
                                <span title="這個時段出現多筆排課結果,顯示第一筆">
                                  ⚠️{" "}
                                </span>
                              )}
                              {schedule.subjectName}
                              <br />
                              {cellDetailOf(schedule, viewMode)}
                            </>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}
