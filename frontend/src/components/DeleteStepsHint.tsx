import type { ReactElement } from "react";
import InfoPopover from "./InfoPopover";
import { ROW_ERROR_TEXT, ROW_ERROR_TEXT_FIXED } from "../styles/ui";

// 「此資料仍被其他資料參照，無法刪除」: an (i) button right of the message
// (Task 98: InfoPopover, was a hover-only ? circle); it shows what to
// delete first, step by step. Renders nothing when there are no steps.
export function DeleteStepsHint({ steps }: { steps: readonly string[] }): ReactElement | null {
  if (steps.length === 0) {
    return null;
  }
  return (
    <InfoPopover label="查看刪除步驟">
      <p className="mb-1 font-medium text-gray-900">請依序完成以下步驟，就能刪除：</p>
      <ol className="list-decimal space-y-1 pl-5">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </InfoPopover>
  );
}

// A row's error line: the message, plus the (i) hint when a refused delete
// came with steps. A <div>, not a <p>: the hint's panel is a <div>.
// `inFixedColumn` (Task 101): the row's 操作 column has a set width (a
// fixed-layout DATA_TABLE) -- the line wraps inside it, at the right.
export function RowErrorText({
  message,
  deleteSteps = [],
  inFixedColumn = false,
}: {
  message: string;
  deleteSteps?: readonly string[];
  inFixedColumn?: boolean;
}): ReactElement {
  return (
    <div
      role="alert"
      className={
        inFixedColumn
          ? `${ROW_ERROR_TEXT_FIXED} flex items-center justify-end gap-1`
          : `${ROW_ERROR_TEXT} flex items-center gap-1`
      }
    >
      <span>{message}</span>
      <DeleteStepsHint steps={deleteSteps} />
    </div>
  );
}
