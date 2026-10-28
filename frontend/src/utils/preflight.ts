// 排課前檢查 (wizard step 6): the problems that would stop 自動排課, one
// line each with where to fix it. Links only ever go back to an earlier
// wizard step or to 學校資料 -- never forward, never elsewhere (the wizard
// only moves on through its own buttons). Pure, no React (preflight.test.ts).

import { resolveViolationPageTarget } from "../constants/violationPageMapping";
import {
  getViolationSentence,
  resolveClassName,
  resolveRoomName,
  resolveSubjectName,
  resolveTeacherName,
  type NameLookups,
} from "./failureDiagnostics";
import type { ConstraintViolationDetail, PreflightResult } from "../types/scheduler";

export interface PreflightLink {
  label: string;
  path: string;
}

export interface PreflightIssue {
  text: string;
  link: PreflightLink | null;
}

export const PREFLIGHT_BLOCKED_REASON = "請先處理上列問題";

const REQUIREMENTS_STEP: PreflightLink = { label: "回到科目需求", path: "/wizard?step=requirements" };

function requirementPrefix(violation: ConstraintViolationDetail, lookups: NameLookups): string {
  const requirement =
    violation.class_subject_requirement_id === null
      ? undefined
      : lookups.requirementById.get(violation.class_subject_requirement_id);
  const classId = requirement?.class_id ?? violation.class_id;
  const subjectId = requirement?.subject_id ?? violation.subject_id;
  return [resolveClassName(classId, lookups), resolveSubjectName(subjectId, lookups)]
    .filter((part) => part !== "")
    .join(" ");
}

// A 停用 item a requirement names: which one, said plainly.
function inactiveText(violation: ConstraintViolationDetail, lookups: NameLookups): string {
  const prefix = requirementPrefix(violation, lookups);
  if (violation.teacher_id !== null) {
    return `${prefix}：指定老師「${resolveTeacherName(violation.teacher_id, lookups)}」已停用`;
  }
  if (violation.room_id !== null) {
    return `${prefix}：特殊教室「${resolveRoomName(violation.room_id, lookups)}」已停用`;
  }
  if (violation.subject_id !== null) {
    return `${prefix}：科目已停用`;
  }
  return `${prefix}：班級已停用`;
}

// Only a link back to an earlier wizard step (the steps before 6) or to
// 學校資料 is kept.
function allowedLink(link: PreflightLink): PreflightLink | null {
  return link.path.startsWith("/wizard?step=") || link.path.startsWith("/data") ? link : null;
}

function violationIssue(violation: ConstraintViolationDetail, lookups: NameLookups): PreflightIssue {
  if (violation.type === "STATIC_INACTIVE_ENTITY_CONFLICT") {
    return { text: inactiveText(violation, lookups), link: REQUIREMENTS_STEP };
  }
  if (violation.type === "INACTIVE_CLASS_IN_RECORD") {
    return {
      text: `${resolveClassName(violation.class_id, lookups)}已停用，回到科目需求後會自動移出這次排課`,
      link: REQUIREMENTS_STEP,
    };
  }
  const target = resolveViolationPageTarget(violation, lookups);
  return {
    text: getViolationSentence(violation, lookups),
    link: target.kind === "link" ? allowedLink({ label: target.label, path: target.path }) : null,
  };
}

// Every violation, then every lesson failure's reasons; the same line only
// once (several lessons often fail for one reason).
export function preflightIssues(result: PreflightResult, lookups: NameLookups): PreflightIssue[] {
  const issues = [
    ...result.violations.map((violation) => violationIssue(violation, lookups)),
    ...result.lesson_failures.flatMap((failure) =>
      failure.reasons.map((reason) => violationIssue(reason, lookups)),
    ),
  ];
  const seen = new Set<string>();
  return issues.filter((issue) => {
    if (seen.has(issue.text)) {
      return false;
    }
    seen.add(issue.text);
    return true;
  });
}
