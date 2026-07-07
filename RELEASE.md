# Release Policy

PyPI releases for `cruxpass` are GitHub-only.

## Local Preflight

Run these locally before tagging:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/cruxpass-py-venv uv run python -m unittest discover -s tests
uv run --group dev ruff check .
uv run --group dev ruff format --check .
uv run --group dev ty check src tests
uv build
uvx twine check dist/cruxpass-<version>*
```

Do not upload from local machines.

## Publish

1. Confirm the matching CruxPass server contract is deployed or ready to deploy.
2. Bump `version` in `pyproject.toml` and update `CHANGELOG.md`.
3. Commit the release changes.
4. Push a `v*.*.*` tag to the GitHub repository.
5. Let `.github/workflows/workflow.yml` publish to PyPI from GitHub Actions
   (`pypa/gh-action-pypi-publish` with trusted publishing from the `release`
   environment).
6. Confirm the release at `https://pypi.org/project/cruxpass/<version>/`.

Never run `twine upload`, `uvx twine upload`, or `uv publish` locally for this
package.
