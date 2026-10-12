import { Fragment, useEffect, useState, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
import { list as listTeachers } from "../api/teachers";
import {
  list as listClasses,
  create as createClass,
  update as updateClass,
  remove as removeClass,
} from "../api/classes";
import {
  list as listSchools,
  create as createSchool,
  update as updateSchool,
  remove as removeSchool,
} from "../api/schools";
import {
  list as listSubjects,
  create as createSubject,
  update as updateSubject,
  remove as removeSubject,
} from "../api/subjects";
import {
  list as listRooms,
  create as createRoom,
  update as updateRoom,
  remove as removeRoom,
} from "../api/rooms";
import { list as listTimeSlots } from "../api/timeSlots";
import {
  list as listAcademicYears,
  create as createAcademicYear,
  update as updateAcademicYear,
  remove as removeAcademicYear,
} from "../api/academicYears";
import {
  list as listSemesters,
  create as createSemester,
  update as updateSemester,
  remove as removeSemester,
} from "../api/semesters";
import { list as listGrades } from "../api/grades";
import { listByTeacher as listTeacherSubjects } from "../api/teacherSubjects";
import { listByTeacher as listTeacherUnavailableSlots } from "../api/teacherAvailability";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import { formatTimeSlotLabel, formatWeekday } from "../utils/timeSlotFormat";
import { isCurrentUserAdmin } from "../utils/auth";
import type { School, SchoolCreate, SchoolUpdate } from "../types/school";
import type { Subject, SubjectCreate, SubjectUpdate } from "../types/subject";
import type { Room, RoomCreate, RoomUpdate } from "../types/room";
import type {
  AcademicYear,
  AcademicYearCreate,
  AcademicYearUpdate,
} from "../types/academicYear";
import type { Semester, SemesterCreate, SemesterUpdate } from "../types/semester";
import type { Class, ClassCreate, ClassUpdate } from "../types/class";
import type { Grade } from "../types/grade";

type TabKey =
  | "schools"
  | "academicYears"
  | "semesters"
  | "teachers"
  | "classes"
  | "subjects"
  | "rooms"
  | "timeSlots";

const TABS: { key: TabKey; label: string }[] = [
  { key: "schools", label: "學校" },
  { key: "academicYears", label: "學年度" },
  { key: "semesters", label: "學期" },
  { key: "teachers", label: "老師" },
  { key: "classes", label: "班級" },
  { key: "subjects", label: "科目" },
  { key: "rooms", label: "教室" },
  { key: "timeSlots", label: "時段" },
];

const TAB_KEYS = new Set<string>(TABS.map((tab) => tab.key));

function isTabKey(value: string | null): value is TabKey {
  return value !== null && TAB_KEYS.has(value);
}

function LoadingOrError({
  isLoading,
  errorMessage,
}: {
  isLoading: boolean;
  errorMessage: string | null;
}): ReactElement | null {
  if (isLoading) {
    return <p>載入中…</p>;
  }
  if (errorMessage !== null) {
    return <p role="alert">{errorMessage}</p>;
  }
  return null;
}

// Task 30's specific requirement: a teacher's row expands to show their
// qualifications (H5) and unavailable slots (H4) -- exactly the two pieces
// of data needed to check a "楊老師工作量超標"-style scheduling failure by
// hand, without needing Swagger UI.
function TeacherDetail({ teacherId }: { teacherId: number }): ReactElement {
  const subjects = useResource(() => listTeacherSubjects(teacherId), [teacherId]);
  const unavailableSlots = useResource(
    () => listTeacherUnavailableSlots(teacherId),
    [teacherId],
  );

  return (
    <div>
      <h3>任教資格</h3>
      <LoadingOrError
        isLoading={subjects.isLoading}
        errorMessage={subjects.errorMessage}
      />
      {subjects.data !== null &&
        (subjects.data.length === 0 ? (
          <p>無</p>
        ) : (
          <ul>
            {subjects.data.map((subject) => (
              <li key={subject.id}>{subject.name}</li>
            ))}
          </ul>
        ))}

      <h3>不可用時段</h3>
      <LoadingOrError
        isLoading={unavailableSlots.isLoading}
        errorMessage={unavailableSlots.errorMessage}
      />
      {unavailableSlots.data !== null &&
        (unavailableSlots.data.length === 0 ? (
          <p>無</p>
        ) : (
          <ul>
            {unavailableSlots.data.map((slot) => (
              <li key={slot.id}>{formatTimeSlotLabel(slot)}</li>
            ))}
          </ul>
        ))}
    </div>
  );
}

function TeachersTab(): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listTeachers(), []);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <table>
          <thead>
            <tr>
              <th>姓名</th>
              <th>啟用中</th>
              <th>最低每週節數</th>
              <th>最高每週節數</th>
            </tr>
          </thead>
          <tbody>
            {data.map((teacher) => {
              const isExpanded = expandedId === teacher.id;
              return (
                <Fragment key={teacher.id}>
                  {/* Task 32.6: a row quietly appearing below on click is
                      easy to miss -- the rotating arrow + background tint
                      make "this row is expanded" obvious at a glance,
                      without needing a new icon library (a plain
                      character, rotated with inline CSS). */}
                  <tr
                    onClick={() => setExpandedId(isExpanded ? null : teacher.id)}
                    aria-expanded={isExpanded}
                    style={{
                      cursor: "pointer",
                      backgroundColor: isExpanded ? "#eef4ff" : undefined,
                    }}
                  >
                    <td>
                      <span
                        aria-hidden="true"
                        style={{
                          display: "inline-block",
                          transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                          marginRight: "0.5em",
                        }}
                      >
                        ▶
                      </span>
                      {teacher.name}
                    </td>
                    <td>{teacher.is_active ? "是" : "否"}</td>
                    <td>{teacher.min_weekly_periods}</td>
                    <td>{teacher.max_weekly_periods}</td>
                  </tr>
                  {isExpanded && (
                    <tr style={{ backgroundColor: "#eef4ff" }}>
                      <td colSpan={4}>
                        <TeacherDetail teacherId={teacher.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

// --- Phase B (Task 42): School/Subject/Room's CRUD tabs. This is the
// FIRST implementation of the "standard CRUD interaction pattern" --
// later tables copy this shape (new-row via a dedicated "+row" component,
// existing rows via a row component that switches between a read-only
// <tr> and an inline-edit <tr> depending on whether it's the one being
// edited), not just the useCrudList() mechanics underneath it.
//
// row error display: a plain <p role="alert"> inside the row's own
// action <td>, same red (#b00020) FailureDiagnostics.tsx already uses --
// deliberately NOT a toast/banner, since the point is that this one row's
// failure is scoped to this one row, with every other row (and the rest
// of the page) staying exactly as it was.
const ROW_ERROR_STYLE = { color: "#b00020", margin: "0.25em 0 0 0" } as const;

function SchoolNewRow({
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: SchoolCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");

  return (
    <tr>
      <td>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="學校名稱"
        />
      </td>
      {/* SchoolCreate has no is_active field -- a new School is always
          created active (Task 7/8's existing decision); only editing an
          existing row can change it, so this column has nothing to input
          here. */}
      <td style={{ color: "#777" }}>啟用中(新增時固定)</td>
      <td>
        <button
          type="button"
          onClick={() => onConfirm({ name })}
          disabled={isPending || name.trim() === ""}
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

function SchoolRow({
  school,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  school: School;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: SchoolUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(school.name);
  const [draftIsActive, setDraftIsActive] = useState(school.is_active);

  // Re-seeds the draft from the row's current values every time inline
  // editing starts (and harmlessly again if `school` itself changes while
  // editing, e.g. an unrelated refetch) -- this is what makes "取消"
  // restore the original values: it doesn't need to reset anything
  // itself, the next edit start always does.
  useEffect(() => {
    if (isEditing) {
      setDraftName(school.name);
      setDraftIsActive(school.is_active);
    }
  }, [isEditing, school]);

  if (isEditing) {
    return (
      <tr>
        <td>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="學校名稱"
          />
        </td>
        <td>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            />
            啟用中
          </label>
        </td>
        <td>
          <button
            type="button"
            onClick={() => onConfirmEdit({ name: draftName, is_active: draftIsActive })}
            disabled={isPending || draftName.trim() === ""}
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
      <td>{school.name}</td>
      <td>{school.is_active ? "是" : "否"}</td>
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

function SchoolsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listSchools(), []);
  const crud = useCrudList<School, SchoolCreate, SchoolUpdate>(data, {
    create: createSchool,
    update: updateSchool,
    remove: removeSchool,
  });

  function handleDelete(id: number, name: string): void {
    if (window.confirm(`確定要刪除「${name}」嗎?此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th>名稱</th>
                <th>啟用中</th>
                {isAdmin && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {crud.isAdding && (
                <SchoolNewRow
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((school) => (
                <SchoolRow
                  key={school.id}
                  school={school}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === school.id}
                  isPending={crud.pendingKey === school.id}
                  errorMessage={crud.rowErrors.get(school.id)}
                  onStartEdit={() => crud.startEditing(school.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(school.id, data)}
                  onDelete={() => handleDelete(school.id, school.name)}
                />
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

// --- Phase B 批次 2(Task 44):AcademicYear/Semester/Class's CRUD tabs --
// AcademicYear is field-wise identical in shape to School/Subject (one
// scalar + is_active, no FK), reusing that exact pattern. Semester and
// Class are this batch's actual new ground: a required FK dropdown
// (Semester's academic_year_id, Class's grade_id) and, for Class, an
// OPTIONAL FK dropdown with its own "不指定" option (homeroom_room_id).

function AcademicYearNewRow({
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: AcademicYearCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [yearText, setYearText] = useState("");
  const year = yearText === "" ? null : Number(yearText);

  return (
    <tr>
      <td>
        <input
          type="number"
          value={yearText}
          onChange={(event) => setYearText(event.target.value)}
          disabled={isPending}
          aria-label="學年度"
        />
      </td>
      <td style={{ color: "#777" }}>啟用中(新增時固定)</td>
      <td>
        <button
          type="button"
          onClick={() => {
            if (year !== null) {
              onConfirm({ year });
            }
          }}
          disabled={isPending || year === null}
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

function AcademicYearRow({
  academicYear,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  academicYear: AcademicYear;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: AcademicYearUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftYearText, setDraftYearText] = useState(String(academicYear.year));
  const [draftIsActive, setDraftIsActive] = useState(academicYear.is_active);

  useEffect(() => {
    if (isEditing) {
      setDraftYearText(String(academicYear.year));
      setDraftIsActive(academicYear.is_active);
    }
  }, [isEditing, academicYear]);

  const draftYear = draftYearText === "" ? null : Number(draftYearText);

  if (isEditing) {
    return (
      <tr>
        <td>
          <input
            type="number"
            value={draftYearText}
            onChange={(event) => setDraftYearText(event.target.value)}
            disabled={isPending}
            aria-label="學年度"
          />
        </td>
        <td>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            />
            啟用中
          </label>
        </td>
        <td>
          <button
            type="button"
            onClick={() => {
              if (draftYear !== null) {
                onConfirmEdit({ year: draftYear, is_active: draftIsActive });
              }
            }}
            disabled={isPending || draftYear === null}
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
      <td>{academicYear.year}</td>
      <td>{academicYear.is_active ? "是" : "否"}</td>
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

function AcademicYearsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listAcademicYears(), []);
  const crud = useCrudList<AcademicYear, AcademicYearCreate, AcademicYearUpdate>(data, {
    create: createAcademicYear,
    update: updateAcademicYear,
    remove: removeAcademicYear,
  });

  function handleDelete(id: number, year: number): void {
    if (window.confirm(`確定要刪除「${year} 學年度」嗎?此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th>學年度</th>
                <th>啟用中</th>
                {isAdmin && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {crud.isAdding && (
                <AcademicYearNewRow
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((academicYear) => (
                <AcademicYearRow
                  key={academicYear.id}
                  academicYear={academicYear}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === academicYear.id}
                  isPending={crud.pendingKey === academicYear.id}
                  errorMessage={crud.rowErrors.get(academicYear.id)}
                  onStartEdit={() => crud.startEditing(academicYear.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(academicYear.id, data)}
                  onDelete={() => handleDelete(academicYear.id, academicYear.year)}
                />
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

// Semester.number is restricted to 1 or 2 at the DB level (CHECK
// constraint) -- a <select> with exactly those two options, rather than a
// free-form number input, means the UI simply cannot submit a value the
// backend would reject for this field.
const SEMESTER_NUMBER_OPTIONS = [1, 2];

function SemesterNewRow({
  academicYears,
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  academicYears: AcademicYear[];
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: SemesterCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [academicYearId, setAcademicYearId] = useState<number | "">("");
  const [numberValue, setNumberValue] = useState<number>(1);
  const hasAcademicYearOptions = academicYears.length > 0;

  return (
    <tr>
      <td>
        <select
          value={academicYearId}
          onChange={(event) =>
            setAcademicYearId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending || !hasAcademicYearOptions}
          aria-label="學年度"
        >
          {hasAcademicYearOptions ? (
            <>
              <option value="">請選擇…</option>
              {academicYears.map((academicYear) => (
                <option key={academicYear.id} value={academicYear.id}>
                  {academicYear.year} 學年度
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
          value={numberValue}
          onChange={(event) => setNumberValue(Number(event.target.value))}
          disabled={isPending}
          aria-label="學期"
        >
          {SEMESTER_NUMBER_OPTIONS.map((number) => (
            <option key={number} value={number}>
              第 {number} 學期
            </option>
          ))}
        </select>
      </td>
      <td style={{ color: "#777" }}>啟用中(新增時固定)</td>
      <td>
        <button
          type="button"
          onClick={() => {
            if (academicYearId !== "") {
              onConfirm({ academic_year_id: academicYearId, number: numberValue });
            }
          }}
          disabled={isPending || academicYearId === ""}
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

function SemesterRow({
  semester,
  academicYears,
  academicYearById,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  semester: Semester;
  academicYears: AcademicYear[];
  academicYearById: Map<number, AcademicYear>;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: SemesterUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftAcademicYearId, setDraftAcademicYearId] = useState(semester.academic_year_id);
  const [draftNumber, setDraftNumber] = useState(semester.number);
  const [draftIsActive, setDraftIsActive] = useState(semester.is_active);
  const hasAcademicYearOptions = academicYears.length > 0;

  useEffect(() => {
    if (isEditing) {
      setDraftAcademicYearId(semester.academic_year_id);
      setDraftNumber(semester.number);
      setDraftIsActive(semester.is_active);
    }
  }, [isEditing, semester]);

  if (isEditing) {
    return (
      <tr>
        <td>
          <select
            value={draftAcademicYearId}
            onChange={(event) => setDraftAcademicYearId(Number(event.target.value))}
            disabled={isPending || !hasAcademicYearOptions}
            aria-label="學年度"
          >
            {hasAcademicYearOptions ? (
              academicYears.map((academicYear) => (
                <option key={academicYear.id} value={academicYear.id}>
                  {academicYear.year} 學年度
                </option>
              ))
            ) : (
              <option value={draftAcademicYearId}>尚無可選項目</option>
            )}
          </select>
        </td>
        <td>
          <select
            value={draftNumber}
            onChange={(event) => setDraftNumber(Number(event.target.value))}
            disabled={isPending}
            aria-label="學期"
          >
            {SEMESTER_NUMBER_OPTIONS.map((number) => (
              <option key={number} value={number}>
                第 {number} 學期
              </option>
            ))}
          </select>
        </td>
        <td>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            />
            啟用中
          </label>
        </td>
        <td>
          <button
            type="button"
            onClick={() =>
              onConfirmEdit({
                academic_year_id: draftAcademicYearId,
                number: draftNumber,
                is_active: draftIsActive,
              })
            }
            disabled={isPending}
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

  const academicYearLabel = academicYearById.get(semester.academic_year_id);

  return (
    <tr>
      <td>
        {academicYearLabel !== undefined
          ? `${academicYearLabel.year} 學年度`
          : `學年度 ID ${semester.academic_year_id}`}
      </td>
      <td>第 {semester.number} 學期</td>
      <td>{semester.is_active ? "是" : "否"}</td>
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

function SemestersTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listSemesters(), []);
  const academicYearsResource = useResource(() => listAcademicYears(), []);
  const crud = useCrudList<Semester, SemesterCreate, SemesterUpdate>(data, {
    create: createSemester,
    update: updateSemester,
    remove: removeSemester,
  });

  function handleDelete(id: number, label: string): void {
    if (window.confirm(`確定要刪除「${label}」嗎?此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  const isLoadingAny = isLoading || academicYearsResource.isLoading;
  const combinedErrorMessage = errorMessage ?? academicYearsResource.errorMessage;
  const academicYears = academicYearsResource.data ?? [];
  const academicYearById = new Map(
    academicYears.map((academicYear) => [academicYear.id, academicYear]),
  );

  return (
    <div>
      <LoadingOrError isLoading={isLoadingAny} errorMessage={combinedErrorMessage} />
      {data !== null && !isLoadingAny && combinedErrorMessage === null && (
        <>
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
                <th>學年度</th>
                <th>學期</th>
                <th>啟用中</th>
                {isAdmin && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {crud.isAdding && (
                <SemesterNewRow
                  academicYears={academicYears}
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((semester) => {
                const academicYear = academicYearById.get(semester.academic_year_id);
                const label = `${
                  academicYear !== undefined
                    ? `${academicYear.year} 學年度`
                    : `學年度 ID ${semester.academic_year_id}`
                }第 ${semester.number} 學期`;
                return (
                  <SemesterRow
                    key={semester.id}
                    semester={semester}
                    academicYears={academicYears}
                    academicYearById={academicYearById}
                    isAdmin={isAdmin}
                    isEditing={crud.editingId === semester.id}
                    isPending={crud.pendingKey === semester.id}
                    errorMessage={crud.rowErrors.get(semester.id)}
                    onStartEdit={() => crud.startEditing(semester.id)}
                    onCancelEdit={crud.cancelEditing}
                    onConfirmEdit={(data) => void crud.submitUpdate(semester.id, data)}
                    onDelete={() => handleDelete(semester.id, label)}
                  />
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function ClassNewRow({
  grades,
  rooms,
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  grades: Grade[];
  rooms: Room[];
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: ClassCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [gradeId, setGradeId] = useState<number | "">("");
  const [name, setName] = useState("");
  const [homeroomRoomId, setHomeroomRoomId] = useState<number | "">("");
  const hasGradeOptions = grades.length > 0;

  return (
    <tr>
      <td>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="班級名稱"
        />
      </td>
      <td>
        <select
          value={gradeId}
          onChange={(event) =>
            setGradeId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending || !hasGradeOptions}
          aria-label="年級"
        >
          {hasGradeOptions ? (
            <>
              <option value="">請選擇…</option>
              {grades.map((grade) => (
                <option key={grade.id} value={grade.id}>
                  {grade.name}
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
          value={homeroomRoomId}
          onChange={(event) =>
            setHomeroomRoomId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending}
          aria-label="導師班教室"
        >
          <option value="">不指定</option>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>
              {room.name}
            </option>
          ))}
        </select>
      </td>
      <td style={{ color: "#777" }}>啟用中(新增時固定)</td>
      <td>
        <button
          type="button"
          onClick={() => {
            if (gradeId !== "" && name.trim() !== "") {
              onConfirm({
                grade_id: gradeId,
                name,
                homeroom_room_id: homeroomRoomId === "" ? null : homeroomRoomId,
              });
            }
          }}
          disabled={isPending || gradeId === "" || name.trim() === ""}
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

function ClassRow({
  classItem,
  grades,
  gradeById,
  rooms,
  roomById,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  classItem: Class;
  grades: Grade[];
  gradeById: Map<number, Grade>;
  rooms: Room[];
  roomById: Map<number, Room>;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: ClassUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(classItem.name);
  const [draftGradeId, setDraftGradeId] = useState(classItem.grade_id);
  const [draftHomeroomRoomId, setDraftHomeroomRoomId] = useState<number | "">(
    classItem.homeroom_room_id ?? "",
  );
  const [draftIsActive, setDraftIsActive] = useState(classItem.is_active);
  const hasGradeOptions = grades.length > 0;

  useEffect(() => {
    if (isEditing) {
      setDraftName(classItem.name);
      setDraftGradeId(classItem.grade_id);
      setDraftHomeroomRoomId(classItem.homeroom_room_id ?? "");
      setDraftIsActive(classItem.is_active);
    }
  }, [isEditing, classItem]);

  if (isEditing) {
    return (
      <tr>
        <td>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="班級名稱"
          />
        </td>
        <td>
          <select
            value={draftGradeId}
            onChange={(event) => setDraftGradeId(Number(event.target.value))}
            disabled={isPending || !hasGradeOptions}
            aria-label="年級"
          >
            {hasGradeOptions ? (
              grades.map((grade) => (
                <option key={grade.id} value={grade.id}>
                  {grade.name}
                </option>
              ))
            ) : (
              <option value={draftGradeId}>尚無可選項目</option>
            )}
          </select>
        </td>
        <td>
          <select
            value={draftHomeroomRoomId}
            onChange={(event) =>
              setDraftHomeroomRoomId(
                event.target.value === "" ? "" : Number(event.target.value),
              )
            }
            disabled={isPending}
            aria-label="導師班教室"
          >
            <option value="">不指定</option>
            {rooms.map((room) => (
              <option key={room.id} value={room.id}>
                {room.name}
              </option>
            ))}
          </select>
        </td>
        <td>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            />
            啟用中
          </label>
        </td>
        <td>
          <button
            type="button"
            onClick={() =>
              onConfirmEdit({
                name: draftName,
                grade_id: draftGradeId,
                homeroom_room_id: draftHomeroomRoomId === "" ? null : draftHomeroomRoomId,
                is_active: draftIsActive,
              })
            }
            disabled={isPending || draftName.trim() === ""}
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

  const grade = gradeById.get(classItem.grade_id);
  const homeroomRoom =
    classItem.homeroom_room_id !== null ? roomById.get(classItem.homeroom_room_id) : undefined;

  return (
    <tr>
      <td>{classItem.name}</td>
      <td>{grade !== undefined ? grade.name : `年級 ID ${classItem.grade_id}`}</td>
      <td>
        {classItem.homeroom_room_id === null
          ? "未指定"
          : homeroomRoom !== undefined
            ? homeroomRoom.name
            : `教室 ID ${classItem.homeroom_room_id}`}
      </td>
      <td>{classItem.is_active ? "是" : "否"}</td>
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

function ClassesTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listClasses(), []);
  const gradesResource = useResource(() => listGrades(), []);
  const roomsResource = useResource(() => listRooms(), []);
  const crud = useCrudList<Class, ClassCreate, ClassUpdate>(data, {
    create: createClass,
    update: updateClass,
    remove: removeClass,
  });

  function handleDelete(id: number, name: string): void {
    if (window.confirm(`確定要刪除「${name}」嗎?此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  const isLoadingAny = isLoading || gradesResource.isLoading || roomsResource.isLoading;
  const combinedErrorMessage =
    errorMessage ?? gradesResource.errorMessage ?? roomsResource.errorMessage;
  const grades = gradesResource.data ?? [];
  const rooms = roomsResource.data ?? [];
  const gradeById = new Map(grades.map((grade) => [grade.id, grade]));
  const roomById = new Map(rooms.map((room) => [room.id, room]));

  return (
    <div>
      <LoadingOrError isLoading={isLoadingAny} errorMessage={combinedErrorMessage} />
      {data !== null && !isLoadingAny && combinedErrorMessage === null && (
        <>
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
                <th>名稱</th>
                <th>年級</th>
                <th>導師班教室</th>
                <th>啟用中</th>
                {isAdmin && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {crud.isAdding && (
                <ClassNewRow
                  grades={grades}
                  rooms={rooms}
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((classItem) => (
                <ClassRow
                  key={classItem.id}
                  classItem={classItem}
                  grades={grades}
                  gradeById={gradeById}
                  rooms={rooms}
                  roomById={roomById}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === classItem.id}
                  isPending={crud.pendingKey === classItem.id}
                  errorMessage={crud.rowErrors.get(classItem.id)}
                  onStartEdit={() => crud.startEditing(classItem.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(classItem.id, data)}
                  onDelete={() => handleDelete(classItem.id, classItem.name)}
                />
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function SubjectNewRow({
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: SubjectCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");

  return (
    <tr>
      <td>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="科目名稱"
        />
      </td>
      <td style={{ color: "#777" }}>啟用中(新增時固定)</td>
      <td>
        <button
          type="button"
          onClick={() => onConfirm({ name })}
          disabled={isPending || name.trim() === ""}
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

function SubjectRow({
  subject,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  subject: Subject;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: SubjectUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(subject.name);
  const [draftIsActive, setDraftIsActive] = useState(subject.is_active);

  useEffect(() => {
    if (isEditing) {
      setDraftName(subject.name);
      setDraftIsActive(subject.is_active);
    }
  }, [isEditing, subject]);

  if (isEditing) {
    return (
      <tr>
        <td>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="科目名稱"
          />
        </td>
        <td>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            />
            啟用中
          </label>
        </td>
        <td>
          <button
            type="button"
            onClick={() => onConfirmEdit({ name: draftName, is_active: draftIsActive })}
            disabled={isPending || draftName.trim() === ""}
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
      <td>{subject.name}</td>
      <td>{subject.is_active ? "是" : "否"}</td>
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

function SubjectsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listSubjects(), []);
  const crud = useCrudList<Subject, SubjectCreate, SubjectUpdate>(data, {
    create: createSubject,
    update: updateSubject,
    remove: removeSubject,
  });

  function handleDelete(id: number, name: string): void {
    if (window.confirm(`確定要刪除「${name}」嗎?此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th>名稱</th>
                <th>啟用中</th>
                {isAdmin && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {crud.isAdding && (
                <SubjectNewRow
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((subject) => (
                <SubjectRow
                  key={subject.id}
                  subject={subject}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === subject.id}
                  isPending={crud.pendingKey === subject.id}
                  errorMessage={crud.rowErrors.get(subject.id)}
                  onStartEdit={() => crud.startEditing(subject.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(subject.id, data)}
                  onDelete={() => handleDelete(subject.id, subject.name)}
                />
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function RoomNewRow({
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: RoomCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");
  const [roomType, setRoomType] = useState("");
  // "" means "留空即可" (capacity left blank) -- kept as its own string
  // state rather than `number | null` so an in-progress empty input never
  // gets coerced to 0 while typing.
  const [capacityText, setCapacityText] = useState("");

  function handleConfirm(): void {
    onConfirm({
      name,
      room_type: roomType,
      capacity: capacityText === "" ? null : Number(capacityText),
    });
  }

  return (
    <tr>
      <td>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="教室名稱"
        />
      </td>
      <td>
        <input
          value={roomType}
          onChange={(event) => setRoomType(event.target.value)}
          disabled={isPending}
          aria-label="教室類型"
          placeholder="例如:普通教室"
        />
      </td>
      <td>
        <input
          type="number"
          min={0}
          value={capacityText}
          onChange={(event) => setCapacityText(event.target.value)}
          disabled={isPending}
          aria-label="容量"
          placeholder="留空即可"
        />
      </td>
      <td style={{ color: "#777" }}>啟用中(新增時固定)</td>
      <td>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={isPending || name.trim() === "" || roomType.trim() === ""}
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

function RoomRow({
  room,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  room: Room;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: RoomUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(room.name);
  const [draftRoomType, setDraftRoomType] = useState(room.room_type);
  const [draftCapacityText, setDraftCapacityText] = useState(
    room.capacity === null ? "" : String(room.capacity),
  );
  const [draftIsActive, setDraftIsActive] = useState(room.is_active);

  useEffect(() => {
    if (isEditing) {
      setDraftName(room.name);
      setDraftRoomType(room.room_type);
      setDraftCapacityText(room.capacity === null ? "" : String(room.capacity));
      setDraftIsActive(room.is_active);
    }
  }, [isEditing, room]);

  if (isEditing) {
    return (
      <tr>
        <td>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="教室名稱"
          />
        </td>
        <td>
          <input
            value={draftRoomType}
            onChange={(event) => setDraftRoomType(event.target.value)}
            disabled={isPending}
            aria-label="教室類型"
          />
        </td>
        <td>
          <input
            type="number"
            min={0}
            value={draftCapacityText}
            onChange={(event) => setDraftCapacityText(event.target.value)}
            disabled={isPending}
            aria-label="容量"
            placeholder="留空即可"
          />
        </td>
        <td>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            />
            啟用中
          </label>
        </td>
        <td>
          <button
            type="button"
            onClick={() =>
              onConfirmEdit({
                name: draftName,
                room_type: draftRoomType,
                capacity: draftCapacityText === "" ? null : Number(draftCapacityText),
                is_active: draftIsActive,
              })
            }
            disabled={isPending || draftName.trim() === "" || draftRoomType.trim() === ""}
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
      <td>{room.name}</td>
      <td>{room.room_type}</td>
      <td>{room.capacity ?? "未設定"}</td>
      <td>{room.is_active ? "是" : "否"}</td>
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

function RoomsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listRooms(), []);
  const crud = useCrudList<Room, RoomCreate, RoomUpdate>(data, {
    create: createRoom,
    update: updateRoom,
    remove: removeRoom,
  });

  function handleDelete(id: number, name: string): void {
    if (window.confirm(`確定要刪除「${name}」嗎?此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th>名稱</th>
                <th>類型</th>
                <th>容量</th>
                <th>啟用中</th>
                {isAdmin && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {crud.isAdding && (
                <RoomNewRow
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((room) => (
                <RoomRow
                  key={room.id}
                  room={room}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === room.id}
                  isPending={crud.pendingKey === room.id}
                  errorMessage={crud.rowErrors.get(room.id)}
                  onStartEdit={() => crud.startEditing(room.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(room.id, data)}
                  onDelete={() => handleDelete(room.id, room.name)}
                />
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function TimeSlotsTab(): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listTimeSlots(), []);

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <table>
          <thead>
            <tr>
              <th>星期</th>
              <th>節次</th>
              <th>教學節次</th>
              <th>開始時間</th>
              <th>結束時間</th>
            </tr>
          </thead>
          <tbody>
            {data.map((timeSlot) => (
              <tr key={timeSlot.id}>
                <td>{formatWeekday(timeSlot.weekday)}</td>
                <td>{timeSlot.period}</td>
                <td>{timeSlot.is_teaching_period ? "是" : "否"}</td>
                <td>{timeSlot.start_time ?? "未設定"}</td>
                <td>{timeSlot.end_time ?? "未設定"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function DataBrowser(): ReactElement {
  // Task 37: FailureDiagnostics.tsx's "請至 {頁面} 修正" links carry
  // ?tab=teachers (etc, see constants/violationPageMapping.ts) so a click
  // lands directly on the relevant tab instead of always the default. Read
  // once on mount, same "lazy useState initializer from a query param"
  // pattern TimetableView.tsx already uses for ?scheduleVersionId= --
  // switching tabs afterwards is still plain local state, not synced back
  // to the URL, matching how this page already behaved before this Task.
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    const requestedTab = searchParams.get("tab");
    return isTabKey(requestedTab) ? requestedTab : "teachers";
  });

  // Task 42: read once per mount, same as the token itself -- a role
  // doesn't change without a fresh login, which always re-mounts this page
  // (ProtectedRoute/Layout sit above it in the route tree), so there is no
  // "role changed mid-session" case this needs to react to.
  const isAdmin = isCurrentUserAdmin();

  return (
    <div>
      <h1>基礎資料瀏覽</h1>
      <nav>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            aria-pressed={activeTab === tab.key}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      {activeTab === "schools" && <SchoolsTab isAdmin={isAdmin} />}
      {activeTab === "academicYears" && <AcademicYearsTab isAdmin={isAdmin} />}
      {activeTab === "semesters" && <SemestersTab isAdmin={isAdmin} />}
      {activeTab === "teachers" && <TeachersTab />}
      {activeTab === "classes" && <ClassesTab isAdmin={isAdmin} />}
      {activeTab === "subjects" && <SubjectsTab isAdmin={isAdmin} />}
      {activeTab === "rooms" && <RoomsTab isAdmin={isAdmin} />}
      {activeTab === "timeSlots" && <TimeSlotsTab />}
    </div>
  );
}
