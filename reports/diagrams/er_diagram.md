# ER dữ liệu tối ưu hóa — SIMULATED

```mermaid
erDiagram
    COURSES {
        string course_id PK
        string course_name
        int credits
        int planned_semester
        string course_type
        string offered_semesters
        string group
        string source_label
    }

    PREREQUISITES {
        string course_id PK, FK
        string prerequisite_id PK, FK
        string type
        string source_label
    }

    STUDENT_PROFILE {
        string student_id PK
        string persona
        int current_semester
        int cumulative_credits
        float gpa
        int failed_courses_count
        string source_label
    }

    STUDENT_PROGRESS {
        string student_id PK, FK
        string course_id PK, FK
        string status
        float grade_10
        int attempt_count
        int semester_taken
        string source_label
    }

    COURSES ||--o{ PREREQUISITES : "course_id"
    COURSES ||--o{ PREREQUISITES : "prerequisite_id"
    STUDENT_PROFILE ||--o{ STUDENT_PROGRESS : has
    COURSES ||--o{ STUDENT_PROGRESS : records
```

## Khóa và ràng buộc

- `courses`: PK `course_id`.
- `prerequisites`: PK ghép (`course_id`, `prerequisite_id`); cả hai là FK tới `courses.course_id`.
- `student_profile`: PK `student_id`.
- `student_progress`: PK ghép (`student_id`, `course_id`); FK `student_id` tới `student_profile.student_id`, FK `course_id` tới `courses.course_id`.
- Tất cả các bảng trong sơ đồ là **SIMULATED**. CSV hiện thực hóa khóa bằng cột định danh; việc cưỡng chế FK/PK được kiểm tra bởi script, vì CSV không tự thực thi ràng buộc quan hệ.
