"""
app.py
Part of TestPrioritize AI.

Production-grade Developer Platform Dashboard for TestPrioritize AI:
- Visual Identity: Dense, restrained, engineering-focused interface inspired by Linear and Vercel.
- Minimum 4 independent demo repositories (Ecommerce, Auth, Payment, Booking) with >= 10 real tests each.
- Interactive changed-file browsing and selection.
- Two distinct execution modes: Standard Alphabetical vs Prioritized AST-Aware Execution.
- High-resolution monotonic timing capturing exact time-to-first-failure (T_fail) and failure position.
- Dedicated Checkout -> Cart AST Dependency Proof demonstrating bidirectional mapping.
- Strictly isolated temporary execution ensuring original repositories are never corrupted.
- Deep-dive evidence: AST import trees, pytest stdout, and TinyFish external risk intelligence.
"""

import html
import os
import sys
import time
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass

import streamlit as st

from demo_manager import (
    DemoRepoInfo,
    IsolatedRunReport,
    ModeExecutionResult,
    execute_demo_scenario,
    get_all_demo_repos,
    list_repo_source_files,
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
    RankingResult,
)
from tinyfish_client import get_api_key

# Page configuration
st.set_page_config(
    page_title="TestPrioritize AI — Test Intelligence & Prioritization Platform",
    page_icon="T",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Design System CSS (Linear / Vercel / Datadog Inspired Monochrome Dark Theme)
# ============================================================================

st.markdown("""
<style>
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

    .brand-container {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 0.25rem 0 1rem 0;
        border-bottom: 1px solid #1E1E22;
        margin-bottom: 1rem;
    }
    .brand-mark {
        width: 26px;
        height: 26px;
        background: #FAFAFA;
        color: #09090B;
        border-radius: 5px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        font-size: 0.82rem;
        letter-spacing: -0.05em;
    }
    .brand-text {
        font-weight: 600;
        font-size: 0.95rem;
        color: #FAFAFA;
        line-height: 1.1;
    }
    .brand-sub {
        font-size: 0.7rem;
        color: #71717A;
        font-family: 'JetBrains Mono', monospace;
    }

    .page-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #FAFAFA;
        letter-spacing: -0.02em;
        margin-bottom: 0.25rem;
    }
    .page-subtitle {
        font-size: 0.82rem;
        color: #A1A1AA;
        margin-bottom: 1.25rem;
        line-height: 1.4;
    }

    .context-bar {
        display: flex;
        align-items: center;
        gap: 1.5rem;
        padding: 0.65rem 1rem;
        background: #0C0C0E;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        margin-bottom: 1.5rem;
        font-size: 0.78rem;
    }
    .context-item {
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .context-label {
        color: #71717A;
        font-weight: 500;
    }
    .context-value {
        color: #E4E4E7;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 500;
    }

    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.75rem;
        margin-bottom: 1.5rem;
    }
    .metric-cell {
        background: #0C0C0E;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        padding: 0.85rem 1rem;
    }
    .metric-cell-label {
        font-size: 0.7rem;
        color: #71717A;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }
    .metric-cell-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #FAFAFA;
        font-family: 'JetBrains Mono', monospace;
        line-height: 1.1;
    }
    .metric-cell-sub {
        font-size: 0.72rem;
        color: #A1A1AA;
        margin-top: 0.35rem;
    }

    .alert-banner {
        padding: 0.75rem 1rem;
        border-radius: 6px;
        font-size: 0.8rem;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .alert-success {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.25);
        color: #34D399;
    }
    .alert-danger {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.25);
        color: #F87171;
    }
    .alert-info {
        background: rgba(59, 130, 246, 0.08);
        border: 1px solid rgba(59, 130, 246, 0.25);
        color: #60A5FA;
    }

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

    .badge {
        display: inline-block;
        padding: 2px 7px;
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

    .flow-card {
        background: #0C0C0E;
        border: 1px solid #1E1E22;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        margin-bottom: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
    }
    .flow-arrow {
        color: #71717A;
        margin: 0 0.5rem;
    }
    .flow-node-source {
        color: #FBBF24;
        font-weight: 600;
    }
    .flow-node-dep {
        color: #60A5FA;
        font-weight: 600;
    }
    .flow-node-test {
        color: #34D399;
        font-weight: 600;
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
# Section A: Sidebar Configuration & Interactive Selection
# ============================================================================

demo_repos = get_all_demo_repos()

with st.sidebar:
    st.markdown("""
    <div class="brand-container">
        <div class="brand-mark">TP</div>
        <div>
            <div class="brand-text">TestPrioritize AI</div>
            <div class="brand-sub">AST Test Intelligence Engine</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    mode_type = st.radio(
        "Workspace Scope",
        ["Demo Repositories (4 Projects)", "Custom Git Repository"],
        index=0,
        help="Select one of the 4 independent demo repositories or inspect a custom workspace."
    )

    selected_repo_id: str = "ecommerce"
    selected_changed_files: List[str] = ["src/checkout.py"]
    selected_scenario_id: Optional[str] = None
    execution_mode = "benchmark"
    custom_repo_path = "."
    custom_base_ref = "HEAD~1"
    custom_target_ref = "HEAD"

    if mode_type == "Demo Repositories (4 Projects)":
        repo_names = {r.id: f"{r.name} ({r.test_count} tests)" for r in demo_repos}
        selected_repo_id = st.selectbox(
            "Target Repository",
            options=list(repo_names.keys()),
            format_func=lambda x: repo_names[x],
            index=0
        )

        active_repo_obj = next(r for r in demo_repos if r.id == selected_repo_id)
        st.caption(active_repo_obj.description)

        # Dynamic source file browser
        available_src_files = list_repo_source_files(active_repo_obj.path)
        selected_changed_files = st.multiselect(
            "Mark Changed Source Files",
            options=available_src_files,
            default=[available_src_files[0]] if available_src_files else [],
            help="Select one or more Python files in src/ to mark as changed for AST dependency analysis."
        )

        # Scenario selector
        scenarios_options = {"baseline": "Healthy Baseline (All Tests Pass)"}
        for sc in active_repo_obj.scenarios:
            tag = "Regression" if sc.get("is_regression") else "Proof"
            scenarios_options[sc["id"]] = f"[{tag}] {sc['title']}"

        selected_scenario_key = st.selectbox(
            "Scenario / Regression Patch",
            options=list(scenarios_options.keys()),
            format_func=lambda k: scenarios_options[k],
            index=1 if len(scenarios_options) > 1 else 0
        )
        selected_scenario_id = None if selected_scenario_key == "baseline" else selected_scenario_key

        # Execution Mode selector
        mode_options = {
            "benchmark": "Side-by-Side Benchmark (Standard vs Prioritized)",
            "prioritized": "Prioritized Execution Only",
            "standard": "Standard Alphabetical Execution Only"
        }
        execution_mode = st.selectbox(
            "Execution Mode",
            options=list(mode_options.keys()),
            format_func=lambda m: mode_options[m],
            index=0
        )
    else:
        custom_repo_path = st.text_input("Repository Path", value=".").strip()
        custom_base_ref = st.text_input("Base Revision", value="HEAD~1").strip()
        custom_target_ref = st.text_input("Target Revision", value="HEAD").strip()
        execution_mode = "prioritized"

    st.markdown('<hr style="border: none; border-top: 1px solid #1E1E22; margin: 0.85rem 0;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 0.68rem; color: #71717A; text-transform: uppercase; font-weight: 600; margin-bottom: 0.4rem;">Execution Options</div>', unsafe_allow_html=True)

    fail_fast_toggle = st.checkbox("Fail-Fast Mode (-x)", value=True, help="Stop test execution immediately on first failure.")
    tinyfish_toggle = st.checkbox("TinyFish External Intelligence", value=True, help="Query breaking change intelligence on requirements.txt deltas.")
    timeout_slider = st.slider("Subprocess Timeout (seconds)", min_value=10, max_value=120, value=60, step=10)

    st.markdown("<br>", unsafe_allow_html=True)
    run_button_clicked = st.button("Execute Pipeline", type="primary", use_container_width=True)

    has_key = bool(get_api_key())
    key_dot = "dot-ready" if has_key else "dot-warning"
    key_label = "Configured" if has_key else "Not Set"

    st.markdown(f"""
    <div style="margin-top: 2rem; padding-top: 0.75rem; border-top: 1px solid #1E1E22; font-size: 0.68rem; color: #71717A; font-family: 'JetBrains Mono', monospace;">
        <div>Engine: <span style="color: #A1A1AA;">AST + Lexical Ranking</span></div>
        <div>TinyFish API: <span style="color: {'#34D399' if has_key else '#FBBF24'};">{key_label}</span></div>
        <div style="margin-top: 4px; color: #52525B;">TestPrioritize AI v1.0.0 | Python 3.11</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# Main Header & Context Bar
# ============================================================================

st.markdown('<div class="page-title">Deterministic AST Test Prioritization</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Inspect source changes, resolve bidirectional AST dependencies, score failure risk, and benchmark fail-fast time-to-first-failure in isolated execution.</div>',
    unsafe_allow_html=True
)

last_run_timestamp = st.session_state.get("last_run_timestamp", "No runs executed yet")
current_repo_title = selected_repo_id if mode_type.startswith("Demo") else custom_repo_path

st.markdown(f"""
<div class="context-bar">
    <div class="context-item">
        <span class="context-label">Repository:</span>
        <span class="context-value">{html.escape(current_repo_title)}</span>
    </div>
    <div class="context-item">
        <span class="context-label">Changed Sources:</span>
        <span class="context-value">{html.escape(", ".join(selected_changed_files) if selected_changed_files else "None")}</span>
    </div>
    <div class="context-item">
        <span class="context-label">Mode:</span>
        <span class="context-value">{html.escape(execution_mode.upper())}</span>
    </div>
    <div class="context-item">
        <span class="context-label">Last Run:</span>
        <span class="context-value">{html.escape(last_run_timestamp)}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================================
# Execution Trigger Handler
# ============================================================================

if run_button_clicked:
    if mode_type == "Demo Repositories (4 Projects)":
        if not selected_changed_files:
            st.error("Please select at least one source file to mark as changed.")
        else:
            with st.spinner("Analyzing AST dependencies, ranking candidate tests, and executing isolated test suites..."):
                t_exec_start = time.perf_counter()
                try:
                    report = execute_demo_scenario(
                        repo_id=selected_repo_id,
                        changed_files=selected_changed_files,
                        scenario_id=selected_scenario_id,
                        mode=execution_mode,
                        fail_fast=fail_fast_toggle,
                        timeout_seconds=float(timeout_slider)
                    )
                    st.session_state["demo_report"] = report
                    st.session_state["last_run_timestamp"] = time.strftime("%H:%M:%S UTC")
                    st.session_state["custom_result"] = None
                except Exception as exc:
                    st.error(f"Execution Error: {exc}")
    else:
        with st.spinner("Running custom git pipeline..."):
            try:
                res = run_pipeline(
                    base_ref=custom_base_ref,
                    target_ref=custom_target_ref,
                    repo_path=custom_repo_path,
                    enable_tinyfish=tinyfish_toggle,
                    execute_tests=True,
                    fail_fast=fail_fast_toggle,
                    test_timeout_seconds=float(timeout_slider)
                )
                st.session_state["custom_result"] = res
                st.session_state["last_run_timestamp"] = time.strftime("%H:%M:%S UTC")
                st.session_state["demo_report"] = None
            except Exception as exc:
                st.error(f"Custom Pipeline Error: {exc}")


# ============================================================================
# Section B & C & D: Results Presentation
# ============================================================================

demo_report: Optional[IsolatedRunReport] = st.session_state.get("demo_report")

if demo_report is not None:
    # 1. Benchmark & Fail-Fast Summary Banner
    if demo_report.mode == "benchmark" and demo_report.standard_run and demo_report.prioritized_run:
        if demo_report.tests_moved_ahead and demo_report.tests_moved_ahead > 0:
            st.markdown(f"""
            <div class="alert-banner alert-success">
                <div>
                    <strong>Fail-Fast Acceleration Confirmed:</strong> {html.escape(demo_report.benchmark_summary)}
                </div>
            </div>
            """, unsafe_allow_html=True)
        elif demo_report.is_regression:
            st.markdown(f"""
            <div class="alert-banner alert-danger">
                <div>
                    <strong>Regression Detected:</strong> {html.escape(demo_report.benchmark_summary)}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="alert-banner alert-info">
                <div>
                    <strong>Healthy Run:</strong> {html.escape(demo_report.benchmark_summary)}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 2. Executive Metrics Grid
    if demo_report.mode == "benchmark" and demo_report.standard_run and demo_report.prioritized_run:
        std_pos_str = f"#{demo_report.standard_run.first_failing_position}" if demo_report.standard_run.first_failing_position else "None"
        pri_pos_str = f"#{demo_report.prioritized_run.first_failing_position}" if demo_report.prioritized_run.first_failing_position else "None"
        time_saved_str = f"{demo_report.time_saved_seconds:.4f}s" if demo_report.time_saved_seconds is not None and demo_report.time_saved_seconds >= 0 else "0.000s"
        pct_saved_str = f"{demo_report.time_saved_percentage}%" if demo_report.time_saved_percentage is not None else "0%"
        moved_str = f"+{demo_report.tests_moved_ahead} tests" if demo_report.tests_moved_ahead else "0"

        st.markdown(f"""
        <div class="metrics-grid">
            <div class="metric-cell">
                <div class="metric-cell-label">First Failure Position</div>
                <div class="metric-cell-value" style="color: #F87171;">{pri_pos_str} <span style="font-size: 0.85rem; color: #71717A;">vs {std_pos_str}</span></div>
                <div class="metric-cell-sub">Surfaced {moved_str} earlier in prioritized mode</div>
            </div>
            <div class="metric-cell">
                <div class="metric-cell-label">Time to First Failure Saved</div>
                <div class="metric-cell-value" style="color: #34D399;">{time_saved_str}</div>
                <div class="metric-cell-sub">{pct_saved_str} faster detection in prioritized mode</div>
            </div>
            <div class="metric-cell">
                <div class="metric-cell-label">Total Execution Runtime</div>
                <div class="metric-cell-value">{demo_report.prioritized_run.duration_seconds:.3f}s</div>
                <div class="metric-cell-sub">Standard total: {demo_report.standard_run.duration_seconds:.3f}s</div>
            </div>
            <div class="metric-cell">
                <div class="metric-cell-label">Static Analysis Overhead</div>
                <div class="metric-cell-value">{demo_report.analysis_overhead_seconds:.4f}s</div>
                <div class="metric-cell-sub">AST parsing & deterministic ranking</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 3. Section B: AST Dependency Flow & Relationships
    st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin: 1.5rem 0 0.5rem 0;">Section B — AST Dependency & Risk Evidence</div>', unsafe_allow_html=True)

    for m in demo_report.mapping_results:
        has_direct = any(match.confidence == "direct" for match in m.matches)
        has_dep = any(match.confidence == "compound" for match in m.matches)

        for match in m.matches:
            if match.confidence == "compound" and "imports" in match.reason.lower():
                st.markdown(f"""
                <div class="flow-card">
                    <span class="flow-node-source">{html.escape(m.source_file)}</span>
                    <span class="flow-arrow">&rarr; [AST Dependency] &rarr;</span>
                    <span class="flow-node-test">{html.escape(match.test_file)}</span>
                    <div style="font-size: 0.72rem; color: #A1A1AA; margin-top: 0.35rem;">
                        {html.escape(match.reason)}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # 4. Section C: Ranked Test Execution Plan
    st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin: 1.5rem 0 0.5rem 0;">Section C — Ranked Test Plan</div>', unsafe_allow_html=True)

    if demo_report.ranking_result and demo_report.ranking_result.ranked_tests:
        r_headers = ["Rank", "Test File", "Score", "Tier", "Match Evidence & Scoring Rationale"]
        r_rows = []
        for idx, item in enumerate(demo_report.ranking_result.ranked_tests, 1):
            tier_class = "badge-high" if item.priority == "HIGH" else ("badge-med" if item.priority == "MEDIUM" else "badge-low")
            r_rows.append([
                f'<span class="mono-num">#{idx}</span>',
                f'<span class="mono-cell">{html.escape(item.test_file)}</span>',
                f'<span class="mono-num" style="font-weight: 700;">{item.score} / 100</span>',
                f'<span class="badge {tier_class}">{html.escape(item.priority)}</span>',
                f'<span style="font-size: 0.74rem;">{html.escape(item.explanation)}</span>'
            ])
        render_html_table(r_headers, r_rows)

    # 5. Section D & E: Live Chronological Execution Results
    st.markdown('<div style="font-size: 0.95rem; font-weight: 600; color: #FAFAFA; margin: 1.5rem 0 0.5rem 0;">Section D & E — Execution Results & Timeline</div>', unsafe_allow_html=True)

    tab_pri, tab_std, tab_logs = st.tabs(["Prioritized Execution Sequence", "Standard Alphabetical Sequence", "Pytest Terminal Logs"])

    with tab_pri:
        pri_res = demo_report.prioritized_run
        if pri_res and pri_res.events:
            p_headers = ["Seq", "Test Node ID", "Outcome", "Test Duration", "Monotonic Elapsed"]
            p_rows = []
            for ev in pri_res.events:
                status_class = "badge-danger" if ev.outcome == "failed" else "badge-success"
                p_rows.append([
                    f'<span class="mono-num">#{ev.sequence_num}</span>',
                    f'<span class="mono-cell">{html.escape(ev.nodeid)}</span>',
                    f'<span class="badge {status_class}">{html.escape(ev.outcome.upper())}</span>',
                    f'<span class="mono-num">{ev.duration_seconds:.4f}s</span>',
                    f'<span class="mono-num">{ev.elapsed_seconds:.4f}s</span>'
                ])
            render_html_table(p_headers, p_rows)
        else:
            st.info("No test execution events recorded in Prioritized mode.")

    with tab_std:
        std_res = demo_report.standard_run
        if std_res and std_res.events:
            s_headers = ["Seq", "Test Node ID", "Outcome", "Test Duration", "Monotonic Elapsed"]
            s_rows = []
            for ev in std_res.events:
                status_class = "badge-danger" if ev.outcome == "failed" else "badge-success"
                s_rows.append([
                    f'<span class="mono-num">#{ev.sequence_num}</span>',
                    f'<span class="mono-cell">{html.escape(ev.nodeid)}</span>',
                    f'<span class="badge {status_class}">{html.escape(ev.outcome.upper())}</span>',
                    f'<span class="mono-num">{ev.duration_seconds:.4f}s</span>',
                    f'<span class="mono-num">{ev.elapsed_seconds:.4f}s</span>'
                ])
            render_html_table(s_headers, s_rows)
        else:
            st.info("No test execution events recorded in Standard mode.")

    with tab_logs:
        if demo_report.prioritized_run and demo_report.prioritized_run.stdout:
            st.markdown("**Prioritized Mode Subprocess Stdout:**")
            st.code(demo_report.prioritized_run.stdout, language="text")
        if demo_report.standard_run and demo_report.standard_run.stdout:
            st.markdown("**Standard Mode Subprocess Stdout:**")
            st.code(demo_report.standard_run.stdout, language="text")

elif st.session_state.get("custom_result") is not None:
    # Custom Git Pipeline Result View
    custom_res: PipelineResult = st.session_state["custom_result"]
    st.markdown(f"**Custom Pipeline Status**: `{custom_res.status}`")
    st.markdown(custom_res.summary)
    if custom_res.ranking_result:
        st.markdown(f"**Ranked Candidate Tests ({len(custom_res.ranking_result.ranked_tests)})**")
        for item in custom_res.ranking_result.ranked_tests:
            st.markdown(f"- `{item.test_file}`: Score {item.score} ({item.priority}) — {item.explanation}")
else:
    st.markdown("""
    <div style="background: #0C0C0E; border: 1px solid #1E1E22; border-radius: 6px; padding: 2rem; text-align: center; color: #71717A;">
        <div style="font-size: 1.1rem; font-weight: 600; color: #E4E4E7; margin-bottom: 0.5rem;">Ready to Execute</div>
        <div style="font-size: 0.82rem; max-width: 500px; margin: 0 auto;">
            Select a demo repository and source file from the sidebar, then click <strong>Execute Pipeline</strong> to run live deterministic AST-aware test prioritization.
        </div>
    </div>
    """, unsafe_allow_html=True)
