# Agent Notes

## Toolchain

- Python 3.13+ only. The project is managed with `uv`: `uv sync --group dev`,
  `uv run`, and `uv build`. Publishing uses `pypa/gh-action-pypi-publish` in
  CI, never `uv publish`.
- Tests are stdlib `unittest` on purpose; the CruxPass server repo's
  `release_preflight.sh` runs `uv run python -m unittest discover -s tests`
  against this checkout. Keep tests discoverable by unittest.
- Lint and format with `ruff`; type check with `ty` (`uv run --group dev ...`).
- The version lives only in `pyproject.toml`; `cruxpass.__version__` reads it
  via `importlib.metadata`.

## Release Policy

- Never publish `cruxpass` to PyPI from a local machine.
- Local release work is limited to tests, lint, `uv build`, and `twine check`.
- PyPI publishing must happen only from the GitHub repository's release workflow
  after the matching `v*.*.*` tag is pushed and CI passes.
- Do not run `twine upload`, `uvx twine upload`, or `uv publish` locally for
  this package.
