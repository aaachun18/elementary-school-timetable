import { useState, type ReactElement } from "react";
import SearchableSelect from "./SearchableSelect";
import type { EnrichedSchedule } from "../hooks/useTimetableData";
import type { SearchableOption } from "../utils/searchableSelect";
import { BUTTON_SECONDARY_SM } from "../styles/ui";

const PICKER_SM = "rounded border border-blue-300 bg-white px-1 py-0.5 text-sm";

// 「更換教師」 in the selection bar of a selected, scheduled lesson: its
// current teacher, a searchable picker of the record's other teachers and
// 「預覽」. A course has one teacher, so the change is for the whole course
// (every lesson of this class's subject), and it also becomes the course's
// 指定教師 in the record's 科目需求. Mounted per lesson (keyed by the
// page), so the choice starts over for every selection.
export default function TeacherChangeControls({
  lesson,
  teachers,
  disabled,
  onPreview,
}: {
  lesson: EnrichedSchedule;
  // The teachers the course may go to (the current one left out).
  teachers: readonly SearchableOption[];
  disabled: boolean;
  onPreview: (newTeacherId: number) => void;
}): ReactElement {
  const [teacherId, setTeacherId] = useState<number | null>(null);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span>目前教師：{lesson.teacherName ?? "未指定教師"}</span>
      <span className="inline-flex items-center gap-1">
        <span>更換教師</span>
        <SearchableSelect
          value={teacherId}
          options={teachers}
          onChange={setTeacherId}
          ariaLabel="更換教師"
          placeholder="輸入姓名搜尋…"
          disabled={disabled}
          className="w-40"
          inputClassName={PICKER_SM}
        />
      </span>
      <button
        type="button"
        onClick={() => teacherId !== null && onPreview(teacherId)}
        disabled={disabled || teacherId === null}
        className={BUTTON_SECONDARY_SM}
      >
        預覽
      </button>
      {teachers.length === 0 && <span className="text-amber-800">這份排課紀錄沒有其他參與排課的老師</span>}
    </span>
  );
}
