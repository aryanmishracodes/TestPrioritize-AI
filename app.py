"""
app.py
Part of TestPrioritize AI.

Production-grade Developer Platform Dashboard for TestPrioritize AI:
- Visual Identity: Dense, restrained, engineering-focused interface inspired by Linear and Vercel.
- Pre-configured reproducible demo scenarios with authentic failing regression.
- Custom repository and revision comparison.
- Hybrid AST import extraction and deterministic test ranking.
- External dependency risk intelligence via TinyFish Search REST API.
- Live pytest execution with fail-fast (-x) and JUnit XML duration capture.
- Fair side-by-side Full-Suite vs Prioritized benchmark comparison.
"""

import html
import os
import sys
import time
from typing import Any, Dict, List, Optional

import streamlit as st

from benchmark_runner import BenchmarkComparison, run_benchmark_comparison
from demo_scenarios import (
    DEMO_REPO_PATH,
    DemoScenario,
    checkout_scenario_target,
    ensure_demo_repo_exists,
    get_demo_scenarios,
    get_scenario_diff,
)
from diff_checker import FileChange
from pipeline import (
    STATUS_ERROR,
    STATUS_GIT_ERROR,
    STATUS_NO_CANDIDATE_TESTS,
    STATUS_NO_CHANGES,
    STATUS_SUCCESS,
    STATUS_TEST_FAILURE,
    STATUS_TIMEOUT,
    PipelineResult,
    run_pipeline,
)
from ranking_engine import (
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    SCORE_COMPOUND_MATCH,
    SCORE_DEPENDENCY_RISK,
    SCORE_DIRECT_MATCH,
    RankedItem,
)
from tinyfish_client import get_api_key

# Page configuration
st.set_page_config(
    page_title="TestPrioritize AI — Test Intelligence & Prioritization",
    page_icon="T",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Design System CSS (Linear / Vercel / Datadog Inspired)
# ============================================================================

st.markdown("""
<style>
    /* Global Reset & Base Typography */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background-color: #09090B !important;
        color: #FAFAFA !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }

    [data-testid="stHeader"] {
        background-color: #09090B !important;
        border-bottom: 1px solid #1E1E22;
    }

    [data-testid="stSidebar"] {
        background-color: #0C0C0E !important;
        border-right: 1px solid #1E1E22 !important;
    }

    /* Brand Header in Sidebar */
    .brand-container {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 0.25rem 0 1rem 0;
        border-bottom: 1px solid #1E1E22;
        margin-bottom: 1rem;
    }
    .brand-mark {
        width: 24px;
        height: 24px;
        background: #2563EB;
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        font-size: 13px;
        color: #FFFFFF;
        letter-spacing: -0.05em;
    }
    .brand-text {
        font-size: 0.95rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #FAFAFA;
    }
    .brand-sub {
        font-size: 0.68rem;
        color: #71717A;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 1px;
    }

    /* Page Header */
    .page-title {
        font-size: 1.45rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: #FAFAFA;
        margin-bottom: 0.2rem;
    }
    .page-subtitle {
        font-size: 0.85rem;
        color: #A1A1AA;
        margin-bottom: 1.1rem;
    }

    /* Context Bar */
    .context-bar {
        background: #111114;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        padding: 0.6rem 0.9rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.78rem;
        color: #A1A1AA;
        margin-bottom: 1.25rem;
    }
    .context-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .context-label {
        color: #71717A;
        text-transform: uppercase;
        font-size: 0.68rem;
        letter-spacing: 0.05em;
    }
    .context-value {
        font-family: 'JetBrains Mono', monospace;
        color: #E4E4E7;
        font-size: 0.75rem;
    }
    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
    }
    .dot-ready { background-color: #10B981; }
    .dot-warning { background-color: #F59E0B; }
    .dot-danger { background-color: #EF4444; }

    /* Operational Summary Metrics Row */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 1px;
        background: #1E1E22;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        overflow: hidden;
        margin-bottom: 1.25rem;
    }
    .metric-cell {
        background: #0C0C0E;
        padding: 0.85rem 1rem;
    }
    .metric-cell-label {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #71717A;
        font-weight: 500;
        margin-bottom: 0.35rem;
    }
    .metric-cell-value {
        font-family: 'Inter', sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        color: #FAFAFA;
        letter-spacing: -0.03em;
        font-variant-numeric: tabular-nums;
    }
    .metric-cell-sub {
        font-size: 0.72rem;
        color: #71717A;
        margin-top: 0.2rem;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Status Notifications */
    .alert-banner {
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.82rem;
        line-height: 1.4;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: flex-start;
        gap: 10px;
    }
    .alert-success {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #6EE7B7;
    }
    .alert-danger {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #FCA5A5;
    }
    .alert-warning {
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: #FCD34D;
    }
    .alert-info {
        background: rgba(37, 99, 235, 0.08);
        border: 1px solid rgba(37, 99, 235, 0.3);
        color: #93C5FD;
    }

    /* Engineering Data Table */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8rem;
        margin-bottom: 1.25rem;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        overflow: hidden;
    }
    .data-table th {
        background: #111114;
        color: #71717A;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 600;
        text-align: left;
        padding: 0.65rem 0.85rem;
        border-bottom: 1px solid #1E1E22;
    }
    .data-table td {
        background: #0C0C0E;
        color: #D4D4D8;
        padding: 0.65rem 0.85rem;
        border-bottom: 1px solid #18181B;
        vertical-align: top;
    }
    .data-table tr:last-child td {
        border-bottom: none;
    }
    .data-table tr:hover td {
        background: #111114;
    }

    /* Monospace Code & Path Styles */
    .mono-cell {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.76rem;
        color: #E4E4E7;
        word-break: break-all;
    }
    .mono-num {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 0.8rem;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 1px 7px;
        border-radius: 3px;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        font-family: 'Inter', sans-serif;
    }
    .badge-high {
        background: rgba(239, 68, 68, 0.12);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.35);
    }
    .badge-med {
        background: rgba(245, 158, 11, 0.12);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }
    .badge-low {
        background: rgba(59, 130, 246, 0.12);
        color: #60A5FA;
        border: 1px solid rgba(59, 130, 246, 0.35);
    }
    .badge-neutral {
        background: #18181B;
        color: #A1A1AA;
        border: 1px solid #27272A;
    }
    .badge-success {
        background: rgba(16, 185, 129, 0.12);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }

    /* Evidence & Finding Cards */
    .evidence-card {
        background: #0C0C0E;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }
    .evidence-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.4rem;
    }
    .evidence-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #FAFAFA;
    }
    .evidence-snippet {
        font-size: 0.78rem;
        color: #A1A1AA;
        line-height: 1.45;
        font-style: italic;
        margin: 0.4rem 0;
    }
    .evidence-meta {
        font-size: 0.72rem;
        color: #71717A;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Streamlit Tab Overrides */
    div[data-testid="stTabs"] div[role="tablist"] {
        gap: 2.25rem !important;
        border-bottom: 1px solid #1E1E22 !important;
        padding-bottom: 0px !important;
    }
    div[data-testid="stTabs"] div[role="tab"],
    div[data-testid="stTabs"] button[role="tab"],
    div[data-testid="stTab"] {
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        color: #71717A !important;
        padding: 0.65rem 0.5rem !important;
        border-bottom: 2px solid transparent !important;
        letter-spacing: -0.01em !important;
        cursor: pointer !important;
        transition: color 0.15s ease, border-color 0.15s ease !important;
    }
    div[data-testid="stTabs"] div[role="tab"] p,
    div[data-testid="stTabs"] button[role="tab"] p,
    div[data-testid="stTab"] p {
        font-size: 0.84rem !important;
        margin: 0 !important;
    }
    div[data-testid="stTabs"] div[role="tab"]:hover,
    div[data-testid="stTabs"] button[role="tab"]:hover,
    div[data-testid="stTab"]:hover {
        color: #D4D4D8 !important;
    }
    div[data-testid="stTabs"] div[role="tab"][aria-selected="true"],
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
    div[data-testid="stTab"][aria-selected="true"] {
        color: #FAFAFA !important;
        border-bottom: 2px solid #2563EB !important;
        background: transparent !important;
    }
    div[data-testid="stTabs"] div[role="tab"][aria-selected="true"] p,
    div[data-testid="stTab"][aria-selected="true"] p {
        color: #FAFAFA !important;
        font-weight: 600 !important;
    }

    /* Button Overrides */
    div.stButton > button {
        border-radius: 4px !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        letter-spacing: -0.01em !important;
        transition: all 0.15s ease-in-out !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #2563EB !important;
        border: 1px solid #1D4ED8 !important;
        color: #FFFFFF !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #1D4ED8 !important;
        border-color: #1E40AF !important;
    }
    div.stButton > button[kind="secondary"] {
        background-color: #141417 !important;
        border: 1px solid #27272A !important;
        color: #FAFAFA !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #18181B !important;
        border-color: #3F3F46 !important;
    }

    /* Sidebar Form Controls */
    div[data-testid="stSidebar"] label {
        font-size: 0.76rem !important;
        font-weight: 500 !important;
        color: #A1A1AA !important;
    }
    div[data-testid="stSidebar"] .stSelectbox, 
    div[data-testid="stSidebar"] .stTextInput {
        font-size: 0.8rem !important;
    }

    /* Terminal Log View */
    .terminal-container {
        background: #050507;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.76rem;
        line-height: 1.5;
        color: #D4D4D8;
        max-height: 380px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)


def render_html_table(headers: List[str], rows: List[List[str]]) -> None:
    """Renders a clean engineering data table natively without pyarrow or pandas."""
    if not rows:
        st.markdown('<div style="color: #71717A; font-size: 0.8rem; padding: 0.5rem 0;">No entries to display.</div>', unsafe_allow_html=True)
        return
    
    th_cells = "".join([f"<th>{h}</th>" for h in headers])
    tr_rows = []
    for row in rows:
        td_cells = "".join([f"<td>{cell}</td>" for cell in row])
        tr_rows.append(f"<tr>{td_cells}</tr>")
    
    table_html = f"""
    <table class="data-table">
        <thead><tr>{th_cells}</tr></thead>
        <tbody>{"".join(tr_rows)}</tbody>
    </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)


# ============================================================================
# Section A: Sidebar Navigation & Configuration
# ============================================================================

with st.sidebar:
    # Minimalist Engineering Brand Header
    st.markdown("""
    <div class="brand-container">
        <div class="brand-mark">TP</div>
        <div>
            <div class="brand-text">TestPrioritize AI</div>
            <div class="brand-sub">Test Intelligence Engine</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Preload demo scenarios
    ensure_demo_repo_exists(DEMO_REPO_PATH)
    demo_scenarios = get_demo_scenarios(DEMO_REPO_PATH)

    mode_choice = st.radio(
        "Analysis Mode",
        ["Demo Scenarios (Pre-configured)", "Custom Git Repository"],
        index=0,
        help="Select a reproducible test scenario or connect to a custom repository."
    )

    active_repo_path = "."
    active_base_ref = "HEAD~1"
    active_target_ref = "HEAD"
    active_scenario: Optional[DemoScenario] = None

    if mode_choice == "Demo Scenarios (Pre-configured)" and demo_scenarios:
        scenario_options = [s.title for s in demo_scenarios]
        selected_title = st.selectbox("Scenario", scenario_options, index=0)
        active_scenario = next((s for s in demo_scenarios if s.title == selected_title), demo_scenarios[0])

        active_repo_path = DEMO_REPO_PATH
        active_base_ref = active_scenario.base_ref
        active_target_ref = active_scenario.target_ref

        st.caption(active_scenario.description)
        if active_scenario.is_regression:
            st.markdown("""
            <div style="font-size: 0.72rem; color: #FCA5A5; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 8px; border-radius: 4px; margin-top: 4px;">
                Intentional Regression: Introduces rounding bug in src/checkout.py to verify fail-fast halting.
            </div>
            """, unsafe_allow_html=True)
    else:
        active_repo_path = st.text_input(
            "Repository Path",
            value=".",
            help="Local repository path."
        ).strip()

        active_base_ref = st.text_input(
            "Base Revision",
            value="HEAD~1",
            help="Starting comparison ref (e.g. main, HEAD~1, commit hash)."
        ).strip()

        active_target_ref = st.text_input(
            "Target Revision",
            value="HEAD",
            help="Target comparison ref (e.g. feature branch, HEAD)."
        ).strip()

    st.markdown('<hr style="border: none; border-top: 1px solid #1E1E22; margin: 1rem 0;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 0.7rem; color: #71717A; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.5rem; font-weight: 600;">Execution Parameters</div>', unsafe_allow_html=True)

    enable_tinyfish_input = st.checkbox("TinyFish Dependency Intelligence", value=True)
    execute_tests_input = st.checkbox("Execute Prioritized Tests (Pytest)", value=True)
    fail_fast_input = st.checkbox("Fail-Fast Mode (-x)", value=True)
    timeout_input = st.slider("Subprocess Timeout (seconds)", min_value=10, max_value=300, value=60, step=10)

    st.markdown("<br>", unsafe_allow_html=True)
    run_clicked = st.button("Run Analysis", type="primary", use_container_width=True)

    # Footer Environment Status
    has_tinyfish_key = bool(get_api_key())
    key_dot_class = "dot-ready" if has_tinyfish_key else "dot-warning"
    key_label = "Active" if has_tinyfish_key else "Not Configured"

    st.markdown(f"""
    <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #1E1E22; font-size: 0.7rem; color: #71717A; font-family: 'JetBrains Mono', monospace;">
        <div>Engine: <span style="color: #A1A1AA;">AST + Lexical</span></div>
        <div>TinyFish API: <span class="status-dot {key_dot_class}"></span> <span style="color: #A1A1AA;">{key_label}</span></div>
        <div style="margin-top: 4px; color: #52525B;">v0.9.4 | Python 3.11</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# Section B: Header & Context Bar
# ============================================================================

st.markdown('<div class="page-title">Test Analysis</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Identify modified code, map dependencies via AST, rank tests by failure risk, and execute prioritized suites.</div>',
    unsafe_allow_html=True
)

last_run_time = st.session_state.get("last_run_time", "None")
repo_display = "demo_repo" if active_repo_path == DEMO_REPO_PATH else active_repo_path

st.markdown(f"""
<div class="context-bar">
    <div class="context-item">
        <span class="context-label">Repository:</span>
        <span class="context-value">{html.escape(repo_display)}</span>
    </div>
    <div class="context-item">
        <span class="context-label">Comparison:</span>
        <span class="context-value">{html.escape(active_base_ref)} &rarr; {html.escape(active_target_ref)}</span>
    </div>
    <div class="context-item">
        <span class="context-label">Prioritization:</span>
        <span class="context-value">Deterministic [0-100]</span>
    </div>
    <div class="context-item">
        <span class="context-label">Last Execution:</span>
        <span class="context-value">{html.escape(last_run_time)}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================================
# Section C: Scenario Diff & Inspection Expander
# ============================================================================

if active_scenario is not None:
    with st.expander("Inspection: Scenario Git Diff and Regression Metadata", expanded=False):
        c_left, c_right = st.columns([3, 1])
        with c_left:
            st.markdown(f"**Target**: `{active_scenario.target_ref}` | **Base**: `{active_scenario.base_ref}`")
            if active_scenario.is_regression and active_scenario.regression_details:
                reg = active_scenario.regression_details
                st.markdown(f"""
                <div style="font-size: 0.78rem; background: #0C0C0E; border: 1px solid #27272A; padding: 0.6rem 0.8rem; border-radius: 4px; margin: 0.4rem 0;">
                    <div><strong>Intended:</strong> {html.escape(reg.get('intended_behavior', ''))}</div>
                    <div style="color: #F87171;"><strong>Introduced:</strong> <code>{html.escape(reg.get('introduced_regression', ''))}</code></div>
                    <div><strong>Detecting Test:</strong> <code>{html.escape(reg.get('detecting_test', ''))}</code></div>
                    <div><strong>Expected vs Observed:</strong> <code>{html.escape(reg.get('expected_outcome', ''))}</code> vs <code style="color: #F87171;">{html.escape(reg.get('observed_outcome', ''))}</code></div>
                </div>
                """, unsafe_allow_html=True)
        with c_right:
            st.markdown(f"**Expected Top Test**: `{active_scenario.expected_top_test or 'None'}`")
            st.markdown(f"**Scope**: {len(active_scenario.expected_changed_files)} file(s)")

        diff_content = get_scenario_diff(active_scenario.base_ref, active_scenario.target_ref, DEMO_REPO_PATH)
        if diff_content:
            st.code(diff_content, language="diff")


# ============================================================================
# Section D: Run Pipeline Trigger
# ============================================================================

if run_clicked:
    if active_repo_path == DEMO_REPO_PATH and active_target_ref:
        checkout_scenario_target(active_target_ref, DEMO_REPO_PATH)

    with st.spinner("Executing Git change detection, AST mapping, and test prioritization..."):
        t_start = time.perf_counter()
        try:
            pipeline_result = run_pipeline(
                base_ref=active_base_ref,
                target_ref=active_target_ref,
                repo_path=active_repo_path,
                enable_tinyfish=enable_tinyfish_input,
                execute_tests=execute_tests_input,
                fail_fast=fail_fast_input,
                test_timeout_seconds=float(timeout_input)
            )
            analysis_time = time.perf_counter() - t_start
            st.session_state["pipeline_result"] = pipeline_result
            st.session_state["analysis_time"] = analysis_time
            st.session_state["last_run_time"] = time.strftime("%H:%M:%S UTC")
            st.session_state["active_repo"] = active_repo_path
            st.session_state["active_base"] = active_base_ref
            st.session_state["active_target"] = active_target_ref
            st.session_state["benchmark_result"] = None
        except Exception as exc:
            st.session_state["pipeline_result"] = None
            st.markdown(f"""
            <div class="alert-banner alert-danger">
                <strong>Pipeline Error:</strong> {html.escape(str(exc))}
            </div>
            """, unsafe_allow_html=True)


# ============================================================================
# Section E: Results Area
# ============================================================================

result: Optional[PipelineResult] = st.session_state.get("pipeline_result")

if result is not None:
    # 1. Status Banner
    if result.status == STATUS_SUCCESS:
        st.markdown(f"""
        <div class="alert-banner alert-success">
            <div>
                <strong>Pipeline Complete:</strong> {html.escape(result.summary)}
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif result.status == STATUS_TEST_FAILURE:
        st.markdown(f"""
        <div class="alert-banner alert-danger">
            <div>
                <strong>Regression Detected (Fail-Fast):</strong> {html.escape(result.summary)}
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif result.status == STATUS_NO_CHANGES:
        st.markdown(f"""
        <div class="alert-banner alert-info">
            <div><strong>No Changes:</strong> {html.escape(result.summary)}</div>
        </div>
        """, unsafe_allow_html=True)
    elif result.status == STATUS_NO_CANDIDATE_TESTS:
        st.markdown(f"""
        <div class="alert-banner alert-warning">
            <div><strong>No Candidate Tests Mapped:</strong> {html.escape(result.summary)}</div>
        </div>
        """, unsafe_allow_html=True)
    elif result.status == STATUS_GIT_ERROR:
        st.markdown(f"""
        <div class="alert-banner alert-danger">
            <div><strong>Git Error:</strong> {html.escape(result.error_message or '')}</div>
        </div>
        """, unsafe_allow_html=True)
    elif result.status == STATUS_TIMEOUT:
        st.markdown(f"""
        <div class="alert-banner alert-danger">
            <div><strong>Execution Timed Out:</strong> {html.escape(result.summary)}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="alert-banner alert-danger">
            <div><strong>Error:</strong> {html.escape(result.error_message or result.summary)}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. Operational Summary Metrics Grid
    changed_count = len(result.changed_files)
    candidate_count = len(result.ranking_result.ranked_tests) if result.ranking_result else 0
    
    if result.execution_outcome and result.execution_outcome.executed:
        passed_val = f"{result.execution_outcome.passed_count}/{result.execution_outcome.total_executed}"
        failed_val = str(result.execution_outcome.failed_count)
        failed_color = "#F87171" if result.execution_outcome.failed_count > 0 else "#FAFAFA"
        duration_val = f"{result.execution_outcome.duration_seconds:.3f}s"
    else:
        passed_val = "N/A"
        failed_val = "0"
        failed_color = "#FAFAFA"
        duration_val = f"{result.duration_seconds:.3f}s"

    analysis_dur = st.session_state.get("analysis_time", result.duration_seconds)

    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-cell">
            <div class="metric-cell-label">Files Changed</div>
            <div class="metric-cell-value">{changed_count}</div>
            <div class="metric-cell-sub">Source + Manifest</div>
        </div>
        <div class="metric-cell">
            <div class="metric-cell-label">Candidate Test Files</div>
            <div class="metric-cell-value">{candidate_count}</div>
            <div class="metric-cell-sub">AST + Lexical Mapped</div>
        </div>
        <div class="metric-cell">
            <div class="metric-cell-label">Tests Passed / Total</div>
            <div class="metric-cell-value">{passed_val}</div>
            <div class="metric-cell-sub">Executed Tests</div>
        </div>
        <div class="metric-cell">
            <div class="metric-cell-label">Failed Tests</div>
            <div class="metric-cell-value" style="color: {failed_color};">{failed_val}</div>
            <div class="metric-cell-sub">Fail-Fast Halts</div>
        </div>
        <div class="metric-cell">
            <div class="metric-cell-label">Analysis Duration</div>
            <div class="metric-cell-value">{analysis_dur:.3f}s</div>
            <div class="metric-cell-sub">Pre-Execution Overhead</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. Main Dashboard Tabs
    tab_tests, tab_benchmark, tab_tinyfish, tab_changes, tab_logs, tab_about = st.tabs([
        "Ranked Tests",
        "Benchmark Comparison",
        "Dependency Intelligence",
        "Changed Files & Diff",
        "Execution Logs",
        "Architecture & Methodology"
    ])

    # ------------------------------------------------------------------------
    # Tab 1: Ranked Tests
    # ------------------------------------------------------------------------
    with tab_tests:
        st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin-bottom: 0.3rem;">Prioritized Test Execution Order</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 0.78rem; color: #71717A; margin-bottom: 0.85rem;">Candidate test files ordered by deterministic failure risk score [0-100] with alphabetical tie-breaking.</div>', unsafe_allow_html=True)

        if result.ranking_result and result.ranking_result.ranked_tests:
            headers = ["Rank", "Test File", "Score", "Tier", "Contributing Sources", "Match Evidence / Rationale"]
            rows = []
            for idx, item in enumerate(result.ranking_result.ranked_tests, start=1):
                badge_class = "badge-high" if item.priority == PRIORITY_HIGH else (
                    "badge-med" if item.priority == PRIORITY_MEDIUM else "badge-low"
                )
                sources_str = ", ".join([f"<code>{html.escape(s)}</code>" for s in item.contributing_sources]) if item.contributing_sources else "&mdash;"
                
                rows.append([
                    f'<span class="mono-num" style="color: #A1A1AA;">#{idx}</span>',
                    f'<span class="mono-cell"><strong>{html.escape(item.test_file)}</strong></span>',
                    f'<span class="mono-num" style="font-weight: 600; color: #FAFAFA;">{item.score}</span> <span style="font-size: 0.7rem; color: #71717A;">/ 100</span>',
                    f'<span class="badge {badge_class}">{item.priority}</span>',
                    sources_str,
                    f'<span style="font-size: 0.76rem; color: #A1A1AA;">{html.escape(item.explanation)}</span>'
                ])
            render_html_table(headers, rows)
        else:
            st.markdown('<div style="color: #71717A; font-size: 0.8rem; padding: 1rem 0;">No candidate test files mapped to changed sources.</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Tab 2: Benchmark Comparison
    # ------------------------------------------------------------------------
    with tab_benchmark:
        st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin-bottom: 0.3rem;">Side-by-Side Suite Execution Comparison</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 0.78rem; color: #71717A; margin-bottom: 0.85rem;">Measures prioritized test subset performance against the full test suite on identical revisions and environment.</div>', unsafe_allow_html=True)

        c_action, c_samples, c_warm = st.columns([2, 1, 1])
        with c_action:
            run_bench_clicked = st.button("Run Benchmark Comparison", type="secondary")
        with c_samples:
            bench_iterations = st.selectbox("Sample Runs", [1, 3, 5], index=0, help="Multiple runs report median duration to eliminate transient noise.")
        with c_warm:
            bench_warmup = st.checkbox("Warm-up run", value=False)

        if run_bench_clicked:
            active_repo = st.session_state.get("active_repo", active_repo_path)
            active_base = st.session_state.get("active_base", active_base_ref)
            active_target = st.session_state.get("active_target", active_target_ref)

            if active_repo == DEMO_REPO_PATH and active_target:
                checkout_scenario_target(active_target, DEMO_REPO_PATH)

            with st.spinner("Measuring prioritized and full suite test execution times..."):
                bench_comp = run_benchmark_comparison(
                    repo_path=active_repo,
                    base_ref=active_base,
                    target_ref=active_target,
                    iterations=int(bench_iterations),
                    fail_fast=fail_fast_input,
                    warm_up=bench_warmup
                )
                st.session_state["benchmark_result"] = bench_comp

        bench_data: Optional[BenchmarkComparison] = st.session_state.get("benchmark_result")
        if bench_data is not None:
            # 4 Summary Tiles
            time_saved_str = f"{bench_data.time_saved_seconds:.3f}s" if bench_data.time_saved_seconds >= 0 else "0.000s"
            st.markdown(f"""
            <div class="metrics-grid" style="grid-template-columns: repeat(4, 1fr); margin-top: 0.75rem;">
                <div class="metric-cell">
                    <div class="metric-cell-label">Prioritized Duration</div>
                    <div class="metric-cell-value">{bench_data.prioritized_duration_seconds:.3f}s</div>
                    <div class="metric-cell-sub">Candidate Subset</div>
                </div>
                <div class="metric-cell">
                    <div class="metric-cell-label">Full Suite Duration</div>
                    <div class="metric-cell-value">{bench_data.full_suite_duration_seconds:.3f}s</div>
                    <div class="metric-cell-sub">All Discovered Tests</div>
                </div>
                <div class="metric-cell">
                    <div class="metric-cell-label">Time Saved</div>
                    <div class="metric-cell-value" style="color: #34D399;">{time_saved_str}</div>
                    <div class="metric-cell-sub">{bench_data.speedup_percentage}% Speedup</div>
                </div>
                <div class="metric-cell">
                    <div class="metric-cell-label">Tests Avoided</div>
                    <div class="metric-cell-value">{bench_data.tests_skipped_count}</div>
                    <div class="metric-cell-sub">Unrelated Tests Skipped</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Detailed Comparative Table
            b_headers = ["Metric", "Prioritized Test Suite", "Full Test Suite", "Observation / Delta"]
            b_rows = [
                [
                    "<strong>Tests Executed</strong>",
                    f'<span class="mono-num">{bench_data.prioritized_run.total_executed} tests</span>',
                    f'<span class="mono-num">{bench_data.full_suite_run.total_executed} tests</span>',
                    f"{bench_data.tests_skipped_count} tests safely avoided"
                ],
                [
                    "<strong>Execution Outcome</strong>",
                    f'{bench_data.prioritized_run.passed_count} passed, <span style="color: {"#F87171" if bench_data.prioritized_run.failed_count > 0 else "#FAFAFA"}">{bench_data.prioritized_run.failed_count} failed</span>',
                    f'{bench_data.full_suite_run.passed_count} passed, <span style="color: {"#F87171" if bench_data.full_suite_run.failed_count > 0 else "#FAFAFA"}">{bench_data.full_suite_run.failed_count} failed</span>',
                    "Deterministic outcome"
                ],
                [
                    "<strong>Pytest Wall-Clock Time</strong>",
                    f'<span class="mono-num">{bench_data.prioritized_duration_seconds:.3f}s</span>',
                    f'<span class="mono-num">{bench_data.full_suite_duration_seconds:.3f}s</span>',
                    f"{bench_data.speedup_percentage}% execution duration reduction" if bench_data.time_saved_seconds > 0 else "Comparable runtime"
                ],
                [
                    "<strong>Time to First Failure</strong>",
                    f'<span class="mono-num" style="color: #F87171;">{bench_data.time_to_first_failure_prioritized:.4f}s</span>' if bench_data.time_to_first_failure_prioritized else '<span style="color: #71717A;">N/A (all passed)</span>',
                    f'<span class="mono-num">{bench_data.time_to_first_failure_full:.4f}s</span>' if bench_data.time_to_first_failure_full else '<span style="color: #71717A;">N/A (all passed)</span>',
                    "Fail-fast response time"
                ],
                [
                    "<strong>Static Analysis Overhead</strong>",
                    f'<span class="mono-num">{bench_data.analysis_overhead_seconds:.4f}s</span> (Diff: {bench_data.change_detection_seconds:.3f}s, AST Map: {bench_data.test_mapping_seconds:.3f}s, Rank: {bench_data.ranking_seconds:.3f}s)',
                    '<span style="color: #71717A;">&mdash;</span>',
                    "Pre-execution static analysis"
                ]
            ]
            render_html_table(b_headers, b_rows)

            st.markdown(f"""
            <div style="font-size: 0.76rem; color: #71717A; background: #0C0C0E; border: 1px solid #1E1E22; padding: 0.6rem 0.8rem; border-radius: 4px; margin-top: 0.5rem;">
                <strong>Engineering Scope:</strong> {html.escape(bench_data.limitation_notes)}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="color: #71717A; font-size: 0.8rem; padding: 1rem 0;">Click <strong>Run Benchmark Comparison</strong> to measure prioritized versus full suite timings.</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Tab 3: Dependency Intelligence
    # ------------------------------------------------------------------------
    with tab_tinyfish:
        st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin-bottom: 0.3rem;">External Dependency Risk Intelligence</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 0.78rem; color: #71717A; margin-bottom: 0.85rem;">Monitors package manifest modifications (requirements.txt) and queries the TinyFish Search REST API for breaking changes.</div>', unsafe_allow_html=True)

        dep_rep = result.dependency_report
        if dep_rep is None:
            st.markdown('<div style="color: #71717A; font-size: 0.8rem;">TinyFish dependency intelligence was not enabled for this execution.</div>', unsafe_allow_html=True)
        elif not dep_rep.manifest_changed:
            st.markdown("""
            <div style="font-size: 0.8rem; color: #71717A; background: #0C0C0E; border: 1px solid #1E1E22; padding: 0.75rem 1rem; border-radius: 6px;">
                No dependency manifest files (<code>requirements.txt</code>) were modified in this comparison. External research was safely skipped.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"**Manifest Summary**: {html.escape(dep_rep.summary)}")

            if dep_rep.dependencies_analyzed:
                st.markdown('<div style="font-size: 0.76rem; color: #71717A; text-transform: uppercase; font-weight: 600; margin: 0.6rem 0 0.3rem 0;">Version Deltas Detected</div>', unsafe_allow_html=True)
                d_headers = ["Package", "Change Type", "Previous Version", "Target Version"]
                d_rows = [
                    [
                        f'<code>{html.escape(dep.package)}</code>',
                        f'<span class="badge badge-neutral">{html.escape(dep.change_type.upper())}</span>',
                        f'<span class="mono-num">{html.escape(dep.old_version or "N/A")}</span>',
                        f'<span class="mono-num" style="color: #34D399;">{html.escape(dep.new_version or "N/A")}</span>'
                    ]
                    for dep in dep_rep.dependencies_analyzed
                ]
                render_html_table(d_headers, d_rows)

            if dep_rep.findings:
                st.markdown(f'<div style="font-size: 0.76rem; color: #71717A; text-transform: uppercase; font-weight: 600; margin: 0.8rem 0 0.4rem 0;">Verified Evidence ({len(dep_rep.findings)} items)</div>', unsafe_allow_html=True)
                for f in dep_rep.findings:
                    cat_class = "badge-high" if f.category == "breaking_change" else (
                        "badge-med" if f.category == "migration_guide" else "badge-low"
                    )
                    cat_label = f.category.replace("_", " ").upper()
                    st.markdown(f"""
                    <div class="evidence-card">
                        <div class="evidence-header">
                            <span class="evidence-title">{html.escape(f.title)}</span>
                            <span class="badge {cat_class}">{cat_label}</span>
                        </div>
                        <div class="evidence-meta">
                            Package: <code>{html.escape(f.package)}</code> | Source: <a href="{html.escape(f.url)}" target="_blank" style="color: #60A5FA; text-decoration: none;">{html.escape(f.url)}</a>
                        </div>
                        <div class="evidence-snippet">"{html.escape(f.snippet)}"</div>
                        <div style="font-size: 0.74rem; color: #A1A1AA;">{html.escape(f.explanation)} (+20 pts risk bonus applied to matching tests)</div>
                    </div>
                    """, unsafe_allow_html=True)
            elif dep_rep.status == "skipped_missing_key":
                st.markdown('<div class="alert-banner alert-warning">TINYFISH_API_KEY environment variable is not configured. External lookup skipped; local deterministic test ranking preserved.</div>', unsafe_allow_html=True)
            elif dep_rep.status == "lookup_failed":
                st.markdown('<div class="alert-banner alert-warning">External intelligence lookup failed due to network/API error. Local deterministic test ranking preserved.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size: 0.8rem; color: #71717A;">Searched package releases; no verified breaking changes or migration advisories detected.</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Tab 4: Changed Files & Diff
    # ------------------------------------------------------------------------
    with tab_changes:
        st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin-bottom: 0.3rem;">Git Changed Files & Unified Diff</div>', unsafe_allow_html=True)
        if result.changed_files:
            c_headers = ["File Path", "Change Type", "Previous Path"]
            c_rows = [
                [
                    f'<span class="mono-cell">{html.escape(cf.path)}</span>',
                    f'<span class="badge badge-neutral">{html.escape(cf.change_type.upper())}</span>',
                    f'<span class="mono-cell">{html.escape(cf.old_path)}</span>' if cf.old_path else '<span style="color: #71717A;">&mdash;</span>'
                ]
                for cf in result.changed_files
            ]
            render_html_table(c_headers, c_rows)

            active_repo = st.session_state.get("active_repo", active_repo_path)
            active_base = st.session_state.get("active_base", active_base_ref)
            active_target = st.session_state.get("active_target", active_target_ref)
            diff_text = get_scenario_diff(active_base, active_target, active_repo)
            if diff_text:
                st.markdown('<div style="font-size: 0.76rem; color: #71717A; text-transform: uppercase; font-weight: 600; margin: 0.8rem 0 0.3rem 0;">Unified Diff</div>', unsafe_allow_html=True)
                st.code(diff_text, language="diff")
        else:
            st.markdown('<div style="color: #71717A; font-size: 0.8rem;">No changed files in this comparison.</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Tab 5: Execution Logs
    # ------------------------------------------------------------------------
    with tab_logs:
        st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin-bottom: 0.3rem;">Subprocess Execution Logs</div>', unsafe_allow_html=True)
        exec_outcome = result.execution_outcome

        if exec_outcome and exec_outcome.executed:
            st.markdown(f'<div style="font-size: 0.78rem; color: #71717A; margin-bottom: 0.5rem;">Mode: <code>{html.escape(exec_outcome.mode.upper())}</code> | Exit Code: <code>{exec_outcome.exit_code}</code> | Pytest Duration: <code>{exec_outcome.duration_seconds:.3f}s</code></div>', unsafe_allow_html=True)
            st.code(" ".join(exec_outcome.command), language="bash")

            if exec_outcome.stdout:
                st.markdown('<div style="font-size: 0.72rem; color: #71717A; text-transform: uppercase; font-weight: 600; margin: 0.6rem 0 0.2rem 0;">Standard Output (stdout)</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="terminal-container"><pre>{html.escape(exec_outcome.stdout)}</pre></div>', unsafe_allow_html=True)

            if exec_outcome.stderr:
                st.markdown('<div style="font-size: 0.72rem; color: #71717A; text-transform: uppercase; font-weight: 600; margin: 0.6rem 0 0.2rem 0;">Standard Error (stderr)</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="terminal-container" style="color: #F87171;"><pre>{html.escape(exec_outcome.stderr)}</pre></div>', unsafe_allow_html=True)
        elif exec_outcome and not exec_outcome.executed:
            st.markdown(f'<div class="alert-banner alert-warning">Test execution was not executed: {html.escape(exec_outcome.error_message or "")}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size: 0.8rem; color: #71717A;">Test execution was disabled in configuration options.</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Tab 6: Architecture & Methodology
    # ------------------------------------------------------------------------
    with tab_about:
        st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin-bottom: 0.3rem;">Engineering Architecture & Scoring Model</div>', unsafe_allow_html=True)
        st.markdown(r"""
        #### Multi-Stage Prioritization Pipeline
        1. **Safe Git Diff (`diff_checker.py`)**: Subprocess execution with `shell=False` querying `git diff --name-status -M` without shell injection risks.
        2. **Hybrid Test Mapper (`test_mapper.py`)**:
           - **AST Static Import Extraction**: Parses Python AST using `ast.Import` and `ast.ImportFrom` to trace exact module imports and cross-file dependencies.
           - **Lexical Matching Fallback**: Direct stem matching and delimited compound matching (`test_<stem>.py`) guarantee resilience on non-parseable code.
        3. **TinyFish Intelligence (`tinyfish_client.py`, `dependency_intelligence.py`)**: Checks package version changes in `requirements.txt` against the TinyFish Search REST API for breaking changes and migration notices.
        4. **Deterministic Ranking Engine (`ranking_engine.py`)**:
           - Direct Stem Match / AST Direct Import: `+50 pts`
           - Compound Match / AST Transitive Dependency: `+25 pts`
           - Multi-Source Corroboration: `+15 pts` per additional changed source file (capped at `+30 pts`).
           - Verified Dependency Risk: `+20 pts` (awarded strictly to tests mapping to the affected package).
           - Clamping: `[0, 100]` with `HIGH` (&ge; 70), `MEDIUM` (40-69), `LOW` (< 40) priority tiers.
           - Tie-Breaking: Score descending &rarr; normalized relative path ascending.
        5. **Pytest Subprocess Runner (`pipeline.py`, `benchmark_runner.py`)**: Executes candidate test files with fail-fast (`-x`) in a secure subprocess, capturing JUnit XML timings down to the millisecond.

        #### Operational Boundaries
        - **Fail-Fast Scope**: Prioritization accelerates initial failure feedback; it does not replace running the full test suite before production deployments.
        - **Static Analysis Scope**: AST analyzes static import syntax; dynamic runtime imports (`importlib`) are not resolved statically.
        """)

else:
    # Empty Initial State
    st.markdown("""
    <div style="background: #0C0C0E; border: 1px solid #1E1E22; border-radius: 6px; padding: 2rem; text-align: center; margin-top: 1rem;">
        <div style="font-size: 1rem; font-weight: 600; color: #FAFAFA; margin-bottom: 0.4rem;">No Analysis Executed Yet</div>
        <div style="font-size: 0.82rem; color: #71717A; max-width: 520px; margin: 0 auto 1.25rem auto;">
            Select a pre-configured code-change scenario or configure a custom local Git repository in the sidebar, then click <strong>Run Analysis</strong>.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("""
        <div style="background: #0C0C0E; border: 1px solid #1E1E22; border-radius: 6px; padding: 0.85rem;">
            <div style="font-size: 0.72rem; color: #71717A; text-transform: uppercase; font-weight: 600;">Scenario 1</div>
            <div style="font-size: 0.82rem; font-weight: 600; color: #FAFAFA; margin: 0.2rem 0;">Cart Enhancement</div>
            <div style="font-size: 0.74rem; color: #71717A;">Healthy feature PR; validates 100% test pass rate with prioritized test_cart.py.</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div style="background: #0C0C0E; border: 1px solid #1E1E22; border-radius: 6px; padding: 0.85rem;">
            <div style="font-size: 0.72rem; color: #F87171; text-transform: uppercase; font-weight: 600;">Scenario 2</div>
            <div style="font-size: 0.82rem; font-weight: 600; color: #FAFAFA; margin: 0.2rem 0;">Currency Rounding Bug</div>
            <div style="font-size: 0.74rem; color: #71717A;">Authentic failing regression; demonstrates instant fail-fast detection in milliseconds.</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div style="background: #0C0C0E; border: 1px solid #1E1E22; border-radius: 6px; padding: 0.85rem;">
            <div style="font-size: 0.72rem; color: #71717A; text-transform: uppercase; font-weight: 600;">Scenario 3</div>
            <div style="font-size: 0.82rem; font-weight: 600; color: #FAFAFA; margin: 0.2rem 0;">Multi-Module Overhaul</div>
            <div style="font-size: 0.74rem; color: #71717A;">Cross-module change touching cart and pricing; evaluates multi-source score boost.</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown("""
        <div style="background: #0C0C0E; border: 1px solid #1E1E22; border-radius: 6px; padding: 0.85rem;">
            <div style="font-size: 0.72rem; color: #71717A; text-transform: uppercase; font-weight: 600;">Scenario 4</div>
            <div style="font-size: 0.82rem; font-weight: 600; color: #FAFAFA; margin: 0.2rem 0;">Dependency Upgrade</div>
            <div style="font-size: 0.74rem; color: #71717A;">Modifies requirements.txt; triggers TinyFish live web search for breaking changes.</div>
        </div>
        """, unsafe_allow_html=True)
