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

### Milestone 4: Dependency Change & Risk Intelligence
- Detect version changes in dependency manifests (e.g., package `X` upgraded from `v1.0.0` to `v2.0.0`).
- Implement external search client to query dependency intelligence (e.g., TinyFish search) with graceful fallback and offline handling.
- Classify findings into breaking changes, migration guides, and release notes.
- Add unit tests for dependency intelligence and error handling.

### Milestone 5: Deterministic Prioritization Engine
- Formulate a transparent, rule-based scoring system:
  - Highest: direct source code modification.
  - High: test file itself modified.
  - Medium: related module in same package directory.
  - Medium/High: dependency with breaking changes.
  - Baseline: untouched tests.
- Produce ordered test execution lists with clear, human-readable explanations.
- Add unit tests verifying deterministic ordering.

### Milestone 6: CLI Runner & Test Suite Integration
- Implement CLI tool (`run_prioritized.py`) supporting:
  - Dry-run / preview mode (showing ranking and rationale without running tests).
  - Execution mode (invoking pytest with fail-fast `-x` flag in prioritized order).

### Milestone 7: Regression Benchmark & Demonstration
- Build an isolated benchmark repository demonstrating time-to-first-failure reduction compared to default test execution order.
