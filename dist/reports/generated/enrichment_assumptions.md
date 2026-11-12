# Curriculum enrichment assumptions

Label: **GIẢ ĐỊNH (suy từ CTĐT)**. `courses.csv` remains unchanged; derived fields are attached at load time.

## Assumptions requiring confirmation against the PDF

- **Specialization:** Suffix match on the exact course_id; suffixes remain part of the course key.
- **Elective slots:** Fields are derived from course_id, course_type, group, and offered_semesters; courses.csv remains unchanged.
- **HP017:** Both 2-credit alternatives are assigned to the same HK3 slot. Members: `HP017-A`, `BUA319`.
- **Graduation:** choose one of HP048 alternatives for 5 credits in semester 8.
- **Course-code origin:** prefixes `['POL', 'SSH', 'BUA', 'MKT', 'PHE', 'QPAD']` are marked PDF; prefixes `['HP']` remain unverified.
- **Offering:** `offered_semesters` uses values ['odd', 'even', 'both']; parity interpretation is labeled `GIẢ ĐỊNH (suy từ CTĐT)`. Academic-term parity is only an inference; summer terms are not modeled.
- **Strict prerequisite:** prior course must be completed — GIẢ ĐỊNH (chờ đối chiếu quy chế).
- **Corequisite:** peer must be completed, in progress, or eligible in the same target term — GIẢ ĐỊNH (chờ đối chiếu quy chế).
- **Prerequisite completeness:** `UNCONFIRMED`; absence of a row is not confirmation that a course has no prerequisite.

## Course IDs needing confirmation

- `TEAM_ASSIGNED_OR_UNVERIFIED`: `HP007`, `HP008`, `HP009`, `HP010`, `HP011`, `HP012`, `HP013`, `HP014`, `HP015`, `HP016-A`, `HP016-B`, `HP017-A`, `HP018-A`, `HP018-B`, `HP018-C`, `HP019-A`, `HP019-B`, `HP022`, `HP023`, `HP024`, `HP025`, `HP026`, `HP027`, `HP028`, `HP029`, `HP030`, `HP031-A`, `HP031-B`, `HP031-C`, `HP031-D`, `HP032`, `HP033`, `HP034`, `HP035`, `HP036`, `HP037`, `HP038`, `HP039-IS`, `HP039-NW`, `HP039-SE`, `HP040-IS`, `HP040-NW`, `HP040-SE`, `HP041-IS`, `HP041-NW`, `HP041-SE`, `HP042-IS`, `HP042-NW`, `HP042-SE`, `HP043-IS`, `HP043-NW`, `HP043-SE`, `HP044-IS`, `HP044-NW`, `HP044-SE`, `HP045-IS-A`, `HP045-IS-B`, `HP045-NW-A`, `HP045-NW-B`, `HP045-SE-A`, `HP045-SE-B`, `HP046-IS-A`, `HP046-IS-B`, `HP046-NW-A`, `HP046-NW-B`, `HP046-SE-A`, `HP046-SE-B`, `HP047-IS-A`, `HP047-IS-B`, `HP047-NW-A`, `HP047-NW-B`, `HP047-SE-A`, `HP047-SE-B`, `HP048-A`, `HP048-B`
- `UNKNOWN`, `source=NOT_FOUND`: none

## Derived fields and rules

| Field | Rule derived from source | Label/status |
|---|---|---|
| `specialization` | Match exact course ID suffix `-SE`, `-IS`, or `-NW`; otherwise `common`. | `GIẢ ĐỊNH (suy từ CTĐT)` |
| `counts_toward_total` | False for groups `['GDTC và QP-AN ngoài 130 tín chỉ']`; true otherwise. | `GIẢ ĐỊNH (suy từ CTĐT)` |
| `elective_slot` | Prefix/exact-ID assignment from `courses_enrichment.yaml`; suffixes remain part of `course_id`. `HP017-A` and `BUA319` are one assumed slot `HP017`: Both 2-credit alternatives are assigned to the same HK3 slot. | `GIẢ ĐỊNH (suy từ CTĐT)` |
| `slot_required_credits` | Use configured required credits for each assigned slot, independent of course IDs. | `GIẢ ĐỊNH (suy từ CTĐT)` |
| `graduation_slot` | `HP048`; select 1 alternative for 5 credits in semester 8; counts as mandatory in the official HK8 total. | `GIẢ ĐỊNH (suy từ CTĐT)` |
| `code_source` | Prefixes `['POL', 'SSH', 'BUA', 'MKT', 'PHE', 'QPAD']` are marked `PDF`; prefixes `['HP']` are `TEAM_ASSIGNED_OR_UNVERIFIED`; other prefixes remain `UNKNOWN`. | `GIẢ ĐỊNH (suy từ CTĐT)` |
| `offering_rule` | Map `offered_semesters` values `odd/even/both` to academic semester parity. This calendar is not present in the official plan. | `GIẢ ĐỊNH (suy từ CTĐT)` |
| `enrichment_label` | Copy the top-level enrichment assumption label to every loaded row. | `GIẢ ĐỊNH (suy từ CTĐT)` |

### Configured credit requirement for each elective slot

| Slot | Required credits |
|---|---:|
| `HP016` | 2 |
| `HP017` | 2 |
| `HP018` | 2 |
| `HP019` | 2 |
| `HP031` | 3 |
| `HP045-IS` | 3 |
| `HP045-NW` | 3 |
| `HP045-SE` | 3 |
| `HP046-IS` | 3 |
| `HP046-NW` | 3 |
| `HP046-SE` | 3 |
| `HP047-IS` | 3 |
| `HP047-NW` | 3 |
| `HP047-SE` | 3 |
| `HP048` | 5 |

Slot identities, prefixes, and the special HP017 pairing are inferred from the course table and must be checked against the PDF.
The `offered_semesters` mapping is a planning assumption, not a confirmed NTU course-offering calendar.

### Prerequisite relationship assumptions

- `tiên quyết`: prior course must be completed — `GIẢ ĐỊNH (chờ đối chiếu quy chế)`.
- `song hành`: peer must be completed, in progress, or eligible in the same target term — `GIẢ ĐỊNH (chờ đối chiếu quy chế)`.
- `prerequisite_completeness`: `UNCONFIRMED`; a missing prerequisite row is not confirmed to mean no prerequisite.

## Known limitations

- The source table does not establish a semester offering calendar; `odd`/`even` is interpreted as term parity only.
- Summer terms are not modeled.
- Retake limits, academic-warning thresholds, and per-term credit caps are `UNKNOWN`, `source=NOT_FOUND`.
