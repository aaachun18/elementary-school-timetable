// 帳號管理's list: the order of the accounts and the search box's state.
// Pure, no React.

import type { UserRole } from "./auth";

export interface SortableAccount {
  username: string;
  role: UserRole;
  teacher_name: string | null;
}

const ROLE_ORDER: Record<UserRole, number> = { ADMIN: 0, COORDINATOR: 1, TEACHER: 2 };

// Teachers by their name's strokes -- the surname's first (zh-Hant's
// collation orders Chinese by stroke count: 丁 2, 王 4, 李 7, 陳 16) --
// then by 帳號名稱. Accounts without a teacher (系統管理員 / 教學組長)
// come first, by role and 帳號名稱. A copy; the input is unchanged.
export function sortAccounts<T extends SortableAccount>(accounts: readonly T[]): T[] {
  return [...accounts].sort((a, b) => {
    if ((a.teacher_name === null) !== (b.teacher_name === null)) {
      return a.teacher_name === null ? -1 : 1;
    }
    if (a.teacher_name === null || b.teacher_name === null) {
      return ROLE_ORDER[a.role] - ROLE_ORDER[b.role] || a.username.localeCompare(b.username);
    }
    return a.teacher_name.localeCompare(b.teacher_name, "zh-Hant-TW") || a.username.localeCompare(b.username);
  });
}

// The 序號 of the row at `index` on page `page` (1-based, across pages).
export function serialNumber(page: number, pageSize: number, index: number): number {
  return (page - 1) * pageSize + index + 1;
}

// The line under the search box while a search is applied: how many were
// found, so it is clear the table is filtered (清除搜尋 sits next to it).
export function searchResultText(search: string, count: number): string {
  return count === 0 ? `找不到包含「${search}」的帳號` : `搜尋「${search}」：共 ${count} 個帳號`;
}
