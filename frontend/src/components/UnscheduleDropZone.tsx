import { useState, type DragEvent, type ReactElement } from "react";
import { UNSCHEDULE_ZONE, UNSCHEDULE_ZONE_ACTIVE } from "../styles/ui";

// 「移出課表」: a box above the timetable while editing. Dropping a lesson
// on it -- or clicking it with a lesson selected -- previews taking the
// lesson (with its whole 連堂 block) out of the timetable; it then waits
// among 「未排入課程」 to be placed again. Nothing is saved without the
// preview's 確認.
export default function UnscheduleDropZone({
  isDraggingLesson,
  hasSelectedLesson,
  disabled,
  onUnschedule,
}: {
  // A lesson of the grid is being dragged right now (not a card).
  isDraggingLesson: boolean;
  hasSelectedLesson: boolean;
  disabled: boolean;
  // The dragged lesson on a drop, the selected one on a click.
  onUnschedule: (source: "drop" | "click") => void;
}): ReactElement {
  const [isOver, setIsOver] = useState(false);
  const canClick = hasSelectedLesson && !disabled;

  function handleDragOver(event: DragEvent<HTMLButtonElement>): void {
    if (!isDraggingLesson || disabled) {
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setIsOver(true);
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>): void {
    setIsOver(false);
    if (!isDraggingLesson || disabled) {
      return;
    }
    event.preventDefault();
    onUnschedule("drop");
  }

  const text = isDraggingLesson
    ? "放到這裡：移出課表（連堂整組一起移出）"
    : hasSelectedLesson
      ? "點這裡把已選取的課移出課表（連堂整組一起移出）"
      : "移出課表：把課拖到這裡，它會回到「未排入課程」，之後可再放回課表";

  return (
    <button
      type="button"
      onClick={() => canClick && onUnschedule("click")}
      onDragOver={handleDragOver}
      onDragLeave={() => setIsOver(false)}
      onDrop={handleDrop}
      aria-disabled={!canClick}
      aria-label={hasSelectedLesson ? "把已選取的課移出課表" : "移出課表"}
      className={isOver || (isDraggingLesson && !disabled) ? UNSCHEDULE_ZONE_ACTIVE : UNSCHEDULE_ZONE}
    >
      {text}
    </button>
  );
}
