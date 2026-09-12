import type { ReactElement } from "react";
import { list as listRequirements } from "../api/classSubjectRequirements";
import { list as listClasses } from "../api/classes";
import { list as listSubjects } from "../api/subjects";
import { list as listTeachers } from "../api/teachers";
import { useResource } from "../hooks/useResource";

export default function RequirementsOverview(): ReactElement {
  const requirements = useResource(() => listRequirements(), []);
  const classes = useResource(() => listClasses(), []);
  const subjects = useResource(() => listSubjects(), []);
  const teachers = useResource(() => listTeachers(), []);

  const isLoading =
    requirements.isLoading ||
    classes.isLoading ||
    subjects.isLoading ||
    teachers.isLoading;
  // Whichever of the four calls fails first is shown -- good enough here
  // since all four are needed together to render a single, meaningful row;
  // there's no partial-table fallback worth building for Phase A.
  const errorMessage =
    requirements.errorMessage ??
    classes.errorMessage ??
    subjects.errorMessage ??
    teachers.errorMessage;

  if (isLoading) {
    return <p>載入中…</p>;
  }
  if (errorMessage !== null) {
    return <p role="alert">{errorMessage}</p>;
  }
  if (requirements.data === null) {
    // Not reachable in practice -- useResource only leaves both isLoading
    // and errorMessage falsy after a successful fetch, which always sets
    // data -- but TypeScript can't see that invariant, so this is a real
    // (if defensive) fallback rather than a type-cast to satisfy it.
    return <p role="alert">資料載入異常,請重新整理頁面。</p>;
  }

  // id -> name lookups, built once the supporting lists are in -- this is
  // the "join" the backend deliberately doesn't do for us (see
  // docs/FRONTEND_REQUIREMENTS.md 第 4 章: reuse the existing list() calls
  // instead of asking the backend for a new merged endpoint).
  const classNameById = new Map(
    (classes.data ?? []).map((classItem) => [classItem.id, classItem.name]),
  );
  const subjectNameById = new Map(
    (subjects.data ?? []).map((subject) => [subject.id, subject.name]),
  );
  const teacherNameById = new Map(
    (teachers.data ?? []).map((teacher) => [teacher.id, teacher.name]),
  );

  return (
    <div>
      <h1>排課需求總覽</h1>
      <table>
        <thead>
          <tr>
            <th>班級</th>
            <th>科目</th>
            <th>每週節數</th>
            <th>指定教師</th>
            <th>指定教室類型</th>
            <th>連續節數限制</th>
          </tr>
        </thead>
        <tbody>
          {requirements.data.map((requirement) => (
            <tr key={requirement.id}>
              <td>
                {classNameById.get(requirement.class_id) ??
                  `班級 ID ${requirement.class_id}`}
              </td>
              <td>
                {subjectNameById.get(requirement.subject_id) ??
                  `科目 ID ${requirement.subject_id}`}
              </td>
              <td>{requirement.weekly_periods}</td>
              <td>
                {requirement.required_teacher_id === null
                  ? "未指定(由系統自動分配)"
                  : (teacherNameById.get(requirement.required_teacher_id) ??
                    `教師 ID ${requirement.required_teacher_id}`)}
              </td>
              <td>{requirement.required_room_type ?? "原班教室"}</td>
              <td>{requirement.consecutive_limit ?? "未設定"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
