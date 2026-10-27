import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { InfoIcon } from "./icons";
import {
  nextInfoPopoverState,
  placeInfoPopover,
  type InfoPopoverEvent,
  type InfoPopoverState,
  type PopoverPlacement,
} from "../utils/infoPopover";
import { ICON_BUTTON, INFO_POPOVER_PANEL } from "../styles/ui";

// How long the mouse may cross the gap between the button and the panel
// before a hover preview closes.
const HOVER_CLOSE_DELAY_MS = 150;

// Task 98: the (i) button next to a title. A click / tap / Enter opens the
// explanation (aria-expanded), a resting mouse previews it; Esc closes it
// and puts focus back on the button, a click outside or focus moving away
// closes it too. The panel is position: fixed (a table's scroll box never
// clips it), at most 360px wide. Put it next to a heading, not inside a
// <p>: the panel is a <div>.
export default function InfoPopover({
  label,
  children,
}: {
  // The button's accessible name and title, e.g. 「教師設定的說明」.
  label: string;
  children: ReactNode;
}): ReactElement {
  const panelId = useId();
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const hoverTimerRef = useRef<number | null>(null);
  const [state, setState] = useState<InfoPopoverState>("closed");
  const [placement, setPlacement] = useState<PopoverPlacement | null>(null);
  const isOpen = state !== "closed";

  const updatePlacement = useCallback((): void => {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (rect !== undefined) {
      setPlacement(
        placeInfoPopover({ left: rect.left, bottom: rect.bottom }, { width: window.innerWidth, height: window.innerHeight }),
      );
    }
  }, []);

  const send = useCallback(
    (event: InfoPopoverEvent): void => {
      if (hoverTimerRef.current !== null) {
        window.clearTimeout(hoverTimerRef.current);
        hoverTimerRef.current = null;
      }
      // Placed together with opening, so the panel never shows at 0,0.
      if (event === "toggle" || event === "hoverStart") {
        updatePlacement();
      }
      setState((previous) => nextInfoPopoverState(previous, event));
    },
    [updatePlacement],
  );

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        event.stopPropagation();
        send("dismiss");
        buttonRef.current?.focus();
      }
    }
    function handlePointerDown(event: globalThis.PointerEvent): void {
      if (event.target instanceof Node && !wrapperRef.current?.contains(event.target)) {
        send("dismiss");
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("pointerdown", handlePointerDown, true);
    window.addEventListener("resize", updatePlacement);
    window.addEventListener("scroll", updatePlacement, true);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("pointerdown", handlePointerDown, true);
      window.removeEventListener("resize", updatePlacement);
      window.removeEventListener("scroll", updatePlacement, true);
    };
  }, [isOpen, send, updatePlacement]);

  useEffect(
    () => () => {
      if (hoverTimerRef.current !== null) {
        window.clearTimeout(hoverTimerRef.current);
      }
    },
    [],
  );

  // Only a real mouse previews on hover: a tap on a touch screen also
  // fires pointerenter, and must simply toggle like a click.
  function handlePointerEnter(event: PointerEvent): void {
    if (event.pointerType === "mouse") {
      send("hoverStart");
    }
  }

  function handlePointerLeave(event: PointerEvent): void {
    if (event.pointerType !== "mouse") {
      return;
    }
    hoverTimerRef.current = window.setTimeout(() => {
      hoverTimerRef.current = null;
      setState((previous) => nextInfoPopoverState(previous, "hoverEnd"));
    }, HOVER_CLOSE_DELAY_MS);
  }

  return (
    <span
      ref={wrapperRef}
      className="inline-flex align-middle"
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
      onBlur={(event) => {
        if (event.relatedTarget !== null && !event.currentTarget.contains(event.relatedTarget)) {
          send("dismiss");
        }
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        title={label}
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
        onClick={() => send("toggle")}
        className={ICON_BUTTON}
      >
        <InfoIcon />
      </button>
      {isOpen && placement !== null && (
        <div
          id={panelId}
          style={{ top: placement.top, left: placement.left, width: placement.width, maxHeight: placement.maxHeight }}
          className={INFO_POPOVER_PANEL}
        >
          {children}
        </div>
      )}
    </span>
  );
}
