# Data Directory

This directory now contains only the database used by the current paper:

`FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`

`analysis_2/config.py` reads this file from sheet `Foglio1`.

## Final Paper Database

`FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx` keeps the original 104-column
schema. It differs from the original database only in the route-efficiency
Minefield columns that could be recalculated from raw data:

- `PLANNING_PERC_PRE`
- `PLANNING_PERC_POST`
- `PWM_PERC_PRE`
- `PWM_PERC_POST`

For these four columns, recalculated raw values are used when available. If raw
data are missing, the historical/original value is retained. All other columns
remain unchanged from the original database.

## Archived Database Inputs and Audits

The files used to create or audit this database have been moved to:

`archive/database_sources_and_audits/`

That archive contains the original source database, raw Minefield files, trial
configuration file, and the full best-available Minefield audit workbook.
