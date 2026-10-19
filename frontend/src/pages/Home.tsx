import { type ReactElement, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listClasses } from "../api/classes";
import { list as listRooms } from "../api/rooms";
import {
  check as checkScheduleVersion,
  list as listScheduleVersions,
  unscheduledLessons,
} from "../api/scheduleVersions";
import { list as listSemesters } from "../api/semesters";
import { list as listSubjects } from "../api/subjects";
import { list as listTeachers } from "../api/teachers";
import { useResource } from "../hooks/useResource";
import { getCurrentUsername, isCurrentUserAdmin } from "../utils/auth";
import {
  formatDateTime,
  pickCurrentSemester,
  pickLatestDraft,
  summarizeDataHealth,
  summarizeDraftHealth,
  summarizeVersions,
  type SemesterVersions,
} from "../utils/dashboard";
import { formatSemesterLabel } from "../utils/scheduleVersionFormat";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";
import {
  BUTTON_SECONDARY_SM,
  CARD,
  DASHBOARD_CARD_TITLE,
  DASHBOARD_GRID,
  ERROR_TEXT,
  LINK_BUTTON,
  LINK_TEXT,
  LOADING_TEXT,
  MUTED_TEXT,
  NOTICE,
  PAGE,
  PAGE_TITLE,
  STAT_LABEL,
  STAT_ROW,
  STAT_VALUE,
  STAT_VALUE_PROBLEM,
  STAT_VALUE_WARNING,
  SUCCESS_TEXT,
} from "../styles/ui";

// Every list the dashboard reads is small (one school); fetched whole.
const ALL = 1000;

// One card: its title, then 「載入中…」, an error with 「重試」, or the
// content. A card that fails never takes the rest of the page with it.
function DashboardCard({
  title,
  isLoading,
  errorMessage,
  onRetry,
  children,
}: {
  title: string;
  isLoading: boolean;
  errorMessage: string | null;
  onRetry: () => void;
  children: ReactNode;
}): ReactElement {
  return (
    <section className={CARD} aria-label={title}>
      <h2 className={DASHBOARD_CARD_TITLE}>{title}</h2>
      {errorMessage !== null ? (
        <div className="flex flex-wrap items-center gap-2">
          <p role="alert" className={ERROR_TEXT}>
            無法載入：{errorMessage}
          </p>
          <button type="button" onClick={onRetry} className={BUTTON_SECONDARY_SM}>
            重試
          </button>
        </div>
      ) : isLoading ? (
        <p className={LOADING_TEXT}>載入中…</p>
      ) : (
        children
      )}
    </section>
  );
}

function Stat({ value, label, tone = "normal" }: { value: number; label: string; tone?: "normal" | "problem" | "warning" }): ReactElement {
  const valueClass = tone === "problem" ? STAT_VALUE_PROBLEM : tone === "warning" ? STAT_VALUE_WARNING : STAT_VALUE;
  return (
    <div>
      <p className={valueClass}>{value}</p>
      <p className={STAT_LABEL}>{label}</p>
    </div>
  );
}

// The semester / version lists both versions of the page start from.
function useSemesterData(): {
  isLoading: boolean;
  errorMessage: string | null;
  reload: () => void;
  semester: Semester | null;
  semesterLabel: string;
  versions: SemesterVersions;
  latestDraft: ScheduleVersion | null;
  // 「1 學年度第 2 學期」 for any semester id ("" if unknown).
  labelOf: (semesterId: number) => string;
} {
  const data = useResource(
    () => Promise.all([listSemesters(0, ALL), listAcademicYears(0, ALL), listScheduleVersions(0, ALL)]),
    [],
  );
  const [semesters, academicYears, versions] = data.data ?? [[], [], []];
  const academicYearById = new Map(academicYears.map((item) => [item.id, item.year]));
  const semesterById = new Map(semesters.map((item) => [item.id, item]));
  const semester = pickCurrentSemester(semesters, academicYearById, versions);
  const labelOf = (semesterId: number): string => {
    const found = semesterById.get(semesterId);
    return found === undefined ? "" : formatSemesterLabel(found, academicYearById);
  };
  return {
    isLoading: data.isLoading && data.data === null,
    errorMessage: data.errorMessage,
    reload: data.reload,
    semester,
    semesterLabel: semester === null ? "" : labelOf(semester.id),
    versions: summarizeVersions(versions, semester?.id ?? null),
    latestDraft: pickLatestDraft(versions),
    labelOf,
  };
}

// --- ADMIN ---

function SemesterCard({ data }: { data: ReturnType<typeof useSemesterData> }): ReactElement {
  const { semester, semesterLabel, versions } = data;
  return (
    <DashboardCard title="學期狀態" isLoading={data.isLoading} errorMessage={data.errorMessage} onRetry={data.reload}>
      {semester === null ? (
        <p className={MUTED_TEXT}>
          還沒有任何學期。
          <Link to="/data?tab=semesters" className={LINK_TEXT}>
            到基礎資料新增學年度與學期
          </Link>
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-gray-700">目前學期：{semesterLabel}</p>
          {versions.published !== null ? (
            <p className="text-sm text-gray-700">
              已發布：v{versions.published.version_number}（發布時間 {formatDateTime(versions.published.updated_at)}）
            </p>
          ) : (
            <p className={NOTICE}>這個學期還沒有已發布的課表，請到排課控制台發布一個草稿。</p>
          )}
          <div className={STAT_ROW}>
            <Stat value={versions.draftCount} label="草稿版本" />
          </div>
        </div>
      )}
    </DashboardCard>
  );
}

function DraftHealthCard({ data }: { data: ReturnType<typeof useSemesterData> }): ReactElement {
  const draft = data.latestDraft;
  const draftId = draft?.id ?? null;
  const health = useResource(
    () =>
      draftId === null
        ? Promise.resolve(null)
        : Promise.all([checkScheduleVersion(draftId), unscheduledLessons(draftId)]),
    [draftId],
  );
  const timetablePath = draftId === null ? "/timetable" : `/timetable?scheduleVersionId=${draftId}`;
  const summary =
    health.data === null ? null : summarizeDraftHealth(health.data[0].violations, health.data[1].lessons.length);
  return (
    <DashboardCard
      title="最新草稿健康度"
      isLoading={data.isLoading || (draftId !== null && health.isLoading && health.data === null)}
      errorMessage={data.errorMessage ?? health.errorMessage}
      onRetry={data.errorMessage !== null ? data.reload : health.reload}
    >
      {draft === null ? (
        <p className={MUTED_TEXT}>
          {data.semester === null ? "還沒有任何學期。" : "目前沒有任何草稿版本。"}
          <Link to="/scheduler" className={LINK_TEXT}>
            到排課控制台建立草稿
          </Link>
        </p>
      ) : summary === null ? (
        <p className={LOADING_TEXT}>載入中…</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-gray-700">
            {data.labelOf(draft.semester_id)} 草稿 v{draft.version_number}
          </p>
          <div className={STAT_ROW}>
            <Stat value={summary.errorCount} label="錯誤" tone={summary.errorCount > 0 ? "problem" : "normal"} />
            <Stat value={summary.warningCount} label="警告" tone={summary.warningCount > 0 ? "warning" : "normal"} />
            <Stat value={summary.unscheduledCount} label="未排入課程" tone={summary.unscheduledCount > 0 ? "warning" : "normal"} />
          </div>
          {summary.isHealthy ? (
            <p className={SUCCESS_TEXT}>✓ 沒有問題，可以發布</p>
          ) : (
            <div className="flex flex-wrap gap-4">
              <Link to={timetablePath} className={LINK_TEXT}>
                到課表檢視查看與修正
              </Link>
              <Link to="/scheduler" className={LINK_TEXT}>
                到排課控制台
              </Link>
            </div>
          )}
        </div>
      )}
    </DashboardCard>
  );
}

function DataHealthCard(): ReactElement {
  const data = useResource(
    () => Promise.all([listTeachers(0, ALL), listClasses(0, ALL), listSubjects(0, ALL), listRooms(0, ALL)]),
    [],
  );
  const summary =
    data.data === null
      ? null
      : summarizeDataHealth({ teachers: data.data[0], classes: data.data[1], subjects: data.data[2], rooms: data.data[3] });
  return (
    <DashboardCard
      title="資料健康度"
      isLoading={data.isLoading && data.data === null}
      errorMessage={data.errorMessage}
      onRetry={data.reload}
    >
      {summary !== null && (
        <div className="flex flex-col gap-3">
          <div className={STAT_ROW}>
            <Stat value={summary.teacherCount} label="老師" />
            <Stat value={summary.classCount} label="班級" />
            <Stat value={summary.subjectCount} label="科目" />
            <Stat value={summary.roomCount} label="教室" />
          </div>
          {summary.issues.length === 0 ? (
            <p className={SUCCESS_TEXT}>✓ 基礎資料齊全</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {summary.issues.map((issue) => (
                <li key={issue.message} className="text-sm text-amber-800">
                  {issue.message}（
                  <Link to={issue.path} className={LINK_TEXT}>
                    到基礎資料補齊
                  </Link>
                  ）
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </DashboardCard>
  );
}

function QuickLinksCard(): ReactElement {
  return (
    <section className={CARD} aria-label="快速入口">
      <h2 className={DASHBOARD_CARD_TITLE}>快速入口</h2>
      <div className="flex flex-wrap gap-2">
        <Link to="/scheduler" className={LINK_BUTTON}>
          排課控制台
        </Link>
        <Link to="/timetable" className={LINK_BUTTON}>
          課表檢視
        </Link>
        <Link to="/requirements" className={LINK_BUTTON}>
          排課需求總覽
        </Link>
      </div>
    </section>
  );
}

function AdminHome(): ReactElement {
  const semesterData = useSemesterData();
  return (
    <div className={DASHBOARD_GRID}>
      <SemesterCard data={semesterData} />
      <DraftHealthCard data={semesterData} />
      <DataHealthCard />
      <QuickLinksCard />
    </div>
  );
}

// --- TEACHER: published timetable only, no drafts / checks / admin links ---

function TeacherHome(): ReactElement {
  const data = useSemesterData();
  const published = data.versions.published;
  return (
    <div className={DASHBOARD_GRID}>
      <DashboardCard title="目前的課表" isLoading={data.isLoading} errorMessage={data.errorMessage} onRetry={data.reload}>
        <div className="flex flex-col gap-3">
          {data.semester !== null && <p className="text-sm text-gray-700">目前學期：{data.semesterLabel}</p>}
          {published !== null ? (
            <p className="text-sm text-gray-700">
              已發布：v{published.version_number}（發布時間 {formatDateTime(published.updated_at)}）
            </p>
          ) : (
            <p className={NOTICE}>目前學期還沒有已發布的課表，發布後就能在課表檢視查看。</p>
          )}
          <div>
            <Link
              to={published === null ? "/timetable" : `/timetable?scheduleVersionId=${published.id}`}
              className={LINK_BUTTON}
            >
              前往課表檢視
            </Link>
          </div>
        </div>
      </DashboardCard>
    </div>
  );
}

// Task 97: the home page is a dashboard by role (decision 33) -- an ADMIN
// sees the semester's versions, the latest draft's health, the basic
// data's health and quick links; anyone else (a TEACHER) only the
// published timetable and the way to it. Every card loads on its own.
export default function Home(): ReactElement {
  const isAdmin = isCurrentUserAdmin();
  const username = getCurrentUsername();
  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>首頁</h1>
      <p className={`${MUTED_TEXT} mb-4`}>
        歡迎回來{username === null ? "" : `，${username}`}（{isAdmin ? "管理員" : "教師"}）
      </p>
      {isAdmin ? <AdminHome /> : <TeacherHome />}
    </div>
  );
}
