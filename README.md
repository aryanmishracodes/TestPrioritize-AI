# TestPrioritize AI

> Intelligent, risk-driven test selection and prioritization for CI/CD pipelines.

## Project Goal
When developers push code changes or upgrade dependencies, running a complete test suite often takes tens of minutes or hours, slowing down developer feedback loops. 

**TestPrioritize AI** aims to solve this by:
1. Detecting changed source files and modified dependency versions.
2. Statically mapping tests to source modules without executing unsafe code.
3. Checking external intelligence for breaking changes when dependencies are upgraded.
4. Deterministically ordering tests so that tests most likely to fail run first (`fail-fast`).

## Current Status
- **Phase**: Phase 1 - Project Setup & Foundation
- **Status**: Repository structure initialized. Core modules will be implemented step by step.

## Setup Instructions

### 1. Prerequisites
- Python 3.9+ installed
- Git installed

### 2. Environment Setup
```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install initial dependencies
pip install -r requirements.txt
```