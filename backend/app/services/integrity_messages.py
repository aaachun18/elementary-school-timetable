from psycopg.errors import CheckViolation, NotNullViolation, UniqueViolation

from app.models.grade_subject_requirement import (
    MAX_GRADE_WEEKLY_PERIODS,
    MIN_GRADE_WEEKLY_PERIODS,
)

# The Chinese sentence shown for a UNIQUE / CHECK constraint violation,
# keyed by the constraint's name -- psycopg reports it as
# exc.orig.diag.constraint_name (PostgreSQL's own structured field, not
# the message text), so this does not depend on wording or locale.
#
# Every constraint of the models is listed. One that is missing still gets
# a sensible sentence from the fallbacks below, never a raw database error.

CONSTRAINT_MESSAGES: dict[str, str] = {
    # users.username has no explicit name: PostgreSQL's default.
    "users_username_key": "這個 Email 已經有帳號，請更換",
    "ck_users_role_valid": "帳號角色不正確，請確認輸入內容",
    "ck_users_school_matches_role": "系統管理員帳號不屬於任何學校，其他帳號必須指定所屬學校",
    "ck_schools_school_type_valid": "學校類型不正確，請確認輸入內容",
    "uq_academic_years_school_year": "這個學年度已經存在，請確認輸入內容",
    "ck_semesters_number_valid": "學期只能是第 1 或第 2 學期",
    "uq_grades_school_level": "這個年級已經存在，請確認輸入內容",
    "ck_grades_level_valid": "年級不在允許的範圍內，請確認輸入內容",
    "uq_classes_grade_name": "班級名稱重複，這個年級已經有同名的班級",
    "ck_classes_name_style_valid": "班級名稱類型不正確，請確認輸入內容",
    "uq_subjects_school_name": "科目名稱重複，這所學校已經有同名的科目",
    "ck_rooms_max_classes_range": "教室同時容納班數必須在 1 到 10 之間",
    "ck_time_slots_weekday_valid": "星期只能是星期一到星期五",
    "uq_time_slots_school_weekday_period": "這個時段已經存在，請確認輸入內容",
    "uq_teachers_user_id_current": "這個帳號已經綁定其他教師資料",
    "ck_teachers_weekly_periods_range": "每週最低節數不能大於最高節數",
    "uq_teacher_subject": "這位教師已經有此科目的任教資格",
    "uq_teacher_timeslot": "這位教師的這個時段已經設定過了",
    "uq_grade_subject_requirement": "這個年級已經有此科目的科目需求，請確認輸入內容",
    "ck_grade_subject_requirements_weekly_periods_valid": (
        f"每週節數必須在 {MIN_GRADE_WEEKLY_PERIODS} 到 {MAX_GRADE_WEEKLY_PERIODS} 節之間"
    ),
    "uq_class_subject_requirement": "這個班級已經有此科目的排課需求，請重新整理頁面後再試",
    "uq_semester_teacher": "這位教師已經在本次排課的教師名單中，請重新整理頁面後再試",
    "uq_semester_teacher_homeroom": "這個班級已經有導師，一個班級只能有一位導師",
    "ck_semester_teachers_min_not_negative": "每週最低節數不能小於 0",
    "ck_semester_teachers_periods_range": "每週最低節數不能大於最高節數",
    "uq_semester_teacher_unavailability": "這個不可排時段已經設定過了，請重新整理頁面後再試",
    "uq_semester_grade_time_slot": "這個年級的可排節次已經設定過了，請重新整理頁面後再試",
    "ck_lessons_block_fields_together": "連堂資料不完整，請重新整理頁面後再試",
    "uq_lesson_requirement_sequence": "課程已經建立過了，請重新整理頁面後再試",
    "uq_schedule_version_lesson": "這堂課在此課表中已經排過了，請重新整理頁面後再試",
    "ck_combined_lessons_merged_count_positive": "合併節數至少要 1 節",
    "uq_combined_lesson_member_requirement": "這個班級的此科目已經在其他共同排課中，請重新整理頁面後再試",
    "uq_combined_lesson_member_position": "共同排課的班級重複，請重新整理頁面後再試",
    "ck_schedule_versions_status_valid": "排課紀錄狀態不正確，請重新整理頁面後再試",
    "ck_schedule_versions_number_unless_editing": "排課紀錄編號不正確，請重新整理頁面後再試",
    "ck_schedule_versions_editing_source": "手動編輯的課表來源不正確，請重新整理頁面後再試",
    "ck_schedule_versions_copied_from": "複製來源不正確，請重新整理頁面後再試",
    "ck_schedule_versions_published_has_timetable": "尚未排課的排課紀錄不能發布",
    "uq_schedule_versions_school_number": "排課紀錄編號重複，請重新整理頁面後再試",
    "uq_schedule_versions_one_published_per_semester": "每個學期只能有一筆已發布的排課紀錄，請重新整理頁面後再試",
}

UNIQUE_FALLBACK_MESSAGE = "資料與現有的資料重複，請確認輸入內容"
CHECK_FALLBACK_MESSAGE = "輸入的值不在允許的範圍內，請確認輸入內容"
NOT_NULL_MESSAGE = "有必填欄位沒有填寫，請確認輸入內容"


def integrity_violation_message(orig: UniqueViolation | CheckViolation | NotNullViolation) -> str:
    """The sentence for one UNIQUE / CHECK / NOT NULL violation."""
    if isinstance(orig, NotNullViolation):
        return NOT_NULL_MESSAGE
    constraint_name = orig.diag.constraint_name
    if constraint_name is not None and constraint_name in CONSTRAINT_MESSAGES:
        return CONSTRAINT_MESSAGES[constraint_name]
    return UNIQUE_FALLBACK_MESSAGE if isinstance(orig, UniqueViolation) else CHECK_FALLBACK_MESSAGE
