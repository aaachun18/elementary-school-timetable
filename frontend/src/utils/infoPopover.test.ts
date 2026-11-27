import { describe, expect, it } from "vitest";
import { INFO_POPOVER_MAX_WIDTH_PX, nextInfoPopoverState, placeInfoPopover } from "./infoPopover";

describe("nextInfoPopoverState", () => {
  it("opens and closes with a click", () => {
    expect(nextInfoPopoverState("closed", "toggle")).toBe("pinned");
    expect(nextInfoPopoverState("pinned", "toggle")).toBe("closed");
  });

  it("previews on mouse hover and hides when the mouse leaves", () => {
    expect(nextInfoPopoverState("closed", "hoverStart")).toBe("hover");
    expect(nextInfoPopoverState("hover", "hoverEnd")).toBe("closed");
  });

  it("keeps a hover preview open when it is clicked", () => {
    expect(nextInfoPopoverState("hover", "toggle")).toBe("pinned");
  });

  it("does not close a clicked-open popover when the mouse leaves", () => {
    expect(nextInfoPopoverState("pinned", "hoverEnd")).toBe("pinned");
    expect(nextInfoPopoverState("pinned", "hoverStart")).toBe("pinned");
  });

  it("closes on Esc / a click outside from any state", () => {
    expect(nextInfoPopoverState("pinned", "dismiss")).toBe("closed");
    expect(nextInfoPopoverState("hover", "dismiss")).toBe("closed");
    expect(nextInfoPopoverState("closed", "dismiss")).toBe("closed");
  });
});

describe("placeInfoPopover", () => {
  const desktop = { width: 1440, height: 900 };

  it("sits below the button, left-aligned, at most 360px wide", () => {
    expect(placeInfoPopover({ left: 200, bottom: 100 }, desktop)).toEqual({
      top: 106,
      left: 200,
      width: INFO_POPOVER_MAX_WIDTH_PX,
      maxHeight: 900 - 106 - 8,
    });
  });

  it("moves left instead of leaving the viewport", () => {
    const placement = placeInfoPopover({ left: 1400, bottom: 100 }, desktop);
    expect(placement.left + placement.width).toBe(1440 - 8);
  });

  it("is never wider than a narrow viewport", () => {
    const placement = placeInfoPopover({ left: 10, bottom: 50 }, { width: 320, height: 600 });
    expect(placement.width).toBe(304);
    expect(placement.left).toBe(8);
  });

  it("keeps a usable height near the bottom of the screen", () => {
    expect(placeInfoPopover({ left: 10, bottom: 880 }, desktop).maxHeight).toBe(120);
  });
});
