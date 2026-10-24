"""
demo_scenarios.py
Part of TestPrioritize AI.

Provides scenario definitions, demo repository verification,
and diff inspection helpers for the interactive judge demonstration.
"""

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEMO_REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "demo_repo"))


@dataclass(frozen=True)
class DemoScenario:
    """Represents a pre-configured, genuine code-change scenario."""
    id: str
    title: str
    description: str
    base_ref: str
    target_ref: str
    base_commit: str
    target_commit: str
    is_regression: bool
    expected_changed_files: List[str]
    expected_top_test: Optional[str]
    expected_pass_rate: float
    notes: str
    detecting_test: Optional[str] = None
    regression_details: Optional[Dict[str, str]] = None


def ensure_demo_repo_exists(demo_path: str = DEMO_REPO_PATH) -> bool:
    """
    Checks if demo_repo exists and has Git initialized.
    If not, calls setup_demo_repo to build it deterministically.
    """
    git_dir = os.path.join(demo_path, ".git")
    scenarios_file = os.path.join(demo_path, "scenarios.json")

    if not os.path.exists(git_dir) or not os.path.exists(scenarios_file):
        try:
            from setup_demo_repo import init_demo_repository
            init_demo_repository(demo_path)
            return True
        except Exception:
            return False
    return True


def get_demo_scenarios(demo_path: str = DEMO_REPO_PATH) -> List[DemoScenario]:
    """Loads all reproducible scenarios from demo_repo/scenarios.json."""
    ensure_demo_repo_exists(demo_path)
    scenarios_file = os.path.join(demo_path, "scenarios.json")

    if not os.path.exists(scenarios_file):
        return []

    try:
        with open(scenarios_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        scenarios = []
        for item in data:
            scenarios.append(DemoScenario(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                base_ref=item["base_ref"],
                target_ref=item["target_ref"],
                base_commit=item.get("base_commit", ""),
                target_commit=item.get("target_commit", ""),
                is_regression=bool(item.get("is_regression", False)),
                expected_changed_files=item.get("expected_changed_files", []),
                expected_top_test=item.get("expected_top_test"),
                expected_pass_rate=float(item.get("expected_pass_rate", 1.0)),
                notes=item.get("notes", ""),
                detecting_test=item.get("detecting_test"),
                regression_details=item.get("regression_details")
            ))
        return scenarios
    except Exception:
        return []


def get_scenario_diff(
    base_ref: str,
    target_ref: str,
    demo_path: str = DEMO_REPO_PATH
) -> str:
    """Safely extracts git diff between scenario revisions."""
    try:
        cmd = ["git", "diff", f"{base_ref}..{target_ref}"]
        res = subprocess.run(
            cmd,
            cwd=demo_path,
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False
        )
        return res.stdout if res.returncode == 0 else ""
    except Exception:
        return ""


def checkout_scenario_target(
    target_ref: str,
    demo_path: str = DEMO_REPO_PATH
) -> bool:
    """
    Safely checks out the target_ref in demo_repo so that on-disk files
    match the revision being executed. Only operates within demo_repo.
    """
    try:
        cmd = ["git", "checkout", target_ref]
        res = subprocess.run(
            cmd,
            cwd=demo_path,
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False
        )
        return res.returncode == 0
    except Exception:
        return False
