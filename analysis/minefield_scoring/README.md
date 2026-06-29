# Minefield scoring

Run the complete recalculation from the repository root with:

```powershell
python analysis\minefield_scoring\scoring.py
```

Inputs:

- `data/Minefield_raw/*.csv`
- `data/configuration_trial.xlsx`
- `data/FINAL_DATABASE.xlsx`

Main output:

- `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`

The first sheet contains the original non-Minefield variables plus 17
recalculated Minefield outcomes for PRE and POST. Historical Minefield columns
are not copied into the new database, so old and recalculated scores cannot be
mixed accidentally. The original database is never overwritten.

Detailed scoring and selection audits are written to
`output/minefield_scoring/`.

PRE and POST are assigned from assessment dates. If a test was restarted on
the same day, the most complete session is retained and the latest timestamp
breaks ties. Participants without raw data remain in the complete database
with blank Minefield cells.
