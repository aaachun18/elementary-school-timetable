// Mirrors backend/app/schemas/room.py in full. Task 98: rooms have no type
// any more -- a requirement names the one special room it needs
// (ClassSubjectRequirement.required_room_id). max_classes: how many classes
// may use the room at the same time (1-10; a 共同排課 lesson counts once).

export interface Room {
  id: number;
  name: string;
  is_active: boolean;
  max_classes: number;
  created_at: string;
  updated_at: string;
}

export interface RoomCreate {
  name: string;
  max_classes: number;
}

export interface RoomUpdate {
  name?: string;
  is_active?: boolean;
  max_classes?: number;
}

// The 「一次最多幾個班級同時使用」 choices.
export const ROOM_MAX_CLASSES_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;
