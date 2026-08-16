# GitHub release checklist

Use `/data/gridpilot` as the only source of truth. Do not make release changes
only in `/homeassistant/custom_components/gridpilot`.

## Before committing

- [ ] Update integration code, translations, tests, documentation, and brand assets in
  `/data/gridpilot`.
- [ ] Update the version in `custom_components/gridpilot/manifest.json`.
- [ ] Update the version in `pyproject.toml`.
- [ ] Add release notes to `CHANGELOG.md`.
- [ ] Run `.venv/bin/pytest`.
- [ ] Run `.venv/bin/ruff check .`.
- [ ] Run `git diff --check`, then review `git status` and `git diff`.

## Include in the release

- `custom_components/gridpilot/` source files.
- `custom_components/gridpilot/translations/` and `strings.json`.
- `custom_components/gridpilot/brand/icon.png`, `icon@2x.png`, `logo.png`, and
  `logo@2x.png` when branding changes.
- Tests, documentation, `CHANGELOG.md`, `manifest.json`, and `pyproject.toml` when
  they changed.

## Exclude from the release

- Home Assistant runtime configuration: `.storage/`, config entries, entity data, and
  dashboards.
- Python and tool caches: `__pycache__/`, `.pytest_cache/`, and `.ruff_cache/`.
- Generated files such as `gridpilot-card.js.gz`, unless the integration explicitly
  serves and requires them.
- Credentials, tokens, and secrets.

## Publish

- [ ] Stage only the reviewed files with `git add <files>`.
- [ ] Commit with a release message, for example `Release GridPilot v1.3.6`.
- [ ] Push `main`.
- [ ] Create and push an annotated `vX.Y.Z` tag.
- [ ] Publish the matching GitHub release.
- [ ] Confirm GitHub Actions: Hassfest, Python, and HACS must pass.

HACS installs the code from GitHub. It does not include a user's existing GridPilot
configuration, selected entities, or dashboard storage.
