// Task 103: front-end paging of 排課紀錄, 帳號管理 and 檢視排課設定's 參與教師
// -- the whole list is already loaded, so a page is just a slice. Pure, no
// React (pagination.test.ts); hooks/usePagination.ts and
// components/Pagination.tsx put it on screen.

export const PAGE_SIZE = 10;

// At least one page, even for an empty list.
export function pageCount(totalItems: number, pageSize: number = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(totalItems / pageSize));
}

// A page number that exists: 1 .. pageCount. When a delete (or anything
// else) empties the last page, the page shown falls back to the new last
// one; on a page that still has rows nothing moves.
export function clampPage(page: number, totalItems: number, pageSize: number = PAGE_SIZE): number {
  const last = pageCount(totalItems, pageSize);
  if (!Number.isFinite(page) || page < 1) {
    return 1;
  }
  return Math.min(Math.floor(page), last);
}

// The rows of that (clamped) page.
export function pageSlice<T>(items: readonly T[], page: number, pageSize: number = PAGE_SIZE): T[] {
  const current = clampPage(page, items.length, pageSize);
  const start = (current - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

// The 上一頁 / 下一頁 controls only appear when there is more than one page.
export function showsPagination(totalItems: number, pageSize: number = PAGE_SIZE): boolean {
  return totalItems > pageSize;
}

export function pageLabel(page: number, totalItems: number, pageSize: number = PAGE_SIZE): string {
  return `第 ${clampPage(page, totalItems, pageSize)} / ${pageCount(totalItems, pageSize)} 頁`;
}
