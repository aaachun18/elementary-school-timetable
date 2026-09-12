// Mirrors backend/app/schemas/subject.py in full.

export interface Subject {
  id: number;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubjectCreate {
  name: string;
}

export interface SubjectUpdate {
  name?: string;
  is_active?: boolean;
}
