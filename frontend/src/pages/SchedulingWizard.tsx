import { useState, type ReactElement } from "react";
import { useSearchParams } from "react-router-dom";
import GradesStep from "../components/wizard/GradesStep";
import RequirementsStep from "../components/wizard/RequirementsStep";
import RunStep from "../components/wizard/RunStep";
import SemesterStep from "../components/wizard/SemesterStep";
import TeachersStep from "../components/wizard/TeachersStep";
import { WIZARD_STEPS, isWizardStep, type WizardStepKey } from "../utils/wizard";
import { BUTTON_PRIMARY, HELP_TEXT, PAGE, PAGE_TITLE, SECTION_TITLE } from "../styles/ui";

// The semester the wizard last worked on, so a link straight to one step
// (?step=teachers, from a failed run's diagnostics) can open it. A per-
// browser convenience only: without it the wizard just starts at step one.
const REMEMBERED_SEMESTER_KEY = "wizard.semester";

interface RememberedSemester {
  id: number;
  label: string;
}

function readRemembered(): RememberedSemester | null {
  try {
    const raw = sessionStorage.getItem(REMEMBERED_SEMESTER_KEY);
    if (raw === null) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      typeof (parsed as RememberedSemester).id === "number" &&
      typeof (parsed as RememberedSemester).label === "string"
    ) {
      return parsed as RememberedSemester;
    }
    return null;
  } catch {
    return null;
  }
}

function remember(semester: RememberedSemester): void {
  try {
    sessionStorage.setItem(REMEMBERED_SEMESTER_KEY, JSON.stringify(semester));
  } catch {
    // Storage unavailable (private mode ...): deep links just start over.
  }
}

// Task 98: 開始排課 -- the one place a 教學組長 sets up and runs a
// semester's scheduling, replacing 基礎資料 / 排課需求總覽 / 排課控制台:
// 學年度與學期 -> 教師設定 -> 年級與可排節次 -> 科目需求 -> 確認並排課.
// Classes and the school's 科目需求 are kept on 學校資料. Every step saves
// its own part, so it can be left and resumed.
export default function SchedulingWizard(): ReactElement {
  const [searchParams] = useSearchParams();
  const requestedStep = searchParams.get("step");
  const [semester, setSemester] = useState<RememberedSemester | null>(() =>
    isWizardStep(requestedStep) ? readRemembered() : null,
  );
  const [step, setStep] = useState<WizardStepKey | null>(() =>
    isWizardStep(requestedStep) ? (readRemembered() === null ? "semester" : requestedStep) : null,
  );

  function go(next: WizardStepKey): void {
    setStep(next);
    window.scrollTo({ top: 0 });
  }

  function chooseSemester(id: number, label: string): void {
    const chosen = { id, label };
    remember(chosen);
    setSemester(chosen);
    go("teachers");
  }

  const stepIndex = step === null ? -1 : WIZARD_STEPS.findIndex((item) => item.key === step);

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>開始排課</h1>
      {step === null ? (
        <div>
          <p className={HELP_TEXT}>
            依序設定學年度與學期、參與的老師、年級可排節次與科目需求，最後由系統自動排課。班級與各年級的科目節數請先在「學校資料」維護。每一步都會先存起來，可以隨時離開再回來。
          </p>
          <button type="button" onClick={() => go("semester")} className={BUTTON_PRIMARY}>
            開始排課 →
          </button>
        </div>
      ) : (
        <>
          <ol className="mb-4 flex flex-wrap gap-2 text-sm" aria-label="排課步驟">
            {WIZARD_STEPS.map((item, index) => {
              const isCurrent = item.key === step;
              const canJump = semester !== null && !isCurrent;
              return (
                <li key={item.key}>
                  <button
                    type="button"
                    onClick={() => go(item.key)}
                    disabled={!canJump}
                    aria-current={isCurrent ? "step" : undefined}
                    className={`rounded-full px-3 py-1 ${
                      isCurrent
                        ? "bg-blue-600 text-white"
                        : index < stepIndex
                          ? "bg-blue-50 text-blue-700"
                          : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {index + 1}. {item.label}
                  </button>
                </li>
              );
            })}
          </ol>
          {semester !== null && step !== "semester" && (
            <p className="mb-2 text-sm text-gray-700">排課學期：{semester.label}</p>
          )}
          <h2 className={SECTION_TITLE}>{WIZARD_STEPS[stepIndex]?.label}</h2>
          {step === "semester" && (
            <SemesterStep initialYear={null} initialNumber={null} onChosen={chooseSemester} />
          )}
          {semester !== null && step === "teachers" && (
            <TeachersStep semesterId={semester.id} onBack={() => go("semester")} onNext={() => go("grades")} />
          )}
          {semester !== null && step === "grades" && (
            <GradesStep semesterId={semester.id} onBack={() => go("teachers")} onNext={() => go("requirements")} />
          )}
          {semester !== null && step === "requirements" && (
            <RequirementsStep
              semesterId={semester.id}
              onBack={() => go("grades")}
              onNext={() => go("run")}
            />
          )}
          {semester !== null && step === "run" && (
            <RunStep semesterId={semester.id} semesterLabel={semester.label} onBack={() => go("requirements")} />
          )}
        </>
      )}
    </div>
  );
}
