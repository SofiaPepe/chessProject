# Minefield scoring

Run the complete recalculation from the repository root with:

```powershell
python analysis\minefield_scoring\scoring.py
```

Inputs:

- `data/Minefield_raw/*.csv`
- `data/configuration_trial.xlsx`
- `data/FINAL_DATABASE.xlsx`

Current paper database output:

- `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`

The output database keeps the original 104-column schema. Only
`PLANNING_PERC_PRE`, `PLANNING_PERC_POST`, `PWM_PERC_PRE`, and `PWM_PERC_POST`
are replaced with recalculated route-efficiency percentages when raw data are
available. Otherwise their original values are retained. The original database
is never overwritten, and a cell-level update audit is written to
`output/minefield_scoring/database_route_efficiency_updates.csv`.

Detailed scoring and selection audits are written to
`output/minefield_scoring/`.

Full audit output:

- `data/FINAL_DATABASE_MINEFIELD_FULL_BEST_AVAILABLE.xlsx`
- `output/minefield_scoring/full_best_available_summary.md`

The full audit database is separate from the current paper pipeline. It keeps
all historical columns unchanged and adds recalculated-only `MF_` columns plus
`MF_BEST_AVAILABLE_` columns. Best-available values use raw recalculation when
available and historical fallback when raw recalculation is missing. The
`minefield_provenance` sheet marks each value as `recalculated_raw`,
`historical_fallback`, or `missing`.

PRE and POST are assigned from assessment dates. If a test was restarted on
the same day, the most complete session is retained and the latest timestamp
breaks ties. Participants without raw data remain in the complete database
with blank Minefield cells.
