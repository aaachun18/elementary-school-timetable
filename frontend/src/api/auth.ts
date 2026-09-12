import { apiClient } from "./client";
import type { LoginResponse } from "../types/auth";

// POST /api/v1/auth/login expects OAuth2PasswordRequestForm -- a
// application/x-www-form-urlencoded body with `username`/`password` fields,
// not JSON (see backend/app/routers/auth.py).
export async function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const response = await apiClient.post<LoginResponse>(
    "/api/v1/auth/login",
    body,
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
  );
  return response.data;
}
