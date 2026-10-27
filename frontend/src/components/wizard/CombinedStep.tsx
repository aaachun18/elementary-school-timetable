import { useState, type ReactElement } from "react";
import {
  create as createCombined,
  list as listCombined,
  remove as removeCombined,
  update as updateCombined,
} from "../../api/combinedLessons";
import { list as listClasses } from "../../api/classes";
import { list as listRequirements } from "../../api/classSubjectRequirements";
import { list as listGrades } from "../../api/grades";
import { list as listRooms } from "../../api/rooms";
import { list as listSubjects } from "../../api/subjects";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import { useResource } from "../../hooks/useResource";
import type { Class } from "../../types/class";
import type { ClassSubjectRequirement } from "../../types/classSubjectRequirement";
import type { CombinedLesson, CombinedLessonFields } from "../../types/combinedLesson";
import type { Grade } from "../../types/grade";
import type { Room } from "../../types/room";
import { blockChoiceLabel, blockChoices, canMergeWith } from "../../utils/combinedLessons";
import ConfirmDialog from "../ConfirmDialog";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  BUTTON_SECONDARY_SM,
  CARD,
  CHECKBOX,
  ERROR_TEXT,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  MUTED_TEXT,
  SELECT,
  SUBSECTION_TITLE,
  TAB_BUTTON,
  TAB_BUTTON_ACTIVE,
} from "../../styles/ui";

const NAV_BUTTON = `${TAB_BUTTON} text-left`;
const NAV_BUTTON_ACTIVE = `${TAB_BUTTON_ACTIVE} text-left`;
// A label and its field on one line, every field of the dialog as wide as
// the others.
const DIALOG_FIELD_ROW = "grid grid-cols-[7rem_1fr] items-center gap-2";
const COMBINED_TAG =
  "ml-1 inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700";

interface Lookups {
  grades: readonly Grade[];
  classes: readonly Class[];
  requirements: readonly ClassSubjectRequirement[];
  rooms: readonly Room[];
  className: ReadonlyMap<number, string>;
  subjectName: ReadonlyMap<number, string>;
}

// 共同排課 (併班上課), the wizard step after 科目需求: lessons of several
// classes taught together count as one lesson -- same time, one room, the
// members' teachers together. Pick a grade on the left, then one of its
// classes and that class's subject; the dialog then names the classes'
// subjects it merges with (grade -> class -> subject, one row each), how
// many of the lessons (whole blocks for a lesson pattern) and the room.
// Saved right away; the backend checks every rule again.
export default function CombinedStep({
  versionId,
  onBack,
  onNext,
}: {
  versionId: number;
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const grades = useResource(() => listGrades(0, 1000), []);
  const classes = useResource(() => listClasses(0, 1000), []);
  const subjects = useResource(() => listSubjects(0, 1000), []);
  const rooms = useResource(() => listRooms(0, 1000), []);
  const requirements = useResource(
    () => listRequirements(0, 1000, { schedule_version_id: versionId }),
    [versionId],
  );
  const combined = useResource(() => listCombined(versionId), [versionId]);

  const errorMessage =
    grades.errorMessage ??
    classes.errorMessage ??
    subjects.errorMessage ??
    rooms.errorMessage ??
    requirements.errorMessage ??
    combined.errorMessage;
  if (errorMessage !== null) {
    return (
      <p role="alert" className={ERROR_TEXT}>
        {errorMessage}
      </p>
    );
  }
  if (
    grades.data === null ||
    classes.data === null ||
    subjects.data === null ||
    rooms.data === null ||
    requirements.data === null ||
    combined.data === null
  ) {
    return <p className={LOADING_TEXT}>載入中…</p>;
  }
  const lookups: Lookups = {
    grades: [...grades.data].sort((a, b) => a.level - b.level),
    classes: [...classes.data].sort((a, b) => a.id - b.id),
    requirements: requirements.data,
    rooms: rooms.data.filter((room) => room.is_active),
    className: new Map(classes.data.map((item) => [item.id, item.name])),
    subjectName: new Map(subjects.data.map((item) => [item.id, item.name])),
  };
  return (
    <CombinedEditor
      versionId={versionId}
      lookups={lookups}
      combined={combined.data}
      onChanged={combined.reload}
      onBack={onBack}
      onNext={onNext}
    />
  );
}

function requirementLabel(requirement: ClassSubjectRequirement, lookups: Lookups): string {
  return `${lookups.className.get(requirement.class_id) ?? "—"} ${lookups.subjectName.get(requirement.subject_id) ?? "—"}`;
}

function CombinedEditor({
  versionId,
  lookups,
  combined,
  onChanged,
  onBack,
  onNext,
}: {
  versionId: number;
  lookups: Lookups;
  combined: readonly CombinedLesson[];
  onChanged: () => void;
  onBack: () => void;
  onNext: () => void;
}): ReactElement {
  const gradesWithClasses = lookups.grades.filter((grade) =>
    lookups.classes.some((item) => item.grade_id === grade.id),
  );
  const [gradeId, setGradeId] = useState<number | null>(gradesWithClasses[0]?.id ?? null);
  const [classId, setClassId] = useState<number | null>(null);
  // The requirement the dialog is open for, and the combined lesson it is
  // already in (editing) -- or null.
  const [editing, setEditing] = useState<{ host: ClassSubjectRequirement; existing: CombinedLesson | null } | null>(
    null,
  );

  const combinedOf = new Map<number, CombinedLesson>();
  for (const item of combined) {
    for (const requirementId of item.requirement_ids) {
      combinedOf.set(requirementId, item);
    }
  }
  const requirementById = new Map(lookups.requirements.map((item) => [item.id, item]));
  const gradeClasses = lookups.classes.filter((item) => item.grade_id === gradeId);
  const classRequirements = lookups.requirements
    .filter((item) => item.class_id === classId)
    .sort((a, b) => a.subject_id - b.subject_id);

  function openFor(requirement: ClassSubjectRequirement): void {
    const existing = combinedOf.get(requirement.id) ?? null;
    const host = existing === null ? requirement : (requirementById.get(existing.requirement_ids[0]) ?? requirement);
    setEditing({ host, existing });
  }

  return (
    <div className={CARD}>
      <p className={HELP_TEXT}>
        併班上課的課（例如一年甲班和二年甲班的本土語文）在這裡合併：合併後視為同一節課，各班同一時間、在同一間教室上課，由各班科目需求指定的老師一起授課（都沒指定時由系統安排一位）。只有每週節數與連堂相同的課能合併；手動調整課表時，合併的課會一起移動。不需要合併可以直接按下一步。
      </p>
      <div className="flex flex-col gap-3 md:flex-row md:items-start">
        <nav aria-label="年級" className="flex shrink-0 flex-row flex-wrap gap-1 md:w-28 md:flex-col">
          {gradesWithClasses.map((grade) => (
            <button
              key={grade.id}
              type="button"
              onClick={() => {
                setGradeId(grade.id);
                setClassId(null);
              }}
              aria-current={grade.id === gradeId ? "true" : undefined}
              className={grade.id === gradeId ? NAV_BUTTON_ACTIVE : NAV_BUTTON}
            >
              {grade.name}
            </button>
          ))}
        </nav>
        <nav aria-label="班級" className="flex shrink-0 flex-row flex-wrap gap-1 md:w-32 md:flex-col">
          {gradeClasses.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setClassId(item.id)}
              aria-current={item.id === classId ? "true" : undefined}
              className={item.id === classId ? NAV_BUTTON_ACTIVE : NAV_BUTTON}
            >
              {item.name}
            </button>
          ))}
        </nav>
        <div className="min-w-0 flex-1">
          {classId === null ? (
            <p className={MUTED_TEXT}>請選擇班級。</p>
          ) : classRequirements.length === 0 ? (
            <p className={MUTED_TEXT}>這個班級沒有科目需求。</p>
          ) : (
            <ul aria-label="科目" className="flex flex-wrap gap-2">
              {classRequirements.map((requirement) => (
                <li key={requirement.id}>
                  <button type="button" onClick={() => openFor(requirement)} className={NAV_BUTTON}>
                    {lookups.subjectName.get(requirement.subject_id) ?? "—"}
                    <span className="ml-1 text-xs text-gray-500">（{requirement.weekly_periods} 節）</span>
                    {combinedOf.has(requirement.id) && <span className={COMBINED_TAG}>已合併</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <h3 className={`${SUBSECTION_TITLE} mt-4`}>已設定的共同排課（{combined.length}）</h3>
      {combined.length === 0 ? (
        <p className={MUTED_TEXT}>還沒有合併任何課。</p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm text-gray-800">
          {combined.map((item) => {
            const members = item.requirement_ids
              .map((id) => requirementById.get(id))
              .filter((value): value is ClassSubjectRequirement => value !== undefined);
            return (
              <li key={item.id} className="flex flex-wrap items-center gap-2">
                <span>
                  {members.map((member) => requirementLabel(member, lookups)).join(" ＋ ")}（合併 {item.merged_count} 節）
                </span>
                {members[0] !== undefined && (
                  <button
                    type="button"
                    onClick={() => setEditing({ host: members[0], existing: item })}
                    className={BUTTON_SECONDARY_SM}
                  >
                    編輯
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-4 flex gap-2">
        <button type="button" onClick={onBack} className={BUTTON_SECONDARY}>
          上一步
        </button>
        <button type="button" onClick={onNext} className={BUTTON_PRIMARY}>
          下一步
        </button>
      </div>
      {editing !== null && (
        <CombineDialog
          key={`${editing.host.id}-${editing.existing?.id ?? "new"}`}
          versionId={versionId}
          host={editing.host}
          existing={editing.existing}
          lookups={lookups}
          combinedRequirementIds={
            new Set(
              [...combinedOf.keys()].filter((id) => editing.existing === null || !editing.existing.requirement_ids.includes(id)),
            )
          }
          onSaved={() => {
            setEditing(null);
            onChanged();
          }}
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  );
}

interface PartnerRow {
  gradeId: number | null;
  classId: number | null;
  requirementId: number | null;
}

const ROOM_PREFIX = "room:";
const HOMEROOM_PREFIX = "class:";

function initialRows(existing: CombinedLesson | null, lookups: Lookups): PartnerRow[] {
  if (existing === null) {
    return [{ gradeId: null, classId: null, requirementId: null }];
  }
  return existing.requirement_ids.slice(1).map((requirementId) => {
    const requirement = lookups.requirements.find((item) => item.id === requirementId);
    const class_ = lookups.classes.find((item) => item.id === requirement?.class_id);
    return { gradeId: class_?.grade_id ?? null, classId: class_?.id ?? null, requirementId };
  });
}

function CombineDialog({
  versionId,
  host,
  existing,
  lookups,
  combinedRequirementIds,
  onSaved,
  onCancel,
}: {
  versionId: number;
  host: ClassSubjectRequirement;
  existing: CombinedLesson | null;
  lookups: Lookups;
  combinedRequirementIds: ReadonlySet<number>;
  onSaved: () => void;
  onCancel: () => void;
}): ReactElement {
  const [rows, setRows] = useState<PartnerRow[]>(() => initialRows(existing, lookups));
  const blocks = blockChoices(host.lesson_pattern);
  const [mergedCount, setMergedCount] = useState(existing?.merged_count ?? host.weekly_periods);
  const [blockNos, setBlockNos] = useState<number[]>(
    () => existing?.block_nos ?? (blocks === null ? [] : blocks.map((block) => block.blockNo)),
  );
  const [roomValue, setRoomValue] = useState(() =>
    existing?.room_id != null
      ? `${ROOM_PREFIX}${existing.room_id}`
      : `${HOMEROOM_PREFIX}${existing?.homeroom_class_id ?? host.class_id}`,
  );
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chosenIds = rows.map((row) => row.requirementId).filter((id): id is number => id !== null);
  const usedClassIds = new Set([host.class_id, ...rows.map((row) => row.classId).filter((id): id is number => id !== null)]);
  const memberClassIds = [host.class_id, ...chosenIds.map((id) => lookups.requirements.find((item) => item.id === id)?.class_id).filter((id): id is number => id !== undefined)];

  function updateRow(index: number, change: Partial<PartnerRow>): void {
    setRows((previous) => previous.map((row, position) => (position === index ? { ...row, ...change } : row)));
    setError(null);
  }

  function toggleBlock(blockNo: number): void {
    setBlockNos((previous) =>
      previous.includes(blockNo) ? previous.filter((item) => item !== blockNo) : [...previous, blockNo].sort(),
    );
  }

  async function handleSave(): Promise<void> {
    const fields: CombinedLessonFields = {
      requirement_ids: [host.id, ...chosenIds],
      merged_count: blocks === null ? mergedCount : null,
      block_nos: blocks === null ? null : blockNos,
      room_id: roomValue.startsWith(ROOM_PREFIX) ? Number(roomValue.slice(ROOM_PREFIX.length)) : null,
      homeroom_class_id: roomValue.startsWith(HOMEROOM_PREFIX) ? Number(roomValue.slice(HOMEROOM_PREFIX.length)) : null,
    };
    setIsSaving(true);
    setError(null);
    try {
      if (existing === null) {
        await createCombined({ schedule_version_id: versionId, ...fields });
      } else {
        await updateCombined(existing.id, fields);
      }
      onSaved();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      setIsSaving(false);
    }
  }

  async function handleDelete(): Promise<void> {
    if (existing === null) {
      return;
    }
    setIsSaving(true);
    try {
      await removeCombined(existing.id);
      onSaved();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      setIsSaving(false);
    }
  }

  const canSave = chosenIds.length > 0 && (blocks === null || blockNos.length > 0);

  return (
    <ConfirmDialog
      open
      wide
      title={`合併「${requirementLabel(host, lookups)}」`}
      confirmLabel="確定合併"
      busy={isSaving}
      busyLabel="儲存中…"
      confirmDisabled={!canSave}
      onConfirm={() => void handleSave()}
      onCancel={onCancel}
    >
      <p>選擇要和這堂課一起上的課（同一列依序選年級、班級、科目），可以新增多列。</p>
      {rows.map((row, index) => {
        const rowClasses = lookups.classes.filter(
          (item) => item.grade_id === row.gradeId && (item.id === row.classId || !usedClassIds.has(item.id)),
        );
        const rowRequirements = lookups.requirements.filter(
          (item) =>
            item.class_id === row.classId &&
            (item.id === row.requirementId || canMergeWith(host, item, combinedRequirementIds)),
        );
        return (
          <div key={index} className="grid grid-cols-[1fr_1fr_1fr_auto] items-center gap-2">
            <select
              value={row.gradeId ?? ""}
              onChange={(event) =>
                updateRow(index, {
                  gradeId: event.target.value === "" ? null : Number(event.target.value),
                  classId: null,
                  requirementId: null,
                })
              }
              disabled={isSaving}
              aria-label={`第 ${index + 1} 列年級`}
              className={`${SELECT} w-full`}
            >
              <option value="">年級</option>
              {lookups.grades.map((grade) => (
                <option key={grade.id} value={grade.id}>
                  {grade.name}
                </option>
              ))}
            </select>
            <select
              value={row.classId ?? ""}
              onChange={(event) =>
                updateRow(index, {
                  classId: event.target.value === "" ? null : Number(event.target.value),
                  requirementId: null,
                })
              }
              disabled={isSaving || row.gradeId === null}
              aria-label={`第 ${index + 1} 列班級`}
              className={`${SELECT} w-full`}
            >
              <option value="">班級</option>
              {rowClasses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <select
              value={row.requirementId ?? ""}
              onChange={(event) =>
                updateRow(index, { requirementId: event.target.value === "" ? null : Number(event.target.value) })
              }
              disabled={isSaving || row.classId === null}
              aria-label={`第 ${index + 1} 列科目`}
              className={`${SELECT} w-full`}
            >
              <option value="">{row.classId !== null && rowRequirements.length === 0 ? "沒有可合併的科目" : "科目"}</option>
              {rowRequirements.map((item) => (
                <option key={item.id} value={item.id}>
                  {lookups.subjectName.get(item.subject_id) ?? "—"}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setRows((previous) => previous.filter((_, position) => position !== index))}
              disabled={isSaving || rows.length === 1}
              className={BUTTON_SECONDARY_SM}
            >
              移除
            </button>
          </div>
        );
      })}
      <p>
        <button
          type="button"
          onClick={() => setRows((previous) => [...previous, { gradeId: null, classId: null, requirementId: null }])}
          disabled={isSaving}
          className={BUTTON_SECONDARY_SM}
        >
          ＋ 新增一列
        </button>
      </p>
      {blocks === null ? (
        <label className={DIALOG_FIELD_ROW}>
          <span className={LABEL}>合併節數</span>
          <select
            value={mergedCount}
            onChange={(event) => setMergedCount(Number(event.target.value))}
            disabled={isSaving}
            aria-label="合併節數"
            className={`${SELECT} w-full`}
          >
            {Array.from({ length: host.weekly_periods }, (_, index) => index + 1).map((count) => (
              <option key={count} value={count}>
                {count} 節（每週 {host.weekly_periods} 節中）
              </option>
            ))}
          </select>
        </label>
      ) : (
        <fieldset className="flex flex-wrap items-center gap-3">
          <legend className={LABEL}>合併哪幾組連堂</legend>
          {blocks.map((block) => (
            <label key={block.blockNo} className="inline-flex items-center gap-1">
              <input
                type="checkbox"
                checked={blockNos.includes(block.blockNo)}
                onChange={() => toggleBlock(block.blockNo)}
                disabled={isSaving}
                className={CHECKBOX}
              />
              {blockChoiceLabel(block)}
            </label>
          ))}
        </fieldset>
      )}
      <label className={DIALOG_FIELD_ROW}>
        <span className={LABEL}>上課教室</span>
        <select
          value={roomValue}
          onChange={(event) => setRoomValue(event.target.value)}
          disabled={isSaving}
          aria-label="上課教室"
          className={`${SELECT} w-full`}
        >
          {memberClassIds.map((memberClassId) => (
            <option key={`class-${memberClassId}`} value={`${HOMEROOM_PREFIX}${memberClassId}`}>
              {lookups.className.get(memberClassId) ?? "—"}
            </option>
          ))}
          {lookups.rooms.map((room) => (
            <option key={`room-${room.id}`} value={`${ROOM_PREFIX}${room.id}`}>
              {room.name}
            </option>
          ))}
        </select>
      </label>
      {existing !== null && (
        <p>
          <button type="button" onClick={() => void handleDelete()} disabled={isSaving} className={BUTTON_SECONDARY_SM}>
            取消這個合併
          </button>
        </p>
      )}
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
    </ConfirmDialog>
  );
}
