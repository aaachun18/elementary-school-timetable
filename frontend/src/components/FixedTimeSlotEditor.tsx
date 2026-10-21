import { useEffect, useState, type ReactElement } from "react";
import { fixTimeSlot } from "../api/lessons";
import { generateLessons } from "../api/scheduleVersions";
import { extractApiErrorMessage } from "../constants/errorMessages";
import { useFixedTimeSlotData, type FixedTimeSlotGroup } from "../hooks/useFixedTimeSlotData";
import type { PeriodDisplayMap } from "../utils/periodDisplay";
import { formatTimeSlotLabel } from "../utils/timeSlotFormat";
import type { GenerateLessonsResponse } from "../types/scheduler";
import {
  BADGE_SUCCESS,
  BUTTON_LINK,
  BUTTON_SECONDARY,
  CARD,
  ERROR_TEXT,
  HELP_TEXT,
  LABEL,
  LOADING_TEXT,
  MUTED_TEXT,
  SELECT,
  SUCCESS_TEXT,
} from "../styles/ui";

const EMPTY_PERIOD_DISPLAY: PeriodDisplayMap = new Map();

// Task 41 / v3: 設定固定時段 (選填) of a 尚未排課 record -- pin individual
// lessons (not whole requirements) to a time slot before 自動排課. Lessons
// exist only after 展開課程清單 (generate-lessons, which 自動排課 also runs).
// Collapsed by default: most records never touch it. Each change is saved
// right away (optimistically, reverted if the save fails).
export default function FixedTimeSlotEditor({ versionId }: { versionId: number }): ReactElement {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateResult, setGenerateResult] = useState<GenerateLessonsResponse | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const fixedSlots = useFixedTimeSlotData(generateResult === null ? null : versionId, generateResult);
  const [groups, setGroups] = useState<FixedTimeSlotGroup[]>([]);
  const [savingLessonId, setSavingLessonId] = useState<number | null>(null);
  const [rowErrors, setRowErrors] = useState<ReadonlyMap<number, string>>(new Map());

  useEffect(() => {
    if (fixedSlots.data !== null) {
      setGroups(fixedSlots.data.groups);
    }
  }, [fixedSlots.data]);

  async function handleGenerate(): Promise<void> {
    setIsGenerating(true);
    setGenerateError(null);
    try {
      setGenerateResult(await generateLessons(versionId));
    } catch (caught) {
      setGenerateError(extractApiErrorMessage(caught));
    } finally {
      setIsGenerating(false);
    }
  }

  function applyValue(lessonId: number, value: number | null): void {
    setGroups((previous) =>
      previous.map((group) => ({
        ...group,
        lessons: group.lessons.map((lesson) =>
          lesson.lessonId === lessonId ? { ...lesson, fixedTimeSlotId: value } : lesson,
        ),
      })),
    );
  }

  function setRowError(lessonId: number, message: string | null): void {
    setRowErrors((previous) => {
      const next = new Map(previous);
      if (message === null) {
        next.delete(lessonId);
      } else {
        next.set(lessonId, message);
      }
      return next;
    });
  }

  async function handleChange(lessonId: number, previousValue: number | null, rawValue: string): Promise<void> {
    const newValue = rawValue === "" ? null : Number(rawValue);
    if (newValue === previousValue) {
      return;
    }
    setSavingLessonId(lessonId);
    setRowError(lessonId, null);
    applyValue(lessonId, newValue);
    try {
      await fixTimeSlot(lessonId, { time_slot_id: newValue });
    } catch (caught) {
      applyValue(lessonId, previousValue);
      setRowError(lessonId, extractApiErrorMessage(caught));
    } finally {
      setSavingLessonId(null);
    }
  }

  const periodDisplay = fixedSlots.data?.periodDisplay ?? EMPTY_PERIOD_DISPLAY;

  return (
    <section className="mb-6">
      <button type="button" onClick={() => setIsExpanded((previous) => !previous)} className={BUTTON_LINK}>
        {isExpanded ? "▾" : "▸"} 設定固定時段（選填）
      </button>
      {isExpanded && (
        <div className={`${CARD} mt-2`}>
          <p className={HELP_TEXT}>把某幾堂課固定在指定的節次，自動排課時會照著放。先展開課程清單，再為每一堂課選擇時段。</p>
          <button type="button" onClick={() => void handleGenerate()} disabled={isGenerating} className={BUTTON_SECONDARY}>
            {isGenerating ? "展開中…" : generateResult === null ? "展開課程清單" : "重新展開課程清單"}
          </button>
          {generateError !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {generateError}
            </p>
          )}
          {generateResult !== null && (
            <p className={`${SUCCESS_TEXT} mt-2`}>✓ 共 {generateResult.total_lesson_count} 堂課</p>
          )}
          {fixedSlots.isLoading && <p className={LOADING_TEXT}>載入中…</p>}
          {fixedSlots.errorMessage !== null && (
            <p role="alert" className={ERROR_TEXT}>
              {fixedSlots.errorMessage}
            </p>
          )}
          {generateResult !== null && !fixedSlots.isLoading && fixedSlots.errorMessage === null && (
            <div className="mt-3 flex flex-col gap-4">
              {groups.length === 0 && <p className={MUTED_TEXT}>目前沒有課程可供設定固定時段。</p>}
              {groups.map((group) => (
                <div key={group.requirementId}>
                  <p className="mb-2 font-semibold text-gray-900">{group.label}</p>
                  <div className="ml-4 flex flex-col gap-2">
                    {group.lessons.map((lessonRow) => {
                      const selectId = `fixed-slot-${lessonRow.lessonId}`;
                      return (
                        <div key={lessonRow.lessonId} className="flex flex-wrap items-center gap-2">
                          <label htmlFor={selectId} className={LABEL}>
                            第 {lessonRow.sequenceNumber} 堂
                            {lessonRow.blockPosition !== "" && (
                              <span className="ml-1 text-xs font-normal text-gray-500">（{lessonRow.blockPosition}）</span>
                            )}
                          </label>
                          <select
                            id={selectId}
                            value={lessonRow.fixedTimeSlotId ?? ""}
                            disabled={savingLessonId === lessonRow.lessonId}
                            onChange={(event) =>
                              void handleChange(lessonRow.lessonId, lessonRow.fixedTimeSlotId, event.target.value)
                            }
                            className={SELECT}
                          >
                            <option value="">不固定（交給系統排）</option>
                            {(fixedSlots.data?.teachingTimeSlots ?? []).map((timeSlot) => (
                              <option key={timeSlot.id} value={timeSlot.id}>
                                {formatTimeSlotLabel(timeSlot, periodDisplay)}
                              </option>
                            ))}
                          </select>
                          {lessonRow.fixedTimeSlotId !== null && <span className={BADGE_SUCCESS}>已固定</span>}
                          {rowErrors.get(lessonRow.lessonId) !== undefined && (
                            <p role="alert" className={`${ERROR_TEXT} w-full`}>
                              {rowErrors.get(lessonRow.lessonId)}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
