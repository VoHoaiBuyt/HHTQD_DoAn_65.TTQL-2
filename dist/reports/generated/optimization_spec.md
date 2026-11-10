# Optimization specification — scenario v2

Nguồn chương trình: OFFICIAL (NTU). Kịch bản đầu vào: SCENARIO; đặc trưng tuyển sinh/nhân khẩu học: REAL (UCI-697).

## Objective

`maximize Σ[c_i p_i - γ c_i(1-p_i) + β u_i] x_i`, where `p_i = clip(p_student × exp(-λ max(0, units(L)-6)) × r_retake(i), 0, 1)`.
Here `units(L)=floor(L/mean_credits+0.5)` and `L` is actual selected credits; every feasible integer L is solved separately so the model stays linear.
`c[(1+γ)p-γ]` has break-even `p*=γ/(1+γ)`; with γ=1, p*=0.5. For p<p*, expected-credit utility is negative unless βu compensates.
Defaults β=0.125, γ=1, λ=0.1, 6-unit threshold, δ=0.5, and retake multipliers {0.9, 1.0, 1.1} are GIẢ ĐỊNH; mapping is first retake=0.9, repeated attempt=1.1, non-retake=1.0.

## Unlock value

`u_i` is the sum of not-completed strict-prerequisite descendant credits discounted by `δ^distance`, plus remaining elective/graduation slot credits where relevant.
Official strict prerequisite edges: 14. Nonzero prerequisite-only u_i: `{"HP024": 5.25, "HP028": 1.5, "HP029": 7.5, "POL307": 3.0, "POL308": 2.0, "POL309": 2.0}`.
Most courses have no strict-prerequisite descendants; unlock value is concentrated, not a general difficulty or course-value score.

## Constraints and outputs

- Binary selection is restricted to eligible courses, official regulatory credit limits, course offering, prerequisites, corequisites, and at most one course per elective slot.
- Mandatory failed-course retakes are hard constraints unless their total credits exceed cmax; such a conflict yields `best_effort`, a regulatory-conflict flag, and an advisor warning.
- `risk_cap_mode` supports off/soft/hard; the main three-plan output uses off and computes `risk_cap_exceeded` afterward. The Fmax grid is scanned post-hoc. P(Dropout) and Fmax are advisory and do not limit registration rights.
- W1/W2 warning probabilities use exact dynamic programming over credits. Courses are independent pass/fail events (limitation); no course-difficulty multiplier is used.
- best_effort and risk-cap/regulatory conflicts always carry explicit risk language and an academic-advisor recommendation; they never use the `An toàn` label.
- Final-semester cases A (regulation-limited) and B (completion plan) are evaluated separately; B is only valid if all missing courses are eligible and offered.

## Limitations and unresolved assumptions

- Corequisite meaning and prerequisite completeness remain UNCONFIRMED.
- Offering parity is inferred from `offered_semesters`; summer offerings and class availability are not modeled.
- Extension-assumption probabilities apply the HK1 stratum estimate beyond T1 and are not validated as a later-term prediction.
- The 130-credit program credit count and official course/pre-requisite rows are not generated or inferred by this optimizer.
