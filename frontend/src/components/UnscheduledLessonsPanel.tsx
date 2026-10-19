import type { DragEvent, ReactElement } from "react";
import {
  groupCardsByClass,
  needsTeacherChoice,
  teacherForCard,
  type PlacementCard,
} from "../utils/placement";
import {
  ERROR_TEXT,
  PLACE_CARD,
  PLACE_CARD_BUTTON,
  PLACE_CARD_BUTTON_DRAGGING,
  PLACE_CARD_BUTTON_NEEDS_TEACHER,
  PLACE_CARD_BUTTON_SELECTED,
  PLACE_GROUP,
  PLACE_GROUP_LABEL,
  PLACE_PANEL,
  PLACE_PANEL_TITLE,
  PLACE_TEACHER_SELECT,
  PLACE_TOGGLE,
} from "../styles/ui";

interface UnscheduledLessonsPanelProps {
  // The cards to show (already narrowed to the view, utils/placement.ts).
  cards: PlacementCard[];
  // Every unscheduled lesson of the version, for the title's count.
  totalLessonCount: number;
  // 「顯示全部班級」 -- only offered in the class view with a class chosen.
  showAllToggle: { showAll: boolean; onToggle: () => void } | null;
  chosenTeacherByCard: ReadonlyMap<string, number>;
  onChooseTeacher: (card: PlacementCard, teacherId: number | null) => void;
  selectedCardKey: string | null;
  draggingCardKey: string | null;
  // A preview / save is in flight, or the timetable is reloading.
  disabled: boolean;
  errorMessage: string | null;
  onCardClick: (card: PlacementCard) => void;
  onCardDragStart: (card: PlacementCard, event: DragEvent<HTMLButtonElement>) => void;
  onCardDragEnd: () => void;
}

function cardTitle(card: PlacementCard, hasTeacher: boolean): string {
  if (!hasTeacher) {
    return "請先選擇教師";
  }
  const partial = card.isPartialBlock ? "，這組連堂已有節次排入，要放在它旁邊" : "";
  return `拖到課表格子，或點選後再點「放到這裡」${partial}`;
}

// Task 93: the lessons of the semester that aren't in this version yet
// (e.g. a requirement added after scheduling), as cards grouped by class.
// A card is dragged onto a cell, or clicked and then placed with the
// cell's 「放到這裡」 -- the same two ways a lesson is moved (Task 69/71).
export default function UnscheduledLessonsPanel({
  cards,
  totalLessonCount,
  showAllToggle,
  chosenTeacherByCard,
  onChooseTeacher,
  selectedCardKey,
  draggingCardKey,
  disabled,
  errorMessage,
  onCardClick,
  onCardDragStart,
  onCardDragEnd,
}: UnscheduledLessonsPanelProps): ReactElement {
  const groups = groupCardsByClass(cards);
  return (
    <section className={PLACE_PANEL} aria-label="未排入課程">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h2 className={PLACE_PANEL_TITLE}>未排入課程（{totalLessonCount}）</h2>
        {showAllToggle !== null && (
          <button
            type="button"
            className={PLACE_TOGGLE}
            aria-pressed={showAllToggle.showAll}
            onClick={showAllToggle.onToggle}
          >
            {showAllToggle.showAll ? "只顯示本班" : "顯示全部班級"}
          </button>
        )}
      </div>
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
      {groups.length === 0 ? (
        <p className="text-xs text-gray-500">本班沒有未排入的課程</p>
      ) : (
        <div className="flex flex-col gap-2">
          {groups.map((group) => (
            <div key={group.classId} className={PLACE_GROUP}>
              <span className={PLACE_GROUP_LABEL}>{group.className}</span>
              {group.cards.map((card) => {
                const teacherId = teacherForCard(card, chosenTeacherByCard);
                const hasTeacher = teacherId !== null;
                const isSelected = selectedCardKey === card.key;
                const isDragging = draggingCardKey === card.key;
                const buttonClass = isDragging
                  ? PLACE_CARD_BUTTON_DRAGGING
                  : !hasTeacher
                    ? PLACE_CARD_BUTTON_NEEDS_TEACHER
                    : isSelected
                      ? PLACE_CARD_BUTTON_SELECTED
                      : PLACE_CARD_BUTTON;
                return (
                  <div key={card.key} className={PLACE_CARD}>
                    <button
                      type="button"
                      className={buttonClass}
                      draggable={!disabled}
                      disabled={disabled}
                      aria-pressed={isSelected}
                      aria-label={`${isSelected ? "取消選取" : "選取"} ${group.className} ${card.label}${
                        hasTeacher ? "" : "（請先選擇教師）"
                      }`}
                      title={cardTitle(card, hasTeacher)}
                      data-place-card={card.key}
                      onClick={() => onCardClick(card)}
                      onDragStart={(event) => onCardDragStart(card, event)}
                      onDragEnd={onCardDragEnd}
                    >
                      {card.label}
                    </button>
                    {needsTeacherChoice(card) && (
                      <select
                        aria-label={`${group.className} ${card.subjectName}的教師`}
                        className={PLACE_TEACHER_SELECT}
                        value={teacherId ?? ""}
                        disabled={disabled}
                        onChange={(event) =>
                          onChooseTeacher(card, event.target.value === "" ? null : Number(event.target.value))
                        }
                      >
                        <option value="">選教師…</option>
                        {card.eligibleTeachers.map((teacher) => (
                          <option key={teacher.teacher_id} value={teacher.teacher_id}>
                            {teacher.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
