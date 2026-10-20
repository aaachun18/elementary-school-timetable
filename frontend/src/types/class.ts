// Mirrors backend/app/schemas/class_.py. A class is only created and
// deleted: its name is one of classNameOptions(grade level, name_style)
// (utils/schoolStructure.ts).

import type { ClassNameStyle } from "../utils/schoolStructure";

export interface Class {
  id: number;
  grade_id: number;
  name_style: ClassNameStyle;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ClassCreate {
  grade_id: number;
  name_style: ClassNameStyle;
  name: string;
}
