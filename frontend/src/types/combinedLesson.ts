// Mirrors backend/app/schemas/combined_lesson.py -- 共同排課 (併班上課) of
// one 排課紀錄: lessons of several class subject requirements taught
// together, one 合併節 at a time.

export interface CombinedLessonFields {
  // The class subject requirements taught together, the one that started
  // the merge first.
  requirement_ids: number[];
  // Without a lesson pattern: how many of their lessons are merged.
  merged_count: number | null;
  // With a pattern: which whole blocks (1 = the first / longest).
  block_nos: number[] | null;
  // A school room -- or null for the 原班教室 of homeroom_class_id.
  room_id: number | null;
  homeroom_class_id: number | null;
}

export interface CombinedLessonCreate extends CombinedLessonFields {
  schedule_version_id: number;
}

export interface CombinedInstance {
  key: string;
  // Per member (requirement_ids order): its lessons of this 合併節, in
  // period order.
  member_lesson_ids: number[][];
}

export interface CombinedLesson extends CombinedLessonFields {
  id: number;
  schedule_version_id: number;
  merged_count: number;
  instances: CombinedInstance[];
  created_at: string;
  updated_at: string;
}
