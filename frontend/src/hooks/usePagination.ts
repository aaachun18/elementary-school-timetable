import { useState } from "react";
import { PAGE_SIZE, clampPage, pageSlice } from "../utils/pagination";

export interface Pagination<T> {
  // The page shown (always one that exists, utils/pagination.ts clampPage).
  page: number;
  pageItems: T[];
  totalItems: number;
  setPage: (page: number) => void;
}

// Task 103: one list's page. The page asked for is kept as it is; the one
// shown is clamped on every render, so a delete or 停用 that empties the
// page lands on the (new) last page, and every other change -- 重設密碼,
// 停用 of a row that stays listed -- keeps the page where it was.
export function usePagination<T>(items: readonly T[], pageSize: number = PAGE_SIZE): Pagination<T> {
  const [requestedPage, setRequestedPage] = useState(1);
  const page = clampPage(requestedPage, items.length, pageSize);
  return {
    page,
    pageItems: pageSlice(items, page, pageSize),
    totalItems: items.length,
    setPage: (next) => setRequestedPage(clampPage(next, items.length, pageSize)),
  };
}
