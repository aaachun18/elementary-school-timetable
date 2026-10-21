import type { ReactElement } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import RoleRoute from "./components/RoleRoute";
import DataBrowser from "./pages/DataBrowser";
import Home from "./pages/Home";
import Login from "./pages/Login";
import RecordSettings from "./pages/RecordSettings";
import ScheduleRecords from "./pages/ScheduleRecords";
import SchedulingWizard from "./pages/SchedulingWizard";
import SchoolManagement from "./pages/SchoolManagement";
import TimetableView from "./pages/TimetableView";
import UserManagement from "./pages/UserManagement";
import type { UserRole } from "./utils/auth";

// Task 98: who may open which page (RoleRoute redirects everyone else).
const SCHOOL_MEMBERS: readonly UserRole[] = ["COORDINATOR", "TEACHER"];
const COORDINATOR_ONLY: readonly UserRole[] = ["COORDINATOR"];
const ACCOUNT_MANAGERS: readonly UserRole[] = ["ADMIN", "COORDINATOR"];
const ADMIN_ONLY: readonly UserRole[] = ["ADMIN"];

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
          {/* Task 43 / 98: each page is wrapped in RoleRoute -- a role
              hitting a URL it may not open (not just missing the nav
              link) is redirected instead of rendering. The 系統管理員
              only has 學校管理 and 帳號管理; a TEACHER only 首頁 (a
              simplified dashboard, Task 97) and 課表. */}
          <Route
            path="/"
            element={
              <RoleRoute allow={SCHOOL_MEMBERS}>
                <Home />
              </RoleRoute>
            }
          />
          <Route
            path="/data"
            element={
              <RoleRoute allow={COORDINATOR_ONLY}>
                <DataBrowser />
              </RoleRoute>
            }
          />
          {/* Task 98: 開始排課 and 排課紀錄 replace 排課需求總覽 /
              排課控制台 (their old addresses still lead to them). */}
          <Route
            path="/wizard"
            element={
              <RoleRoute allow={COORDINATOR_ONLY}>
                <SchedulingWizard />
              </RoleRoute>
            }
          />
          <Route
            path="/records"
            element={
              <RoleRoute allow={COORDINATOR_ONLY}>
                <ScheduleRecords />
              </RoleRoute>
            }
          />
          {/* v3: 檢視排課設定 of one record (its own page, back to 排課紀錄). */}
          <Route
            path="/records/:recordId/settings"
            element={
              <RoleRoute allow={COORDINATOR_ONLY}>
                <RecordSettings />
              </RoleRoute>
            }
          />
          <Route path="/requirements" element={<Navigate to="/wizard?step=requirements" replace />} />
          <Route path="/scheduler" element={<Navigate to="/records" replace />} />
          {/* Task 59 / 98: account management -- the 系統管理員 and the
              教學組長; the backend's require_manager and per-school scope
              are the real lock. */}
          <Route
            path="/users"
            element={
              <RoleRoute allow={ACCOUNT_MANAGERS}>
                <UserManagement />
              </RoleRoute>
            }
          />
          <Route
            path="/schools"
            element={
              <RoleRoute allow={ADMIN_ONLY}>
                <SchoolManagement />
              </RoleRoute>
            }
          />
          <Route
            path="/timetable"
            element={
              <RoleRoute allow={SCHOOL_MEMBERS}>
                <TimetableView />
              </RoleRoute>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
