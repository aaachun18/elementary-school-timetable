import { useEffect, useState, type ReactElement } from "react";
import {
  list as listRequirements,
  create as createRequirement,
  update as updateRequirement,
  remove as removeRequirement,
} from "../api/classSubjectRequirements";
import { list as listSemesters } from "../api/semesters";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listClasses } from "../api/classes";
import { list as listSubjects } from "../api/subjects";
import { list as listTeachers } from "../api/teachers";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import { formatSemesterLabel } from "../utils/scheduleVersionFormat";
import type {
  ClassSubjectRequirement,
  ClassSubjectRequirementCreate,
  ClassSubjectRequirementUpdate,
} from "../types/classSubjectRequirement";
import type { Semester } from "../types/semester";
import type { Class } from "../types/class";
import type { Subject } from "../types/subject";
import type { Teacher } from "../types/teacher";
import { isCurrentUserAdmin } from "../utils/auth";
import {
  BUTTON_DANGER_SM,
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY_SM,
  ERROR_TEXT,
  HELP_TEXT,
  LOADING_TEXT,
  LOCK_BADGE,
  PAGE,
  PAGE_TITLE,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_LOCKED,
  TH,
  TR_HOVER,
} from "../styles/ui";

// Same red error text every CRUD table in DataBrowser.tsx already uses --
// this page lives separately from that file, so it imports the shared
// token from styles/ui.ts the same way, rather than duplicating a literal
// color value.
const ROW_SELECT = `${SELECT} w-full`;

// Task 47: this table's UNIQUE constraint is (semester_id, class_id,
// subject_id) -- the frontend can't know for certain whether a given
// combination is already taken (that needs a real query, which is what
// the 409 on submit is for), but once both semester_id and class_id are
// picked, it CAN narrow the 科目 dropdown to exclude subjects this
// class/semester already has a requirement for, cutting down on the most
// common accidental-duplicate case. `excludeRequirementId` lets an edit
// row exclude every OTHER requirement's subject but still keep its own
// current subject selectable.
function getTakenSubjectIds(
  requirements: ClassSubjectRequirement[],
  semesterId: number | "",
  classId: number | "",
  excludeRequirementId?: number,
): Set<number> {
  if (semesterId === "" || classId === "") {
    return new Set();
  }
  return new Set(
    requirements
      .filter(
        (requirement) =>
          requirement.semester_id === semesterId &&
          requirement.class_id === classId &&
          requirement.id !== excludeRequirementId,
      )
      .map((requirement) => requirement.subject_id),
  );
}

function RequirementNewRow({
  requirements,
  semesters,
  academicYearById,
  classes,
  subjects,
  teachers,
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  requirements: ClassSubjectRequirement[];
  semesters: Semester[];
  academicYearById: Map<number, number>;
  classes: Class[];
  subjects: Subject[];
  teachers: Teacher[];
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: ClassSubjectRequirementCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [semesterId, setSemesterId] = useState<number | "">("");
  const [classId, setClassId] = useState<number | "">("");
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [weeklyPeriodsText, setWeeklyPeriodsText] = useState("");
  const [requiredTeacherId, setRequiredTeacherId] = useState<number | "">("");
  const [requiredRoomType, setRequiredRoomType] = useState("");
  const [consecutiveLimitText, setConsecutiveLimitText] = useState("");

  const weeklyPeriods = weeklyPeriodsText === "" ? null : Number(weeklyPeriodsText);
  const consecutiveLimit =
    consecutiveLimitText === "" ? null : Number(consecutiveLimitText);

  const hasSemesterOptions = semesters.length > 0;
  const hasClassOptions = classes.length > 0;
  const takenSubjectIds = getTakenSubjectIds(requirements, semesterId, classId);
  const availableSubjects = subjects.filter((subject) => !takenSubjectIds.has(subject.id));
  const hasSubjectOptions = availableSubjects.length > 0;

  function handleConfirm(): void {
    if (semesterId === "" || classId === "" || subjectId === "" || weeklyPeriods === null) {
      return;
    }
    onConfirm({
      semester_id: semesterId,
      class_id: classId,
      subject_id: subjectId,
      weekly_periods: weeklyPeriods,
      required_teacher_id: requiredTeacherId === "" ? null : requiredTeacherId,
      required_room_type: requiredRoomType.trim() === "" ? null : requiredRoomType,
      consecutive_limit: consecutiveLimit,
    });
  }

  return (
    <tr data-row-key="new" className="bg-blue-50/40">
      <td className={TD}>
        <select
          value={semesterId}
          onChange={(event) => {
            setSemesterId(event.target.value === "" ? "" : Number(event.target.value));
            setSubjectId("");
          }}
          disabled={isPending || !hasSemesterOptions}
          aria-label="學期"
          className={ROW_SELECT}
        >
          {hasSemesterOptions ? (
            <>
              <option value="">請選擇…</option>
              {semesters.map((semester) => (
                <option key={semester.id} value={semester.id}>
                  {formatSemesterLabel(semester, academicYearById)}
                </option>
              ))}
            </>
          ) : (
            <option value="">尚無可選項目</option>
          )}
        </select>
      </td>
      <td className={TD}>
        <select
          value={classId}
          onChange={(event) => {
            setClassId(event.target.value === "" ? "" : Number(event.target.value));
            setSubjectId("");
          }}
          disabled={isPending || !hasClassOptions}
          aria-label="班級"
          className={ROW_SELECT}
        >
          {hasClassOptions ? (
            <>
              <option value="">請選擇…</option>
              {classes.map((classItem) => (
                <option key={classItem.id} value={classItem.id}>
                  {classItem.name}
                </option>
              ))}
            </>
          ) : (
            <option value="">尚無可選項目</option>
          )}
        </select>
      </td>
      <td className={TD}>
        <select
          value={subjectId}
          onChange={(event) =>
            setSubjectId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending || !hasSubjectOptions}
          aria-label="科目"
          className={ROW_SELECT}
        >
          {hasSubjectOptions ? (
            <>
              <option value="">請選擇…</option>
              {availableSubjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </>
          ) : (
            <option value="">尚無可選項目</option>
          )}
        </select>
      </td>
      <td className={TD}>
        <input
          type="number"
          value={weeklyPeriodsText}
          onChange={(event) => setWeeklyPeriodsText(event.target.value)}
          disabled={isPending}
          aria-label="每週節數"
          className={`${SELECT} w-20`}
        />
      </td>
      <td className={TD}>
        <select
          value={requiredTeacherId}
          onChange={(event) =>
            setRequiredTeacherId(
              event.target.value === "" ? "" : Number(event.target.value),
            )
          }
          disabled={isPending}
          aria-label="指定教師"
          className={ROW_SELECT}
        >
          <option value="">不指定（由系統自動分配）</option>
          {teachers.map((teacher) => (
            <option key={teacher.id} value={teacher.id}>
              {teacher.name}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        <input
          value={requiredRoomType}
          onChange={(event) => setRequiredRoomType(event.target.value)}
          disabled={isPending}
          aria-label="指定教室類型"
          placeholder="原班教室"
          className={`${SELECT} w-28`}
        />
      </td>
      <td className={TD}>
        <input
          type="number"
          value={consecutiveLimitText}
          onChange={(event) => setConsecutiveLimitText(event.target.value)}
          disabled={isPending}
          aria-label="連續節數限制"
          placeholder="未設定"
          className={`${SELECT} w-20`}
        />
      </td>
      <td className={TD}>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleConfirm}
            disabled={
              isPending ||
              semesterId === "" ||
              classId === "" ||
              subjectId === "" ||
              weeklyPeriods === null
            }
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
        </div>
        {errorMessage !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {errorMessage}
          </p>
        )}
      </td>
    </tr>
  );
}

function RequirementRow({
  requirement,
  requirements,
  semesters,
  academicYearById,
  semesterById,
  classes,
  classNameById,
  subjects,
  subjectNameById,
  teachers,
  teacherNameById,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  requirement: ClassSubjectRequirement;
  requirements: ClassSubjectRequirement[];
  semesters: Semester[];
  academicYearById: Map<number, number>;
  semesterById: Map<number, Semester>;
  classes: Class[];
  classNameById: Map<number, string>;
  subjects: Subject[];
  subjectNameById: Map<number, string>;
  teachers: Teacher[];
  teacherNameById: Map<number, string>;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: ClassSubjectRequirementUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftSemesterId, setDraftSemesterId] = useState(requirement.semester_id);
  const [draftClassId, setDraftClassId] = useState(requirement.class_id);
  const [draftSubjectId, setDraftSubjectId] = useState(requirement.subject_id);
  const [draftWeeklyPeriodsText, setDraftWeeklyPeriodsText] = useState(
    String(requirement.weekly_periods),
  );
  const [draftRequiredTeacherId, setDraftRequiredTeacherId] = useState<number | "">(
    requirement.required_teacher_id ?? "",
  );
  const [draftRequiredRoomType, setDraftRequiredRoomType] = useState(
    requirement.required_room_type ?? "",
  );
  const [draftConsecutiveLimitText, setDraftConsecutiveLimitText] = useState(
    requirement.consecutive_limit === null ? "" : String(requirement.consecutive_limit),
  );

  // Re-seeds every draft field from the row's current values every time
  // inline editing starts -- same pattern every other CRUD row in this
  // app already uses (see DataBrowser.tsx), so 取消 needs no reset logic
  // of its own: it doesn't touch the drafts at all, the next edit start
  // always re-seeds them.
  useEffect(() => {
    if (isEditing) {
      setDraftSemesterId(requirement.semester_id);
      setDraftClassId(requirement.class_id);
      setDraftSubjectId(requirement.subject_id);
      setDraftWeeklyPeriodsText(String(requirement.weekly_periods));
      setDraftRequiredTeacherId(requirement.required_teacher_id ?? "");
      setDraftRequiredRoomType(requirement.required_room_type ?? "");
      setDraftConsecutiveLimitText(
        requirement.consecutive_limit === null
          ? ""
          : String(requirement.consecutive_limit),
      );
    }
  }, [isEditing, requirement]);

  const draftWeeklyPeriods =
    draftWeeklyPeriodsText === "" ? null : Number(draftWeeklyPeriodsText);
  const draftConsecutiveLimit =
    draftConsecutiveLimitText === "" ? null : Number(draftConsecutiveLimitText);

  const takenSubjectIds = getTakenSubjectIds(
    requirements,
    draftSemesterId,
    draftClassId,
    requirement.id,
  );
  const availableSubjects = subjects.filter(
    (subject) => !takenSubjectIds.has(subject.id) || subject.id === draftSubjectId,
  );

  function handleConfirmEdit(): void {
    if (draftWeeklyPeriods === null) {
      return;
    }
    onConfirmEdit({
      semester_id: draftSemesterId,
      class_id: draftClassId,
      subject_id: draftSubjectId,
      weekly_periods: draftWeeklyPeriods,
      required_teacher_id: draftRequiredTeacherId === "" ? null : draftRequiredTeacherId,
      required_room_type:
        draftRequiredRoomType.trim() === "" ? null : draftRequiredRoomType,
      consecutive_limit: draftConsecutiveLimit,
    });
  }

  if (isEditing) {
    return (
      <tr className="bg-blue-50/40" data-row-key={requirement.id}>
        <td className={TD}>
          <select
            value={draftSemesterId}
            onChange={(event) => {
              setDraftSemesterId(Number(event.target.value));
            }}
            disabled={isPending || semesters.length === 0}
            aria-label="學期"
            className={ROW_SELECT}
          >
            {semesters.length > 0 ? (
              semesters.map((semester) => (
                <option key={semester.id} value={semester.id}>
                  {formatSemesterLabel(semester, academicYearById)}
                </option>
              ))
            ) : (
              <option value={draftSemesterId}>尚無可選項目</option>
            )}
          </select>
        </td>
        <td className={TD}>
          <select
            value={draftClassId}
            onChange={(event) => setDraftClassId(Number(event.target.value))}
            disabled={isPending || classes.length === 0}
            aria-label="班級"
            className={ROW_SELECT}
          >
            {classes.length > 0 ? (
              classes.map((classItem) => (
                <option key={classItem.id} value={classItem.id}>
                  {classItem.name}
                </option>
              ))
            ) : (
              <option value={draftClassId}>尚無可選項目</option>
            )}
          </select>
        </td>
        <td className={TD}>
          <select
            value={draftSubjectId}
            onChange={(event) => setDraftSubjectId(Number(event.target.value))}
            disabled={isPending || availableSubjects.length === 0}
            aria-label="科目"
            className={ROW_SELECT}
          >
            {availableSubjects.length > 0 ? (
              availableSubjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))
            ) : (
              <option value={draftSubjectId}>尚無可選項目</option>
            )}
          </select>
        </td>
        <td className={TD}>
          <input
            type="number"
            value={draftWeeklyPeriodsText}
            onChange={(event) => setDraftWeeklyPeriodsText(event.target.value)}
            disabled={isPending}
            aria-label="每週節數"
            className={`${SELECT} w-20`}
          />
        </td>
        <td className={TD}>
          <select
            value={draftRequiredTeacherId}
            onChange={(event) =>
              setDraftRequiredTeacherId(
                event.target.value === "" ? "" : Number(event.target.value),
              )
            }
            disabled={isPending}
            aria-label="指定教師"
            className={ROW_SELECT}
          >
            <option value="">不指定（由系統自動分配）</option>
            {teachers.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {teacher.name}
              </option>
            ))}
          </select>
        </td>
        <td className={TD}>
          <input
            value={draftRequiredRoomType}
            onChange={(event) => setDraftRequiredRoomType(event.target.value)}
            disabled={isPending}
            aria-label="指定教室類型"
            placeholder="原班教室"
            className={`${SELECT} w-28`}
          />
        </td>
        <td className={TD}>
          <input
            type="number"
            value={draftConsecutiveLimitText}
            onChange={(event) => setDraftConsecutiveLimitText(event.target.value)}
            disabled={isPending}
            aria-label="連續節數限制"
            placeholder="未設定"
            className={`${SELECT} w-20`}
          />
        </td>
        <td className={TD}>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleConfirmEdit}
              disabled={isPending || draftWeeklyPeriods === null}
              className={BUTTON_PRIMARY_SM}
            >
              {isPending ? "送出中…" : "確認"}
            </button>
            <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              取消
            </button>
          </div>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>
              {errorMessage}
            </p>
          )}
        </td>
      </tr>
    );
  }

  // Task 73: used by a PUBLISHED or ARCHIVED version (decided by the
  // backend's is_locked) -- shown greyed out with its reason, edit/delete
  // disabled. The backend's 409 stays as the last line of defense.
  const isLocked = requirement.is_locked;
  const cellClass = isLocked ? TD_LOCKED : TD;
  const lockedReason = "被已發布或已封存的課表使用，如需調整請先複製成草稿";

  return (
    <tr className={TR_HOVER}>
      <td className={cellClass}>
        {(() => {
          const semester = semesterById.get(requirement.semester_id);
          return semester !== undefined
            ? formatSemesterLabel(semester, academicYearById)
            : `學期 ID ${requirement.semester_id}`;
        })()}
      </td>
      <td className={cellClass}>
        {classNameById.get(requirement.class_id) ?? `班級 ID ${requirement.class_id}`}
      </td>
      <td className={cellClass}>
        {subjectNameById.get(requirement.subject_id) ?? `科目 ID ${requirement.subject_id}`}
      </td>
      <td className={cellClass}>{requirement.weekly_periods}</td>
      <td className={cellClass}>
        {requirement.required_teacher_id === null
          ? "未指定（由系統自動分配）"
          : (teacherNameById.get(requirement.required_teacher_id) ??
            `教師 ID ${requirement.required_teacher_id}`)}
      </td>
      <td className={cellClass}>{requirement.required_room_type ?? "原班教室"}</td>
      <td className={cellClass}>{requirement.consecutive_limit ?? "未設定"}</td>
      <td className={TD}>
        {isLocked && (
          <div className="mb-1 flex flex-col items-start gap-1">
            <span className={LOCK_BADGE}>
              <span aria-hidden="true">🔒</span>已鎖定
            </span>
            <span className="text-xs text-gray-500">{lockedReason}</span>
          </div>
        )}
        {isAdmin && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onStartEdit}
              disabled={isPending || isLocked}
              title={isLocked ? `無法編輯：${lockedReason}` : undefined}
              aria-label={isLocked ? `編輯（已鎖定，${lockedReason}）` : undefined}
              className={BUTTON_SECONDARY_SM}
            >
              編輯
            </button>
            <button
              type="button"
              onClick={onDelete}
              disabled={isPending || isLocked}
              title={isLocked ? `無法刪除：${lockedReason}` : undefined}
              aria-label={isLocked ? `刪除（已鎖定，${lockedReason}）` : undefined}
              className={BUTTON_DANGER_SM}
            >
              刪除
            </button>
          </div>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>
            {errorMessage}
          </p>
        )}
      </td>
    </tr>
  );
}

export default function RequirementsOverview(): ReactElement {
  const requirementsResource = useResource(() => listRequirements(), []);
  const semestersResource = useResource(() => listSemesters(), []);
  const academicYearsResource = useResource(() => listAcademicYears(), []);
  const classesResource = useResource(() => listClasses(), []);
  const subjectsResource = useResource(() => listSubjects(), []);
  const teachersResource = useResource(() => listTeachers(), []);

  const crud = useCrudList<
    ClassSubjectRequirement,
    ClassSubjectRequirementCreate,
    ClassSubjectRequirementUpdate
  >(requirementsResource.data, {
    create: createRequirement,
    update: updateRequirement,
    remove: removeRequirement,
  });

  const isAdmin = isCurrentUserAdmin();

  const isLoading =
    requirementsResource.isLoading ||
    semestersResource.isLoading ||
    academicYearsResource.isLoading ||
    classesResource.isLoading ||
    subjectsResource.isLoading ||
    teachersResource.isLoading;
  // Whichever of the six calls fails first is shown -- good enough here
  // since all six are needed together to render a single, meaningful row
  // (same stance Task 31 already took with the original four).
  const errorMessage =
    requirementsResource.errorMessage ??
    semestersResource.errorMessage ??
    academicYearsResource.errorMessage ??
    classesResource.errorMessage ??
    subjectsResource.errorMessage ??
    teachersResource.errorMessage;

  if (isLoading) {
    return (
      <div className={PAGE}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  if (errorMessage !== null) {
    return (
      <div className={PAGE}>
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      </div>
    );
  }
  if (requirementsResource.data === null) {
    // Not reachable in practice -- useResource only leaves both isLoading
    // and errorMessage falsy after a successful fetch, which always sets
    // data -- but TypeScript can't see that invariant, so this is a real
    // (if defensive) fallback rather than a type-cast to satisfy it.
    return (
      <div className={PAGE}>
        <p role="alert" className={ERROR_TEXT}>
          資料載入異常，請重新整理頁面。
        </p>
      </div>
    );
  }

  function handleDelete(id: number, label: string): void {
    if (window.confirm(`確定要刪除「${label}」這筆排課需求嗎？會連同已展開的課程清單一併刪除，此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  const semesters = semestersResource.data ?? [];
  const academicYears = academicYearsResource.data ?? [];
  const classes = classesResource.data ?? [];
  const subjects = subjectsResource.data ?? [];
  const teachers = teachersResource.data ?? [];

  // id -> name lookups, built once the supporting lists are in -- this is
  // the "join" the backend deliberately doesn't do for us (Task 31's
  // existing reasoning, unchanged by this Task).
  const academicYearById = new Map(
    academicYears.map((academicYear) => [academicYear.id, academicYear.year]),
  );
  const semesterById = new Map(semesters.map((semester) => [semester.id, semester]));
  const classNameById = new Map(classes.map((classItem) => [classItem.id, classItem.name]));
  const subjectNameById = new Map(subjects.map((subject) => [subject.id, subject.name]));
  const teacherNameById = new Map(teachers.map((teacher) => [teacher.id, teacher.name]));

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>排課需求總覽</h1>
      {/* Task 47: generate-lessons diff-syncs off this table's CURRENT
          contents (Task 21) -- a version that's already had 展開課程清單
          run is NOT automatically kept in sync when a requirement changes
          here afterwards. */}
      <p className={HELP_TEXT}>
        修改排課需求後，請記得回到排課控制台重新執行「展開課程清單」以同步最新變動。
      </p>
      {isAdmin && (
        <p className="mb-3">
          <button
            type="button"
            onClick={crud.startAdding}
            disabled={crud.isAdding || crud.pendingKey !== null}
            className={BUTTON_PRIMARY}
          >
            新增
          </button>
        </p>
      )}
      <div className={TABLE_WRAPPER}>
        <table className={TABLE}>
          <thead>
            <tr className={TABLE_HEAD_ROW}>
              <th className={TH}>學期</th>
              <th className={TH}>班級</th>
              <th className={TH}>科目</th>
              <th className={TH}>每週節數</th>
              <th className={TH}>指定教師</th>
              <th className={TH}>指定教室類型</th>
              <th className={TH}>連續節數限制</th>
              {isAdmin && <th className={TH}>操作</th>}
            </tr>
          </thead>
          <tbody onChange={crud.handleRowChange}>
            {crud.isAdding && (
              <RequirementNewRow
                requirements={crud.items}
                semesters={semesters}
                academicYearById={academicYearById}
                classes={classes}
                subjects={subjects}
                teachers={teachers}
                isPending={crud.pendingKey === "new"}
                errorMessage={crud.rowErrors.get("new") ?? null}
                onConfirm={(data) => void crud.submitCreate(data)}
                onCancel={crud.cancelAdding}
              />
            )}
            {crud.items.map((requirement) => (
              <RequirementRow
                key={requirement.id}
                requirement={requirement}
                requirements={crud.items}
                semesters={semesters}
                academicYearById={academicYearById}
                semesterById={semesterById}
                classes={classes}
                classNameById={classNameById}
                subjects={subjects}
                subjectNameById={subjectNameById}
                teachers={teachers}
                teacherNameById={teacherNameById}
                isAdmin={isAdmin}
                isEditing={crud.editingId === requirement.id}
                isPending={crud.pendingKey === requirement.id}
                errorMessage={crud.rowErrors.get(requirement.id)}
                onStartEdit={() => crud.startEditing(requirement.id)}
                onCancelEdit={crud.cancelEditing}
                onConfirmEdit={(data) => void crud.submitUpdate(requirement.id, data)}
                onDelete={() =>
                  handleDelete(
                    requirement.id,
                    `${classNameById.get(requirement.class_id) ?? requirement.class_id}的${
                      subjectNameById.get(requirement.subject_id) ?? requirement.subject_id
                    }`,
                  )
                }
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
