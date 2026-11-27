// Task 102: 學校資料's lists edit a row in place -- click a field's text,
// then Enter saves and Esc cancels. Pure, no React (inlineEdit.test.ts).

import { isEnterKey } from "./dialogKeyboard";

export type InlineEditKeyAction = "save" | "cancel" | null;

// What a key pressed in an editing row's field does. Only the fields
// (input / select) react, so Enter on the row's own 確認 / 取消 buttons
// keeps doing just that button. Enter is also known by its `code`: with an
// IME on (e.g. 微軟注音) `key` is "Process" (see dialogKeyboard.ts); but an
// Enter that ends a composition (typing 中文) only picks the characters.
export function inlineEditKeyAction(
  key: string,
  code: string,
  targetTag: string,
  isComposing: boolean,
): InlineEditKeyAction {
  if (targetTag !== "INPUT" && targetTag !== "SELECT") {
    return null;
  }
  if (key === "Escape") {
    return "cancel";
  }
  if (isEnterKey(key, code) && !isComposing) {
    return "save";
  }
  return null;
}
