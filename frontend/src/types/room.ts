// Mirrors backend/app/schemas/room.py in full. Task 98: rooms have no type
// (and no capacity) any more -- a requirement names the one special room it
// needs (ClassSubjectRequirement.required_room_id).

export interface Room {
  id: number;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoomCreate {
  name: string;
}

export interface RoomUpdate {
  name?: string;
  is_active?: boolean;
}
