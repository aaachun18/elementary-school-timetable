// Mirrors backend/app/schemas/room.py in full. capacity is `| null` --
// Task 14 made Room.capacity optional on the backend, so the frontend type
// must allow null too, not just make the field itself optional.

export interface Room {
  id: number;
  name: string;
  room_type: string;
  capacity: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoomCreate {
  name: string;
  room_type: string;
  capacity?: number | null;
}

export interface RoomUpdate {
  name?: string;
  room_type?: string;
  capacity?: number | null;
  is_active?: boolean;
}
