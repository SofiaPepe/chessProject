# Chess project route-efficiency recalculation

- The output database retains the original 104-column schema and 101 participant rows.
- Only `PLANNING_PERC_PRE`, `PLANNING_PERC_POST`, `PWM_PERC_PRE`, and `PWM_PERC_POST` may change.
- Recalculated route efficiency is used when raw data are available; otherwise the original value is retained.
- `PLANNING_EFF_*` and `PWM_EFF_*` remain unchanged because they are tile-difference measures.

## Counts

- Configurations: 54
- Trial audit rows: 3241
- Efficiency cells considered: 404
- Recalculated cells used: 347
- Original cells retained: 57

## Outputs

- `data\FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`
- `output\minefield_scoring\database_route_efficiency_updates.csv`
- `output\minefield_scoring\minefield_scoring.xlsx`
