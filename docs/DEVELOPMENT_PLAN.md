# Development Plan: TestPrioritize AI

## Problem Statement
In software development teams, test suites grow large and slow over time. Running every test sequentially in continuous integration (CI) causes high wait times and delays PR feedback. When regressions happen, running tests in arbitrary or alphabetical order wastes time executing unrelated tests before hitting the failure.

## High-Level Architecture (Plain English)
The system operates as a four-stage pipeline:
1. **Change Detector (Git Diff)**: Inspects the repository to find exactly which source files and dependency declarations (`requirements.txt`) were modified between two commits or branches.
2. **Test Discovery & Static Mapping (AST)**: Scans the codebase to catalog test files and test functions, mapping each test to the application source code it imports or tests without executing untrusted test code.
3. **Dependency Risk Intelligence**: When third-party packages are upgraded in manifest files, checks for breaking changes, migration notices, or deprecations.
4. **Deterministic Ranking Engine**: Combines direct file changes, related package changes, and dependency risks to assign a priority score to every test. Tests touching modified and high-risk code execute first.

---

## Roadmap & Milestones

### Milestone 1: Initial Repository & Environment Setup (Current)
- Initialize clean repository structure, `.gitignore`, minimal `requirements.txt`, and development documentation.

### Milestone 2: Git Diff & Changed File Detection
- Implement a module to safely call Git CLI via Python standard library (`subprocess`).
- Detect added, modified, deleted source files and dependency manifests.
- Handle edge cases: non-git repository, invalid refs, no changes.
- Add unit tests for diff detection.

### Milestone 3: Test Discovery & Static AST Mapping
- Recursively discover Python test files following standard naming conventions (`test_*.py`, `*_test.py`).
- Parse test files using Python's built-in `ast` module to safely extract test classes, test functions, and imports.
- Conservatively map tests to source files (e.g., name-based match, import match).
- Add unit tests for AST discovery and mapping.

### Milestone 4: Dependency Change & Risk Intelligence (TinyFish Integration Completed)
- Implemented official TinyFish Search REST API client in `tinyfish_client.py`:
  - Authentication via `X-API-Key` header loaded safely from `TINYFISH_API_KEY`.
  - Structured result extraction (`title`, `url`, `snippet`, `site_name`, `position`).
  - Strict URL validation, timeout controls, and graceful error handling (`missing_key`, `timeout`, `http_error`, `invalid_json`).
- Implemented `dependency_intelligence.py`:
  - Detects manifest modifications in `requirements.txt`.
  - Computes version deltas (added, modified, removed packages) between Git revisions.
  - Builds targeted search queries for official release notes and breaking changes.
  - Categorizes evidence into `breaking_change`, `migration_guide`, `release_notes`, and `general_advisory`.
  - Discards unverified items where package name is absent.
- Integrated external findings into `ranking_engine.py`:
  - Verified breaking changes for an upgraded package add `+20` points (`SCORE_DEPENDENCY_RISK`) only to candidate tests that connect to that package.
  - Preserves 100% of local deterministic ranking when TinyFish is disabled or returns no relevant evidence.
- Full test coverage in `tests/test_tinyfish.py` (18 passing tests with mocked network).

### Milestone 5: Deterministic Prioritization Engine (Completed)
- Standalone, explainable scoring engine implemented in `ranking_engine.py`:
  - **Base Weights**:
    - Direct lexical match (`confidence == "direct"`): `+50` points.
    - Compound delimited match (`confidence == "compound"`): `+25` points.
    - Unsupported / unknown confidence: `+0` points (unweighted).
  - **Multi-Source Corroborating Evidence**:
    - Each additional distinct changed source mapped to the same test adds `+15` points.
    - Additional source bonus is strictly capped at `+30` points (maximum 2 extra sources counted).
  - **Scale & Clamping**:
    - Final score clamped to `[0, 100]`.
  - **Priority Tier Thresholds**:
    - `HIGH`: `score >= 70`
    - `MEDIUM`: `40 <= score < 70`
    - `LOW`: `score < 40`
  - **Deterministic Tie-Breaking**:
    - Sorted by `score` descending, then by normalized `test_path` ascending (alphabetical).
  - **Explainability**:
    - Generates human-readable breakdown matching the actual contributing signals.
- Unit tests implemented in `tests/test_ranking_engine.py` (12 passing tests).

### Milestone 6: Pipeline Orchestration & Test Suite Integration (Completed)
- Implemented unified pipeline orchestrator in `pipeline.py`:
  - Coordinates `diff_checker.py`, `test_mapper.py`, `dependency_intelligence.py`, and `ranking_engine.py`.
  - Safely invokes `pytest` via `subprocess` with argument lists (`shell=False`) and timeout protections.
  - Supports fail-fast execution (`-x`) and parses actual pass/fail counts and durations without fabricating results.
  - Provides graceful fallbacks when TinyFish is disabled or unavailable.
  - Returns structured `PipelineResult` containing changes, candidate mappings, dependency findings, rankings, and execution outcomes.
- Unit tests implemented in `tests/test_pipeline.py` (11 passing tests with mocked subprocess).

### Milestone 7: Streamlit Interactive Dashboard (Completed)
- Implemented comprehensive, production-grade developer UI in `app.py`:
  - **Header & Readiness**: Tagline "Run the right tests first." with live environment checks (TinyFish key status, Git availability).
  - **Repository & Git Controls**: Sidebar inputs for repository path, base/target revisions with guidance for selecting local commits, timeout sliders, TinyFish toggles, and pytest execution settings.
  - **Run Orchestration**: "Analyze and Prioritize Tests" button invoking `pipeline.run_pipeline` with session state caching to prevent spurious reruns.
  - **Results Metrics**: 5 executive summary metric cards (Changed files, Prioritized tests, Executed & Passed tests, Execution duration, TinyFish status).
  - **Changed Files Panel**: Clean table with relative paths, change types (added, modified, deleted), and rename tracking.
  - **Prioritized Tests Table**: Visual badges for rank (`#1`, `#2`), priority tier (`HIGH`, `MEDIUM`, `LOW`), computed score `[0, 100]`, contributing source files, and detailed rationale breakdown.
  - **TinyFish Intelligence Showcase**: Dedicated high-visibility panel displaying manifest diffs, queried package names, evidence categories (`breaking_change`, `migration_guide`, `release_notes`), verified source URLs, snippets, and explanation of the `+20` points risk score bonus.
  - **Pytest Output Viewer**: Collapsible real-time execution logs with stdout, stderr, execution duration, and exit codes.
  - **Transparency & Documentation**: Embedded architectural guide explaining lexical mapping, deterministic scoring, and real-world limitations.
- Verified dashboard accessibility, session state persistence, and error resilience via unit tests in `tests/test_app.py` and live browser testing.

### Milestone 8: Interactive Demo Scenarios & Fair Benchmark Suite (Completed)
- **Isolated Demo Repository (`setup_demo_repo.py`)**:
  - Initialized isolated sample repository under `demo_repo/` with clean commit history, domain modules (`cart.py`, `checkout.py`, `pricing.py`, `user_service.py`), and 31 unit tests.
  - Configured 4 reproducible scenarios with authentic Git tags (`base`, `cart-enhancement`, `checkout-regression`, `bulk-pricing`, `dep-upgrade`).
  - Implemented an **authentic failing regression demonstration**: integer truncation in `src/checkout.py` legitimately detected by `tests/test_checkout.py::test_apply_tax_fractional_precision` via fail-fast execution.
- **Fair Side-by-Side Benchmark Engine (`benchmark_runner.py`)**:
  - Evaluates prioritized test subset vs. entire test suite against the exact same commit and environment.
  - Measures change detection time, AST mapping time, deterministic ranking time, and pytest execution durations.
  - Parses structured JUnit XML to capture per-test timings, exit codes, and exact time-to-first-failure.
  - Supports multiple iterations with warm-up runs, reporting median durations to eliminate OS caching noise.
- **Dashboard Redesign for Judge Workflow (`app.py`)**:
  - Added dedicated **Interactive Demo Scenarios** mode preselecting scenarios without typing commit hashes.
  - Added live `git diff` preview expander with syntax highlighting.
  - Replaced pyarrow/pandas-dependent UI tables with native Markdown tables to prevent host environment version conflicts.
  - Added dedicated **Full-Suite Benchmark** tab with side-by-side comparison tables and honest interpretation guidelines.
- **Automated QA & Verification (`tests/test_demo_and_benchmark.py`)**:
  - Added 8 focused integration tests covering scenario definitions, authentic regression detection, JUnit XML parsing, and benchmark metrics.
  - Total test suite expanded to 108 passing tests with 0 failures and 0 warnings.
