import { useEffect, useState } from "react";
import { extractApiErrorMessage } from "../constants/errorMessages";

// One item's add()/remove() functions against a semantic sub-resource
// endpoint (e.g. POST/DELETE /teachers/{id}/subjects) -- NOT a full
// CrudApi (see useCrudList.ts): there is no update(), since "membership
// in this collection" is the only thing that ever changes here, never a
// field on the item itself.
export interface MembershipApi<T> {
  add: (itemId: number) => Promise<T>;
  remove: (itemId: number) => Promise<void>;
}

// Which item a piece of per-item state belongs to -- "new" for the
// add-control's own pending/error state (which has no itemId of its own
// until it succeeds), or an existing item's id.
export type MembershipKey = number | "new";

export interface MembershipListController<T> {
  items: T[];
  pendingKey: MembershipKey | null;
  rowErrors: Map<MembershipKey, string>;
  // Returns whether the add succeeded, so the caller can reset its own
  // "currently selected option" state only on success (and leave it alone
  // on failure, so the user can see what they picked and retry/adjust).
  submitAdd: (itemId: number) => Promise<boolean>;
  submitRemove: (itemId: number) => Promise<void>;
}

// Task 46's shared add/remove mechanics for a "membership in a child
// collection" sub-resource -- TeacherDetail's 任教資格/不可用時段 sections
// are the first (and, per Task 5's existing decision, deliberately only)
// two call sites: these are semantic sub-resources of Teacher, not
// standalone CRUD tables, so this is NOT useCrudList (no inline edit, no
// standard Create/Update body shape, no "new row" -- just "is this item
// currently in the collection or not").
//
// `sourceItems` is the latest fetch from useResource(); kept as a local
// copy (seeded from it, then updated directly on each successful add/
// remove) so the screen reflects a change immediately without waiting on,
// or forcing, a refetch -- same reasoning as useCrudList's own `items`.
export function useMembershipList<T extends { id: number }>(
  sourceItems: T[] | null,
  api: MembershipApi<T>,
): MembershipListController<T> {
  const [items, setItems] = useState<T[]>([]);
  useEffect(() => {
    if (sourceItems !== null) {
      setItems(sourceItems);
    }
  }, [sourceItems]);

  const [pendingKey, setPendingKey] = useState<MembershipKey | null>(null);
  const [rowErrors, setRowErrors] = useState<Map<MembershipKey, string>>(new Map());

  function clearError(key: MembershipKey): void {
    setRowErrors((previous) => {
      if (!previous.has(key)) {
        return previous;
      }
      const next = new Map(previous);
      next.delete(key);
      return next;
    });
  }

  async function submitAdd(itemId: number): Promise<boolean> {
    setPendingKey("new");
    clearError("new");
    try {
      const added = await api.add(itemId);
      setItems((previous) => [...previous, added]);
      return true;
    } catch (error) {
      setRowErrors((previous) => new Map(previous).set("new", extractApiErrorMessage(error)));
      return false;
    } finally {
      setPendingKey(null);
    }
  }

  async function submitRemove(itemId: number): Promise<void> {
    setPendingKey(itemId);
    clearError(itemId);
    try {
      await api.remove(itemId);
      setItems((previous) => previous.filter((item) => item.id !== itemId));
    } catch (error) {
      setRowErrors((previous) => new Map(previous).set(itemId, extractApiErrorMessage(error)));
    } finally {
      setPendingKey(null);
    }
  }

  return { items, pendingKey, rowErrors, submitAdd, submitRemove };
}
