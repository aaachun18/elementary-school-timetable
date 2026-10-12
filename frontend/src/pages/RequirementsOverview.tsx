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

// Same red (#b00020), row-scoped error display every CRUD tab in
// DataBrowser.tsx already uses -- this page lives separately from that
// file, so it gets its own copy of the constant rather than importing
// across pages.
const ROW_ERROR_STYLE = { color: "#b00020", margin: "0.25em 0 0 0" } as const;

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
    <tr>
      <td>
        <select
          value={semesterId}
          onChange={(event) => {
            setSemesterId(event.target.value === "" ? "" : Number(event.target.value));
            setSubjectId("");
          }}
          disabled={isPending || !hasSemesterOptions}
          aria-label="學期"
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
      <td>
        <select
          value={classId}
          onChange={(event) => {
            setClassId(event.target.value === "" ? "" : Number(event.target.value));
            setSubjectId("");
          }}
          disabled={isPending || !hasClassOptions}
          aria-label="班級"
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
      <td>
        <select
          value={subjectId}
          onChange={(event) =>
            setSubjectId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending || !hasSubjectOptions}
          aria-label="科目"
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
      <td>
        <input
          type="number"
          value={weeklyPeriodsText}
          onChange={(event) => setWeeklyPeriodsText(event.target.value)}
          disabled={isPending}
          aria-label="每週節數"
        />
      </td>
      <td>
        <select
          value={requiredTeacherId}
          onChange={(event) =>
            setRequiredTeacherId(
              event.target.value === "" ? "" : Number(event.target.value),
            )
          }
          disabled={isPending}
          aria-label="指定教師"
        >
          <option value="">不指定(由系統自動分配)</option>
          {teachers.map((teacher) => (
            <option key={teacher.id} value={teacher.id}>
              {teacher.name}
            </option>
          ))}
        </select>
      </td>
      <td>
        <input
          value={requiredRoomType}
          onChange={(event) => setRequiredRoomType(event.target.value)}
          disabled={isPending}
          aria-label="指定教室類型"
          placeholder="原班教室"
        />
      </td>
      <td>
        <input
          type="number"
          value={consecutiveLimitText}
          onChange={(event) => setConsecutiveLimitText(event.target.value)}
          disabled={isPending}
          aria-label="連續節數限制"
          placeholder="未設定"
        />
      </td>
      <td>
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
        >
          確認
        </button>
        <button type="button" onClick={onCancel} disabled={isPending}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" style={ROW_ERROR_STYLE}>{errorMessage}</p>}
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
      <tr>
        <td>
          <select
            value={draftSemesterId}
            onChange={(event) => {
              setDraftSemesterId(Number(event.target.value));
            }}
            disabled={isPending || semesters.length === 0}
            aria-label="學期"
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
        <td>
          <select
            value={draftClassId}
            onChange={(event) => setDraftClassId(Number(event.target.value))}
            disabled={isPending || classes.length === 0}
            aria-label="班級"
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
        <td>
          <select
            value={draftSubjectId}
            onChange={(event) => setDraftSubjectId(Number(event.target.value))}
            disabled={isPending || availableSubjects.length === 0}
            aria-label="科目"
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
        <td>
          <input
            type="number"
            value={draftWeeklyPeriodsText}
            onChange={(event) => setDraftWeeklyPeriodsText(event.target.value)}
            disabled={isPending}
            aria-label="每週節數"
          />
        </td>
        <td>
          <select
            value={draftRequiredTeacherId}
            onChange={(event) =>
              setDraftRequiredTeacherId(
                event.target.value === "" ? "" : Number(event.target.value),
              )
            }
            disabled={isPending}
            aria-label="指定教師"
          >
            <option value="">不指定(由系統自動分配)</option>
            {teachers.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {teacher.name}
              </option>
            ))}
          </select>
        </td>
        <td>
          <input
            value={draftRequiredRoomType}
            onChange={(event) => setDraftRequiredRoomType(event.target.value)}
            disabled={isPending}
            aria-label="指定教室類型"
            placeholder="原班教室"
          />
        </td>
        <td>
          <input
            type="number"
            value={draftConsecutiveLimitText}
            onChange={(event) => setDraftConsecutiveLimitText(event.target.value)}
            disabled={isPending}
            aria-label="連續節數限制"
            placeholder="未設定"
          />
        </td>
        <td>
          <button
            type="button"
            onClick={handleConfirmEdit}
            disabled={isPending || draftWeeklyPeriods === null}
          >
            確認
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" style={ROW_ERROR_STYLE}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr>
      <td>
        {(() => {
          const semester = semesterById.get(requirement.semester_id);
          return semester !== undefined
            ? formatSemesterLabel(semester, academicYearById)
            : `學期 ID ${requirement.semester_id}`;
        })()}
      </td>
      <td>
        {classNameById.get(requirement.class_id) ?? `班級 ID ${requirement.class_id}`}
      </td>
      <td>
        {subjectNameById.get(requirement.subject_id) ?? `科目 ID ${requirement.subject_id}`}
      </td>
      <td>{requirement.weekly_periods}</td>
      <td>
        {requirement.required_teacher_id === null
          ? "未指定(由系統自動分配)"
          : (teacherNameById.get(requirement.required_teacher_id) ??
            `教師 ID ${requirement.required_teacher_id}`)}
      </td>
      <td>{requirement.required_room_type ?? "原班教室"}</td>
      <td>{requirement.consecutive_limit ?? "未設定"}</td>
      <td>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" style={ROW_ERROR_STYLE}>{errorMessage}</p>
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
    return <p>載入中…</p>;
  }
  if (errorMessage !== null) {
    return <p role="alert">{errorMessage}</p>;
  }
  if (requirementsResource.data === null) {
    // Not reachable in practice -- useResource only leaves both isLoading
    // and errorMessage falsy after a successful fetch, which always sets
    // data -- but TypeScript can't see that invariant, so this is a real
    // (if defensive) fallback rather than a type-cast to satisfy it.
    return <p role="alert">資料載入異常,請重新整理頁面。</p>;
  }

  function handleDelete(id: number, label: string): void {
    if (window.confirm(`確定要刪除「${label}」這筆排課需求嗎?此操作無法復原。`)) {
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
    <div>
      <h1>排課需求總覽</h1>
      {/* Task 47: generate-lessons diff-syncs off this table's CURRENT
          contents (Task 21) -- a version that's already had 展開課程清單
          run is NOT automatically kept in sync when a requirement changes
          here afterwards. */}
      <p style={{ color: "#555", fontSize: "0.9em" }}>
        修改排課需求後,請記得回到排課控制台重新執行「展開課程清單」以同步最新變動。
      </p>
      {isAdmin && (
        <p>
          <button
            type="button"
            onClick={crud.startAdding}
            disabled={crud.isAdding || crud.pendingKey !== null}
          >
            新增
          </button>
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th>學期</th>
            <th>班級</th>
            <th>科目</th>
            <th>每週節數</th>
            <th>指定教師</th>
            <th>指定教室類型</th>
            <th>連續節數限制</th>
            {isAdmin && <th>操作</th>}
          </tr>
        </thead>
        <tbody>
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
  );
}
