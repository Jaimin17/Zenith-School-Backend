DB_SCHEMA_COMPACT = """\
TABLES — PostgreSQL. Rules: always is_delete=false. Quote "class". CAST('id' AS UUID) for UUIDs. Only SELECT.

STRING MATCHING RULE (critical):
NEVER use = for text columns like subject.name, exam.title, class.name, teacher name etc.
ALWAYS use ILIKE with % wildcards: s.name ILIKE '%math%'
This handles partial words: user says "math" → matches "Mathematics", "Math 101", etc.
User says "sci" → matches "Science", "Computer Science" etc.

student(id,first_name,last_name,email,phone,sex,dob,is_delete, parent_id→parent.id, class_id→"class".id, grade_id→grade.id)
teacher(id,first_name,last_name,email,phone,sex,dob,is_delete)
parent(id,first_name,last_name,email,phone,is_delete)
"class"(id,name,capacity,is_delete, supervisor_id→teacher.id, grade_id→grade.id)
grade(id,level,is_delete)
subject(id,name,is_delete)
teacher_subject_link(teacher_id→teacher.id, subject_id→subject.id)
lesson(id,name,day,start_time,end_time,is_delete, subject_id→subject.id, class_id→"class".id, teacher_id→teacher.id)
exam(id,title,start_time,end_time,is_delete, lesson_id→lesson.id)
assignment(id,title,description,start_date,due_date,is_delete, lesson_id→lesson.id)
result(id,score,is_delete, student_id→student.id, exam_id→exam.id, assignment_id→assignment.id)
attendance(id,attendance_date,present,is_delete, student_id→student.id, lesson_id→lesson.id)
announcement(id,title,description,announcement_date,is_delete, class_id→"class".id)
event(id,title,description,start_time,end_time,is_delete, class_id→"class".id)

FK DIRECTIONS (critical — do not reverse these):
  exam.lesson_id → lesson.id           JOIN lesson l ON l.id = e.lesson_id
  result.exam_id → exam.id             JOIN exam e ON e.id = r.exam_id
  result.assignment_id → assignment.id  JOIN assignment a ON a.id = r.assignment_id
  result.student_id → student.id       JOIN student st ON st.id = r.student_id
  lesson.subject_id → subject.id       JOIN subject s ON s.id = l.subject_id
  lesson.class_id → "class".id         JOIN "class" c ON c.id = l.class_id
  lesson.teacher_id → teacher.id       JOIN teacher t ON t.id = l.teacher_id
  attendance.student_id → student.id   JOIN student st ON st.id = a.student_id
  attendance.lesson_id → lesson.id     JOIN lesson l ON l.id = a.lesson_id
  student.class_id → "class".id        JOIN "class" c ON c.id = st.class_id

CRITICAL RULE — result vs exam table:
  result table = only contains GRADED/RELEASED scores. An exam with no result yet = not in result table.
  USE result table ONLY when user asks about: score, marks, grade, result, performance.
  USE exam table directly when user asks about: date, time, schedule, upcoming, when, list of exams.
  NEVER use result table to find exam dates — exam may not be graded yet and will be missing.

VERIFIED QUERY TEMPLATES — use these as exact base patterns:

[exam SCORE/RESULT for student — use when user asks for score/marks/result]
SELECT e.title, e.start_time, r.score
FROM result r
JOIN exam e ON e.id = r.exam_id
JOIN lesson l ON l.id = e.lesson_id
JOIN subject s ON s.id = l.subject_id
WHERE r.student_id = CAST('STUDENT_ID' AS UUID)
  AND r.exam_id IS NOT NULL
  AND s.name ILIKE '%SUBJECT_KEYWORD%'
  AND r.is_delete = false
  AND e.is_delete = false
  AND l.is_delete = false
ORDER BY e.start_time DESC;

[all exam SCORES for student — use when user asks for all results/marks]
SELECT e.title, e.start_time, r.score
FROM result r
JOIN exam e ON e.id = r.exam_id
WHERE r.student_id = CAST('STUDENT_ID' AS UUID)
  AND r.exam_id IS NOT NULL
  AND r.is_delete = false
  AND e.is_delete = false
ORDER BY e.start_time DESC;

[exam DATE/TIME/SCHEDULE for student — use when user asks WHEN exam is, date, upcoming]
SELECT e.title, e.start_time, e.end_time, s.name as subject_name
FROM exam e
JOIN lesson l ON l.id = e.lesson_id
JOIN "class" c ON c.id = l.class_id
JOIN student st ON st.class_id = c.id
LEFT JOIN subject s ON s.id = l.subject_id
WHERE st.id = CAST('STUDENT_ID' AS UUID)
  AND e.is_delete = false
  AND l.is_delete = false
  AND c.is_delete = false
ORDER BY e.start_time DESC;

[exam DATE/TIME for student by subject — use when user asks WHEN a specific subject exam is]
SELECT e.title, e.start_time, e.end_time
FROM exam e
JOIN lesson l ON l.id = e.lesson_id
JOIN "class" c ON c.id = l.class_id
JOIN student st ON st.class_id = c.id
LEFT JOIN subject s ON s.id = l.subject_id
WHERE st.id = CAST('STUDENT_ID' AS UUID)
  AND s.name ILIKE '%SUBJECT_KEYWORD%'
  AND e.is_delete = false
  AND l.is_delete = false
  AND c.is_delete = false
ORDER BY e.start_time DESC;

[assignment DATE/DUE for student — use when user asks WHEN assignment is due, not the score]
SELECT a.title, a.start_date, a.due_date, s.name as subject_name
FROM assignment a
JOIN lesson l ON l.id = a.lesson_id
JOIN "class" c ON c.id = l.class_id
JOIN student st ON st.class_id = c.id
LEFT JOIN subject s ON s.id = l.subject_id
WHERE st.id = CAST('STUDENT_ID' AS UUID)
  AND a.is_delete = false
  AND l.is_delete = false
  AND c.is_delete = false
ORDER BY a.due_date DESC;

[assignment SCORE/RESULT for student — use when user asks for assignment score/marks]
SELECT a.title, a.due_date, r.score
FROM result r
JOIN assignment a ON a.id = r.assignment_id
WHERE r.student_id = CAST('STUDENT_ID' AS UUID)
  AND r.assignment_id IS NOT NULL
  AND r.is_delete = false
  AND a.is_delete = false
ORDER BY a.due_date DESC;

[student attendance]
SELECT a.attendance_date, a.present, l.name as lesson_name
FROM attendance a
JOIN lesson l ON l.id = a.lesson_id
WHERE a.student_id = CAST('STUDENT_ID' AS UUID)
  AND a.is_delete = false
  AND l.is_delete = false
ORDER BY a.attendance_date DESC;

[student schedule]
SELECT l.name, l.day, l.start_time, l.end_time, s.name as subject_name
FROM lesson l
JOIN "class" c ON c.id = l.class_id
JOIN student st ON st.class_id = c.id
LEFT JOIN subject s ON s.id = l.subject_id
WHERE st.id = CAST('STUDENT_ID' AS UUID)
  AND l.is_delete = false
  AND c.is_delete = false;

[announcements for student]
SELECT title, description, announcement_date
FROM announcement
WHERE (class_id = (SELECT class_id FROM student WHERE id = CAST('STUDENT_ID' AS UUID))
   OR class_id IS NULL)
  AND is_delete = false
ORDER BY announcement_date DESC;

[teacher lessons]
SELECT l.name, l.day, l.start_time, l.end_time, s.name as subject_name, c.name as class_name
FROM lesson l
LEFT JOIN subject s ON s.id = l.subject_id
LEFT JOIN "class" c ON c.id = l.class_id
WHERE l.teacher_id = CAST('TEACHER_ID' AS UUID)
  AND l.is_delete = false;

[events for student]
SELECT title, description, start_time, end_time
FROM event
WHERE (class_id = (SELECT class_id FROM student WHERE id = CAST('STUDENT_ID' AS UUID))
   OR class_id IS NULL)
  AND is_delete = false
ORDER BY start_time DESC;
"""

# ── Keyword pre-router ────────────────────────────────────────────
# Maps lowercase words → DB table name
# Used to skip the LLM type-decision call for obvious queries
KEYWORD_TABLE_MAP = {
    "announcement": "announcement", "announcements": "announcement",
    "notice": "announcement", "notices": "announcement",
    "bulletin": "announcement", "news": "announcement",
    "attendance": "attendance", "present": "attendance",
    "absent": "attendance", "absence": "attendance",
    "result": "result", "results": "result",
    "score": "result", "scores": "result",
    "grade": "result", "grades": "result",
    "marks": "result", "mark": "result",
    "performance": "result",
    "exam": "exam", "exams": "exam",
    "test": "exam", "tests": "exam",
    "quiz": "exam",
    "assignment": "assignment", "assignments": "assignment",
    "homework": "assignment", "task": "assignment",
    "schedule": "lesson", "timetable": "lesson",
    "lesson": "lesson", "lessons": "lesson",
    "period": "lesson",
    "event": "event", "events": "event",
    "activity": "event",
    "subject": "subject", "subjects": "subject",
    "teacher": "teacher", "teachers": "teacher",
    "student": "student", "students": "student",
}

DB_ONLY_TABLES = {
    "attendance", "result", "student", "teacher",
    "parent", "grade", "class", "lesson",
    "exam", "announcement", "event", "subject",
}
