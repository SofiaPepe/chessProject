# Chess project full best-available Minefield database

## Method

- Trial minimum paths were recalculated from `configuration_trial.xlsx` with BFS on an 8x8 grid.
- Only orthogonal movement is allowed and bomb cells are blocked.
- Historical raw `percorso_minimo` values were retained only for audit.
- Repeated sessions on the same date were resolved by completeness, then recency.
- The earliest assessment date is PRE and the latest is POST.
- The source `FINAL_DATABASE.xlsx` was not modified.
- All historical columns are retained unchanged; `MF_` columns remain recalculated-only and `MF_BEST_AVAILABLE_` columns add historical fallback values.

## Counts

- Trial configurations: 54
- Raw CSV rows read: 3844
- Official-project trial rows retained: 3249
- Rows excluded because ID is not in the official database: 567
- Rows excluded for reused SPR2 ID: 21
- Same-day restarted sessions superseded: 4
- Selected participant/task sessions: 545
- Trial audit rows: 3241
- Successful trial rows included in timing means: 2251
- Negative execution-time rows excluded: 0
- Negative path-efficiency rows excluded: 17
- Long score rows: 202 (101 participants x PRE/POST)
- Original database columns: 104
- Original database columns retained: 104
- Recalculated Minefield columns added: 34
- Best-available Minefield columns added: 34
- Recalculated raw values: 2940
- Historical fallback values: 310
- Values still missing: 184

## Source Counts by Measure

| Measure | Recalculated raw | Historical fallback | Missing |
|---|---:|---:|---:|
| `span_wm` | 182 | 19 | 1 |
| `accuracy_wm` | 182 | 19 | 1 |
| `span_planning` | 182 | 19 | 1 |
| `accuracy_planning` | 182 | 19 | 1 |
| `span_wmplanning` | 181 | 0 | 21 |
| `accuracy_wmplanning` | 181 | 20 | 1 |
| `route_efficiency_pct_planning` | 181 | 20 | 1 |
| `route_efficiency_pct_wmplanning` | 166 | 35 | 1 |
| `wm_mean_total_time` | 152 | 0 | 50 |
| `wm_mean_planning_time` | 152 | 0 | 50 |
| `wm_mean_execution_time` | 152 | 0 | 50 |
| `planning_mean_total_time` | 181 | 20 | 1 |
| `planning_mean_planning_time` | 181 | 20 | 1 |
| `planning_mean_execution_time` | 181 | 20 | 1 |
| `wmplanning_mean_total_time` | 168 | 33 | 1 |
| `wmplanning_mean_planning_time` | 168 | 33 | 1 |
| `wmplanning_mean_execution_time` | 168 | 33 | 1 |

## ID coverage

- `complete_pre_post`: 85
- `missing_raw`: 5
- `partial_pre_post`: 1
- `post_only`: 1
- `pre_only`: 9
- Missing raw IDs: EXP01, EXP09, EXP11, EXP13, EXP14

## Outputs

- `data\FINAL_DATABASE_MINEFIELD_FULL_BEST_AVAILABLE.xlsx`
- `output\minefield_scoring\minefield_scores_long.csv`
- `output\minefield_scoring\minefield_scoring.xlsx`
