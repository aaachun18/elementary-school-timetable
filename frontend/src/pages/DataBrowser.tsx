import { useEffect, useState, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
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
import { RowErrorText } from "../components/DeleteStepsHint";
import PageHeader from "../components/PageHeader";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import { useConfirm } from "../hooks/useConfirm";
import DeleteIconButton from "../components/DeleteIconButton";
import { deleteButtonLabel, deleteConfirmText } from "../utils/confirmText";
import { isCurrentUserCoordinator } from "../utils/auth";
import { SCHOOL_TYPE_LABELS } from "../utils/schoolStructure";
import ClassesTab from "../components/schoolData/ClassesTab";
import GradeRequirementsTab from "../components/schoolData/GradeRequirementsTab";
import NameCreateDialog from "../components/schoolData/NameCreateDialog";
import RoomCreateDialog from "../components/schoolData/RoomCreateDialog";
import SchoolCreateDialog from "../components/schoolData/SchoolCreateDialog";
import TimeSlotsTab from "../components/schoolData/TimeSlotsTab";
import type { School, SchoolCreate, SchoolUpdate } from "../types/school";
import type { Subject, SubjectCreate, SubjectUpdate } from "../types/subject";
import { ROOM_MAX_CLASSES_OPTIONS, type Room, type RoomCreate, type RoomUpdate } from "../types/room";
import {
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY_SM,
  CHECKBOX,
  ERROR_TEXT,
  INPUT,
  LOADING_TEXT,
  PAGE,
  ROW_ACTIONS_END,
  ROW_ERROR_TEXT,
  SELECT,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_ACTIONS,
  TH,
  TH_ACTIONS,
  TR_HOVER,
} from "../styles/ui";

// Task 98: schools moved to their own 系統管理員 page (SchoolManagement.tsx).
// No 學年度 / 學期 / 年級 tabs: the wizard creates the semester it works on,
// and a school's grades come with its type.
type TabKey = "classes" | "subjects" | "gradeRequirements" | "rooms" | "timeSlots";

const TABS: { key: TabKey; label: string }[] = [
  { key: "classes", label: "班級" },
  { key: "subjects", label: "科目" },
  { key: "gradeRequirements", label: "科目需求" },
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
// row error display: a plain <p className={ROW_ERROR_TEXT}> inside the row's
// own action <td className={TD}> -- deliberately NOT a toast/banner, since the point is
// that this one row's failure is scoped to this one row, with every other
// row (and the rest of the page) staying exactly as it was.

function SchoolRow({
  school,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  deleteSteps,
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
  deleteSteps: readonly string[] | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: SchoolUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(school.name);

  // Re-seeds the draft from the row's current values every time inline
  // editing starts (and harmlessly again if `school` itself changes while
  // editing, e.g. an unrelated refetch) -- this is what makes "取消"
  // restore the original values: it doesn't need to reset anything
  // itself, the next edit start always does.
  useEffect(() => {
    if (isEditing) {
      setDraftName(school.name);
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
          className={`${INPUT} w-full`}
          />
        </td>
        <td className={`${TD} text-gray-500`}>{SCHOOL_TYPE_LABELS[school.school_type]}</td>
        <td className={TD_ACTIONS}>
          <div className={ROW_ACTIONS_END}>
          <button
            type="button"
            onClick={() => onConfirmEdit({ name: draftName })}
            disabled={isPending || draftName.trim() === ""}
            className={BUTTON_PRIMARY_SM}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
          </div>
          {errorMessage !== undefined && (
            <p role="alert" className={ROW_ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{school.name}</td>
      <td className={TD}>{SCHOOL_TYPE_LABELS[school.school_type]}</td>
      <td className={TD_ACTIONS}>
        {isAdmin && (
          <div className={ROW_ACTIONS_END}>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <DeleteIconButton label={deleteButtonLabel("school", school.name)} onClick={onDelete} disabled={isPending} />
          </div>
        )}
        {errorMessage !== undefined && <RowErrorText message={errorMessage} deleteSteps={deleteSteps} />}
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
  const { confirm, dialog: confirmDialog } = useConfirm();

  async function handleDelete(id: number, name: string): Promise<void> {
    if (await confirm(deleteConfirmText("school", name))) {
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
                <th className={TH}>類型</th>
                {isAdmin && <th className={TH_ACTIONS}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
              {crud.items.map((school) => (
                <SchoolRow
                  key={school.id}
                  school={school}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === school.id}
                  isPending={crud.pendingKey === school.id}
                  errorMessage={crud.rowErrors.get(school.id)}
                  deleteSteps={crud.rowDeleteSteps.get(school.id)}
                  onStartEdit={() => crud.startEditing(school.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(school.id, data)}
                  onDelete={() => void handleDelete(school.id, school.name)}
                />
              ))}
            </tbody>
          </table>
          </div>
          {crud.isAdding && (
            <SchoolCreateDialog
              busy={crud.pendingKey === "new"}
              errorMessage={crud.rowErrors.get("new") ?? null}
              onSave={(data) => void crud.submitCreate(data)}
              onCancel={crud.cancelAdding}
            />
          )}
          {confirmDialog}
        </>
      )}
    </div>
  );
}

function SubjectRow({
  subject,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  deleteSteps,
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
  deleteSteps: readonly string[] | undefined;
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
          className={`${INPUT} w-full`}
          />
        </td>
        <td className={TD}>
          <label>
            <input
              type="checkbox"
              checked={draftIsActive}
              onChange={(event) => setDraftIsActive(event.target.checked)}
              disabled={isPending}
            className={CHECKBOX}
            />
            啟用中
          </label>
        </td>
        <td className={TD_ACTIONS}>
          <div className={ROW_ACTIONS_END}>
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
          </div>
          {errorMessage !== undefined && (
            <p role="alert" className={ROW_ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{subject.name}</td>
      <td className={TD}>{subject.is_active ? "是" : "否"}</td>
      <td className={TD_ACTIONS}>
        {isAdmin && (
          <div className={ROW_ACTIONS_END}>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <DeleteIconButton label={deleteButtonLabel("subject", subject.name)} onClick={onDelete} disabled={isPending} />
          </div>
        )}
        {errorMessage !== undefined && <RowErrorText message={errorMessage} deleteSteps={deleteSteps} />}
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
  const { confirm, dialog: confirmDialog } = useConfirm();

  async function handleDelete(id: number, name: string): Promise<void> {
    if (await confirm(deleteConfirmText("subject", name))) {
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
                {isAdmin && <th className={TH_ACTIONS}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
              {crud.items.map((subject) => (
                <SubjectRow
                  key={subject.id}
                  subject={subject}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === subject.id}
                  isPending={crud.pendingKey === subject.id}
                  errorMessage={crud.rowErrors.get(subject.id)}
                  deleteSteps={crud.rowDeleteSteps.get(subject.id)}
                  onStartEdit={() => crud.startEditing(subject.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(subject.id, data)}
                  onDelete={() => void handleDelete(subject.id, subject.name)}
                />
              ))}
            </tbody>
          </table>
          </div>
          {confirmDialog}
          {crud.isAdding && (
            <NameCreateDialog
              title="新增科目"
              label="科目名稱"
              busy={crud.pendingKey === "new"}
              errorMessage={crud.rowErrors.get("new") ?? null}
              onSave={(name) => void crud.submitCreate({ name })}
              onCancel={crud.cancelAdding}
            />
          )}
        </>
      )}
    </div>
  );
}

function RoomRow({
  room,
  isAdmin,
  isEditing,
  isPending,
  errorMessage,
  deleteSteps,
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
  deleteSteps: readonly string[] | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: RoomUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(room.name);
  const [draftIsActive, setDraftIsActive] = useState(room.is_active);
  const [draftMaxClasses, setDraftMaxClasses] = useState(room.max_classes);

  useEffect(() => {
    if (isEditing) {
      setDraftName(room.name);
      setDraftIsActive(room.is_active);
      setDraftMaxClasses(room.max_classes);
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
          className={`${INPUT} w-full`}
          />
        </td>
        <td className={TD}>
          <select
            value={draftMaxClasses}
            onChange={(event) => setDraftMaxClasses(Number(event.target.value))}
            disabled={isPending}
            aria-label="一次最多幾班同時使用"
            className={`${SELECT} w-full`}
          >
            {ROOM_MAX_CLASSES_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option} 班
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
            className={CHECKBOX}
            />
            啟用中
          </label>
        </td>
        <td className={TD_ACTIONS}>
          <div className={ROW_ACTIONS_END}>
          <button
            type="button"
            onClick={() =>
              onConfirmEdit({
                name: draftName,
                is_active: draftIsActive,
                max_classes: draftMaxClasses,
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
          </div>
          {errorMessage !== undefined && (
            <p role="alert" className={ROW_ERROR_TEXT}>{errorMessage}</p>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={TD}>{room.name}</td>
      <td className={TD}>{room.max_classes} 班</td>
      <td className={TD}>{room.is_active ? "是" : "否"}</td>
      <td className={TD_ACTIONS}>
        {isAdmin && (
          <div className={ROW_ACTIONS_END}>
            <button type="button" onClick={onStartEdit} disabled={isPending} className={BUTTON_SECONDARY_SM}>
              編輯
            </button>
            <DeleteIconButton label={deleteButtonLabel("room", room.name)} onClick={onDelete} disabled={isPending} />
          </div>
        )}
        {errorMessage !== undefined && <RowErrorText message={errorMessage} deleteSteps={deleteSteps} />}
      </td>
    </tr>
  );
}

// Task 98: a room is just its name -- a requirement names the one special
// room it needs, so rooms have no types (and no capacity) any more.

function RoomsTab({ isAdmin }: { isAdmin: boolean }): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listRooms(), []);
  const crud = useCrudList<Room, RoomCreate, RoomUpdate>(data, {
    create: createRoom,
    update: updateRoom,
    remove: removeRoom,
  });
  const { confirm, dialog: confirmDialog } = useConfirm();

  async function handleDelete(id: number, name: string): Promise<void> {
    if (await confirm(deleteConfirmText("room", name))) {
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
                <th className={TH}>一次最多幾班同時使用</th>
                <th className={TH}>啟用中</th>
                {isAdmin && <th className={TH_ACTIONS}>操作</th>}
              </tr>
            </thead>
            <tbody onChange={crud.handleRowChange}>
              {crud.items.map((room) => (
                <RoomRow
                  key={room.id}
                  room={room}
                  isAdmin={isAdmin}
                  isEditing={crud.editingId === room.id}
                  isPending={crud.pendingKey === room.id}
                  errorMessage={crud.rowErrors.get(room.id)}
                  deleteSteps={crud.rowDeleteSteps.get(room.id)}
                  onStartEdit={() => crud.startEditing(room.id)}
                  onCancelEdit={crud.cancelEditing}
                  onConfirmEdit={(data) => void crud.submitUpdate(room.id, data)}
                  onDelete={() => void handleDelete(room.id, room.name)}
                />
              ))}
            </tbody>
          </table>
          </div>
          {confirmDialog}
          {crud.isAdding && (
            <RoomCreateDialog
              busy={crud.pendingKey === "new"}
              errorMessage={crud.rowErrors.get("new") ?? null}
              onSave={(data) => void crud.submitCreate(data)}
              onCancel={crud.cancelAdding}
            />
          )}
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
    return isTabKey(requestedTab) ? requestedTab : "classes";
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
      <PageHeader
        title="學校資料"
        info={
          <p>
            維護學校的班級、科目、各年級科目需求、教室與時段；教師請到「帳號管理」建立一般老師帳號，每學期的教師設定、年級可排節次、連堂與指定老師／教室在「開始排課」設定。
          </p>
        }
      />
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
      {activeTab === "classes" && <ClassesTab isAdmin={isAdmin} />}
      {activeTab === "subjects" && <SubjectsTab isAdmin={isAdmin} />}
      {activeTab === "gradeRequirements" && <GradeRequirementsTab isAdmin={isAdmin} />}
      {activeTab === "rooms" && <RoomsTab isAdmin={isAdmin} />}
      {activeTab === "timeSlots" && <TimeSlotsTab isAdmin={isAdmin} />}
    </div>
  );
}
