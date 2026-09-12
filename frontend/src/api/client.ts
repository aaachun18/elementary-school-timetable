import axios from "axios";

// sessionStorage (not localStorage): cleared when the browser tab closes --
// see docs/FRONTEND_REQUIREMENTS.md Task 27's Token 儲存 decision.
export const TOKEN_KEY = "access_token";

export const apiClient = axios.create({
  baseURL: "http://localhost:8000",
});

// Every request automatically carries the JWT, if one is stored -- no call
// site needs to remember to attach it by hand.
apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 on an AUTHENTICATED request means the stored token is
// expired/invalid -- clear it and send the user back to /login. A hard
// redirect (not react-router navigation) is used deliberately: this
// interceptor runs outside any React component, so there is no router
// context to navigate with here.
//
// Task 29.5 bug fix: this used to fire for EVERY 401, including the login
// endpoint's own 401 for a wrong password. Login.tsx calls login() through
// this same apiClient, so a failed login attempt was ALSO caught here --
// window.location.href triggered a full page reload a moment after
// Login.tsx had just set its error message state, wiping it before the
// user could read it (the "flashes and disappears" bug). The login
// endpoint's own 401 is an expected, normal outcome the page already
// handles itself; it must never be treated as "the session expired."
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginRequest = axios.isAxiosError(error)
      ? error.config?.url?.includes("/api/v1/auth/login")
      : false;
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      !isLoginRequest
    ) {
      sessionStorage.removeItem(TOKEN_KEY);
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
