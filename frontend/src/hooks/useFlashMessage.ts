import { useCallback, useEffect, useRef, useState } from "react";

// A short-lived, self-dismissing success message ("toast" without a toast
// library -- Task 32.6 explicitly rules out adding one). Used for actions
// whose only feedback would otherwise be a silent state change elsewhere
// on the page (e.g. a dropdown's selected value quietly updating) -- the
// action itself succeeded, but nothing about the resulting screen change
// is obviously "new" without this.
export function useFlashMessage(durationMs = 3000): {
  message: string | null;
  showFlash: (text: string) => void;
} {
  const [message, setMessage] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const showFlash = useCallback(
    (text: string) => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      setMessage(text);
      timeoutRef.current = window.setTimeout(() => {
        setMessage(null);
        timeoutRef.current = null;
      }, durationMs);
    },
    [durationMs],
  );

  return { message, showFlash };
}
