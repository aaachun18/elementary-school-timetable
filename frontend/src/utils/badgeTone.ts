import { BADGE_DANGER, BADGE_INFO, BADGE_MANUAL, BADGE_NEUTRAL, BADGE_SUCCESS, BADGE_WARNING } from "../styles/ui";

// Task 98: the StatusBadge tones (light background + dark text, from
// the badge tokens in index.css). What a tone MEANS is decided where the
// badge is used (e.g. recordStatusTone() for 排課紀錄); this only maps a
// tone to its classes.
// Task 99 added danger (「N 個錯誤」).
export type BadgeTone = "info" | "manual" | "warning" | "success" | "neutral" | "danger";

const BADGE_CLASSES: Record<BadgeTone, string> = {
  info: BADGE_INFO,
  manual: BADGE_MANUAL,
  warning: BADGE_WARNING,
  success: BADGE_SUCCESS,
  neutral: BADGE_NEUTRAL,
  danger: BADGE_DANGER,
};

export function badgeClass(tone: BadgeTone): string {
  return BADGE_CLASSES[tone];
}
