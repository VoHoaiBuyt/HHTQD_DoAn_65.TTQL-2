# Quy chế đào tạo NTU — nguồn QĐ 753/2021

Nguồn: OFFICIAL (NTU), Quyết định 753/QĐ-ĐHNT ngày 13/08/2021, áp dụng khóa 60 trở đi.
`rule_status` mô tả căn cứ quy chế; `modeled` mô tả phạm vi hiện thực hóa trong code.

| Quy tắc | Giá trị | Điều/nguồn | rule_status | modeled | Ghi chú |
|---|---|---|---|---:|---|
| `active_ruleset` | `ntu_qd753_2021` | QĐ 753/QĐ-ĐHNT | `CONFIRMED` | True |  |
| `credit_limits.first_semester_scope` | `excluded_university_plan` | Đ9.1b | `CONFIRMED` | True |  |
| `credit_limits.previous_semester_average_threshold` | `5.0` | Đ9.3, Đ9.4, Đ17.2 | `CONFIRMED` | True |  |
| `credit_limits.normal.minimum` | `15` | Đ9.3 | `CONFIRMED` | True |  |
| `credit_limits.normal.maximum` | `27` | Đ9.3 | `CONFIRMED` | True |  |
| `credit_limits.weak_or_poor.condition` | `TBHK học kỳ chính liền trước < 5.00` | Đ17.2 | `CONFIRMED` | True |  |
| `credit_limits.weak_or_poor.minimum` | `12` | Đ9.4 | `CONFIRMED` | True |  |
| `credit_limits.weak_or_poor.maximum` | `18` | Đ9.4 | `CONFIRMED` | True |  |
| `credit_limits.final_semester` | `Không áp dụng giới hạn tối thiểu/tối đa` | Đ9.3, Đ9.4 | `CONFIRMED` | True |  |
| `credit_limits.final_semester.recognition` | `Kế hoạch đăng ký hoàn tất toàn bộ tín chỉ còn thiếu` | Đ9.3, Đ9.4 | `UNCONFIRMED` | True | GIẢ ĐỊNH (kỳ cuối khóa nhận diện qua kế hoạch hoàn tất) |
| `credit_limits.summer_term` | `Không áp dụng giới hạn tối thiểu/tối đa` | Đ7.2b | `CONFIRMED` | True |  |
| `gpa.grade_scale` | `10` | Đ14.1, Đ15.2b | `CONFIRMED` | True |  |
| `gpa.course_grade_rounding_decimals` | `1` | Đ15.2b | `CONFIRMED` | True |  |
| `gpa.rounding_decimals` | `2` | Đ17.1 | `CONFIRMED` | True |  |
| `gpa.semester_average` | `Tất cả học phần có điểm trong học kỳ, kể cả không đạt` | Đ14.2c, Đ17.1 | `CONFIRMED` | True |  |
| `gpa.cumulative_average` | `Học phần đã đạt; lấy điểm cao nhất của các lần học` | Đ14.2c, Đ17.1, Đ11.4 | `CONFIRMED` | True |  |
| `gpa.passing_grade_minimum` | `5.0` | Đ15.2c | `CONFIRMED` | True |  |
| `gpa.excluded_grade_codes` | `['I', 'X', 'R']` | Đ15.2c | `CONFIRMED` | True |  |
| `gpa.excluded_course_groups` | `['GDTC và QP-AN ngoài 130 tín chỉ']` | Đ6.2g, Đ21.1đ | `CONFIRMED` | True |  |
| `gpa.excluded_course_type_values` | `['điều kiện']` | Đ6.2g, Đ21.1đ | `CONFIRMED` | True |  |
| `academic_classification.weak_or_poor_threshold` | `5.0` | Đ17.2 | `CONFIRMED` | True |  |
| `study_year.credit_thresholds` | `[35, 70, 105]` | Đ18.1 | `CONFIRMED` | True |  |
| `study_year.exactly_105_credits` | `Đúng 105 tín chỉ gán năm thứ tư` | Đ18.1 | `UNCONFIRMED` | True | GIẢ ĐỊNH (xử lý biên tại 105 tín chỉ) |
| `academic_warnings.evaluation_scope` | `Chỉ xét cảnh báo sau học kỳ chính; không xét học kỳ hè` | Đ19.1 | `CONFIRMED` | True |  |
| `academic_warnings.W1.threshold` | `24` | Đ19.1a | `CONFIRMED` | True |  |
| `academic_warnings.W1.debt_definition` | `Tín chỉ các học phần đã trượt và chưa đạt lại` | Đ19.1a | `UNCONFIRMED` | True | GIẢ ĐỊNH (nợ đọng tính trên môn đã trượt, chưa đạt lại) |
| `academic_warnings.W2.threshold` | `0.5` | Đ19.1a | `CONFIRMED` | True |  |
| `academic_warnings.W3.first_semester_threshold` | `4.0` | Đ19.1b | `CONFIRMED` | True |  |
| `academic_warnings.W3.later_semester_threshold` | `4.5` | Đ19.1b | `CONFIRMED` | True |  |
| `academic_warnings.W4.cumulative_average_threshold_by_study_year` | `{1: 5.2, 2: 5.3, 3: 5.4, 4: 5.5}` | Đ19.1c | `CONFIRMED` | True |  |
| `academic_warnings.forced_withdrawal.consecutive_warnings_strictly_greater_than` | `2` | Đ19.2a | `CONFIRMED` | True |  |
| `academic_warnings.forced_withdrawal.maximum_main_semesters` | `16` | Đ2.4c, Đ19.2b | `CONFIRMED` | True |  |
| `academic_warnings.forced_withdrawal.summer_terms_count` | `False` | Đ19.1 | `CONFIRMED` | True |  |
| `academic_warnings.monte_carlo_scope` | `Áp dụng W1/W2; W3/W4 chỉ khi có điểm` | Giới hạn dữ liệu mô phỏng | `MODELING_DECISION` | True |  |
| `retake.mandatory_below_grade` | `5.0` | Đ11.1 | `CONFIRMED` | True |  |
| `retake.elective_below_grade` | `5.0` | Đ11.2 | `CONFIRMED` | True |  |
| `retake.improvement_study` | `not_modeled` | Đ11.3 | `CONFIRMED` | False |  |
| `retake.honors_repeat_credit_ratio` | `0.05` | Đ22.3a | `CONFIRMED` | True |  |
| `retake.honors_program_credits` | `130` | 210_CNTT.pdf, mục 7.1 | `CONFIRMED` | True |  |
| `graduation.credits_required` | `130` | 210_CNTT.pdf, mục 7.1 | `CONFIRMED` | True |  |
| `graduation.cumulative_gpa_minimum` | `5.5` | Đ14.3, Đ21.1c | `CONFIRMED` | True |  |
| `graduation.required_outcomes` | `['qpan', 'gdtc', 'foreign_language', 'informatics']` | Đ21.1b, Đ21.1d, Đ21.1đ | `CONFIRMED` | True | Danh mục điều kiện theo Đ21.1; kết quả Boolean trong kịch bản là giả định. |
| `graduation.outcome_details` | `UNKNOWN` | NOT_FOUND | `UNKNOWN` | False | Chi tiết chuẩn đầu ra chưa được nhóm cung cấp. |
| `limitations.summer_terms` | `Điều kiện mở lớp và học phần hè chưa mô hình hóa; kết quả thận trọng hơn thực tế` | Không có lịch mở lớp trong dữ liệu CTĐT | `UNCONFIRMED` | True |  |
| `limitations.course_offerings` | `Lịch mở chẵn/lẻ theo cột offered_semesters do nhóm cung cấp; chưa có trong văn bản quy chế` | NOT_FOUND | `UNCONFIRMED` | True | GIẢ ĐỊNH (lịch mở chẵn/lẻ theo dữ liệu nhóm) |
| `limitations.corequisite_semantics` | `Song hành = học cùng kỳ hoặc đã/đang học` | Chờ đối chiếu quy chế | `UNCONFIRMED` | True | GIẢ ĐỊNH (song hành được thỏa nếu học cùng kỳ hoặc đã/đang học) |
| `limitations.final_semester_recognition` | `Kỳ cuối khóa khi kế hoạch đăng ký hoàn tất mọi tín chỉ còn thiếu` | Đ9.3, Đ9.4 | `UNCONFIRMED` | True | GIẢ ĐỊNH (nhận diện kỳ cuối khóa) |
| `limitations.exact_105_credit_year` | `Gán năm thứ tư khi đúng 105 tín chỉ tích lũy` | Đ18.1 | `UNCONFIRMED` | True | GIẢ ĐỊNH (đúng 105 tín chỉ thuộc năm thứ tư) |
| `limitations.outcome_details` | `Chi tiết chuẩn đầu ra UNKNOWN; chỉ nhận cờ Boolean trong hồ sơ kịch bản` | NOT_FOUND | `UNKNOWN` | False | Chi tiết đầu ra chưa được cung cấp. |

## UNCONFIRMED/UNKNOWN

- `credit_limits.final_semester.recognition`: `UNCONFIRMED`
- `study_year.exactly_105_credits`: `UNCONFIRMED`
- `academic_warnings.W1.debt_definition`: `UNCONFIRMED`
- `academic_warnings.monte_carlo_scope`: `MODELING_DECISION`
- `graduation.outcome_details`: `UNKNOWN`
- `limitations.summer_terms`: `UNCONFIRMED`
- `limitations.course_offerings`: `UNCONFIRMED`
- `limitations.corequisite_semantics`: `UNCONFIRMED`
- `limitations.final_semester_recognition`: `UNCONFIRMED`
- `limitations.exact_105_credit_year`: `UNCONFIRMED`
- `limitations.outcome_details`: `UNKNOWN`

## GIẢ ĐỊNH cần nhóm xác nhận

- `w1_debt`: Nợ đọng là tín chỉ học phần đã trượt và chưa đạt lại. (`UNCONFIRMED`, modeled=`True`)
- `study_year_boundary`: Đúng 105 tín chỉ gán năm thứ tư. (`UNCONFIRMED`, modeled=`True`)
- `final_semester`: Kỳ cuối khóa khi kế hoạch đăng ký hoàn tất mọi tín chỉ còn thiếu. (`UNCONFIRMED`, modeled=`True`)
- `corequisite_semantics`: Song hành được thỏa nếu học cùng kỳ hoặc đã/đang học. (`UNCONFIRMED`, modeled=`True`)
- `odd_even_offerings`: Lịch mở chẵn/lẻ lấy từ cột offered_semesters do nhóm cung cấp; không có trong văn bản quy chế. (`UNCONFIRMED`, modeled=`True`)

## Hạn chế và phạm vi

- Học kỳ hè và điều kiện mở lớp chưa mô hình hóa; kết quả thận trọng hơn thực tế.
- Học cải thiện chưa mô hình hóa.
- Học kỳ phụ, điều kiện mở lớp, và chuẩn đầu ra chi tiết chưa mô hình hóa.
- Chuẩn đầu ra chi tiết chưa có; chỉ nhận cờ Boolean trong hồ sơ kịch bản.
- Giới hạn đăng ký theo quy chế là ràng buộc chính thức; trần rủi ro là khuyến nghị mềm, không làm mất quyền đăng ký.
