# Contributing

GridPilot is under active development. Open an issue before implementing a
large controller change. Every control-law change must include boundary tests
and fail-safe tests.

Run the backend checks with:

```bash
pytest
ruff check .
```

Frontend changes must keep the generated file at
`custom_components/gridpilot/frontend/gridpilot-card.js` up to date.
