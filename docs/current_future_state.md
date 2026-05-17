# Current State vs Future State Analysis

## Current State (As-Is)

- Warehouse inspection is handwritten on physical RGA and rejected-parts forms.
- Back-office staff manually re-enter each line into BMS DRET.
- Typical effort is about 5 minutes per line (95 minutes for 19-line sample in POC).
- Process delay is measured in days due to physical document movement and re-entry workload.
- Rejection reasons are inconsistent across users, increasing dealer disputes and re-work.
- Auditability is weak because paper forms can be misplaced or interpreted inconsistently.

## Future State (To-Be)

- Warehouse uploads two images (RGA + rejected list) from phone/scanner.
- OCR digitizes handwritten content in seconds.
- Open-source LLM extracts line-level data and emits structured JSON for BMS integration.
- Rejection code mapping preserves inspector intent using deterministic lookup.
- Confidence routing applies high-confidence lines automatically and sends low-confidence lines to review.
- Standardized rejection narratives improve dealer communication and reduce disputes.

## Measurable Targets from Requirement Deck

- 80%+ reduction in manual entry.
- 95 minutes saved per 19-line RGA sample.
- 100% digital audit coverage for processed lines.
- 0 additional headcount required for scaling volume.

## Rollout Strategy

- Phase 1: Shadow mode (parallel run, no auto-apply).
- Phase 2: Assisted mode (human confirm/edit).
- Phase 3: Autonomous mode (threshold-based auto-apply).
- Phase 4: Optimize and expand beyond CECO scope.
