import { useEffect, useState } from "react";
import { extractApiErrorMessage } from "../constants/errorMessages";

// One row's create()/update()/remove() functions -- exactly the shape
// every resource's api/*.ts module already exports (see teachers.ts's
// comment on why every module has all 5, even ones Phase A never called).
export interface CrudApi<T, TCreate, TUpdate> {
  create: (data: TCreate) => Promise<T>;
  update: (id: number, data: TUpdate) => Promise<T>;
  remove: (id: number) => Promise<void>;
}

// Which row a piece of per-row state belongs to -- "new" for the add-row
// draft (which has no id yet), or an existing row's id.
export type RowKey = number | "new";

export interface CrudListController<T, TCreate, TUpdate> {
  items: T[];
  isAdding: boolean;
  startAdding: () => void;
  cancelAdding: () => void;
  editingId: number | null;
  startEditing: (id: number) => void;
  cancelEditing: () => void;
  // The one row whose create/update/delete request is currently in
  // flight, or null -- at most one at a time, since every button that
  // starts a request is itself disabled for the duration (see spec: "三種
  // 操作進行中時,該列相關按鈕 disabled"). Callers use this to disable
  // that row's own Confirm/Cancel/Edit/Delete buttons.
  pendingKey: RowKey | null;
  rowErrors: Map<RowKey, string>;
  submitCreate: (data: TCreate) => Promise<void>;
  submitUpdate: (id: number, data: TUpdate) => Promise<void>;
  submitDelete: (id: number) => Promise<void>;
}

// Phase B's shared add/edit/delete interaction mechanics (Task 42) --
// School/Subject/Room's tabs in DataBrowser.tsx are the first 3 call
// sites, each supplying its own row markup (their fields all differ) but
// sharing this same state machine, so the pattern is established ONCE and
// every later table's tab is "write the row JSX, plug in its api/*.ts
// module" instead of re-deriving this from scratch.
//
// `sourceItems` is the latest fetch from useResource(); this hook keeps
// its own local copy (seeded from it, then updated directly on each
// successful create/update/delete) so the screen reflects a change
// immediately without waiting on, or forcing, a refetch -- the same
// pattern SchedulerConsole.tsx's `versions` state already uses for
// exactly this reason.
export function useCrudList<T extends { id: number }, TCreate, TUpdate>(
  sourceItems: T[] | null,
  api: CrudApi<T, TCreate, TUpdate>,
): CrudListController<T, TCreate, TUpdate> {
  const [items, setItems] = useState<T[]>([]);
  useEffect(() => {
    if (sourceItems !== null) {
      setItems(sourceItems);
    }
  }, [sourceItems]);

  const [isAdding, setIsAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [pendingKey, setPendingKey] = useState<RowKey | null>(null);
  const [rowErrors, setRowErrors] = useState<Map<RowKey, string>>(new Map());

  function clearRowError(key: RowKey): void {
    setRowErrors((previous) => {
      if (!previous.has(key)) {
        return previous;
      }
      const next = new Map(previous);
      next.delete(key);
      return next;
    });
  }

  function startAdding(): void {
    clearRowError("new");
    setIsAdding(true);
  }

  function cancelAdding(): void {
    setIsAdding(false);
    clearRowError("new");
  }

  function startEditing(id: number): void {
    clearRowError(id);
    setEditingId(id);
  }

  function cancelEditing(): void {
    setEditingId(null);
  }

  async function submitCreate(data: TCreate): Promise<void> {
    setPendingKey("new");
    clearRowError("new");
    try {
      const created = await api.create(data);
      setItems((previous) => [...previous, created]);
      setIsAdding(false);
    } catch (error) {
      setRowErrors((previous) => new Map(previous).set("new", extractApiErrorMessage(error)));
    } finally {
      setPendingKey(null);
    }
  }

  async function submitUpdate(id: number, data: TUpdate): Promise<void> {
    setPendingKey(id);
    clearRowError(id);
    try {
      const updated = await api.update(id, data);
      setItems((previous) => previous.map((item) => (item.id === id ? updated : item)));
      setEditingId(null);
    } catch (error) {
      setRowErrors((previous) => new Map(previous).set(id, extractApiErrorMessage(error)));
    } finally {
      setPendingKey(null);
    }
  }

  async function submitDelete(id: number): Promise<void> {
    setPendingKey(id);
    clearRowError(id);
    try {
      await api.remove(id);
      setItems((previous) => previous.filter((item) => item.id !== id));
    } catch (error) {
      setRowErrors((previous) => new Map(previous).set(id, extractApiErrorMessage(error)));
    } finally {
      setPendingKey(null);
    }
  }

  return {
    items,
    isAdding,
    startAdding,
    cancelAdding,
    editingId,
    startEditing,
    cancelEditing,
    pendingKey,
    rowErrors,
    submitCreate,
    submitUpdate,
    submitDelete,
  };
}
