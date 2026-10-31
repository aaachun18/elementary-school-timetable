import { useEffect, useState, type KeyboardEvent, type ReactElement, type ReactNode } from "react";
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
  deactivationImpact as subjectDeactivationImpact,
} from "../api/subjects";
import {
  list as listRooms,
  create as createRoom,
  update as updateRoom,
  remove as removeRoom,
  deactivationImpact as roomDeactivationImpact,
} from "../api/rooms";
import { RowErrorText } from "../components/DeleteStepsHint";
import PageHeader from "../components/PageHeader";
import DeactivateConfirmDialog from "../components/DeactivateConfirmDialog";
import StatusBadge from "../components/StatusBadge";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import { useConfirm } from "../hooks/useConfirm";
import DeleteIconButton from "../components/DeleteIconButton";
import EditIconButton from "../components/EditIconButton";
import { deleteButtonLabel, deleteConfirmText, editButtonLabel } from "../utils/confirmText";
import { isCurrentUserCoordinator } from "../utils/auth";
import { activeStatusBadge, visibleItems } from "../utils/deactivation";
import { inlineEditKeyAction } from "../utils/inlineEdit";
import { SCHOOL_TYPE_LABELS } from "../utils/schoolStructure";
import { sortBySubject } from "../utils/subjectOrder";
import ClassesTab from "../components/schoolData/ClassesTab";
import GradeRequirementsTab from "../components/schoolData/GradeRequirementsTab";
import NameCreateDialog from "../components/schoolData/NameCreateDialog";
import RoomCreateDialog from "../components/schoolData/RoomCreateDialog";
import SchoolCreateDialog from "../components/schoolData/SchoolCreateDialog";
import ShowInactiveToggle from "../components/schoolData/ShowInactiveToggle";
import TimeSlotsTab from "../components/schoolData/TimeSlotsTab";
import type { School, SchoolCreate, SchoolUpdate } from "../types/school";
import type { Subject, SubjectCreate, SubjectUpdate } from "../types/subject";
import { ROOM_MAX_CLASSES_OPTIONS, type Room, type RoomCreate, type RoomUpdate } from "../types/room";
import {
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_ROW,
  BUTTON_SECONDARY_ROW,
  ERROR_TEXT,
  HELP_TEXT,
  INLINE_EDIT_TEXT,
  INPUT,
  LOADING_TEXT,
  PAGE_DATA,
  ROW_ACTIONS,
  ROW_ACTIONS_END,
  ROW_ERROR_TEXT,
  ROW_ERROR_TEXT_FIXED,
  ROOM_COLS,
  SELECT,
  SUBJECT_COLS,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
  DATA_TABLE,
  DATA_TABLE_WRAPPER,
  TH_DATA,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_ACTIONS,
  TD_DATA_ACTIONS,
  TD_LOCKED,
  TD_NOWRAP,
  TH,
  TH_ACTIONS,
  TH_DATA_ACTIONS,
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
            className={BUTTON_PRIMARY_ROW}
          >
            {isPending ? "送出中…" : "確認"}
          </button>
          <button type="button" onClick={onCancelEdit} disabled={isPending} className={BUTTON_SECONDARY_ROW}>
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
            <EditIconButton label={editButtonLabel(school.name)} onClick={onStartEdit} disabled={isPending} />
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

// --- Task 102: 科目 / 教室 -- the same list shape as 班級 (ClassesTab.tsx):
// ... | 狀態 | 操作. 狀態 is a 啟用中 / 已停用 badge; 操作 is 停用 (asks
// first, DeactivateConfirmDialog) or 啟用 (doesn't), then the trash. No
// pencil and no 啟用中 checkbox: an editable field's text is clicked to edit
// the row in place (Enter saves, Esc cancels, or 確認 / 取消), and 啟用 /
// 停用 only goes through the 操作 button. 已停用 rows are hidden until
// 「顯示已停用」, then shown faded.

function ActiveStatusCell({ isActive }: { isActive: boolean }): ReactElement {
  const badge = activeStatusBadge(isActive);
  return (
    <td className={TD_NOWRAP}>
      <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>
    </td>
  );
}

// A row's 操作 while it isn't being edited: 停用 / 啟用, then the trash.
function ActiveRowActions({
  isActive,
  deleteLabel,
  disabled,
  onToggleActive,
  onDelete,
}: {
  isActive: boolean;
  deleteLabel: string;
  disabled: boolean;
  onToggleActive: () => void;
  onDelete: () => void;
}): ReactElement {
  return (
    <div className={ROW_ACTIONS_END}>
      <button type="button" onClick={onToggleActive} disabled={disabled} className={BUTTON_SECONDARY_ROW}>
        {isActive ? "停用" : "啟用"}
      </button>
      <DeleteIconButton label={deleteLabel} onClick={onDelete} disabled={disabled} />
    </div>
  );
}

// An editing row's 操作: 確認 / 取消, and the row's error under them.
function InlineEditActions({
  isPending,
  canSave,
  errorMessage,
  onSave,
  onCancel,
}: {
  isPending: boolean;
  canSave: boolean;
  errorMessage: string | undefined;
  onSave: () => void;
  onCancel: () => void;
}): ReactElement {
  return (
    <td className={TD_DATA_ACTIONS}>
      <div className={ROW_ACTIONS_END}>
        <button type="button" onClick={onSave} disabled={isPending || !canSave} className={BUTTON_PRIMARY_ROW}>
          {isPending ? "送出中…" : "確認"}
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_ROW}>
          取消
        </button>
      </div>
      {errorMessage !== undefined && (
        <p role="alert" className={ROW_ERROR_TEXT_FIXED}>
          {errorMessage}
        </p>
      )}
    </td>
  );
}

// The editing row's onKeyDown: Enter in a field saves, Esc cancels.
function inlineEditKeyDown(onSave: () => void, onCancel: () => void): (event: KeyboardEvent<HTMLElement>) => void {
  return (event) => {
    const tag = event.target instanceof HTMLElement ? event.target.tagName : "";
    const action = inlineEditKeyAction(event.key, event.code, tag, event.nativeEvent.isComposing);
    if (action === null) {
      return;
    }
    event.preventDefault();
    if (action === "save") {
      onSave();
    } else {
      onCancel();
    }
  };
}

// An editable field's text: a click edits the row (coordinators only --
// everyone else just reads it).
function InlineEditText({
  canEdit,
  label,
  disabled,
  onClick,
  children,
}: {
  canEdit: boolean;
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}): ReactElement {
  if (!canEdit) {
    return <>{children}</>;
  }
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={label} title="點一下即可編輯" className={INLINE_EDIT_TEXT}>
      {children}
    </button>
  );
}

function SubjectRow({
  subject,
  isAdmin,
  isEditing,
  isPending,
  isBusy,
  errorMessage,
  deleteSteps,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onToggleActive,
  onDelete,
}: {
  subject: Subject;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  // Some row's request is in flight: every row's buttons wait.
  isBusy: boolean;
  errorMessage: string | undefined;
  deleteSteps: readonly string[] | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: SubjectUpdate) => void;
  onToggleActive: () => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(subject.name);
  const canSave = draftName.trim() !== "";

  // The draft starts from the row's current name every time editing starts,
  // so 取消 needs nothing to restore.
  function startEdit(): void {
    setDraftName(subject.name);
    onStartEdit();
  }

  function save(): void {
    if (canSave && !isPending) {
      onConfirmEdit({ name: draftName });
    }
  }

  const cell = subject.is_active ? TD : TD_LOCKED;

  if (isEditing) {
    return (
      <tr className="bg-blue-50/40" data-row-key={subject.id} onKeyDown={inlineEditKeyDown(save, onCancelEdit)}>
        <td className={TD}>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="科目名稱"
            autoFocus
            className={`${INPUT} w-full`}
          />
        </td>
        <ActiveStatusCell isActive={subject.is_active} />
        <InlineEditActions
          isPending={isPending}
          canSave={canSave}
          errorMessage={errorMessage}
          onSave={save}
          onCancel={onCancelEdit}
        />
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={cell}>
        <InlineEditText canEdit={isAdmin} label={`修改「${subject.name}」的名稱`} disabled={isBusy} onClick={startEdit}>
          {subject.name}
        </InlineEditText>
      </td>
      <ActiveStatusCell isActive={subject.is_active} />
      {isAdmin && (
        <td className={TD_DATA_ACTIONS}>
          <ActiveRowActions
            isActive={subject.is_active}
            deleteLabel={deleteButtonLabel("subject", subject.name)}
            disabled={isBusy}
            onToggleActive={onToggleActive}
            onDelete={onDelete}
          />
          {errorMessage !== undefined && <RowErrorText message={errorMessage} deleteSteps={deleteSteps} inFixedColumn />}
        </td>
      )}
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
  const [showInactive, setShowInactive] = useState(false);
  // 停用 asks first, with what it touches; 啟用 doesn't.
  const [deactivating, setDeactivating] = useState<Subject | null>(null);

  function handleToggleActive(item: Subject): void {
    if (item.is_active) {
      setDeactivating(item);
      return;
    }
    void crud.submitUpdate(item.id, { is_active: true });
  }

  async function handleDelete(id: number, name: string): Promise<void> {
    if (await confirm(deleteConfirmText("subject", name))) {
      void crud.submitDelete(id);
    }
  }

  // The school order of subjects (utils/subjectOrder.ts).
  const shown = sortBySubject(visibleItems(crud.items, showInactive), (item) => item.name);
  const columnCount = isAdmin ? 3 : 2;

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
          <div className="mb-3 flex flex-wrap items-end gap-3">            
            {isAdmin && (
              <div className={ROW_ACTIONS}>
                <button
                  type="button"
                  onClick={crud.startAdding}
                  disabled={crud.isAdding || crud.pendingKey !== null}
                  className={BUTTON_PRIMARY}
                >
                  新增
                </button>
              </div>
            )}
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} noun="科目" />
          </div>
          <div className={DATA_TABLE_WRAPPER}>
            <table className={DATA_TABLE}>
              <colgroup>
                {SUBJECT_COLS.slice(0, columnCount).map((width) => (
                  <col key={width} className={width} />
                ))}
              </colgroup>
              <thead>
                <tr className={TABLE_HEAD_ROW}>
                  <th className={TH_DATA}>名稱</th>
                  <th className={TH_DATA}>狀態</th>
                  {isAdmin && <th className={TH_DATA_ACTIONS}>操作</th>}
                </tr>
              </thead>
              <tbody onChange={crud.handleRowChange}>
                {shown.map((subject) => (
                  <SubjectRow
                    key={subject.id}
                    subject={subject}
                    isAdmin={isAdmin}
                    isEditing={crud.editingId === subject.id}
                    isPending={crud.pendingKey === subject.id}
                    isBusy={crud.pendingKey !== null}
                    errorMessage={crud.rowErrors.get(subject.id)}
                    deleteSteps={crud.rowDeleteSteps.get(subject.id)}
                    onStartEdit={() => crud.startEditing(subject.id)}
                    onCancelEdit={crud.cancelEditing}
                    onConfirmEdit={(changes) => void crud.submitUpdate(subject.id, changes)}
                    onToggleActive={() => handleToggleActive(subject)}
                    onDelete={() => void handleDelete(subject.id, subject.name)}
                  />
                ))}
                {shown.length === 0 && (
                  <tr>
                    <td className={TD} colSpan={columnCount}>
                      <span className={HELP_TEXT}>
                        {crud.items.length === 0 ? "目前沒有科目。" : "目前沒有啟用中的科目。"}
                      </span>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {confirmDialog}
          {deactivating !== null && (
            <DeactivateConfirmDialog
              kind="subject"
              name={deactivating.name}
              loadImpact={() => subjectDeactivationImpact(deactivating.id)}
              onConfirm={() => {
                const item = deactivating;
                setDeactivating(null);
                void crud.submitUpdate(item.id, { is_active: false });
              }}
              onCancel={() => setDeactivating(null)}
            />
          )}
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

type RoomField = "name" | "maxClasses";

function RoomRow({
  room,
  isAdmin,
  isEditing,
  isPending,
  isBusy,
  errorMessage,
  deleteSteps,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onToggleActive,
  onDelete,
}: {
  room: Room;
  isAdmin: boolean;
  isEditing: boolean;
  isPending: boolean;
  isBusy: boolean;
  errorMessage: string | undefined;
  deleteSteps: readonly string[] | undefined;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: (data: RoomUpdate) => void;
  onToggleActive: () => void;
  onDelete: () => void;
}): ReactElement {
  const [draftName, setDraftName] = useState(room.name);
  const [draftMaxClasses, setDraftMaxClasses] = useState(room.max_classes);
  // The field whose text was clicked gets the focus.
  const [focusField, setFocusField] = useState<RoomField>("name");
  const canSave = draftName.trim() !== "";

  function startEdit(field: RoomField): void {
    setDraftName(room.name);
    setDraftMaxClasses(room.max_classes);
    setFocusField(field);
    onStartEdit();
  }

  function save(): void {
    if (canSave && !isPending) {
      onConfirmEdit({ name: draftName, max_classes: draftMaxClasses });
    }
  }

  const cell = room.is_active ? TD : TD_LOCKED;

  if (isEditing) {
    return (
      <tr className="bg-blue-50/40" data-row-key={room.id} onKeyDown={inlineEditKeyDown(save, onCancelEdit)}>
        <td className={TD}>
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            disabled={isPending}
            aria-label="教室名稱"
            autoFocus={focusField === "name"}
            className={`${INPUT} w-full`}
          />
        </td>
        <td className={TD}>
          <select
            value={draftMaxClasses}
            onChange={(event) => setDraftMaxClasses(Number(event.target.value))}
            disabled={isPending}
            aria-label="一次最多幾班同時使用"
            autoFocus={focusField === "maxClasses"}
            className={`${SELECT} w-full`}
          >
            {ROOM_MAX_CLASSES_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option} 班
              </option>
            ))}
          </select>
        </td>
        <ActiveStatusCell isActive={room.is_active} />
        <InlineEditActions
          isPending={isPending}
          canSave={canSave}
          errorMessage={errorMessage}
          onSave={save}
          onCancel={onCancelEdit}
        />
      </tr>
    );
  }

  return (
    <tr className={TR_HOVER}>
      <td className={cell}>
        <InlineEditText
          canEdit={isAdmin}
          label={`修改「${room.name}」的名稱`}
          disabled={isBusy}
          onClick={() => startEdit("name")}
        >
          {room.name}
        </InlineEditText>
      </td>
      <td className={cell}>
        <InlineEditText
          canEdit={isAdmin}
          label={`修改「${room.name}」一次最多幾班同時使用`}
          disabled={isBusy}
          onClick={() => startEdit("maxClasses")}
        >
          {room.max_classes} 班
        </InlineEditText>
      </td>
      <ActiveStatusCell isActive={room.is_active} />
      {isAdmin && (
        <td className={TD_DATA_ACTIONS}>
          <ActiveRowActions
            isActive={room.is_active}
            deleteLabel={deleteButtonLabel("room", room.name)}
            disabled={isBusy}
            onToggleActive={onToggleActive}
            onDelete={onDelete}
          />
          {errorMessage !== undefined && <RowErrorText message={errorMessage} deleteSteps={deleteSteps} inFixedColumn />}
        </td>
      )}
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
  const [showInactive, setShowInactive] = useState(false);
  // 停用 asks first, with what it touches; 啟用 doesn't.
  const [deactivating, setDeactivating] = useState<Room | null>(null);

  function handleToggleActive(item: Room): void {
    if (item.is_active) {
      setDeactivating(item);
      return;
    }
    void crud.submitUpdate(item.id, { is_active: true });
  }

  async function handleDelete(id: number, name: string): Promise<void> {
    if (await confirm(deleteConfirmText("room", name))) {
      void crud.submitDelete(id);
    }
  }

  const shown = visibleItems(crud.items, showInactive);
  const columnCount = isAdmin ? 4 : 3;

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <>
          <div className="mb-3 flex flex-wrap items-end gap-3">
            {isAdmin && (
              <div className={ROW_ACTIONS}>
                <button
                  type="button"
                  onClick={crud.startAdding}
                  disabled={crud.isAdding || crud.pendingKey !== null}
                  className={BUTTON_PRIMARY}
                >
                  新增
                </button>
              </div>
            )}
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} noun="教室" />
          </div>
          <div className={DATA_TABLE_WRAPPER}>
            <table className={DATA_TABLE}>
              <colgroup>
                {ROOM_COLS.slice(0, columnCount).map((width) => (
                  <col key={width} className={width} />
                ))}
              </colgroup>
              <thead>
                <tr className={TABLE_HEAD_ROW}>
                  <th className={TH_DATA}>名稱</th>
                  <th className={TH_DATA}>一次最多幾班同時使用</th>
                  <th className={TH_DATA}>狀態</th>
                  {isAdmin && <th className={TH_DATA_ACTIONS}>操作</th>}
                </tr>
              </thead>
              <tbody onChange={crud.handleRowChange}>
                {shown.map((room) => (
                  <RoomRow
                    key={room.id}
                    room={room}
                    isAdmin={isAdmin}
                    isEditing={crud.editingId === room.id}
                    isPending={crud.pendingKey === room.id}
                    isBusy={crud.pendingKey !== null}
                    errorMessage={crud.rowErrors.get(room.id)}
                    deleteSteps={crud.rowDeleteSteps.get(room.id)}
                    onStartEdit={() => crud.startEditing(room.id)}
                    onCancelEdit={crud.cancelEditing}
                    onConfirmEdit={(changes) => void crud.submitUpdate(room.id, changes)}
                    onToggleActive={() => handleToggleActive(room)}
                    onDelete={() => void handleDelete(room.id, room.name)}
                  />
                ))}
                {shown.length === 0 && (
                  <tr>
                    <td className={TD} colSpan={columnCount}>
                      <span className={HELP_TEXT}>
                        {crud.items.length === 0 ? "目前沒有教室。" : "目前沒有啟用中的教室。"}
                      </span>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {confirmDialog}
          {deactivating !== null && (
            <DeactivateConfirmDialog
              kind="room"
              name={deactivating.name}
              loadImpact={() => roomDeactivationImpact(deactivating.id)}
              onConfirm={() => {
                const item = deactivating;
                setDeactivating(null);
                void crud.submitUpdate(item.id, { is_active: false });
              }}
              onCancel={() => setDeactivating(null)}
            />
          )}
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
    <div className={PAGE_DATA}>
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
