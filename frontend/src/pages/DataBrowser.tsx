import { Fragment, useState, type ReactElement } from "react";
import { list as listTeachers } from "../api/teachers";
import { list as listClasses } from "../api/classes";
import { list as listSubjects } from "../api/subjects";
import { list as listRooms } from "../api/rooms";
import { list as listTimeSlots } from "../api/timeSlots";
import { listByTeacher as listTeacherSubjects } from "../api/teacherSubjects";
import { listByTeacher as listTeacherUnavailableSlots } from "../api/teacherAvailability";
import { useResource } from "../hooks/useResource";
import { formatTimeSlotLabel, formatWeekday } from "../utils/timeSlotFormat";

type TabKey = "teachers" | "classes" | "subjects" | "rooms" | "timeSlots";

const TABS: { key: TabKey; label: string }[] = [
  { key: "teachers", label: "老師" },
  { key: "classes", label: "班級" },
  { key: "subjects", label: "科目" },
  { key: "rooms", label: "教室" },
  { key: "timeSlots", label: "時段" },
];

function LoadingOrError({
  isLoading,
  errorMessage,
}: {
  isLoading: boolean;
  errorMessage: string | null;
}): ReactElement | null {
  if (isLoading) {
    return <p>載入中…</p>;
  }
  if (errorMessage !== null) {
    return <p role="alert">{errorMessage}</p>;
  }
  return null;
}

// Task 30's specific requirement: a teacher's row expands to show their
// qualifications (H5) and unavailable slots (H4) -- exactly the two pieces
// of data needed to check a "楊老師工作量超標"-style scheduling failure by
// hand, without needing Swagger UI.
function TeacherDetail({ teacherId }: { teacherId: number }): ReactElement {
  const subjects = useResource(() => listTeacherSubjects(teacherId), [teacherId]);
  const unavailableSlots = useResource(
    () => listTeacherUnavailableSlots(teacherId),
    [teacherId],
  );

  return (
    <div>
      <h3>任教資格</h3>
      <LoadingOrError
        isLoading={subjects.isLoading}
        errorMessage={subjects.errorMessage}
      />
      {subjects.data !== null &&
        (subjects.data.length === 0 ? (
          <p>無</p>
        ) : (
          <ul>
            {subjects.data.map((subject) => (
              <li key={subject.id}>{subject.name}</li>
            ))}
          </ul>
        ))}

      <h3>不可用時段</h3>
      <LoadingOrError
        isLoading={unavailableSlots.isLoading}
        errorMessage={unavailableSlots.errorMessage}
      />
      {unavailableSlots.data !== null &&
        (unavailableSlots.data.length === 0 ? (
          <p>無</p>
        ) : (
          <ul>
            {unavailableSlots.data.map((slot) => (
              <li key={slot.id}>{formatTimeSlotLabel(slot)}</li>
            ))}
          </ul>
        ))}
    </div>
  );
}

function TeachersTab(): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listTeachers(), []);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <table>
          <thead>
            <tr>
              <th>姓名</th>
              <th>啟用中</th>
              <th>最低每週節數</th>
              <th>最高每週節數</th>
            </tr>
          </thead>
          <tbody>
            {data.map((teacher) => (
              <Fragment key={teacher.id}>
                <tr
                  onClick={() =>
                    setExpandedId((current) =>
                      current === teacher.id ? null : teacher.id,
                    )
                  }
                  style={{ cursor: "pointer" }}
                >
                  <td>{teacher.name}</td>
                  <td>{teacher.is_active ? "是" : "否"}</td>
                  <td>{teacher.min_weekly_periods}</td>
                  <td>{teacher.max_weekly_periods}</td>
                </tr>
                {expandedId === teacher.id && (
                  <tr>
                    <td colSpan={4}>
                      <TeacherDetail teacherId={teacher.id} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ClassesTab(): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listClasses(), []);

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <table>
          <thead>
            <tr>
              <th>名稱</th>
              <th>年級 ID</th>
              <th>啟用中</th>
              <th>導師班教室 ID</th>
            </tr>
          </thead>
          <tbody>
            {data.map((classItem) => (
              <tr key={classItem.id}>
                <td>{classItem.name}</td>
                <td>{classItem.grade_id}</td>
                <td>{classItem.is_active ? "是" : "否"}</td>
                <td>{classItem.homeroom_room_id ?? "無"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SubjectsTab(): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listSubjects(), []);

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <table>
          <thead>
            <tr>
              <th>名稱</th>
              <th>啟用中</th>
            </tr>
          </thead>
          <tbody>
            {data.map((subject) => (
              <tr key={subject.id}>
                <td>{subject.name}</td>
                <td>{subject.is_active ? "是" : "否"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function RoomsTab(): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listRooms(), []);

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <table>
          <thead>
            <tr>
              <th>名稱</th>
              <th>類型</th>
              <th>容量</th>
              <th>啟用中</th>
            </tr>
          </thead>
          <tbody>
            {data.map((room) => (
              <tr key={room.id}>
                <td>{room.name}</td>
                <td>{room.room_type}</td>
                <td>{room.capacity ?? "未設定"}</td>
                <td>{room.is_active ? "是" : "否"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TimeSlotsTab(): ReactElement {
  const { data, isLoading, errorMessage } = useResource(() => listTimeSlots(), []);

  return (
    <div>
      <LoadingOrError isLoading={isLoading} errorMessage={errorMessage} />
      {data !== null && (
        <table>
          <thead>
            <tr>
              <th>星期</th>
              <th>節次</th>
              <th>教學節次</th>
              <th>開始時間</th>
              <th>結束時間</th>
            </tr>
          </thead>
          <tbody>
            {data.map((timeSlot) => (
              <tr key={timeSlot.id}>
                <td>{formatWeekday(timeSlot.weekday)}</td>
                <td>{timeSlot.period}</td>
                <td>{timeSlot.is_teaching_period ? "是" : "否"}</td>
                <td>{timeSlot.start_time ?? "未設定"}</td>
                <td>{timeSlot.end_time ?? "未設定"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function DataBrowser(): ReactElement {
  const [activeTab, setActiveTab] = useState<TabKey>("teachers");

  return (
    <div>
      <h1>基礎資料瀏覽</h1>
      <nav>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            aria-pressed={activeTab === tab.key}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      {activeTab === "teachers" && <TeachersTab />}
      {activeTab === "classes" && <ClassesTab />}
      {activeTab === "subjects" && <SubjectsTab />}
      {activeTab === "rooms" && <RoomsTab />}
      {activeTab === "timeSlots" && <TimeSlotsTab />}
    </div>
  );
}
