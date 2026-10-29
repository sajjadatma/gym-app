# Motion Playwright Failures Investigation Plan

> **For agentic workers:** Use the native inline execution method selected by the user. Complete each verification step before committing.

**Goal:** Resolve or accurately classify the 17 Playwright failures observed after the ASCORA motion-system changes, without weakening tests or changing unrelated behavior.

**Architecture:** Compare the uncommitted feature diff with baseline `a918893`, reproduce affected tests, and fix only confirmed motion regressions or legitimate test synchronization/fixture defects. Preserve the CSS-first M3 motion tokens and reduced-motion behavior.

**Tech Stack:** React, CSS, Vite, Playwright, Bun, GitHub Actions.

**Spec:** User request in this session: investigate all 17 failures, fix confirmed regressions, run full verification, visually inspect, commit and push feature branch, and do not promote production.

## Global Constraints

- Keep Standard motion for routine feedback and Expressive spatial motion selective.
- Preserve reduced-motion accessibility, keyboard behavior, mobile performance, business logic, and workflows.
- Do not increase timeouts blindly, disable tests, weaken assertions, or remove animations to get green tests.
- Do not bypass GitHub branch protection or production safeguards.

## Review Focus

- Menu/item click detachment: distinguish scroll-driven close behavior from entrance-animation timing.
- Authenticated role mismatch: verify environment/storage-state identity before blaming UI changes.
- Field dimensions: compare baseline declarations and measured controls at each viewport/theme.
- Strict or stale locators: align locators with rendered semantics without weakening expected behavior.
- Date picker and archive fixture setup: verify network/data readiness and deterministic selectors.

---

### Task 1: Capture and classify failures

**Files:** Playwright report output; no product-code changes.

- [ ] Run the full Playwright suite with a machine-readable report and record every failing test and error.
- [ ] Group failures by observed root cause and compare affected selectors/styles against `a918893`.
- [ ] Reproduce representative failures individually and identify baseline/environment-dependent behavior.

### Task 2: Fix only confirmed issues

**Files:** Only source/test files implicated by Task 1.

- [ ] Add or update a focused regression test for each confirmed motion regression or test-synchronization defect.
- [ ] Verify the regression test fails for the diagnosed reason before applying the smallest correction.
- [ ] Preserve M3 timings, reduced-motion behavior, keyboard support, and workflows.

### Task 3: Verify and review

**Files:** No further scope expansion.

- [ ] Run affected tests, the full Playwright suite, unit tests, lint, TypeScript/build, and a visual browser check.
- [ ] Review the final diff for unrelated changes and resolve all review findings.

### Task 4: Commit and push

- [ ] Commit verified changes on `feat/standard-motion-system`.
- [ ] Push the feature branch without bypassing branch protection.
- [ ] Report commit SHA and observed CI/CD status; do not run production promotion.
