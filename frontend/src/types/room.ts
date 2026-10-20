// Mirrors backend/app/schemas/room.py in full. capacity is `| null` --
// Task 14 made Room.capacity optional on the backend, so the frontend type
// must allow null too, not just make the field itself optional. Task 98:
// rooms have no type any more -- a requirement names the one special room
// it needs (ClassSubjectRequirement.required_room_id).

export interface Room {
  id: number;
  name: string;
  capacity: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoomCreate {
  name: string;
  capacity?: number | null;
}

export interface RoomUpdate {
  name?: string;
  capacity?: number | null;
  is_active?: boolean;
}
