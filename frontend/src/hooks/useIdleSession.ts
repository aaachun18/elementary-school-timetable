import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { refreshToken } from "../api/auth";
import { TOKEN_KEY } from "../api/client";
import { SESSION_CHECK_INTERVAL_MS, rememberLogoutReason, sessionAction } from "../utils/session";

// Anything a person working does -- moving or clicking the mouse, typing,
// touching, scrolling, dragging a lesson.
const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "dragover", "scroll"] as const;

// Idle logout (utils/session.ts), for every logged-in page (Layout). While
// the person is active the token is renewed; after IDLE_TIMEOUT_MINUTES
// without any activity they are logged out to the login page, which says
// why. Activity is only noted in a ref -- no re-render on every move.
export function useIdleSession(): void {
  const navigate = useNavigate();
  // Set when the page starts (the effect below): opening it counts as activity.
  const lastActivityAtRef = useRef(0);
  // 0: the token in hand may be old (a reloaded page), so the first check
  // after any activity renews it.
  const lastRefreshAtRef = useRef(0);
  const isRefreshingRef = useRef(false);

  useEffect(() => {
    function noteActivity(): void {
      lastActivityAtRef.current = Date.now();
    }
    noteActivity();

    function check(): void {
      const now = Date.now();
      const action = sessionAction({
        now,
        lastActivityAt: lastActivityAtRef.current,
        lastRefreshAt: lastRefreshAtRef.current,
      });
      if (action === "logout") {
        sessionStorage.removeItem(TOKEN_KEY);
        rememberLogoutReason("idle");
        navigate("/login", { replace: true });
        return;
      }
      if (action === "refresh" && !isRefreshingRef.current) {
        isRefreshingRef.current = true;
        refreshToken()
          .then((data) => {
            sessionStorage.setItem(TOKEN_KEY, data.access_token);
            lastRefreshAtRef.current = now;
          })
          // A failed renewal is tried again on the next check; a refused
          // one (401: the token already ran out) is the API client's
          // login redirect.
          .catch(() => undefined)
          .finally(() => {
            isRefreshingRef.current = false;
          });
      }
    }

    // Coming back to the tab (e.g. after the computer slept): check at once.
    function handleVisibilityChange(): void {
      if (document.visibilityState === "visible") {
        check();
      }
    }

    for (const type of ACTIVITY_EVENTS) {
      window.addEventListener(type, noteActivity, { passive: true, capture: true });
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);
    const timer = window.setInterval(check, SESSION_CHECK_INTERVAL_MS);
    return () => {
      for (const type of ACTIVITY_EVENTS) {
        window.removeEventListener(type, noteActivity, { capture: true });
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.clearInterval(timer);
    };
  }, [navigate]);
}
