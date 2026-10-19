// Task 93: placing an unscheduled lesson (backend Task 92 / 92B) from the
// timetable's edit mode -- the cards of the 「未排入課程」 panel, the teacher
// and room defaults, the candidate marks, the preview's lines and the 409
// reasons. Pure functions, no React (placement.test.ts).

import {
  candidateCacheKey as moveCandidateCacheKey,
  assessCandidate,
  type CandidateMark,
  type CandidateMarks,
  type SentenceOf,
} from "./moveCandidates";
import type { TimetableViewMode } from "./violationLocate";
import type {
  EligibleTeacher,
  PlaceCandidatesResult,
  PlacementChangeDetail,
  UnscheduledLesson,
} from "../types/scheduler";

// --- Cards ---

// One card of the panel: a lesson of no block, or the still-unscheduled
// lessons of one block (連堂), placed together.
export interface PlacementCard {
  // Stable across reloads: the requirement plus the block, or the lesson.
  key: string;
  // The lesson the backend is asked about: the block's first unscheduled
  // lesson -- the backend works out the rest of the block from where it
  // sits in it.
  anchorLessonId: number;
  // Every unscheduled lesson of the card, in block order.
  lessonIds: number[];
  requirementId: number;
  classId: number;
  className: string;
  subjectId: number;
  subjectName: string;
  blockNo: number | null;
  // Lessons of the block already in the version: the rest must go next to
  // them (BLOCK_PARTIAL_MISMATCH otherwise).
  isPartialBlock: boolean;
  requiredTeacherId: number | null;
  eligibleTeachers: EligibleTeacher[];
  suggestedRoomId: number | null;
  // Task 94 (from the backend): the requirement's room type, the room
  // place-lesson uses when none is sent, and -- with a room type --
  // whether any active room has exactly that type (null without one).
  roomType: string | null;
  defaultRoomId: number | null;
  hasMatchingRoom: boolean | null;
  // 「自然 · 2 節連堂」 / 「自然 · 1 節」.
  label: string;
}

// The size of block `blockNo` in a pattern like "2+1"; null when unknown.
export function blockSize(pattern: string | null, blockNo: number | null): number | null {
  if (pattern === null || blockNo === null) {
    return null;
  }
  const sizes = pattern.split("+").map((part) => Number(part.trim()));
  const size = sizes[blockNo - 1];
  return size === undefined || !Number.isInteger(size) ? null : size;
}

export function cardLabel(subjectName: string, lessonCount: number, isBlock: boolean): string {
  return `${subjectName} · ${lessonCount} 節${isBlock && lessonCount > 1 ? "連堂" : ""}`;
}

// The backend's order (class, subject, block, place in block) is kept: a
// block's lessons become one card at the place of its first lesson.
export function buildPlacementCards(lessons: readonly UnscheduledLesson[]): PlacementCard[] {
  const cards: PlacementCard[] = [];
  const byKey = new Map<string, PlacementCard>();
  for (const lesson of lessons) {
    const key =
      lesson.block_no === null
        ? `lesson:${lesson.lesson_id}`
        : `block:${lesson.class_subject_requirement_id}:${lesson.block_no}`;
    const existing = byKey.get(key);
    if (existing !== undefined) {
      existing.lessonIds.push(lesson.lesson_id);
      continue;
    }
    const card: PlacementCard = {
      key,
      anchorLessonId: lesson.lesson_id,
      lessonIds: [lesson.lesson_id],
      requirementId: lesson.class_subject_requirement_id,
      classId: lesson.class_id,
      className: lesson.class_name,
      subjectId: lesson.subject_id,
      subjectName: lesson.subject_name,
      blockNo: lesson.block_no,
      isPartialBlock: false,
      requiredTeacherId: lesson.required_teacher_id,
      eligibleTeachers: lesson.eligible_teachers,
      suggestedRoomId: lesson.suggested_room_id,
      roomType: lesson.room_type ?? null,
      defaultRoomId: lesson.default_room_id ?? null,
      hasMatchingRoom: lesson.has_matching_room ?? null,
      label: "",
    };
    byKey.set(key, card);
    cards.push(card);
  }
  // Within a block the backend lists lessons by block_seq; the anchor is
  // the first of them.
  const seqOf = new Map(lessons.map((lesson) => [lesson.lesson_id, lesson.block_seq ?? 0]));
  const patternOf = new Map(lessons.map((lesson) => [lesson.lesson_id, lesson.lesson_pattern]));
  for (const card of cards) {
    card.lessonIds.sort((a, b) => (seqOf.get(a) ?? 0) - (seqOf.get(b) ?? 0));
    card.anchorLessonId = card.lessonIds[0];
    const size = blockSize(patternOf.get(card.anchorLessonId) ?? null, card.blockNo);
    card.isPartialBlock = size !== null && card.lessonIds.length < size;
    card.label = cardLabel(card.subjectName, card.lessonIds.length, card.blockNo !== null && (size ?? 0) > 1);
  }
  return cards;
}

export interface PlacementCardGroup {
  classId: number;
  className: string;
  cards: PlacementCard[];
}

export function groupCardsByClass(cards: readonly PlacementCard[]): PlacementCardGroup[] {
  const groups: PlacementCardGroup[] = [];
  const byClass = new Map<number, PlacementCardGroup>();
  for (const card of cards) {
    let group = byClass.get(card.classId);
    if (group === undefined) {
      group = { classId: card.classId, className: card.className, cards: [] };
      byClass.set(card.classId, group);
      groups.push(group);
    }
    group.cards.push(card);
  }
  return groups;
}

// The class view shows the chosen class's cards unless 「顯示全部班級」 is
// on; the teacher and room views always show every class.
export function cardsForView(
  cards: readonly PlacementCard[],
  viewMode: TimetableViewMode,
  targetId: number | null,
  showAllClasses: boolean,
): PlacementCard[] {
  if (viewMode !== "class" || targetId === null || showAllClasses) {
    return [...cards];
  }
  return cards.filter((card) => card.classId === targetId);
}

export function lessonCount(cards: readonly PlacementCard[]): number {
  return cards.reduce((total, card) => total + card.lessonIds.length, 0);
}

// --- Teacher and room ---

// The required teacher, else the one picked on the card, else null (the
// card can't be placed until one is picked).
export function teacherForCard(
  card: PlacementCard,
  chosenTeacherByCard: ReadonlyMap<string, number>,
): number | null {
  return card.requiredTeacherId ?? chosenTeacherByCard.get(card.key) ?? null;
}

export function needsTeacherChoice(card: PlacementCard): boolean {
  return card.requiredTeacherId === null;
}

// The room the selection bar starts from: the suggested room (the
// homeroom for 原班上課, else the first room of the type), or none.
export function roomForCard(
  card: PlacementCard,
  chosenRoomByCard: ReadonlyMap<string, number | null>,
): number | null {
  return chosenRoomByCard.has(card.key)
    ? (chosenRoomByCard.get(card.key) ?? null)
    : card.suggestedRoomId;
}

// 「不指定教室」 can only be asked for where the backend's own default is
// no room (a requirement with a room type, or a class without a homeroom):
// place-lesson treats an omitted room_id as "the default", so for 原班上課
// in a class with a homeroom it would put the homeroom there anyway.
// Task 94: decided from the backend's default_room_id (the card's
// defaultRoomId), no longer recomputed here.
export function canChooseNoRoom(card: PlacementCard): boolean {
  return card.defaultRoomId === null;
}

// Task 94: the selection bar's line when the requirement's room type
// matches no active room -- placing leaves the lesson without a room.
export function missingRoomTypeHint(card: PlacementCard): string | null {
  if (card.roomType === null || card.hasMatchingRoom !== false) {
    return null;
  }
  return `找不到類型「${card.roomType}」的教室，放入後這堂課沒有教室`;
}

// --- Candidates ---

// The cache key of one card's place-candidates: the version, the anchor
// lesson, the teacher, the room and the edit revision -- a different
// teacher or room is a different answer.
export function placeCandidateCacheKey(
  versionId: number | null,
  lessonId: number | null,
  teacherId: number | null,
  roomId: number | null,
  revision: number,
): string | null {
  if (lessonId === null || teacherId === null) {
    return null;
  }
  const base = moveCandidateCacheKey(versionId, lessonId, revision);
  return base === null ? null : `place:${base}:t${teacherId}:r${roomId ?? "none"}`;
}

// Why a lesson can't be placed in a slot (409 reason / unavailable_reason).
export const PLACE_REFUSAL_MESSAGES: Record<string, string> = {
  NON_TEACHING_SLOT: "這不是上課時段",
  BLOCK_OUT_OF_RANGE: "整組放不下：會超出當天節次或跨過午休",
  BLOCK_TARGET_OCCUPIED: "這個時段本班已經有課",
  BLOCK_PARTIAL_MISMATCH: "要放在同組已排入的那一節旁邊",
  TEACHER_REQUIRED: "請先選擇教師",
};

export function placeRefusalMessage(reason: string | null): string | null {
  return reason === null ? null : (PLACE_REFUSAL_MESSAGES[reason] ?? null);
}

// The marks of one place-candidates response, in the shape the grid
// already draws for moves (no swaps). Same ERROR-only rule as moving
// (assessCandidate); a non-teaching slot is simply not a target.
export function buildPlaceCandidateMarks(
  data: PlaceCandidatesResult,
  sentenceOf: SentenceOf,
): CandidateMarks {
  const cells = new Map<number, CandidateMark>();
  const cellRanges = new Map<number, readonly number[]>();
  for (const candidate of data.candidates) {
    if (!candidate.available || candidate.check === null) {
      const reason = candidate.unavailable_reason;
      const text = reason === "NON_TEACHING_SLOT" ? null : placeRefusalMessage(reason);
      cells.set(candidate.time_slot_id, text === null ? { status: "unavailable" } : { status: "blocked", reason: text });
      continue;
    }
    cells.set(candidate.time_slot_id, assessCandidate(data.baseline, candidate.check, sentenceOf));
    const members = candidate.block_members ?? null;
    if (members !== null && members.length > 0) {
      cellRanges.set(
        candidate.time_slot_id,
        members.map((member) => member.to_time_slot_id),
      );
    }
  }
  return { cells, swaps: new Map(), cellRanges, swapRanges: new Map() };
}

// --- Preview ---

// 「四年甲班 自然：放入 星期一第 2 節（整組 2 節一起放入）」.
export function describePlaceLine(courseName: string, firstSlot: string, changeCount: number): string {
  const block = changeCount > 1 ? `（整組 ${changeCount} 節一起放入）` : "";
  return `${courseName}：放入 ${firstSlot}${block}`;
}

// One line per new row, 「第 N 節：星期一第 2 節」, in the card's lesson
// order. Matched by lesson_id: a preview's rows have no schedule_id yet.
export function placementChangeLines(
  changes: readonly PlacementChangeDetail[],
  lessonIds: readonly number[],
  slotLabel: (timeSlotId: number) => string,
): string[] {
  const order = new Map(lessonIds.map((id, index) => [id, index]));
  return [...changes]
    .sort((a, b) => (order.get(a.lesson_id) ?? Infinity) - (order.get(b.lesson_id) ?? Infinity))
    .map((change, index) => `第 ${index + 1} 節：${slotLabel(change.new_time_slot_id)}`);
}

// The first slot the card lands in (its first lesson's), for the action
// line and the 「剛調整」 marker.
export function firstPlacedSlot(
  changes: readonly PlacementChangeDetail[],
  lessonIds: readonly number[],
): number | null {
  for (const lessonId of lessonIds) {
    const change = changes.find((item) => item.lesson_id === lessonId);
    if (change !== undefined) {
      return change.new_time_slot_id;
    }
  }
  return changes[0]?.new_time_slot_id ?? null;
}

// The reason of a place-lesson / place-candidates 409, or null for any
// other error (then the backend's own Chinese detail is shown).
export function placeRefusalReasonOf(error: unknown): string | null {
  if (typeof error !== "object" || error === null || !("response" in error)) {
    return null;
  }
  const response = (error as { response?: { status?: unknown; data?: unknown } }).response;
  if (response?.status !== 409 || typeof response.data !== "object" || response.data === null) {
    return null;
  }
  const reason = (response.data as { reason?: unknown }).reason;
  return typeof reason === "string" && reason in PLACE_REFUSAL_MESSAGES ? reason : null;
}
