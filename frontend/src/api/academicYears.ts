import { apiClient } from "./client";
import type {
  AcademicYear,
  AcademicYearCreate,
  AcademicYearUpdate,
} from "../types/academicYear";

// Not in Task 32's explicit module list -- added alongside semesters.ts to
// resolve a Semester's academic_year_id into an actual year for the
// ScheduleVersion dropdown label. See types/academicYear.ts for the full
// disclosure. Mirrors backend/app/routers/academic_year.py's 5 endpoints.

export async function list(skip = 0, limit = 100): Promise<AcademicYear[]> {
  const response = await apiClient.get<AcademicYear[]>("/api/v1/academic-years/", {
    params: { skip, limit },
  });
  return response.data;
}

export async function get(academicYearId: number): Promise<AcademicYear> {
  const response = await apiClient.get<AcademicYear>(
    `/api/v1/academic-years/${academicYearId}`,
  );
  return response.data;
}

export async function create(data: AcademicYearCreate): Promise<AcademicYear> {
  const response = await apiClient.post<AcademicYear>(
    "/api/v1/academic-years/",
    data,
  );
  return response.data;
}

export async function update(
  academicYearId: number,
  data: AcademicYearUpdate,
): Promise<AcademicYear> {
  const response = await apiClient.patch<AcademicYear>(
    `/api/v1/academic-years/${academicYearId}`,
    data,
  );
  return response.data;
}

export async function remove(academicYearId: number): Promise<void> {
  await apiClient.delete(`/api/v1/academic-years/${academicYearId}`);
}
