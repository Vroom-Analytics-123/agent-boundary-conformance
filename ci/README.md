# CI workflow

CI lives at `.github/workflows/ci.yml`: pytest, offline sealed-bundle
verification (Day-6 + post-fix bundles), and the scorecard determinism
check. It runs on pushes to main and on pull requests. Python 3.12,
stdlib only, no network.

Locally the same steps are validated with `python3 -m pytest tests/ -q`
(101 passed + 90 subtests, Nov 1 2026) and the `tools/verify_bundle.py`
commands in the workflow.
