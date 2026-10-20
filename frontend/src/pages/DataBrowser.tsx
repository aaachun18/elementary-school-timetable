import { useEffect, useState, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
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
import {
  list as listTimeSlots,
  create as createTimeSlot,
  update as updateTimeSlot,
  remove as removeTimeSlot,
} from "../api/timeSlots";
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
import {
  list as listGrades,
  create as createGrade,
  update as updateGrade,
  remove as removeGrade,
} from "../api/grades";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import { buildPeriodDisplay } from "../utils/periodDisplay";
import { formatTimeSlotLabel, formatWeekday } from "../utils/timeSlotFormat";
import { isCurrentUserCoordinator } from "../utils/auth";
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
import type { Grade, GradeCreate, GradeUpdate } from "../types/grade";
import type { TimeSlot, TimeSlotCreate, TimeSlotUpdate } from "../types/timeSlot";
import {
  BUTTON_DANGER_SM,
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY_SM,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LOADING_TEXT,
  PAGE,
  PAGE_TITLE,
  SELECT,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
  TR_HOVER,
} from "../styles/ui";

// Task 98: schools moved to their own 系統管理員 page (SchoolManagement.tsx).
type TabKey =
  | "academicYears"
  | "semesters"
  | "grades"
  | "classes"
  | "subjects"
  | "rooms"
  | "timeSlots";

const TABS: { key: TabKey; label: string }[] = [
  { key: "academicYears", label: "學年度" },
  { key: "semesters", label: "學期" },
  { key: "grades", label: "年級" },
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
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  return null;
}

// --- Phase B (Task 42): School/Subject/Room's CRUD tabs. This is the
// FIRST implementation of the "standard CRUD interaction pattern" --
// later tables copy this shape (new-row via a dedicated "+row" component,
// existing rows via a row component that switches between a read-only
// <tr> and an inline-edit <tr> depending on whether it's the one being
// edited), not just the useCrudList() mechanics underneath it.
//
// row error display: a plain <p className={ERROR_TEXT}> inside the row's
// own action <td className={TD}> -- deliberately NOT a toast/banner, since the point is
// that this one row's failure is scoped to this one row, with every other
// row (and the rest of the page) staying exactly as it was.

// --- Task 45: Grade's CRUD tab. Unlike every other lookup table so far,
// Grade has no is_active column at all (see backend/app/models/
// grade_class.py) -- there is genuinely no field for the create form to
// omit, so (unlike School/Subject/AcademicYear) its row has nothing
// create-locked at all; every field is editable in both modes.
// level has a UNIQUE constraint, same DuplicateValueError 409 path as
// Subject.name -- no extra handling needed here either.

function GradeNewRow({
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: GradeCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");
  const [levelText, setLevelText] = useState("");
  const level = levelText === "" ? null : Number(levelText);

  return (
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="年級名稱"
        className={INPUT}
        />
      </td>
      <td className={TD}>
        <input
          type="number"
          value={levelText}
          onChange={(event) => setLevelText(event.target.value)}
          disabled={isPending}
          aria-label="年級序號"
        className={INPUT}
        />
      </td>
      <td className={TD}>
        <button
          type="button"
          onClick={() => {
            if (name.trim() !== "" && level !== null) {
              onConfirm({ name, level });
            }
          }}
          disabled={isPending || name.trim() === "" || level === null}
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
      </td>
    </tr>
  );
}

function GradeRow({
  grade,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  grade: Grade;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: GradeUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(grade.name);
  const [draftLevelText, setDraftLevelText] = useState(String(grade.level));

  useEffect(() => {
    if (isEditing) {
      setDraftName(grade.name);
      setDraftLevelText(String(grade.level));
    }
  }, [isEditing, grade]);

  const draftLevel = draftLevelText === "" ? null : Number(draftLevelText);

  if (isEditing) {
    return (
      <tr className="bg-blue-50/40" data-row-key={grade.id}>
        <td className={TD}>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="年級名稱"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <input
            type="number"
            value={draftLevelText}
            onChange={(event) => setDraftLevelText(event.target.value)}
            disabled={isPending}
            aria-label="年級序號"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <button
            type="button"
            onClick={() => {
              if (draftName.trim() !== "" && draftLevel !== null) {
                onConfirmEdit({ name: draftName, level: draftLevel });
              }
            }}
            disabled={isPending || draftName.trim() === "" || draftLevel === null}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{grade.name}</td>
      <td className={TD}>{grade.level}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
        )}
      </td>
    </tr>
  );
}

function GradesTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listGrades(), []);
  const crud = useCrudList<Grade, GradeCreate, GradeUpdate>(data, {
    create: createGrade,
    update: updateGrade,
    remove: removeGrade,
  });

  function handleDelete(id: number, name: string): void {
    if (window.confirm(`確定要刪除「${name}」嗎？此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th className={TH}>名稱</th>
                <th className={TH}>年級序號</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
              {crud.isAdding && (
                <GradeNewRow
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((grade) => (
                <GradeRow
                  key={grade.id}
                  grade={grade}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === grade.id}
                  isPending={crud.pendingKey === grade.id}
                  errorMessage={crud.rowErrors.get(grade.id)}
                  onStartEdit={() => crud.startEditing(grade.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(grade.id, data)}
                  onDelete={() => handleDelete(grade.id, grade.name)}
                />
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}
    </div>
  );
}

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
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="學校名稱"
        className={INPUT}
        />
      </td>
      {/* SchoolCreate has no is_active field -- a new School is always
          created active (Task 7/8's existing decision); only editing an
          existing row can change it, so this column has nothing to input
          here. */}
      <td className={`${TD} text-gray-400`}>啟用中（新增時固定）</td>
      <td className={TD}>
        <button
          type="button"
          onClick={() => onConfirm({ name })}
          disabled={isPending || name.trim() === ""}
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
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
      <tr className="bg-blue-50/40" data-row-key={school.id}>
        <td className={TD}>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="學校名稱"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            啟用中
          </label>
        </td>
        <td className={TD}>
          <button
            type="button"
            onClick={() => onConfirmEdit({ name: draftName, is_active: draftIsActive })}
            disabled={isPending || draftName.trim() === ""}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{school.name}</td>
      <td className={TD}>{school.is_active ? "是" : "否"}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
        )}
      </td>
    </tr>
  );
}

// Task 98: exported for the 系統管理員's SchoolManagement page.
export function SchoolsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listSchools(), []);
  const crud = useCrudList<School, SchoolCreate, SchoolUpdate>(data, {
    create: createSchool,
    update: updateSchool,
    remove: removeSchool,
  });

  function handleDelete(id: number, name: string): void {
    if (window.confirm(`確定要刪除「${name}」嗎？此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th className={TH}>名稱</th>
                <th className={TH}>啟用中</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
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
          </div>
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
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <input
          type="number"
          value={yearText}
          onChange={(event) => setYearText(event.target.value)}
          disabled={isPending}
          aria-label="學年度"
        className={INPUT}
        />
      </td>
      <td className={`${TD} text-gray-400`}>啟用中（新增時固定）</td>
      <td className={TD}>
        <button
          type="button"
          onClick={() => {
            if (year !== null) {
              onConfirm({ year });
            }
          }}
          disabled={isPending || year === null}
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
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
      <tr className="bg-blue-50/40" data-row-key={academicYear.id}>
        <td className={TD}>
          <input
            type="number"
            value={draftYearText}
            onChange={(event) => setDraftYearText(event.target.value)}
            disabled={isPending}
            aria-label="學年度"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            啟用中
          </label>
        </td>
        <td className={TD}>
          <button
            type="button"
            onClick={() => {
              if (draftYear !== null) {
                onConfirmEdit({ year: draftYear, is_active: draftIsActive });
              }
            }}
            disabled={isPending || draftYear === null}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{academicYear.year}</td>
      <td className={TD}>{academicYear.is_active ? "是" : "否"}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
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
    if (window.confirm(`確定要刪除「${year} 學年度」嗎？此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th className={TH}>學年度</th>
                <th className={TH}>啟用中</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
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
          </div>
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
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <select
          value={academicYearId}
          onChange={(event) =>
            setAcademicYearId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending || !hasAcademicYearOptions}
          aria-label="學年度"
        className={SELECT}
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
      <td className={TD}>
        <select
          value={numberValue}
          onChange={(event) => setNumberValue(Number(event.target.value))}
          disabled={isPending}
          aria-label="學期"
        className={SELECT}
        >
          {SEMESTER_NUMBER_OPTIONS.map((number) => (
            <option key={number} value={number}>
              第 {number} 學期
            </option>
          ))}
        </select>
      </td>
      <td className={`${TD} text-gray-400`}>啟用中（新增時固定）</td>
      <td className={TD}>
        <button
          type="button"
          onClick={() => {
            if (academicYearId !== "") {
              onConfirm({ academic_year_id: academicYearId, number: numberValue });
            }
          }}
          disabled={isPending || academicYearId === ""}
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
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
      <tr className="bg-blue-50/40" data-row-key={semester.id}>
        <td className={TD}>
          <select
            value={draftAcademicYearId}
            onChange={(event) => setDraftAcademicYearId(Number(event.target.value))}
            disabled={isPending || !hasAcademicYearOptions}
            aria-label="學年度"
          className={SELECT}
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
        <td className={TD}>
          <select
            value={draftNumber}
            onChange={(event) => setDraftNumber(Number(event.target.value))}
            disabled={isPending}
            aria-label="學期"
          className={SELECT}
          >
            {SEMESTER_NUMBER_OPTIONS.map((number) => (
              <option key={number} value={number}>
                第 {number} 學期
              </option>
            ))}
          </select>
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            啟用中
          </label>
        </td>
        <td className={TD}>
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
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  const academicYearLabel = academicYearById.get(semester.academic_year_id);

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>
        {academicYearLabel !== undefined
          ? `${academicYearLabel.year} 學年度`
          : `學年度 ID ${semester.academic_year_id}`}
      </td>
      <td className={TD}>第 {semester.number} 學期</td>
      <td className={TD}>{semester.is_active ? "是" : "否"}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
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
    if (window.confirm(`確定要刪除「${label}」嗎？此操作無法復原。`)) {
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
                <th className={TH}>學年度</th>
                <th className={TH}>學期</th>
                <th className={TH}>啟用中</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
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
          </div>
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
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="班級名稱"
        className={INPUT}
        />
      </td>
      <td className={TD}>
        <select
          value={gradeId}
          onChange={(event) =>
            setGradeId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending || !hasGradeOptions}
          aria-label="年級"
        className={SELECT}
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
      <td className={TD}>
        <select
          value={homeroomRoomId}
          onChange={(event) =>
            setHomeroomRoomId(event.target.value === "" ? "" : Number(event.target.value))
          }
          disabled={isPending}
          aria-label="導師班教室"
        className={SELECT}
        >
          <option value="">不指定</option>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>
              {room.name}
            </option>
          ))}
        </select>
      </td>
      <td className={`${TD} text-gray-400`}>啟用中（新增時固定）</td>
      <td className={TD}>
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
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
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
      <tr className="bg-blue-50/40" data-row-key={classItem.id}>
        <td className={TD}>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="班級名稱"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <select
            value={draftGradeId}
            onChange={(event) => setDraftGradeId(Number(event.target.value))}
            disabled={isPending || !hasGradeOptions}
            aria-label="年級"
          className={SELECT}
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
        <td className={TD}>
          <select
            value={draftHomeroomRoomId}
            onChange={(event) =>
              setDraftHomeroomRoomId(
                event.target.value === "" ? "" : Number(event.target.value),
              )
            }
            disabled={isPending}
            aria-label="導師班教室"
          className={SELECT}
          >
            <option value="">不指定</option>
            {rooms.map((room) => (
              <option key={room.id} value={room.id}>
                {room.name}
              </option>
            ))}
          </select>
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            啟用中
          </label>
        </td>
        <td className={TD}>
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
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  const grade = gradeById.get(classItem.grade_id);
  const homeroomRoom =
    classItem.homeroom_room_id !== null ? roomById.get(classItem.homeroom_room_id) : undefined;

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{classItem.name}</td>
      <td className={TD}>{grade !== undefined ? grade.name : `年級 ID ${classItem.grade_id}`}</td>
      <td className={TD}>
        {classItem.homeroom_room_id === null
          ? "未指定"
          : homeroomRoom !== undefined
            ? homeroomRoom.name
            : `教室 ID ${classItem.homeroom_room_id}`}
      </td>
      <td className={TD}>{classItem.is_active ? "是" : "否"}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
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
    if (window.confirm(`確定要刪除「${name}」嗎？此操作無法復原。`)) {
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
                <th className={TH}>名稱</th>
                <th className={TH}>年級</th>
                <th className={TH}>導師班教室</th>
                <th className={TH}>啟用中</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
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
          </div>
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
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="科目名稱"
        className={INPUT}
        />
      </td>
      <td className={`${TD} text-gray-400`}>啟用中（新增時固定）</td>
      <td className={TD}>
        <button
          type="button"
          onClick={() => onConfirm({ name })}
          disabled={isPending || name.trim() === ""}
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
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
      <tr className="bg-blue-50/40" data-row-key={subject.id}>
        <td className={TD}>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="科目名稱"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            啟用中
          </label>
        </td>
        <td className={TD}>
          <button
            type="button"
            onClick={() => onConfirmEdit({ name: draftName, is_active: draftIsActive })}
            disabled={isPending || draftName.trim() === ""}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{subject.name}</td>
      <td className={TD}>{subject.is_active ? "是" : "否"}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
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
    if (window.confirm(`確定要刪除「${name}」嗎？此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th className={TH}>名稱</th>
                <th className={TH}>啟用中</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
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
          </div>
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
  // "" means "留空即可" (capacity left blank) -- kept as its own string
  // state rather than `number | null` so an in-progress empty input never
  // gets coerced to 0 while typing.
  const [capacityText, setCapacityText] = useState("");

  function handleConfirm(): void {
    onConfirm({
      name,
      capacity: capacityText === "" ? null : Number(capacityText),
    });
  }

  return (
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isPending}
          aria-label="教室名稱"
          placeholder="這間教室自己的名字"
        className={INPUT}
        />
      </td>
      <td className={TD}>
        <input
          type="number"
          min={0}
          value={capacityText}
          onChange={(event) => setCapacityText(event.target.value)}
          disabled={isPending}
          aria-label="容量"
          placeholder="留空即可"
        className={INPUT}
        />
      </td>
      <td className={`${TD} text-gray-400`}>啟用中（新增時固定）</td>
      <td className={TD}>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={isPending || name.trim() === ""}
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
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
  const [draftCapacityText, setDraftCapacityText] = useState(
    room.capacity === null ? "" : String(room.capacity),
  );
  const [draftIsActive, setDraftIsActive] = useState(room.is_active);

  useEffect(() => {
    if (isEditing) {
      setDraftName(room.name);
      setDraftCapacityText(room.capacity === null ? "" : String(room.capacity));
      setDraftIsActive(room.is_active);
    }
  }, [isEditing, room]);

  if (isEditing) {
    return (
      <tr className="bg-blue-50/40" data-row-key={room.id}>
        <td className={TD}>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="教室名稱"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <input
            type="number"
            min={0}
            value={draftCapacityText}
            onChange={(event) => setDraftCapacityText(event.target.value)}
            disabled={isPending}
            aria-label="容量"
            placeholder="留空即可"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            啟用中
          </label>
        </td>
        <td className={TD}>
          <button
            type="button"
            onClick={() =>
              onConfirmEdit({
                name: draftName,
                capacity: draftCapacityText === "" ? null : Number(draftCapacityText),
                is_active: draftIsActive,
              })
            }
            disabled={isPending || draftName.trim() === ""}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{room.name}</td>
      <td className={TD}>{room.capacity ?? "未設定"}</td>
      <td className={TD}>{room.is_active ? "是" : "否"}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
        )}
      </td>
    </tr>
  );
}

// Task 98: a room is just its name (and capacity) -- a requirement names
// the one special room it needs, so rooms have no types any more.

function RoomsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listRooms(), []);
  const crud = useCrudList<Room, RoomCreate, RoomUpdate>(data, {
    create: createRoom,
    update: updateRoom,
    remove: removeRoom,
  });

  function handleDelete(id: number, name: string): void {
    if (window.confirm(`確定要刪除「${name}」嗎？此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
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
                <th className={TH}>名稱</th>
                <th className={TH}>容量</th>
                <th className={TH}>啟用中</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
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
          </div>
        </>
      )}
    </div>
  );
}

// weekday is 1-5 per the backend's CHECK constraint -- a <select> with
// exactly these 5 options (not a free-form number input) means the UI
// cannot submit a value that constraint would reject.
const WEEKDAY_OPTIONS = [1, 2, 3, 4, 5];

function TimeSlotNewRow({
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: TimeSlotCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [weekday, setWeekday] = useState(1);
  const [periodText, setPeriodText] = useState("");
  const [isTeachingPeriod, setIsTeachingPeriod] = useState(true);
  const [label, setLabel] = useState("");
  const period = periodText === "" ? null : Number(periodText);

  return (
    <tr data-row-key="new" className={TR_HOVER}>
      <td className={TD}>
        <select
          value={weekday}
          onChange={(event) => setWeekday(Number(event.target.value))}
          disabled={isPending}
          aria-label="星期"
        className={SELECT}
        >
          {WEEKDAY_OPTIONS.map((day) => (
            <option key={day} value={day}>
              {formatWeekday(day)}
            </option>
          ))}
        </select>
      </td>
      <td className={TD}>
        <input
          type="number"
          value={periodText}
          onChange={(event) => setPeriodText(event.target.value)}
          disabled={isPending}
          aria-label="節次"
        className={INPUT}
        />
      </td>
      <td className={TD}>
        <label>
          <input
            type="checkbox"
            checked={isTeachingPeriod}
            onChange={(event) => setIsTeachingPeriod(event.target.checked)}
            disabled={isPending}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          可排課
        </label>
      </td>
      <td className={TD}>
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          disabled={isPending}
          aria-label="標籤"
          placeholder="選填"
        className={INPUT}
        />
      </td>
      {/* start_time/end_time: 顯示用欄位,本次不開放輸入(見 Task 45 報告
          的設計說明)-- 新增時一律是空值,所以這裡沒有輸入框可放,直接顯示
          「未設定」。 */}
      <td className={TD}>未設定</td>
      <td className={TD}>未設定</td>
      <td className={TD}>
        <button
          type="button"
          onClick={() => {
            if (period !== null) {
              onConfirm({
                weekday,
                period,
                is_teaching_period: isTeachingPeriod,
                label: label.trim() === "" ? null : label,
              });
            }
          }}
          disabled={isPending || period === null}
          className={BUTTON_PRIMARY_SM}
        >
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
        {errorMessage !== null && <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>}
      </td>
    </tr>
  );
}

function TimeSlotRow({
  timeSlot,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onDelete,
}: {
  timeSlot: TimeSlot;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: TimeSlotUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftWeekday, setDraftWeekday] = useState(timeSlot.weekday);
  const [draftPeriodText, setDraftPeriodText] = useState(String(timeSlot.period));
  const [draftIsTeachingPeriod, setDraftIsTeachingPeriod] = useState(
    timeSlot.is_teaching_period,
  );
  const [draftLabel, setDraftLabel] = useState(timeSlot.label ?? "");

  useEffect(() => {
    if (isEditing) {
      setDraftWeekday(timeSlot.weekday);
      setDraftPeriodText(String(timeSlot.period));
      setDraftIsTeachingPeriod(timeSlot.is_teaching_period);
      setDraftLabel(timeSlot.label ?? "");
    }
  }, [isEditing, timeSlot]);

  const draftPeriod = draftPeriodText === "" ? null : Number(draftPeriodText);

  if (isEditing) {
    return (
      <tr className="bg-blue-50/40" data-row-key={timeSlot.id}>
        <td className={TD}>
          <select
            value={draftWeekday}
            onChange={(event) => setDraftWeekday(Number(event.target.value))}
            disabled={isPending}
            aria-label="星期"
          className={SELECT}
          >
            {WEEKDAY_OPTIONS.map((day) => (
              <option key={day} value={day}>
                {formatWeekday(day)}
              </option>
            ))}
          </select>
        </td>
        <td className={TD}>
          <input
            type="number"
            value={draftPeriodText}
            onChange={(event) => setDraftPeriodText(event.target.value)}
            disabled={isPending}
            aria-label="節次"
          className={INPUT}
          />
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsTeachingPeriod}
              onChange={(event) => setDraftIsTeachingPeriod(event.target.checked)}
              disabled={isPending}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            可排課
          </label>
        </td>
        <td className={TD}>
          <input
            value={draftLabel}
            onChange={(event) => setDraftLabel(event.target.value)}
            disabled={isPending}
            aria-label="標籤"
            placeholder="選填"
          className={INPUT}
          />
        </td>
        {/* start_time/end_time 不開放編輯,即使在編輯模式也只顯示目前的值
            (或「未設定」),不是輸入框。 */}
        <td className={TD}>{timeSlot.start_time ?? "未設定"}</td>
        <td className={TD}>{timeSlot.end_time ?? "未設定"}</td>
        <td className={TD}>
          <button
            type="button"
            onClick={() => {
              if (draftPeriod !== null) {
                onConfirmEdit({
                  weekday: draftWeekday,
                  period: draftPeriod,
                  is_teaching_period: draftIsTeachingPeriod,
                  label: draftLabel.trim() === "" ? null : draftLabel,
                });
              }
            }}
            disabled={isPending || draftPeriod === null}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          {errorMessage !== undefined && (
            <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{formatWeekday(timeSlot.weekday)}</td>
      <td className={TD}>{timeSlot.period}</td>
      <td className={TD}>{timeSlot.is_teaching_period ? "是" : "否"}</td>
      <td className={TD}>{timeSlot.label ?? "未設定"}</td>
      <td className={TD}>{timeSlot.start_time ?? "未設定"}</td>
      <td className={TD}>{timeSlot.end_time ?? "未設定"}</td>
      <td className={TD}>
        {isAdmin && (
          <>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <button type="button" onClick={onDelete} disabled={isPending} className={BUTTON_DANGER_SM}>
              刪除
            </button>
          </>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>{errorMessage}</p>
        )}
      </td>
    </tr>
  );
}

function TimeSlotsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listTimeSlots(), []);
  const crud = useCrudList<TimeSlot, TimeSlotCreate, TimeSlotUpdate>(data, {
    create: createTimeSlot,
    update: updateTimeSlot,
    remove: removeTimeSlot,
  });
  // Task 78: only for the delete confirmation's wording -- the table itself
  // shows and edits the raw period.
  const periodDisplay = buildPeriodDisplay(crud.items);

  function handleDelete(id: number, label: string): void {
    if (window.confirm(`確定要刪除「${label}」嗎？此操作無法復原。`)) {
      void crud.submitDelete(id);
    }
  }

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
          {/* Task 35/35.5 的既有限制:系統不會自動檢查每個 period 編號在
              星期一到五的意義是否一致(例如星期一第 3 節是數學課的時段,
              星期三第 3 節卻被建成午休時段)——這裡只是手動維護,打錯或漏
              建系統都不會主動提醒,請自行確認。 */}
          <p className={HELP_TEXT}>
            請確保每個節次編號在星期一到五的意義一致（例如都代表「第 3
            節」），系統不會自動檢查這一點。
          </p>
          <p className={HELP_TEXT}>
            此處為原始節次號碼，課表上的節次會依教學時段重新編號。
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
                <th className={TH}>星期</th>
                <th className={TH}>節次</th>
                <th className={TH}>可排課</th>
                <th className={TH}>標籤</th>
                <th className={TH}>開始時間</th>
                <th className={TH}>結束時間</th>
                {isAdmin && <th className={TH}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
              {crud.isAdding && (
                <TimeSlotNewRow
                  isPending={crud.pendingKey === "new"}
                  errorMessage={crud.rowErrors.get("new") ?? null}
                  onConfirm={(data) => void crud.submitCreate(data)}
                  onCancel={crud.cancelAdding}
                />
              )}
              {crud.items.map((timeSlot) => (
                <TimeSlotRow
                  key={timeSlot.id}
                  timeSlot={timeSlot}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === timeSlot.id}
                  isPending={crud.pendingKey === timeSlot.id}
                  errorMessage={crud.rowErrors.get(timeSlot.id)}
                  onStartEdit={() => crud.startEditing(timeSlot.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(timeSlot.id, data)}
                  onDelete={() =>
                    handleDelete(
                      timeSlot.id,
                      `${formatTimeSlotLabel(timeSlot, periodDisplay)}（原始節次 ${timeSlot.period}）`,
                    )
                  }
                />
              ))}
            </tbody>
          </table>
          </div>
        </>
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
    return isTabKey(requestedTab) ? requestedTab : "subjects";
  });

  // Task 42: read once per mount, same as the token itself -- a role
  // doesn't change without a fresh login, which always re-mounts this page
  // (ProtectedRoute/Layout sit above it in the route tree), so there is no
  // "role changed mid-session" case this needs to react to.
  // Task 98: "isAdmin" here means whoever may edit scheduling data -- a
  // 教學組長 (backend require_coordinator).
  const isAdmin = isCurrentUserCoordinator();

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>學校資料</h1>
      <p className={HELP_TEXT}>
        維護學校的科目、教室與時段等資料；教師請到「帳號管理」建立一般老師帳號，每學期的教師設定、年級可排節次與科目需求在「開始排課」設定。
      </p>
      <nav className="mb-4 flex flex-wrap gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            aria-pressed={activeTab === tab.key}
            className={activeTab === tab.key ? TAB_BUTTON_ACTIVE : TAB_BUTTON}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      {activeTab === "academicYears" && <AcademicYearsTab isAdmin={isAdmin} />}
      {activeTab === "semesters" && <SemestersTab isAdmin={isAdmin} />}
      {activeTab === "grades" && <GradesTab isAdmin={isAdmin} />}
      {activeTab === "classes" && <ClassesTab isAdmin={isAdmin} />}
      {activeTab === "subjects" && <SubjectsTab isAdmin={isAdmin} />}
      {activeTab === "rooms" && <RoomsTab isAdmin={isAdmin} />}
      {activeTab === "timeSlots" && <TimeSlotsTab isAdmin={isAdmin} />}
    </div>
  );
}
