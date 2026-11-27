// Task 98: InfoPopover's behavior as pure functions (the component only
// wires them to events).
//
// "hover" = a mouse is resting on the (i) button: a preview that goes away
// when the mouse leaves. "pinned" = opened by a click / tap / Enter: stays
// open until clicked again, Esc, or a click outside.
export type InfoPopoverState = "closed" | "hover" | "pinned";

export type InfoPopoverEvent =
  // Click / tap / Enter / Space on the (i) button.
  | "toggle"
  // A mouse (not touch) enters / leaves the button or the panel.
  | "hoverStart"
  | "hoverEnd"
  // Esc, a click outside, focus moving elsewhere.
  | "dismiss";

export function nextInfoPopoverState(state: InfoPopoverState, event: InfoPopoverEvent): InfoPopoverState {
  switch (event) {
    case "toggle":
      // A click on a hover preview keeps it open rather than closing it
      // under the pointer.
      return state === "pinned" ? "closed" : "pinned";
    case "hoverStart":
      return state === "closed" ? "hover" : state;
    case "hoverEnd":
      return state === "hover" ? "closed" : state;
    case "dismiss":
      return "closed";
  }
}

export const INFO_POPOVER_MAX_WIDTH_PX = 460;
const VIEWPORT_MARGIN_PX = 8;
const GAP_PX = 6;
const MIN_HEIGHT_PX = 120;

export interface PopoverPlacement {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
}

// The panel sits just below the button, left-aligned with it, moved left
// if it would leave the viewport, never wider than 360px or the viewport
// (minus a margin each side); a long text scrolls inside it.
export function placeInfoPopover(
  trigger: { left: number; bottom: number },
  viewport: { width: number; height: number },
): PopoverPlacement {
  const width = Math.min(INFO_POPOVER_MAX_WIDTH_PX, viewport.width - 2 * VIEWPORT_MARGIN_PX);
  const maxLeft = viewport.width - width - VIEWPORT_MARGIN_PX;
  const left = Math.max(VIEWPORT_MARGIN_PX, Math.min(trigger.left, maxLeft));
  const top = trigger.bottom + GAP_PX;
  const maxHeight = Math.max(MIN_HEIGHT_PX, viewport.height - top - VIEWPORT_MARGIN_PX);
  return { top, left, width, maxHeight };
}
