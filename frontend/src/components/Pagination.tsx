import type { ReactElement } from "react";
import { PAGE_SIZE, clampPage, pageCount, pageLabel, showsPagination } from "../utils/pagination";
import { BUTTON_SECONDARY_SM, MUTED_TEXT } from "../styles/ui";

// Task 103: right under a paged table -- 上一頁, 第 X / Y 頁, 下一頁. Nothing
// at all for ten rows or fewer.
export default function Pagination({
  page,
  totalItems,
  onPageChange,
  pageSize = PAGE_SIZE,
}: {
  page: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
}): ReactElement | null {
  if (!showsPagination(totalItems, pageSize)) {
    return null;
  }
  const current = clampPage(page, totalItems, pageSize);
  const last = pageCount(totalItems, pageSize);
  return (
    <nav aria-label="分頁" className="mt-3 flex items-center justify-center gap-3">
      <button
        type="button"
        onClick={() => onPageChange(current - 1)}
        disabled={current <= 1}
        className={BUTTON_SECONDARY_SM}
      >
        上一頁
      </button>
      <span className={MUTED_TEXT} aria-live="polite">
        {pageLabel(current, totalItems, pageSize)}
      </span>
      <button
        type="button"
        onClick={() => onPageChange(current + 1)}
        disabled={current >= last}
        className={BUTTON_SECONDARY_SM}
      >
        下一頁
      </button>
    </nav>
  );
}
