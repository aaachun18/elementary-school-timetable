// Mirrors backend/app/schemas/class_.py -- every field on
// ClassRead/ClassCreate/ClassUpdate, not just what the read-only Phase A
// table renders (see docs/FRONTEND_REQUIREMENTS.md Task 27 appendix).

export interface Class {
  id: number;
  grade_id: number;
  name: string;
  is_active: boolean;
  homeroom_room_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ClassCreate {
  grade_id: number;
  name: string;
  homeroom_room_id?: number | null;
}

export interface ClassUpdate {
  grade_id?: number;
  name?: string;
  is_active?: boolean;
  homeroom_room_id?: number | null;
}
