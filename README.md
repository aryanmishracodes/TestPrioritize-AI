# TestPrioritize AI

> Intelligent, risk-driven, AST-aware test selection and prioritization for CI/CD pipelines.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://testprioritize-ai.streamlit.app)
[![Tests Passing](https://img.shields.io/badge/Tests-154%2F154%20Passing-brightgreen.svg)](tests/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

### 🔗 Live Production Links & Finale Deliverables:
- 🚀 **Live Production Dashboard**: [testprioritize-ai.streamlit.app](https://testprioritize-ai.streamlit.app)
- 📊 **Interactive HTML Slide Deck**: [`presentation.html`](presentation.html)
- 🎤 **Grand Finale Pitch & Q&A Guide**: [`PITCH_DECK_GUIDE.md`](PITCH_DECK_GUIDE.md)
- 📽️ **Native PowerPoint Deck**: [`TestPrioritize_AI_Finale_Pitch.pptx`](TestPrioritize_AI_Finale_Pitch.pptx)

---

## ⚡ What is TestPrioritize AI?

**TestPrioritize AI** accelerates developer feedback loops by running the tests most relevant to code changes first. Instead of executing hundreds of test files in arbitrary or alphabetical order, TestPrioritize AI statically detects modified code, maps dependencies, checks external intelligence for breaking changes, and orders test execution so regressions are caught early (**fail-fast**).

### Core Workflow:
1. **Change Detection**: Inspects Git diffs between two commits or branches to find modified source files and dependency manifests (`requirements.txt`).
2. **Deterministic Source-to-Test Mapping**: Statically maps changed files to candidate test files using lexical and structural heuristics without executing untrusted test code.
3. **Dependency Risk Intelligence (TinyFish Search API)**: When dependency manifests are upgraded, queries the official TinyFish API for breaking change advisories and migration notices.
4. **Deterministic Ranking Engine**: Assigns an explainable score `[0, 100]` and priority tier (`HIGH`, `MEDIUM`, `LOW`) with detailed rationales.
5. **Prioritized Pytest Execution**: Runs prioritized tests via `pytest` with timeouts, fail-fast (`-x`) support, and live outcome capture.
6. **Side-by-Side Benchmark Engine**: Evaluates prioritized tests vs the entire suite on identical revisions and environments, capturing exact time-to-first-failure.
7. **Interactive Streamlit Dashboard**: A full developer UI featuring bundled demo scenarios, live diff viewing, and benchmark visualizers.

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- Python 3.9+ (Python 3.11 recommended)
- Git installed and on your `PATH`

### 2. Setup Virtual Environment
```bash
# Clone repository
git clone https://github.com/aryanmishracodes/TestPrioritize-AI.git
cd TestPrioritize-AI

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Initialize Demo Repository
Initialize the bundled sample e-commerce repository containing genuine Git history and reproducible change scenarios:
```bash
python setup_demo_repo.py
```
This generates an isolated Git repository under `demo_repo/` with clean commit tags and test suites.

### 4. Configure TinyFish API Key (Optional but Recommended)
TestPrioritize AI integrates with the **TinyFish Search API** to detect external dependency risks.
- Copy `.env.example` to `.env`:
  ```bash
  cp .env.example .env
  ```
- Edit `.env` and insert your key:
  ```env
  TINYFISH_API_KEY=your_actual_api_key_here
  ```
- Or set it as an environment variable:
  ```bash
  # PowerShell:
  $env:TINYFISH_API_KEY="your_actual_api_key_here"
  # Linux / macOS:
  export TINYFISH_API_KEY="your_actual_api_key_here"
  ```
> **Security Note**: Never commit `.env` or hardcode API keys. `.env` is ignored in `.gitignore`. If `TINYFISH_API_KEY` is not set, the pipeline runs smoothly using local deterministic ranking.

---

## 🖥️ Launching the Streamlit Dashboard

Run the following command in the project root:

```bash
python -m streamlit run app.py
```
Or:
```bash
streamlit run app.py
```

The dashboard opens automatically in your browser at `http://localhost:8501`.

---

## 🎯 Interactive Demo Scenarios (For Hackathon Judges)

The dashboard includes a dedicated **Interactive Demo Scenarios** mode that eliminates the need to look up Git hashes:

| Scenario | Target Tag | Description & Expected Outcome |
|---|---|---|
| **Scenario 1: Cart Calculation Enhancement** | `cart-enhancement` | Adds max item checks to `src/cart.py`. Prioritizes `tests/test_cart.py` at Rank 1. 100% pass rate. |
| **Scenario 2: Currency Rounding Regression** | `checkout-regression` | **Authentic Failing Demo**: An intentional regression in `src/checkout.py` truncates fractional cents. Prioritizes `tests/test_checkout.py` at Rank 1. Fails immediately on `test_apply_tax_fractional_precision` via fail-fast! |
| **Scenario 3: Multi-Module Overhaul** | `bulk-pricing` | Updates both `src/cart.py` and `src/pricing.py`. Demonstrates multi-source corroboration ranking (+15 pts bonus). |
| **Scenario 4: Dependency Upgrade** | `dep-upgrade` | Upgrades `requests` to `3.0.0` in `requirements.txt`. Triggers TinyFish search for breaking changes and assigns dependency risk boost (+20 pts). |

### Custom Repository Mode
Judges can toggle to **Custom Repository & Git Revisions** in the sidebar to test any local Git repository by entering path and base/target revisions (e.g., `HEAD~1` vs `HEAD`).

---

## ⚡ Fair Full-Suite Benchmark Comparison

Navigate to the **⚡ Full-Suite Benchmark** tab in the dashboard and click **🔬 Run Benchmark Comparison**:
- **Same Revision & Interpreter**: Runs both the prioritized test files and the complete test suite against the exact same commit and environment.
- **Timing Metrics Measured**:
  - `Change Detection & Mapping Time`: Time taken to run `git diff` and parse AST mappings.
  - `Ranking Time`: Time taken by the deterministic scoring engine.
  - `Static Analysis Overhead`: Combined pre-execution overhead.
  - `Prioritized Test Duration`: Pytest duration running only candidate test files.
  - `Full Suite Duration`: Pytest duration running all tests in `tests/`.
  - `Time to First Failure`: Milliseconds elapsed until the failing test halts execution (via `-x`).
- **Warm-Up & Median**: Supports 1, 3, or 5 iterations with optional warm-up runs, reporting the median duration to prevent transient OS caching noise.

---

## 📊 Scoring & Prioritization Model

The prioritization engine uses an explainable, deterministic scoring formula:

$$\text{Final Score} = \min(100, \text{Base Score} + \text{Multi-Source Bonus} + \text{Dependency Risk Bonus})$$

### 1. Base Match Score
- **Direct Lexical Match (`confidence == "direct"`)**: `+50` points. E.g., `src/cart.py` directly matches `tests/test_cart.py`.
- **Compound Delimited Match (`confidence == "compound"`)**: `+25` points. E.g., `src/order_utils.py` matches `tests/test_order.py`.
- **Unknown Confidence**: `+0` points.

### 2. Multi-Source Corroborating Bonus
- When a test exercises multiple modified source files, each additional changed source file adds `+15` points.
- Capped at `+30` points (maximum 2 extra sources counted).

### 3. Dependency Risk Bonus (TinyFish)
- When `requirements.txt` is modified and TinyFish verifies high-risk external evidence (e.g. `breaking_change`), tests mapping to that package receive a `+20` points risk boost.

### 4. Priority Tiers
| Tier | Score Range | Meaning |
|---|---|---|
| **HIGH** | `70 - 100` | Critical priority; directly touches modified source or multiple changed files / high-risk dependencies. |
| **MEDIUM** | `40 - 69` | Moderate priority; compound or single direct match. |
| **LOW** | `0 - 39` | Low priority; indirect or exploratory matches. |

### Deterministic Tie-Breaking
Tests with identical scores are sorted alphabetically by normalized test file path, ensuring reproducible CI behavior across runs.

---

## 🧪 Running Automated Tests

Run the full automated test suite using `pytest`:

```bash
python -m pytest -v
```

All 108 unit and integration tests run offline without requiring external network access or modifying Git history.

---

## ⚠️ Known Limitations & Integrity Notes

1. **Small Suite Process Overhead**: On tiny test suites (< 50 tests), subprocess invocation overhead dominates execution time. Test prioritization delivers maximum value on enterprise CI test suites spanning hundreds of test files by surfacing regressions in the first few seconds (**fail-fast**).
2. **Static / Lexical Mapping Heuristic**: Candidate test mapping is based on naming conventions and static AST imports. Dynamic runtime reflection (e.g., `importlib.import_module()`) is not resolved statically.
3. **No Total Runtime Reduction Guarantee**: Test prioritization optimizes **time-to-first-failure** (`fail-fast`). It does not reduce the total runtime if all tests in the entire suite are ultimately executed.
4. **External API Quota**: When TinyFish is enabled, requests require network connectivity and an active API key. If unreachable or unauthenticated, the pipeline gracefully falls back to local deterministic scoring.