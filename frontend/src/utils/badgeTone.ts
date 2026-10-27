import { BADGE_INFO, BADGE_MANUAL, BADGE_NEUTRAL, BADGE_SUCCESS, BADGE_WARNING } from "../styles/ui";

// Task 98: the five StatusBadge tones (light background + dark text, from
// the badge tokens in index.css). What a tone MEANS is decided where the
// badge is used (e.g. recordStatusTone() for 排課紀錄); this only maps a
// tone to its classes.
export type BadgeTone = "info" | "manual" | "warning" | "success" | "neutral";

const BADGE_CLASSES: Record<BadgeTone, string> = {
  info: BADGE_INFO,
  manual: BADGE_MANUAL,
  warning: BADGE_WARNING,
  success: BADGE_SUCCESS,
  neutral: BADGE_NEUTRAL,
};

export function badgeClass(tone: BadgeTone): string {
  return BADGE_CLASSES[tone];
}
