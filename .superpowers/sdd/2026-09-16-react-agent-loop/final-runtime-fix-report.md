# C1 + I1 final runtime fix report

## Review result

- Allowlisted commands are resolved once at server startup through the fixed absolute PATH `/app/.venv/bin:/usr/local/bin:/usr/bin:/bin`, validated as executable regular files outside the workspace, canonicalized, and dispatched by absolute path. Empty and relative PATH entries are rejected, so workspace contents cannot participate in command lookup.
- The sandbox image installs the locked `dev` dependency group, which contains `pytest`; the default allowlist and image manifest agree on `python`, `python3`, and `pytest`.
- `workspace/.gitkeep` tracks the default workspace while `.gitignore` excludes runtime contents. The shared CLI and all three standalone entrypoints resolve the same chapter-local workspace and skills defaults.
- README, page copy, source-code tabs, allowlist manifest tests, and Dockerfile comments match the shipped behavior.

## Verification

- `uv run --frozen --group dev pytest -m 'not docker'`: **333 passed, 3 deselected**
- `uv run --frozen --group dev python -m compileall -q ...`: **passed**
- Essential Ruff checks (`E4,E7,E9,F`) on all changed Python files: **passed**
- `npm run build`: **passed**, 12 pages built
- `git diff --check`: **passed**
- Focused command-resolution regression: **17 passed**, including rejection of leading, trailing, and interior empty PATH entries

## Docker blocker

A bounded 90-second image build pulled the pinned Python base image and reached the locked `uv sync --frozen --group dev --no-install-project` step. Dependency downloads did not finish before the bound (stalled while downloading `cryptography`/`zstandard`), so the three Docker-marked integration tests were not run. The attempt was terminated at the configured timeout and did not block completion.

## Security-rule application

No credentials, certificates, private keys, or cryptographic algorithms were added. The changes keep model credentials on the host and strengthen command-execution isolation by removing runtime workspace-controlled PATH resolution.
