import { useState, type ReactElement } from "react";
import TeacherReassignPreviewDialog from "./TeacherReassignPreviewDialog";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useTeacherReassignment } from "../hooks/useTeacherReassignment";
import type { TimetableData } from "../hooks/useTimetableData";
import {
  resolveClassName,
  resolveRequirementLabel,
  resolveSubjectName,
  resolveTeacherName,
} from "../utils/failureDiagnostics";
import {
  coursesOfTeacher,
  currentTeacherIdsOf,
  teacherIdsWithCourses,
} from "../utils/teacherReassignment";
import type { TeacherReassignmentResult } from "../types/scheduler";
import {
  BADGE_INFO,
  BUTTON_PRIMARY_SM,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  MUTED_TEXT,
  SELECT,
  SUBSECTION_TITLE,
  SUCCESS_TEXT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
} from "../styles/ui";

interface TeacherReassignPanelProps {
  // The parent mounts the panel with key={versionId}, so switching versions
  // starts it over (selection, handed-away rows, any request in flight).
  scheduleVersionId: number;
  timetable: TimetableData;
  // The timetable is (re)loading: names/teachers may be stale.
  disabled: boolean;
  onSaved: (result: TeacherReassignmentResult) => void;
}

// A course handed away from a teacher during this panel's lifetime -- kept
// in that teacher's list (marked) so the next step of a chain can follow.
interface HandedAway {
  requirementId: number;
  fromTeacherId: number;
  toTeacherId: number;
}

// Task 70: 換教師 -- for a departing teacher, hand each of their courses
// (one ClassSubjectRequirement at a time) to another teacher, previewing
// each change first. Works on the timetable data TimetableView already
// loaded; the only requests are the preview/save of one reassignment.
export default function TeacherReassignPanel({
  scheduleVersionId,
  timetable,
  disabled,
  onSaved,
}: TeacherReassignPanelProps): ReactElement {
  const reassignment = useTeacherReassignment(scheduleVersionId);
  const flash = useFlashMessage(5000);
  const [originalTeacherId, setOriginalTeacherId] = useState<number | "">("");
  const [newTeacherByRequirement, setNewTeacherByRequirement] = useState<Map<number, number>>(
    new Map(),
  );
  const [handedAway, setHandedAway] = useState<HandedAway[]>([]);

  const { lookups, teacherIdsByRequirementId } = timetable;
  const requirements = Array.from(lookups.requirementById.values());
  const teacherName = (teacherId: number): string => resolveTeacherName(teacherId, lookups);
  const byName = (a: number, b: number): number =>
    teacherName(a).localeCompare(teacherName(b), "zh-Hant");

  // 原教師: everyone holding a course now, plus anyone who just handed
  // their last course away (so the list they're working from stays).
  const originalTeacherOptions = Array.from(
    new Set([
      ...teacherIdsWithCourses(requirements, teacherIdsByRequirementId),
      ...handedAway.map((entry) => entry.fromTeacherId),
    ]),
  ).sort(byName);

  const handedAwayFromSelected = handedAway.filter(
    (entry) => entry.fromTeacherId === originalTeacherId,
  );
  const courses =
    originalTeacherId === ""
      ? []
      : coursesOfTeacher(
          originalTeacherId,
          requirements,
          teacherIdsByRequirementId,
          new Set(handedAwayFromSelected.map((entry) => entry.requirementId)),
        );

  // 新教師 candidates: active teachers other than the 原教師. Each row then
  // also leaves out that course's own current teacher(s) (Task 71) -- e.g.
  // on a 「剛換給…」 row, the teacher it was just handed to.
  const activeTeacherIds = Array.from(lookups.teacherById.values())
    .filter((teacher) => teacher.is_active && teacher.id !== originalTeacherId)
    .map((teacher) => teacher.id)
    .sort(byName);

  const isBusy = disabled || reassignment.phase !== "idle";

  function handleSelectOriginalTeacher(value: string): void {
    setOriginalTeacherId(value === "" ? "" : Number(value));
    setNewTeacherByRequirement(new Map());
  }

  function handleSelectNewTeacher(requirementId: number, value: string): void {
    setNewTeacherByRequirement((previous) => {
      const next = new Map(previous);
      if (value === "") {
        next.delete(requirementId);
      } else {
        next.set(requirementId, Number(value));
      }
      return next;
    });
  }

  function handlePreview(requirementId: number): void {
    const newTeacherId = newTeacherByRequirement.get(requirementId);
    if (newTeacherId === undefined) {
      return;
    }
    reassignment.requestPreview({ requirementId, newTeacherId });
  }

  function handleConfirm(): void {
    void reassignment.confirm().then((result) => {
      if (result === null) {
        return;
      }
      const requirementId = result.class_subject_requirement_id;
      if (originalTeacherId !== "") {
        setHandedAway((previous) => [
          ...previous.filter((entry) => entry.requirementId !== requirementId),
          { requirementId, fromTeacherId: originalTeacherId, toTeacherId: result.new_teacher_id },
        ]);
      }
      handleSelectNewTeacher(requirementId, "");
      flash.showFlash(
        `已將「${resolveRequirementLabel(requirementId, lookups)}」換給${teacherName(
          result.new_teacher_id,
        )}（${result.updated_schedule_row_count} 堂課）`,
      );
      onSaved(result);
    });
  }

  return (
    <section className={`${CARD} mb-4`} aria-label="換教師">
      <h2 className={SUBSECTION_TITLE}>換教師</h2>
      <p className={HELP_TEXT}>
        以「一門課」（某班級的某科目）為單位換人，例如處理教師離職：先選原教師，再為每門課指定新教師並預覽。可以連續操作，例如把
        A 的課交給 B 之後，再改選 B 把 B 原本的課交給 C。
      </p>

      <label htmlFor="reassign-original-teacher" className={`${LABEL} mb-1 block`}>
        原教師
      </label>
      {originalTeacherOptions.length === 0 ? (
        <p className={MUTED_TEXT}>這個版本還沒有任何指定教師的課。</p>
      ) : (
        <select
          id="reassign-original-teacher"
          value={originalTeacherId}
          onChange={(event) => handleSelectOriginalTeacher(event.target.value)}
          disabled={isBusy}
          className={`${SELECT} mb-3`}
        >
          <option value="">請選擇…</option>
          {originalTeacherOptions.map((teacherId) => (
            <option key={teacherId} value={teacherId}>
              {teacherName(teacherId)}
              {lookups.teacherById.get(teacherId)?.is_active === false ? "（已停用）" : ""}
            </option>
          ))}
        </select>
      )}

      {flash.message !== null && <p className={`${SUCCESS_TEXT} mb-2`}>✓ {flash.message}</p>}
      {reassignment.previewError !== null && (
        <p role="alert" className={`${ERROR_TEXT} mb-2`}>
          無法預覽這次換人，已取消：{reassignment.previewError}
        </p>
      )}
      {reassignment.phase === "loadingPreview" && (
        <p className={`${LOADING_TEXT} mb-2`} aria-live="polite">
          正在預覽換人結果…
        </p>
      )}

      {originalTeacherId !== "" &&
        (courses.length === 0 ? (
          <p className={MUTED_TEXT}>這位教師在這個版本沒有任何課。</p>
        ) : (
          <div className={TABLE_WRAPPER}>
            <table className={TABLE}>
              <thead>
                <tr className={TABLE_HEAD_ROW}>
                  <th className={TH}>班級</th>
                  <th className={TH}>科目</th>
                  <th className={TH}>每週節數</th>
                  <th className={TH}>目前教師</th>
                  <th className={TH}>新教師</th>
                  <th className={TH}>
                    <span className="sr-only">動作</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {courses.map((requirement) => {
                  const courseName = resolveRequirementLabel(requirement.id, lookups);
                  const currentTeacherIds = currentTeacherIdsOf(
                    requirement,
                    teacherIdsByRequirementId.get(requirement.id),
                  );
                  const currentNames = currentTeacherIds.map(teacherName);
                  const newTeacherOptions = activeTeacherIds.filter(
                    (teacherId) => !currentTeacherIds.includes(teacherId),
                  );
                  const handedTo = handedAwayFromSelected.find(
                    (entry) => entry.requirementId === requirement.id,
                  );
                  const selectedNewTeacher = newTeacherByRequirement.get(requirement.id);
                  return (
                    <tr key={requirement.id}>
                      <td className={TD}>{resolveClassName(requirement.class_id, lookups)}</td>
                      <td className={TD}>{resolveSubjectName(requirement.subject_id, lookups)}</td>
                      <td className={TD}>{requirement.weekly_periods}</td>
                      <td className={TD}>
                        {currentNames.length === 0 ? "未指定" : currentNames.join("、")}
                        {handedTo !== undefined && (
                          <span className={`${BADGE_INFO} ml-2`}>
                            剛換給{teacherName(handedTo.toTeacherId)}
                          </span>
                        )}
                      </td>
                      <td className={TD}>
                        <select
                          aria-label={`${courseName} 的新教師`}
                          value={selectedNewTeacher ?? ""}
                          onChange={(event) =>
                            handleSelectNewTeacher(requirement.id, event.target.value)
                          }
                          disabled={isBusy}
                          className={SELECT}
                        >
                          <option value="">請選擇…</option>
                          {newTeacherOptions.map((teacherId) => (
                            <option key={teacherId} value={teacherId}>
                              {teacherName(teacherId)}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className={TD}>
                        <button
                          type="button"
                          onClick={() => handlePreview(requirement.id)}
                          disabled={isBusy || selectedNewTeacher === undefined}
                          aria-label={`預覽把 ${courseName} 換給新教師`}
                          className={BUTTON_PRIMARY_SM}
                        >
                          預覽
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}

      <TeacherReassignPreviewDialog
        preview={reassignment.preview}
        lookups={lookups}
        isSaving={reassignment.phase === "saving"}
        saveError={reassignment.saveError}
        onConfirm={handleConfirm}
        onCancel={reassignment.closePreview}
      />
    </section>
  );
}
