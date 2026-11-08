# TFS Metrics Pipeline

A Python pipeline that checks a month of NYC TLC Yellow Taxi trip records and turns
the clean rows into daily and per-zone revenue metrics in SQLite. It works like a
financial book-close control: if the data fails its checks badly enough, the run is
BLOCKED and nothing is published.

It runs automatically every day on a Linux machine through GitHub Actions.

## How it works

load -> 7 checks (gate) -> set aside bad rows -> compute metrics -> save -> alert

- **Checks:** missing values, duplicates, negative amounts, dropoff before pickup,
  pickup outside the month, zero distance, and fare components not adding up to total_amount.
- **Gate:** each check has a limit. Under it the run logs a warning. Over it the run
  is BLOCKED, nothing is saved, and the process exits with code 1.
- **Quarantine:** rows with serious problems are left out of the revenue numbers.
- **Metrics:** daily trips, revenue and average fare, and the same by pickup zone.
- **Alert:** a day whose revenue is more than 50% away from the median day is logged as ALERT.
- **Logging:** every run writes to the console and logs/pipeline.log.
- **Tests:** 12 pytest tests cover each check, the gate, the quarantine, the metrics and the alert.

## Automation

The workflow in .github/workflows/daily.yml runs every day at 00:30 UTC (06:00 India time)
and can also be started by hand. On a fresh Ubuntu machine it installs the requirements,
downloads the data, runs the tests, then runs the pipeline.

If the tests fail or the gate blocks the run, the process exits with code 1 and the run is
marked failed in the Actions tab. I tested this by lowering the fare_mismatch limit to 10%:
the run was blocked and showed as failed. [Email notification for failed runs is enabled in
my GitHub settings, but I have not yet received one.]

Limit: the workflow downloads the same January 2026 file every day, so daily runs demonstrate
scheduling, validation and alerting, not new data.

## What I found in the January 2026 data (3,724,889 rows)

- 38.46% of rows (1,432,763) do not add up to total_amount.
- All 1,088,058 Flex Fare trips (payment type 0) have no congestion_surcharge value,
  and 88.5% of them fail the check. The most common gap is $2.50, which matches the
  standard congestion fee. [My interpretation: the total includes it but the row does not itemize it.]
- Among other payment types, 17.8% fail. The most common gap is $3.25 (congestion
  fee plus the new CBD fee). [The cause is not confirmed.]
- About 40,000 rows (1.07%) have negative amounts, mostly disputes and cash reversals.
- 125,738 rows (3.38%) have zero or negative distance.
- 0 duplicates, 1 dropoff-before-pickup, 7 pickups outside January.
- The alert flagged January 25 at 63% below the median day. [Cause unknown.]

## Decisions and limits

- Because 38% fail reconciliation in this data, I set the block limit at 45%,
  so a sudden worsening is caught. The limits are starting values from one month of data.
- Disputed and voided trips are counted in revenue. Whether they should be is a business rule.
- The alert compares each day to the median day, so genuine low days can trigger it.

## Run it

pip install -r requirements.txt
python src/pipeline.py
pytest

Data: NYC TLC Trip Record Data (https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
The data file is not stored in this repository. Download yellow_tripdata_2026-01.parquet into a data/ folder.