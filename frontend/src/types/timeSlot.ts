// Mirrors backend/app/schemas/time_slot.py in full. A school's grid is
// built with the school (國小 periods 0-9, 國中/高中 0-10, Monday-Friday)
// and fixed: only label (`| null`, e.g. "早自習"/"午休") and whether the
// slot is schedulable change.

export interface TimeSlot {
  id: number;
  weekday: number;
  period: number;
  is_teaching_period: boolean;
  label: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimeSlotUpdate {
  is_teaching_period?: boolean;
  label?: string | null;
}

export interface TimeSlotBulkUpdateItem extends TimeSlotUpdate {
  id: number;
}
