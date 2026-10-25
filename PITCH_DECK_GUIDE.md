# TestPrioritize AI — HackIIITD Grand Finale Pitch & Presentation Guide

> **Quick Access**: Open [`presentation.html`](presentation.html) in any browser (Chrome, Edge) and press `F11` for a fullscreen presentation slide deck. Use `Space` / `Arrow Keys` to navigate and `N` to toggle speaker notes.

---

## 1. The 5 Core Pointers for the Grand Finale Judges

### Pointer 1: Solution Workflow
1. **Developer Code Change**: A developer pushes a PR or makes local changes to source files (e.g., `src/checkout.py`).
2. **Unified Git Diff Ingestion**: TestPrioritize AI parses the git diff to identify modified file paths, altered function line ranges, and behavioral diff keywords.
3. **Bidirectional AST Code Mapping**: In < 5 milliseconds, the engine constructs an in-memory Abstract Syntax Tree without executing code, traversing:
   - **Direct tests**: Tests matching the module name.
   - **Downstream imports**: Tests importing the changed file.
   - **Upstream dependencies**: Files that the changed file imports (e.g., `checkout.py` imports `cart.py`), pulling in related test suites.
4. **Deterministic Risk Scoring**: Assigns transparent scores (0–100) and risk tiers (`HIGH`, `MEDIUM`, `LOW`) based on AST call depth, diff function matching, and behavioral parameter overlap.
5. **External Intelligence (TinyFish)**: If `requirements.txt` was modified, queries TinyFish REST API for CVEs and breaking changes, boosting risk scores by +20 pts.
6. **Isolated Pytest Orchestration**: Executes prioritized tests in a clean temporary directory with fail-fast (`-x`) enabled, streaming microsecond-accurate monotonic timing events.

---

### Pointer 2: Tech Stack (Frontend & Backend)
- **Core Engine (Backend)**: Python 3.11, Python `ast` module (in-memory syntax tree parsing), `subprocess` (isolated process orchestration), `pytest` with custom embedded hook listeners.
- **External Risk Intelligence**: Official TinyFish Search REST API (`api.search.tinyfish.ai`) via `requests`, dotenv secrets management, and offline fallback handlers.
- **Frontend Dashboard**: Streamlit web application styled with a custom Linear/Vercel-inspired monochrome dark design system (JetBrains Mono typography, tabular metrics, responsive controls, zero emojis).
- **Test Automation Suite**: 146 automated unit and integration tests with a 100% pass rate.

---

### Pointer 3: Execution of MVP & Architecture
- **Pristine Process Isolation**: Standard and prioritized benchmark runs execute in separate, isolated temporary clones using `shutil.copytree` and `tempfile.TemporaryDirectory`. Neither run can poison or mutate global repo state.
- **Real Pytest Events**: Execution outcomes (duration, sequence number, pass/fail, error tracebacks) are captured directly from real Pytest subprocess events, never simulated or cached.
- **User-Controlled Selection**:
  - **Top-N Mode**: Runs the top $N$ ranked candidates (e.g. Top 4).
  - **Manual Mode**: Allows selecting specific pytest node IDs with Select All / Clear Selection.
  - Symmetrical subsetting guarantees both standard and prioritized benchmarks run the exact same subset.

---

### Pointer 4: Technical Feasibility & Deep Backend Workflow
- **Zero LLM Hallucination / Latency**: The static analysis is 100% deterministic, running in under 5 milliseconds. It never hallucinates non-existent tests and never slows down CI.
- **High-Resolution Microsecond Timers**: Employs `time.perf_counter()` to capture sub-millisecond execution duration and time-to-first-failure ($T_{\text{fail}}$).
- **Sub-module Auto-Initialization**: Self-heals on fresh cloud deployment: discovers if any of the 4 demo repos are missing or unpopulated and automatically initializes git commits, branches, and scenarios.

---

### Pointer 5: Progress & Team Contributions
- **Complete Working System**: Fully functional end-to-end prototype deployed to GitHub (`aryanmishracodes/TestPrioritize-AI.git`) and live on Streamlit Cloud.
- **4 Diverse Demo Repositories**: 83 genuine unit tests across E-Commerce (32 tests), Authentication (17 tests), Payment Gateway (17 tests), and Booking Platform (17 tests).
- **Proven Failure Acceleration**: Demonstrates a **13-test acceleration** (#1 vs #14) and **85.5% faster detection** on real regression bugs.

---

## 2. Slide-by-Slide Presentation Pitch Script (3 to 5 Minutes)

### Slide 1: Title & Hook (30 seconds)
> "Good morning respected judges. We are proud to present **TestPrioritize AI** — an intelligent, deterministic test orchestration engine designed to solve the single largest bottleneck in modern software engineering: waiting for slow continuous integration test feedback. 
> 
> In this presentation, we will demonstrate how combining static Abstract Syntax Tree analysis, bidirectional dependency tracing, and external risk intelligence cuts regression detection time by up to **85%**."

---

### Slide 2: The High Cost of Blind Test Execution (30 seconds)
> "Every engineering team faces this problem daily: CI/CD test runners like Pytest run tests alphabetically or arbitrarily. If a developer pushes a bug in checkout logic, `test_checkout.py` might be test number 800 in the suite.
> 
> The developer context-switches, forgets what they wrote, and 40 minutes later gets an email that the pipeline failed. Companies burn millions of dollars in GitHub Actions compute running passing tests before finally hitting the broken test at the end."

---

### Slide 3: Our Technical Moat — Bidirectional AST Mapping (45 seconds)
> "Our core technical breakthrough is **Bidirectional AST Dependency Mapping**. Traditional tools only look downstream — who imports the changed file. 
> 
> But what if `src/checkout.py` changes, and it imports `src/cart.py`? If checkout breaks cart assumptions, cart tests might fail! Our engine traverses upstream imports as well, mapping both `test_checkout.py` and `test_cart.py`. 
> 
> Furthermore, we parse the unified git diff to identify exact modified function lines, scoring test functions that exercise the changed logic ahead of unrelated tests."

---

### Slide 4: End-to-End Execution Pipeline (30 seconds)
> "Here is our 5-stage architecture:
> 1. **Git Ingestion**: Parses unified diffs and changed file hunks.
> 2. **Static AST Analysis**: Traverses the syntax graph in under 3 milliseconds — zero LLM hallucination, zero runtime cost.
> 3. **Deterministic Ranking Engine**: Computes transparent scores from 0 to 100 into High, Medium, and Low risk tiers.
> 4. **Pristine Pytest Orchestration**: Runs the prioritized suite in temporary isolated clones with fail-fast enabled.
> 5. **External Intelligence**: Connects to the TinyFish REST API for dependency CVEs and breaking changes."

---

### Slide 5: The Benchmark Proof — 13 Tests Faster Failure (45 seconds)
> "We don't just claim this works — we benchmarked it live. 
> 
> On our 32-test E-Commerce platform, we seeded a currency precision bug into `checkout.py`. Under standard alphabetical execution, the bug was caught at **test #14** because 13 passing cart tests ran first. 
> 
> Under our Prioritized AST Mode, the exact same regression was surfaced at **test #1** — moving 13 tests ahead, saving **85.5%** of the time-to-first-failure. And our static analysis overhead was just **0.003 seconds**."

---

### Slide 6: User-Controlled Test Selection (30 seconds)
> "We also give developers complete agency with **Test Selection**:
> - **Top-N Mode**: Run only the top 3 or top 5 most critical tests for an ultra-fast pre-commit check.
> - **Manual Selection**: Select specific test cases using a granular checklist with one-click 'Select All' and 'Clear Selection'.
> - Symmetrical execution ensures both standard and prioritized benchmarks run the exact same subset, accompanied by transparent subset warning banners."

---

### Slide 7: TinyFish External Intelligence Integration (30 seconds)
> "Third-party dependencies are a frequent source of sudden CI failures. We integrated the official **TinyFish Search REST API**. 
> 
> When `requirements.txt` changes, our pipeline queries TinyFish for breaking changes, migration notes, and CVE advisories. If a breaking change is verified in a library like Flask 3.0, tests exercising that library receive an automatic **+20 point risk boost**."

---

### Slide 8: 4 Production-Grade Demo Repositories (30 seconds)
> "To prove our system generalizes beyond a toy example, we built 4 independent, production-grade repositories with **83 genuine unit tests**:
> 1. **E-Commerce Platform**: Cart calculations, checkout precision, and inventory limits.
> 2. **Authentication Service**: Token expiration, password hashing, and RBAC permissions.
> 3. **Payment Gateway**: Credit card Luhn validation, refunds, and invoice totals.
> 4. **Booking Platform**: Slot scheduling, rate calculations, and customer alerts."

---

### Slide 9: Software Engineering Rigor (30 seconds)
> "Our engineering rigor speaks for itself:
> - **146 automated tests with a 100% pass rate**.
> - Clean monochrome **Linear and Vercel-inspired dark UI** designed for professional developer tooling.
> - **100% pure static analysis**: We parse syntax trees safely in memory without executing untrusted user code."

---

### Slide 10: Conclusion & Business Impact (30 seconds)
> "TestPrioritize AI delivers immediate ROI:
> - Catches regressions in seconds instead of minutes.
> - Cuts failing build compute costs by up to 50%.
> - Preserves developer flow state and velocity.
> 
> It is ready for production as a GitHub Action or local CLI. Thank you, and we'd love to take you through the live demonstration!"

---

## 3. Anticipated Judge Questions & Bulletproof Answers

#### Q1: "Why use AST instead of an LLM to prioritize tests?"
> **Answer**: "Speed, cost, and determinism. An LLM takes 2 to 5 seconds, costs API tokens per PR, and can hallucinate tests that don't exist. Our AST engine parses Python syntax trees in **under 3 milliseconds**, costs zero dollars, and is **100% deterministic and mathematically reproducible**."

#### Q2: "What happens if a test fails due to an indirect dependency?"
> **Answer**: "That is exactly why we built **Bidirectional AST Mapping**. If `checkout.py` changes, we don't just map `test_checkout.py`. We parse `checkout.py`'s imports and discover it relies on `cart.py`. We map `test_cart.py` with a compound dependency score (+25 pts). Both direct and indirect test suites are prioritized ahead of unrelated tests."

#### Q3: "Does prioritization modify the original codebase or test files?"
> **Answer**: "Never. All benchmarks run in strictly isolated temporary clones using `shutil.copytree` and `tempfile.TemporaryDirectory`. When the run finishes, the temporary directory is discarded. The original repository is never modified."

#### Q4: "How does this integrate into existing CI/CD pipelines like GitHub Actions?"
> **Answer**: "We built `pipeline.py` to be invoked directly via CLI: `python pipeline.py --base HEAD~1 --target HEAD --fail-fast`. It exits with standard exit code 0 on pass, 1 on test failure, and generates a structured JSON report that can post comments directly on GitHub PRs."

---

## 4. Live Demo Walkthrough Script (2 Minutes)

1. **Open the Dashboard**: `http://localhost:8501`.
2. **Showcase Benchmark Acceleration**:
   - Select **E-Commerce Platform** and the **Currency Rounding Bug** scenario.
   - Click **Execute Pipeline**.
   - Point out the metrics:
     > *"Notice here: In standard alphabetical mode, the failure occurred at test #14. In our prioritized AST mode, the failure was caught at test #1. We saved 85% of the time-to-first-failure."*
3. **Showcase AST Dependency Evidence**:
   - Scroll to **Section B**:
     > *"Here you can see the AST dependency card showing that `checkout.py` imports `cart.py`, which is why cart tests were pulled into the candidate plan."*
4. **Showcase User-Controlled Selection**:
   - In the sidebar under **Test Selection Strategy**, select **Top N Ranked Tests** and set $N=4$.
   - Open **Execution Plan Preview** to show the 4 planned tests.
   - Click **Execute Pipeline**.
   - Point out the **Test Subset Active Notice** banner:
     > *"Notice that exactly 4 tests ran, and the subset warning informs the engineer that unselected tests were not executed."*
