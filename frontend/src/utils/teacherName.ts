// Task 99 (item 13): how a teacher's name is shown everywhere. When two or
// more teachers of the school share a name, each of them gets its account
// name after it -- 「王老師(teacher11)」, half-width parentheses, no space;
// a name no one else has stays as it is. Pure, no React, no API
// (teacherName.test.ts); hooks/useTeacherAccounts.ts reads the accounts.
//
// "Shared" is judged over every teacher of the school the screen can read
// (GET /teachers, 停用 ones included) -- the same rule the backend uses for
// 同名同姓 (services/user.py _shared_teacher_names): a 停用 teacher still
// appears on older timetables, so the two must stay apart there too.

export interface NamedTeacher {
  id: number;
  name: string;
}

// The account names of the teachers whose name another teacher also has,
// by teacher id. A shared-name teacher without a known account (e.g. the
// viewer may not read the accounts) is simply left out.
export function sameNameAccounts(
  teachers: readonly NamedTeacher[],
  usernameByTeacherId: ReadonlyMap<number, string>,
): Map<number, string> {
  const countByName = new Map<string, number>();
  for (const teacher of teachers) {
    countByName.set(teacher.name, (countByName.get(teacher.name) ?? 0) + 1);
  }
  const accounts = new Map<number, string>();
  for (const teacher of teachers) {
    const username = usernameByTeacherId.get(teacher.id);
    if ((countByName.get(teacher.name) ?? 0) > 1 && username !== undefined) {
      accounts.set(teacher.id, username);
    }
  }
  return accounts;
}

// 「王老師」 + 「teacher11」 -> 「王老師(teacher11)」; no account -> the name.
export function formatTeacherName(name: string, account: string | null | undefined): string {
  return account === null || account === undefined ? name : `${name}(${account})`;
}

// The one way to show a teacher's name on one line.
export function teacherDisplayName(
  teacher: NamedTeacher,
  allTeachers: readonly NamedTeacher[],
  usernameByTeacherId: ReadonlyMap<number, string>,
): string {
  return formatTeacherName(teacher.name, sameNameAccounts(allTeachers, usernameByTeacherId).get(teacher.id));
}

// The timetable grid puts the account on a second, smaller line: splits a
// formatTeacherName() label (optionally followed by the 合併節 「*」) back
// into its parts. Only an account in `knownAccounts` is split off, so a
// name that itself ends in parentheses is never cut.
export function splitTeacherLabel(
  label: string,
  knownAccounts: ReadonlySet<string>,
): { name: string; account: string | null; mark: string } {
  const match = /^(.+)\(([^()]+)\)(\*?)$/.exec(label);
  if (match === null || !knownAccounts.has(match[2])) {
    const mark = label.endsWith("*") ? "*" : "";
    return { name: mark === "" ? label : label.slice(0, -1), account: null, mark };
  }
  return { name: match[1], account: match[2], mark: match[3] };
}

// teacher id -> account name, from 帳號管理's list (GET /users).
export function usernamesByTeacherId(
  users: readonly { teacher_id: number | null; username: string }[],
): Map<number, string> {
  const result = new Map<number, string>();
  for (const user of users) {
    if (user.teacher_id !== null) {
      result.set(user.teacher_id, user.username);
    }
  }
  return result;
}
