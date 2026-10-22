# CI workflow (not in the GitHub-magic path)

`github-actions-ci.yml` is the CI workflow for this repo: pytest, offline
bundle verification, and the scorecard determinism check. It is deliberately
NOT committed at `.github/workflows/ci.yml` because the API-scoped GitHub
credential used to push this repo (see AGENTS.md, secure vault flow) lacks the
`workflow` scope — GitHub's Trees API returns 404 for any `.github/workflows/`
path. To activate CI on GitHub: move this file back to
`.github/workflows/ci.yml` with a credential that has the `workflow` scope.

Locally the CI steps are validated (24 tests passed, Day-6 clean-rerun).
