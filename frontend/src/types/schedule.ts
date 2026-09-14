// Mirrors backend/app/schemas/schedule.py in full.

export interface Schedule {
  id: number;
  schedule_version_id: number;
  lesson_id: number;
  teacher_id: number | null;
  time_slot_id: number | null;
  room_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreate {
  schedule_version_id: number;
  lesson_id: number;
  teacher_id?: number | null;
  time_slot_id?: number | null;
  room_id?: number | null;
}

export interface ScheduleUpdate {
  schedule_version_id?: number;
  lesson_id?: number;
  teacher_id?: number | null;
  time_slot_id?: number | null;
  room_id?: number | null;
}
