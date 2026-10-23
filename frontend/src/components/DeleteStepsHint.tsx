import { useId, useRef, useState, type ReactElement } from "react";
import { ERROR_TEXT } from "../styles/ui";

const TOOLTIP_WIDTH_PX = 320;
const VIEWPORT_MARGIN_PX = 8;

// 「此資料仍被其他資料參照，無法刪除」: a small light-gray ? circle right of
// the message; hovering (or focusing) it shows what to delete first, step
// by step. The tooltip is position: fixed so a table's scroll box never
// clips it. Renders nothing when there are no steps.
export function DeleteStepsHint({ steps }: { steps: readonly string[] }): ReactElement | null {
  const tooltipId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  if (steps.length === 0) {
    return null;
  }

  function show(): void {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (rect === undefined) {
      return;
    }
    const maxLeft = window.innerWidth - TOOLTIP_WIDTH_PX - VIEWPORT_MARGIN_PX;
    setPosition({
      top: rect.bottom + 6,
      left: Math.max(VIEWPORT_MARGIN_PX, Math.min(rect.left, maxLeft)),
    });
  }

  function hide(): void {
    setPosition(null);
  }

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-label="查看刪除步驟"
        aria-describedby={position !== null ? tooltipId : undefined}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className="ml-1.5 inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-gray-200 align-middle text-[11px] font-bold leading-none text-gray-600 hover:bg-gray-300"
      >
        ?
      </button>
      {position !== null && (
        <div
          id={tooltipId}
          role="tooltip"
          style={{ top: position.top, left: position.left, width: TOOLTIP_WIDTH_PX }}
          className="fixed z-50 rounded-md border border-gray-200 bg-white p-3 text-left text-sm text-gray-700 shadow-lg"
        >
          <p className="mb-1 font-medium text-gray-900">請依序完成以下步驟，就能刪除：</p>
          <ol className="list-decimal space-y-1 pl-5">
            {steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      )}
    </>
  );
}

// A row's error line: the message, plus the ? hint when a refused delete
// came with steps.
export function RowErrorText({
  message,
  deleteSteps = [],
}: {
  message: string;
  deleteSteps?: readonly string[];
}): ReactElement {
  return (
    <p role="alert" className={ERROR_TEXT}>
      {message}
      <DeleteStepsHint steps={deleteSteps} />
    </p>
  );
}
