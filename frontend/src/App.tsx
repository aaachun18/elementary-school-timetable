import type { ReactElement } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import DataBrowser from "./pages/DataBrowser";
import Home from "./pages/Home";
import Login from "./pages/Login";
import RequirementsOverview from "./pages/RequirementsOverview";

export default function App(): ReactElement {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        {/* ProtectedRoute + Layout combined as one parent layout route --
            every nested route below renders inside Layout's <Outlet />,
            already behind the same login check and sharing the same nav
            bar / logout button, with no per-page duplication. */}
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Home />} />
          <Route path="/data" element={<DataBrowser />} />
          <Route path="/requirements" element={<RequirementsOverview />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
