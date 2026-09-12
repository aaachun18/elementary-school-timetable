import { useState, type ChangeEvent, type FormEvent, type ReactElement } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { login } from "../api/auth";
import { TOKEN_KEY } from "../api/client";
import { translateErrorMessage } from "../constants/errorMessages";
import type { ApiErrorResponse } from "../types/api";

// Minimal inline SVGs -- no icon library added just for two static shapes
// (see Task 29.5's explicit "smallest sufficient dependency" instruction).
function EyeIcon(): ReactElement {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function EyeOffIcon(): ReactElement {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
      <line x1="2" y1="22" x2="22" y2="2" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

export default function Login(): ReactElement {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  // Task 29.5: clearing on every keystroke (rather than only at the next
  // submit) means the stale error disappears the moment the user starts
  // correcting their input, instead of sitting there -- possibly
  // contradicting what they just typed -- until they click submit again.
  // The submit handler below also clears it at the start, as a safety net
  // for the case where a field is resubmitted completely unchanged.
  function handleUsernameChange(event: ChangeEvent<HTMLInputElement>): void {
    setUsername(event.target.value);
    setErrorMessage(null);
  }

  function handlePasswordChange(event: ChangeEvent<HTMLInputElement>): void {
    setPassword(event.target.value);
    setErrorMessage(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      const data = await login(username, password);
      sessionStorage.setItem(TOKEN_KEY, data.access_token);
      navigate("/");
    } catch (error) {
      // Password is cleared so the user can retype it; username is kept so
      // they don't have to retype that too (see docs/FRONTEND_REQUIREMENTS.md).
      setPassword("");
      if (axios.isAxiosError<ApiErrorResponse>(error) && error.response?.data?.detail) {
        // The backend's own message -- translated to Chinese (see
        // constants/errorMessages.ts), never replaced with a generic
        // "登入失敗,請重試". An unrecognized message still shows verbatim
        // (in English) rather than being dropped, per that module's
        // fallback rule.
        setErrorMessage(translateErrorMessage(error.response.data.detail));
      } else {
        setErrorMessage("無法連線到伺服器,請確認後端服務是否啟動。");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <h1>登入</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="username">帳號</label>
          <br />
          <input
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={handleUsernameChange}
            required
          />
        </div>
        <div>
          <label htmlFor="password">密碼</label>
          <br />
          <input
            id="password"
            name="password"
            type={isPasswordVisible ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            onChange={handlePasswordChange}
            required
          />
          <button
            type="button"
            onClick={() => setIsPasswordVisible((visible) => !visible)}
            aria-label={isPasswordVisible ? "隱藏密碼" : "顯示密碼"}
            aria-pressed={isPasswordVisible}
          >
            {isPasswordVisible ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        </div>
        {errorMessage !== null && <p role="alert">{errorMessage}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "登入中…" : "登入"}
        </button>
      </form>
    </div>
  );
}
