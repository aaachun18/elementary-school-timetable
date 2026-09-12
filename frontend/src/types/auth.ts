// Mirrors backend/app/schemas/auth.py::Token, returned by POST /api/v1/auth/login.
export interface LoginResponse {
  access_token: string;
  token_type: string;
}
