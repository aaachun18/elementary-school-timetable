import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";

// The token check happens synchronously during render, not in a useEffect
// -- so an unauthenticated visit to a protected route renders straight to
// <Navigate>, never the protected content first. Wrap any page that
// requires login with this instead of duplicating the check per page.
export default function ProtectedRoute({
  children,
}: {
  children: ReactElement;
}): ReactElement {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
