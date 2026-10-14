// Task 70: which courses (ClassSubjectRequirements) a teacher currently
// holds in one version, for the 換教師 panel. Pure functions, no React.

import type { ClassSubjectRequirement } from "../types/classSubjectRequirement";

// A course's current teacher(s) in this version: the teachers on its
// Schedule rows (what the timetable shows); if no row has a teacher, the
// requirement's own required teacher. Normally exactly one id -- several
// only if a course's lessons are split across teachers. Mirrors how the
// backend's reassign-teacher picks previous_teacher_id.
export function currentTeacherIdsOf(
  requirement: ClassSubjectRequirement,
  rowTeacherIds: number[] | undefined,
): number[] {
  if (rowTeacherIds !== undefined && rowTeacherIds.length > 0) {
    return rowTeacherIds;
  }
  return requirement.required_teacher_id === null ? [] : [requirement.required_teacher_id];
}

// Every teacher who currently holds at least one course.
export function teacherIdsWithCourses(
  requirements: ClassSubjectRequirement[],
  teacherIdsByRequirementId: Map<number, number[]>,
): Set<number> {
  const teacherIds = new Set<number>();
  for (const requirement of requirements) {
    for (const teacherId of currentTeacherIdsOf(
      requirement,
      teacherIdsByRequirementId.get(requirement.id),
    )) {
      teacherIds.add(teacherId);
    }
  }
  return teacherIds;
}

// The courses `teacherId` currently holds, plus any listed in
// `alsoInclude` (courses just handed away from them this session, kept
// visible so a chain of reassignments can continue from the same list).
// Ordered by requirement id for a stable list.
export function coursesOfTeacher(
  teacherId: number,
  requirements: ClassSubjectRequirement[],
  teacherIdsByRequirementId: Map<number, number[]>,
  alsoInclude: ReadonlySet<number>,
): ClassSubjectRequirement[] {
  return requirements
    .filter(
      (requirement) =>
        alsoInclude.has(requirement.id) ||
        currentTeacherIdsOf(requirement, teacherIdsByRequirementId.get(requirement.id)).includes(
          teacherId,
        ),
    )
    .sort((a, b) => a.id - b.id);
}
