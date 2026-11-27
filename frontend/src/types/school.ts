// Mirrors backend/app/schemas/school.py in full. SchoolCreate deliberately
// has no is_active field (a new School is always created active -- see
// Task 7/8's decision, reused here by Task 42's "新增時固定為啟用" rule):
// there is no way to pass is_active=false through POST at all, so the
// create form never offers that field; only SchoolUpdate allows it.
// school_type (國小 / 國中 / 高中) is chosen on create only: the grades and
// time slots built from it can't follow a change.

import type { SchoolType } from "../utils/schoolStructure";

export interface School {
  id: number;
  name: string;
  is_active: boolean;
  school_type: SchoolType;
  created_at: string;
  updated_at: string;
}

export interface SchoolCreate {
  name: string;
  school_type: SchoolType;
}

export interface SchoolUpdate {
  name?: string;
  is_active?: boolean;
}
