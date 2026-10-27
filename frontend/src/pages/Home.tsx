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
import { CalendarPlusIcon, ClipboardListIcon, SchoolIcon } from "../components/icons";
import PageHeader from "../components/PageHeader";
import { RecordStatusBadge } from "../components/StatusBadge";
import { recordsCardText, schoolDataCardText, wizardCardText } from "../utils/homeCards";
import { useResource } from "../hooks/useResource";
import { getCurrentUserRole, getCurrentUsername, isCurrentUserCoordinator, ROLE_LABELS } from "../utils/auth";
import {
  formatDateTime,
  pickCurrentSemester,
  pickLatestUnpublished,
  summarizeDataHealth,
  summarizeDraftHealth,
  summarizeVersions,
  type SemesterVersions,
} from "../utils/dashboard";
import { formatSemesterLabel } from "../utils/scheduleVersionFormat";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";
import {
  ACTION_CARD,
  ACTION_CARD_GRID,
  ACTION_CARD_ICON,
  ACTION_CARD_TEXT,
  ACTION_CARD_TITLE,
  BUTTON_PRIMARY,
  BUTTON_SECONDARY_SM,
  CARD,
  DASHBOARD_CARD_TITLE,
  DASHBOARD_GRID,
  ERROR_TEXT,
  LINK_TEXT,
  LOADING_TEXT,
  META_TAG,
  MUTED_TEXT,
  NOTICE,
  PAGE,
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
  latestUnpublished: ScheduleVersion | null;
  // Every record of the school (the Action Cards' lines).
  records: readonly ScheduleVersion[];
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
    latestUnpublished: pickLatestUnpublished(versions),
    records: versions,
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
          <Link to="/wizard" className={LINK_TEXT}>
            到開始排課設定學年度與學期
          </Link>
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-gray-700">目前學期：{semesterLabel}</p>
          {versions.published !== null ? (
            <p className="flex flex-wrap items-center gap-2 text-sm text-gray-700">
              <RecordStatusBadge record={versions.published} />
              編號 {versions.published.display_number}（最後更新 {formatDateTime(versions.published.updated_at)}）
            </p>
          ) : (
            <p className={NOTICE}>這個學期還沒有已發布的課表，請到排課紀錄檢視課表後發布。</p>
          )}
          <p className="text-sm text-gray-700">
            這個學期另有 {versions.otherCount} 筆未發布的排課紀錄
            {versions.otherCount > 0 && (
              <>
                （
                <Link to="/records" className={LINK_TEXT}>
                  查看排課紀錄
                </Link>
                ）
              </>
            )}
          </p>
        </div>
      )}
    </DashboardCard>
  );
}

function DraftHealthCard({ data }: { data: ReturnType<typeof useSemesterData> }): ReactElement {
  const draft = data.latestUnpublished;
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
      title="最新未發布課表健康度"
      isLoading={data.isLoading || (draftId !== null && health.isLoading && health.data === null)}
      errorMessage={data.errorMessage ?? health.errorMessage}
      onRetry={data.errorMessage !== null ? data.reload : health.reload}
    >
      {draft === null ? (
        <p className={MUTED_TEXT}>
          {data.semester === null ? "還沒有任何學期。" : "目前沒有尚未發布的課表。"}
          <Link to="/wizard" className={LINK_TEXT}>
            到開始排課排出一份課表
          </Link>
        </p>
      ) : summary === null ? (
        <p className={LOADING_TEXT}>載入中…</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="flex flex-wrap items-center gap-2 text-sm text-gray-700">
            {data.labelOf(draft.semester_id)} 編號 {draft.display_number}
            <RecordStatusBadge record={draft} />
          </p>
          <div className={STAT_ROW}>
            <Stat value={summary.errorCount} label="錯誤" tone={summary.errorCount > 0 ? "problem" : "normal"} />
            <Stat value={summary.warningCount} label="警告" tone={summary.warningCount > 0 ? "warning" : "normal"} />
            <Stat value={summary.unscheduledCount} label="未排入課程" tone={summary.unscheduledCount > 0 ? "warning" : "normal"} />
          </div>
          {summary.isHealthy ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className={SUCCESS_TEXT}>✓ 沒有問題，可以發布</p>
              <Link to={timetablePath} className={BUTTON_PRIMARY}>
                檢視並發布
              </Link>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Link to={timetablePath} className={BUTTON_PRIMARY}>
                前往修正
              </Link>
              <Link to="/records" className={LINK_TEXT}>
                到排課紀錄
              </Link>
            </div>
          )}
        </div>
      )}
    </DashboardCard>
  );
}

// The school's data, read once for 資料健康度 and the 學校資料 Action Card.
function useSchoolData() {
  return useResource(
    () => Promise.all([listTeachers(0, ALL), listClasses(0, ALL), listSubjects(0, ALL), listRooms(0, ALL)]),
    [],
  );
}

function DataHealthCard({ data }: { data: ReturnType<typeof useSchoolData> }): ReactElement {
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
            <p className={SUCCESS_TEXT}>✓ 學校資料齊全</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {summary.issues.map((issue) => (
                <li key={issue.message} className="text-sm text-amber-800">
                  {issue.message}（
                  <Link to={issue.path} className={LINK_TEXT}>
                    前往補齊
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

// Task 98 Phase D: the three ways in -- each card one link, with a line
// saying where things stand (utils/homeCards.ts). Replaces 快速入口.
function ActionCards({
  semesterData,
  schoolData,
}: {
  semesterData: ReturnType<typeof useSemesterData>;
  schoolData: ReturnType<typeof useSchoolData>;
}): ReactElement {
  const records = semesterData.isLoading ? null : semesterData.records;
  const school = schoolData.data;
  const cards = [
    {
      to: "/wizard",
      title: "開始排課",
      icon: <CalendarPlusIcon size={22} />,
      text: records === null ? "…" : wizardCardText(records),
    },
    {
      to: "/records",
      title: "排課紀錄",
      icon: <ClipboardListIcon size={22} />,
      text: records === null ? "…" : recordsCardText(records),
    },
    {
      to: "/data",
      title: "學校資料",
      icon: <SchoolIcon size={22} />,
      text: school === null ? "…" : schoolDataCardText(school[0].length, school[1].length),
    },
  ];
  return (
    <nav aria-label="快速入口" className={ACTION_CARD_GRID}>
      {cards.map((card) => (
        <Link key={card.to} to={card.to} className={ACTION_CARD}>
          <span className={ACTION_CARD_ICON}>{card.icon}</span>
          <span className="min-w-0">
            <span className={`${ACTION_CARD_TITLE} block`}>{card.title}</span>
            <span className={`${ACTION_CARD_TEXT} block`}>{card.text}</span>
          </span>
        </Link>
      ))}
    </nav>
  );
}

function AdminHome(): ReactElement {
  const semesterData = useSemesterData();
  const schoolData = useSchoolData();
  return (
    <>
      <ActionCards semesterData={semesterData} schoolData={schoolData} />
      <div className={DASHBOARD_GRID}>
        <SemesterCard data={semesterData} />
        <DraftHealthCard data={semesterData} />
        <DataHealthCard data={schoolData} />
      </div>
    </>
  );
}

// --- TEACHER: published timetable only, no other records / checks / admin links ---

function TeacherHome(): ReactElement {
  const data = useSemesterData();
  const published = data.versions.published;
  return (
    <div className={DASHBOARD_GRID}>
      <DashboardCard title="目前的課表" isLoading={data.isLoading} errorMessage={data.errorMessage} onRetry={data.reload}>
        <div className="flex flex-col gap-3">
          {data.semester !== null && <p className="text-sm text-gray-700">目前學期：{data.semesterLabel}</p>}
          {published !== null ? (
            <p className="flex flex-wrap items-center gap-2 text-sm text-gray-700">
              <RecordStatusBadge record={published} />
              編號 {published.display_number}（最後更新 {formatDateTime(published.updated_at)}）
            </p>
          ) : (
            <p className={NOTICE}>目前學期還沒有已發布的課表，發布後就能在課表查看。</p>
          )}
          <div>
            <Link
              to={published === null ? "/timetable" : `/timetable?scheduleVersionId=${published.id}`}
              className={BUTTON_PRIMARY}
            >
              前往課表
            </Link>
          </div>
        </div>
      </DashboardCard>
    </div>
  );
}

// Task 97: the home page is a dashboard by role (decision 33) -- an ADMIN
// sees the semester's 排課紀錄, the latest unpublished timetable's health, the basic
// data's health and quick links; anyone else (a TEACHER) only the
// published timetable and the way to it. Every card loads on its own.
// Task 98: the full dashboard is for the 教學組長 (the 系統管理員 has no
// home page -- RoleRoute sends it to 學校管理).
export default function Home(): ReactElement {
  const isAdmin = isCurrentUserCoordinator();
  const role = getCurrentUserRole();
  const username = getCurrentUsername();
  return (
    <div className={PAGE}>
      <PageHeader
        title="首頁"
        meta={
          <span className={META_TAG}>
            歡迎回來{username === null ? "" : `，${username}`}
            {role === null ? "" : `（${ROLE_LABELS[role]}）`}
          </span>
        }
      />
      {isAdmin ? <AdminHome /> : <TeacherHome />}
    </div>
  );
}
