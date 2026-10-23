import { useEffect, useState, type ReactElement } from "react";
import { fixTimeSlot, list as listLessons } from "../../api/lessons";
import { generateLessons } from "../../api/scheduleVersions";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import type { Lesson } from "../../types/lesson";
import type { TimeSlot } from "../../types/timeSlot";
import { formatBlockPosition, parseLessonPattern } from "../../utils/lessonPattern";
import type { PeriodDisplayMap } from "../../utils/periodDisplay";
import { formatTimeSlotLabel } from "../../utils/timeSlotFormat";
import ConfirmDialog from "../ConfirmDialog";
import { BADGE_SUCCESS, ERROR_TEXT, HELP_TEXT, LABEL, LOADING_TEXT, SELECT } from "../../styles/ui";

// 開始排課 > 科目需求's 「固定時段」 (選填): pin some of one requirement's
// lessons to a time slot before 自動排課. Opening it makes the record's
// lessons (generate-lessons -- 自動排課 does the same) and lists this
// requirement's, one time slot choice each; every change is saved right
// away. A lesson in a 共同排課 fixes the other classes' lesson with it (the
// backend does that).
export default function FixedSlotsDialog({
  versionId,
  requirementId,
  lessonPattern,
  title,
  teachingTimeSlots,
  periodDisplay,
  onClose,
}: {
  versionId: number;
  requirementId: number;
  lessonPattern: string | null;
  title: string;
  teachingTimeSlots: readonly TimeSlot[];
  periodDisplay: PeriodDisplayMap;
  onClose: () => void;
}): ReactElement {
  const [lessons, setLessons] = useState<Lesson[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [savingLessonId, setSavingLessonId] = useState<number | null>(null);
  const [rowErrors, setRowErrors] = useState<ReadonlyMap<number, string>>(new Map());

  useEffect(() => {
    let isCurrent = true;
    generateLessons(versionId)
      .then(() => listLessons(0, 1000, { schedule_version_id: versionId }))
      .then((all) => {
        if (isCurrent) {
          setLessons(
            all
              .filter((lesson) => lesson.class_subject_requirement_id === requirementId)
              .sort((a, b) => a.sequence_number - b.sequence_number),
          );
        }
      })
      .catch((caught: unknown) => {
        if (isCurrent) {
          setLoadError(extractApiErrorMessage(caught));
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [versionId, requirementId]);

  const blockSizes = lessonPattern === null ? null : parseLessonPattern(lessonPattern);

  async function handleChange(lesson: Lesson, rawValue: string): Promise<void> {
    const newValue = rawValue === "" ? null : Number(rawValue);
    if (newValue === lesson.fixed_time_slot_id) {
      return;
    }
    setSavingLessonId(lesson.id);
    setRowErrors((previous) => {
      const next = new Map(previous);
      next.delete(lesson.id);
      return next;
    });
    try {
      const saved = await fixTimeSlot(lesson.id, { time_slot_id: newValue });
      setLessons((previous) => (previous ?? []).map((item) => (item.id === saved.id ? saved : item)));
    } catch (caught) {
      setRowErrors((previous) => new Map(previous).set(lesson.id, extractApiErrorMessage(caught)));
    } finally {
      setSavingLessonId(null);
    }
  }

  return (
    <ConfirmDialog
      open
      title={title}
      cancelLabel="完成"
      showConfirm={false}
      busy={savingLessonId !== null}
      onConfirm={onClose}
      onCancel={onClose}
    >
      <p className={HELP_TEXT}>把這個科目的某幾堂課固定在指定的節次，自動排課時會照著放；不固定的交給系統排。修改後立即儲存。</p>
      {loadError !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {loadError}
        </p>
      )}
      {lessons === null && loadError === null && <p className={LOADING_TEXT}>載入中…</p>}
      {lessons !== null &&
        lessons.map((lesson) => {
          const blockNo = lesson.block_no ?? null;
          const blockSize = blockSizes !== null && blockNo !== null ? (blockSizes[blockNo - 1] ?? 1) : 1;
          const position = formatBlockPosition(blockNo, lesson.block_seq, blockSize);
          const selectId = `fixed-slot-${lesson.id}`;
          return (
            <div key={lesson.id} className="grid grid-cols-[8rem_1fr_auto] items-center gap-2">
              <label htmlFor={selectId} className={LABEL}>
                第 {lesson.sequence_number} 堂
                {position !== "" && <span className="ml-1 text-xs font-normal text-gray-500">（{position}）</span>}
              </label>
              <select
                id={selectId}
                value={lesson.fixed_time_slot_id ?? ""}
                disabled={savingLessonId === lesson.id}
                onChange={(event) => void handleChange(lesson, event.target.value)}
                className={`${SELECT} w-full`}
              >
                <option value="">不固定（交給系統排）</option>
                {teachingTimeSlots.map((timeSlot) => (
                  <option key={timeSlot.id} value={timeSlot.id}>
                    {formatTimeSlotLabel(timeSlot, periodDisplay)}
                  </option>
                ))}
              </select>
              {lesson.fixed_time_slot_id !== null ? <span className={BADGE_SUCCESS}>已固定</span> : <span />}
              {rowErrors.get(lesson.id) !== undefined && (
                <p role="alert" className={`${ERROR_TEXT} col-span-3`}>
                  {rowErrors.get(lesson.id)}
                </p>
              )}
            </div>
          );
        })}
    </ConfirmDialog>
  );
}
