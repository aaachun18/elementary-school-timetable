import type { ReactElement } from "react";
import { AlertIcon, CheckIcon } from "./icons";
import type { BadgeTone } from "../utils/badgeTone";
import type { CheckTag, CheckTagState } from "../utils/checkTag";
import {
  BUTTON_SECONDARY_SM,
  CHECK_FAILED_TEXT,
  CHECK_TAG_BUTTON,
  CHECK_TAG_CHEVRON,
  CHECK_TAG_DANGER,
  CHECK_TAG_NEUTRAL,
  CHECK_TAG_ROW,
  CHECK_TAG_SUCCESS,
  CHECK_TAG_WARNING,
} from "../styles/ui";

const TAG_ICON_SIZE = 16;

const TAG_CLASSES: Partial<Record<BadgeTone, string>> = {
  success: CHECK_TAG_SUCCESS,
  danger: CHECK_TAG_DANGER,
  warning: CHECK_TAG_WARNING,
};

function Tag({ tag }: { tag: CheckTag }): ReactElement {
  return (
    <span className={TAG_CLASSES[tag.tone] ?? CHECK_TAG_NEUTRAL}>
      {tag.icon === "check" && <CheckIcon size={TAG_ICON_SIZE} />}
      {tag.icon === "alert" && <AlertIcon size={TAG_ICON_SIZE} />}
      {tag.label}
    </span>
  );
}

// Task 100 (item 5): the timetable's check result, one component for the
// view and the edit mode (same look, same place: right under the title
// row). What it says comes from utils/checkTag.ts; a click on the tags
// opens / closes the list (`listId`), which the page renders.
export default function CheckStatusTag({
  state,
  isOpen,
  onToggle,
  errorMessage,
  onRetry,
  listId,
}: {
  state: CheckTagState;
  isOpen: boolean;
  onToggle: () => void;
  errorMessage: string | null;
  onRetry: () => void;
  listId: string;
}): ReactElement | null {
  if (state.kind === "idle") {
    return null;
  }
  if (state.kind === "failed") {
    return (
      <div className={CHECK_TAG_ROW}>
        <p role="alert" className={CHECK_FAILED_TEXT}>
          檢查失敗：{errorMessage}
        </p>
        <button type="button" onClick={onRetry} className={BUTTON_SECONDARY_SM}>
          重試
        </button>
      </div>
    );
  }
  if (state.kind === "checking") {
    return (
      <div className={CHECK_TAG_ROW} aria-live="polite">
        {state.tags.map((tag) => (
          <Tag key={tag.label} tag={tag} />
        ))}
      </div>
    );
  }
  return (
    <div className={CHECK_TAG_ROW} aria-live="polite">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={listId}
        title={isOpen ? "收起問題清單" : "展開問題清單"}
        className={CHECK_TAG_BUTTON}
      >
        {state.tags.map((tag) => (
          <Tag key={tag.label} tag={tag} />
        ))}
        <span aria-hidden="true" className={CHECK_TAG_CHEVRON}>
          {isOpen ? "▴" : "▾"}
        </span>
      </button>
    </div>
  );
}
