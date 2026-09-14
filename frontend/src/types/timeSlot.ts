// Mirrors backend/app/schemas/time_slot.py in full. start_time/end_time are
// `| null` -- Task 15 made them optional on the backend. Backend `time`
// values serialize as "HH:MM:SS" strings over JSON, so they're typed as
// `string | null` here, not `Date`. label (`| null`, Task 35) is a
// human-readable name for the slot -- e.g. "早自習"/"午餐/午休" for
// non-teaching periods.

export interface TimeSlot {
  id: number;
  weekday: number;
  period: number;
  start_time: string | null;
  end_time: string | null;
  is_teaching_period: boolean;
  label: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimeSlotCreate {
  weekday: number;
  period: number;
  start_time?: string | null;
  end_time?: string | null;
  is_teaching_period?: boolean;
  label?: string | null;
}

export interface TimeSlotUpdate {
  weekday?: number;
  period?: number;
  start_time?: string | null;
  end_time?: string | null;
  is_teaching_period?: boolean;
  label?: string | null;
}
