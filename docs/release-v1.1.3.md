# GridPilot v1.1.3

This release prevents unnecessary EV charging interruptions when GridPilot settings
change.

- Recalculate PV priority changes without first writing the 5 A stop value.
- Preserve the measured EV current during charging-strategy changes.
- Keep 5 A for explicit stop decisions only.

All tests pass, with GitHub validation checks also passing.
