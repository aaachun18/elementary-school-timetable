import { useCallback, useEffect, useState, type DependencyList } from "react";
import axios from "axios";
import { extractApiErrorMessage } from "../constants/errorMessages";

interface UseResourceResult<T> {
  data: T | null;
  isLoading: boolean;
  errorMessage: string | null;
  // Task 67: re-runs `fetcher` with the same deps. The previous `data` stays
  // in place while the reload is in flight (isLoading goes back to true),
  // so a page doesn't flash empty between the two results.
  reload: () => void;
}

// Shared loading/error/data bookkeeping for the read-only API calls
// DataBrowser.tsx's five tabs (and each teacher's expanded detail) all make
// -- five call sites doing this by hand would be five copies of the same
// try/catch/translate boilerplate already established in Login.tsx.
// `deps` controls when `fetcher` re-runs, same idea as useEffect's own
// dependency array; `fetcher` itself is deliberately NOT part of that
// array (every call site here is a fresh arrow function each render) --
// callers are expected to put everything the fetcher actually depends on
// (e.g. a teacherId) into `deps` themselves.
export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: DependencyList,
): UseResourceResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // Bumped by reload(); part of the effect's dependencies alongside the
  // caller's own `deps`, so a reload is just "deps changed" once more.
  const [reloadCount, setReloadCount] = useState(0);
  const reload = useCallback(() => {
    setReloadCount((previous) => previous + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setErrorMessage(null);
    fetcher()
      .then((result) => {
        if (!cancelled) {
          setData(result);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        // Task 60: any error WITH a response goes through
        // extractApiErrorMessage() (string detail -> translated, 422 array
        // -> Chinese, anything else -> "伺服器回應異常..."), the same rules
        // as every other call site. Only "no response at all" keeps this
        // hook's own loading-specific connectivity message.
        if (axios.isAxiosError(error) && error.response !== undefined) {
          setErrorMessage(extractApiErrorMessage(error));
        } else {
          setErrorMessage("無法載入資料，請確認後端服務是否啟動。");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadCount]);

  return { data, isLoading, errorMessage, reload };
}
