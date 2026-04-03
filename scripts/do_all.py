#!/usr/bin/env python3
"""
Run all setup/verification steps: migrations + tests.
Usage: from backend dir: python -m scripts.do_all
       or: python scripts/do_all.py
"""
import subprocess
import sys
import os

def run(cmd, cwd=None):
    cwd = cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run(cmd, shell=True, cwd=cwd)
    if r.returncode != 0:
        print(f"Command failed (exit {r.returncode}): {cmd}")
        sys.exit(r.returncode)

def main():
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("1. Running Alembic migrations...")
    run("python -m alembic upgrade head", cwd=backend)
    print("2. Running tests...")
    run("python -m pytest tests/ -v --tb=short --no-cov", cwd=backend)
    print("Done. Migrations applied and tests passed.")

if __name__ == "__main__":
    main()
