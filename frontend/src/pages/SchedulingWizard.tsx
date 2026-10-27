import { useEffect, useState, type ReactElement } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { get as getRecord } from "../api/scheduleVersions";
import { list as listAcademicYears } from "../api/academicYears";
import { list as listSemesters } from "../api/semesters";
import CombinedStep from "../components/wizard/CombinedStep";
import GradesStep from "../components/wizard/GradesStep";
import RequirementsStep from "../components/wizard/RequirementsStep";
import RunStep from "../components/wizard/RunStep";
import SemesterStep from "../components/wizard/SemesterStep";
import TeachersStep from "../components/wizard/TeachersStep";
import { extractApiErrorMessage } from "../constants/errorMessages";
import { formatSemesterLabel } from "../utils/scheduleVersionFormat";
import { WIZARD_STEPS, isWizardStep, type WizardStepKey } from "../utils/wizard";
import {
  forgetWizardRecord,
  readRememberedWizardRecord,
  readRememberedWizardStep,
  rememberWizardRecord,
  rememberWizardStep,
} from "../utils/wizardRecord";
import type { ScheduleVersion } from "../types/scheduleVersion";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import Stepper from "../components/Stepper";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY_SM,
  CARD,
  ERROR_TEXT,
  LINK_TEXT,
  LOADING_TEXT,
  META_TAG,
  NOTICE,
  PAGE,
  RULE_NOTE,
} from "../styles/ui";

interface WizardRecord {
  id: number;
  versionNumber: number | null;
  semesterLabel: string;
}

function parseId(raw: string | null): number | null {
  const parsed = raw === null ? NaN : Number(raw);
  return Number.isInteger(parsed) ? parsed : null;
}

// The record named by ?record= (檢視排課設定 > 修改排課設定) or else the
// remembered one -- loaded with its semester's label. A record that is no
// longer 尚未排課 can't be edited here.
async function loadRecord(recordId: number): Promise<{ record: WizardRecord; isEditable: boolean }> {
  const [version, semesters, academicYears] = await Promise.all([
    getRecord(recordId),
    listSemesters(0, 1000),
    listAcademicYears(0, 1000),
  ]);
  const semester = semesters.find((item) => item.id === version.semester_id);
  const academicYearById = new Map(academicYears.map((item) => [item.id, item.year]));
  return {
    record: {
      id: version.id,
      versionNumber: version.display_number,
      semesterLabel: semester === undefined ? "" : formatSemesterLabel(semester, academicYearById),
    },
    isEditable: version.status === "NOT_SCHEDULED",
  };
}

// The whole flow, in the header's (i).
const WIZARD_HELP =
  "依序設定學年度與學期、參與的老師、年級可排節次與科目需求，最後由系統自動排課。每次開始排課都會新增一筆「尚未排課」的排課紀錄，每一步都會先存進這筆紀錄，可以隨時離開，回到「開始排課」會自動接續上次的步驟（也可以從排課紀錄的「檢視排課設定」繼續）。班級與各年級的科目節數請先在「學校資料」維護。";

// Task 98 / v3: 開始排課 -- 學年度與學期 (creates a 尚未排課 排課紀錄) ->
// 教師設定 -> 年級與可排節次 -> 科目需求 -> 共同排課 -> 確認並自動排課. Every step saves
// its part into the record, so it can be left and resumed (排課紀錄 >
// 檢視排課設定 > 修改排課設定 opens it again). Classes and the school's
// 科目需求 are kept on 學校資料.
export default function SchedulingWizard(): ReactElement {
  const [searchParams] = useSearchParams();
  const requestedStep = searchParams.get("step");
  const explicitRecordId = parseId(searchParams.get("record"));
  // Without ?record=, coming back to 開始排課 resumes the record (and the
  // step) left unfinished.
  const isResuming = explicitRecordId === null;
  const requestedRecordId = explicitRecordId ?? readRememberedWizardRecord();
  const [record, setRecord] = useState<WizardRecord | null>(null);
  const [isLoading, setIsLoading] = useState(requestedRecordId !== null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lockedRecord, setLockedRecord] = useState<WizardRecord | null>(null);
  const [step, setStep] = useState<WizardStepKey | null>(null);

  useEffect(() => {
    if (requestedRecordId === null) {
      return;
    }
    let isCurrent = true;
    loadRecord(requestedRecordId)
      .then(({ record: loaded, isEditable }) => {
        if (!isCurrent) {
          return;
        }
        if (isEditable) {
          rememberWizardRecord(loaded.id);
          const resumedStep = isResuming ? readRememberedWizardStep() : null;
          const nextStep =
            isWizardStep(requestedStep) && requestedStep !== "semester"
              ? requestedStep
              : resumedStep !== null && resumedStep !== "semester"
                ? resumedStep
                : "teachers";
          rememberWizardStep(nextStep);
          setRecord(loaded);
          setStep(nextStep);
        } else if (isResuming) {
          // Scheduled since (e.g. from 排課紀錄): nothing left to resume.
          forgetWizardRecord();
        } else {
          setLockedRecord(loaded);
        }
      })
      .catch((caught: unknown) => {
        if (!isCurrent) {
          return;
        }
        if (isResuming) {
          // Deleted since, or another account's record: start afresh.
          forgetWizardRecord();
        } else {
          setLoadError(extractApiErrorMessage(caught));
        }
      })
      .finally(() => {
        if (isCurrent) {
          setIsLoading(false);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [requestedRecordId, requestedStep, isResuming]);

  function go(next: WizardStepKey): void {
    if (next !== "semester") {
      rememberWizardStep(next);
    }
    setStep(next);
    window.scrollTo({ top: 0 });
  }

  // 另開新的排課: the unfinished record stays in 排課紀錄 (尚未排課).
  function startNew(): void {
    forgetWizardRecord();
    setRecord(null);
    setLockedRecord(null);
    setLoadError(null);
    go("semester");
  }

  function chooseRecord(created: ScheduleVersion, semesterLabel: string): void {
    rememberWizardRecord(created.id);
    setRecord({ id: created.id, versionNumber: created.display_number, semesterLabel });
    go("teachers");
  }

  const stepIndex = step === null ? -1 : WIZARD_STEPS.findIndex((item) => item.key === step);

  if (isLoading) {
    return (
      <div className={PAGE}>
        <PageHeader title="開始排課" />
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }

  const hasRecordHeader = record !== null && step !== null && step !== "semester";

  return (
    <div className={PAGE}>
      <PageHeader
        title="開始排課"
        info={<p>{WIZARD_HELP}</p>}
        meta={
          hasRecordHeader && (
            <>
              <span className={META_TAG}>
                {record.semesterLabel} · 紀錄 #{record.versionNumber}
              </span>
              <StatusBadge tone="warning">尚未排課</StatusBadge>
            </>
          )
        }
        actions={
          hasRecordHeader ? (
            <button type="button" onClick={startNew} className={BUTTON_SECONDARY_SM}>
              另開新的排課
            </button>
          ) : undefined
        }
      />
      {loadError !== null && (
        <p role="alert" className={ERROR_TEXT}>
          無法開啟這筆排課紀錄：{loadError}
        </p>
      )}
      {lockedRecord !== null && (
        <p className={`${NOTICE} mb-4`}>
          排課紀錄編號 {lockedRecord.versionNumber} 已經排過課，排課設定不能再修改。請到
          <Link to="/records" className={LINK_TEXT}>
            排課紀錄
          </Link>
          「複製此次排課設定」後再修改。
        </p>
      )}
      {step === null ? (
        <div className={CARD}>
          <p className={RULE_NOTE}>每次開始排課都會新增一筆「尚未排課」的排課紀錄，可以隨時離開，之後會自動接續。</p>
          <button type="button" onClick={startNew} className={BUTTON_PRIMARY}>
            開始排課 →
          </button>
        </div>
      ) : (
        <>
          <Stepper
            steps={WIZARD_STEPS}
            currentIndex={stepIndex}
            ariaLabel="排課步驟"
            // A record's semester is fixed once it exists.
            canJump={(index) => record !== null && index !== stepIndex && WIZARD_STEPS[index].key !== "semester"}
            onJump={(index) => go(WIZARD_STEPS[index].key)}
          />
          {step === "semester" && (
            <SemesterStep initialYear={null} initialNumber={null} onChosen={chooseRecord} />
          )}
          {record !== null && step === "teachers" && (
            // No 上一步: the record's semester can't change any more.
            <TeachersStep versionId={record.id} onNext={() => go("grades")} />
          )}
          {record !== null && step === "grades" && (
            <GradesStep versionId={record.id} onBack={() => go("teachers")} onNext={() => go("requirements")} />
          )}
          {record !== null && step === "requirements" && (
            <RequirementsStep versionId={record.id} onBack={() => go("grades")} onNext={() => go("combined")} />
          )}
          {record !== null && step === "combined" && (
            <CombinedStep versionId={record.id} onBack={() => go("requirements")} onNext={() => go("run")} />
          )}
          {record !== null && step === "run" && (
            <RunStep
              versionId={record.id}
              versionNumber={record.versionNumber}
              semesterLabel={record.semesterLabel}
              onBack={() => go("combined")}
            />
          )}
        </>
      )}
    </div>
  );
}
