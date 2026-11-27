import { list as listTeachers } from "../api/teachers";
import { list as listUsers } from "../api/users";
import { isCurrentUserManager } from "../utils/auth";
import { formatTeacherName, sameNameAccounts, usernamesByTeacherId, type NamedTeacher } from "../utils/teacherName";
import { useResource } from "./useResource";

// Every teacher of the school (one school: small, fetched whole).
const ALL = 1000;

// Task 99 (item 13): the account names of the school's shared-name
// teachers (utils/teacherName.ts). The accounts come from 帳號管理's list
// (GET /users), which only a 系統管理員 / 教學組長 may read -- for anyone
// else (a 一般老師) this is empty and names show as they are -- by the
// user's decision a 一般老師 never sees the accounts. GET /users
// is only asked when some name actually is shared.
export async function loadSameNameAccounts(teachers: readonly NamedTeacher[]): Promise<Map<number, string>> {
  const names = teachers.map((teacher) => teacher.name);
  const hasSharedName = new Set(names).size < names.length;
  if (!hasSharedName || !isCurrentUserManager()) {
    return new Map();
  }
  return sameNameAccounts(teachers, usernamesByTeacherId(await listUsers()));
}

export interface TeacherNames {
  // teacher id -> its account, for the shared-name teachers only.
  accounts: ReadonlyMap<number, string>;
  // 「王老師(teacher11)」 for a shared name, else the name given.
  label: (teacherId: number, name: string) => string;
  // Loading the accounts failed: names show without them meanwhile.
  errorMessage: string | null;
}

// For a screen whose own lists carry only id + name (教師設定, 科目需求,
// 排課設定...): reads the school's teachers and their accounts once.
export function useTeacherNames(): TeacherNames {
  const resource = useResource(
    () => listTeachers(0, ALL).then((teachers) => loadSameNameAccounts(teachers)),
    [],
  );
  const accounts = resource.data ?? new Map<number, string>();
  return {
    accounts,
    label: (teacherId, name) => formatTeacherName(name, accounts.get(teacherId)),
    errorMessage: resource.errorMessage,
  };
}
