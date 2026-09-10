from app.models.academic_year import AcademicYear, Semester
from app.models.class_subject_requirement import ClassSubjectRequirement
from app.models.grade_class import Class, Grade
from app.models.lesson import Lesson
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.schedule_version import ScheduleVersion
from app.models.school import School
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherAvailability, TeacherSubject
from app.models.time_slot import TimeSlot
from app.models.user import User

__all__ = [
    "AcademicYear",
    "Semester",
    "ClassSubjectRequirement",
    "Grade",
    "Class",
    "Lesson",
    "Room",
    "Schedule",
    "ScheduleVersion",
    "School",
    "Subject",
    "Teacher",
    "TeacherAvailability",
    "TeacherSubject",
    "TimeSlot",
    "User",
]
