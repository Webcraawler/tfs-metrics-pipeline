import sys
import sqlite3
import logging
from pathlib import Path
import pandas as pd

REQUIRED = ["tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID",
            "payment_type", "fare_amount", "total_amount"]
PARTS = ["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
         "improvement_surcharge", "congestion_surcharge", "Airport_fee",
         "cbd_congestion_fee"]


def load(path):
    df = pd.read_parquet(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    return df


def find_problems(df):
    """For each check, return a True/False value for every row (True = bad row)."""
    problems = {}
    problems["missing_required"] = df[REQUIRED].isna().any(axis=1)
    problems["duplicate_rows"] = df.duplicated()
    problems["negative_amounts"] = (df["fare_amount"] < 0) | (df["total_amount"] < 0)
    problems["bad_timestamps"] = df["tpep_dropoff_datetime"] < df["tpep_pickup_datetime"]
    month = df["tpep_pickup_datetime"].dt.to_period("M")
    problems["outside_period"] = month != month.mode()[0]
    problems["zero_distance"] = df["trip_distance"] <= 0
    calc = df[PARTS].fillna(0).sum(axis=1)
    problems["fare_mismatch"] = (calc - df["total_amount"]).abs() > 0.015
    return problems


# check name - block the run if MORE than this share of rows is bad (None = never block)
THRESHOLDS = {
    "missing_required": 0.01,
    "duplicate_rows": 0.01,
    "negative_amounts": 0.03,
    "bad_timestamps": 0.01,
    "outside_period": 0.01,
    "zero_distance": None,
    "fare_mismatch": 0.10, # correct value = 0.45 , to test fail value = 0.10
}
# rows failing these checks are left out of the revenue metrics
QUARANTINE = ["missing_required", "duplicate_rows", "negative_amounts",
              "bad_timestamps", "outside_period"]


def run_gate(df):
    problems = find_problems(df)
    blocked = False
    for name, bad in problems.items():
        share = bad.mean()
        limit = THRESHOLDS[name]
        if limit is not None and share > limit:
            status = "BLOCK"
            blocked = True
        elif bad.sum() > 0:
            status = "WARN"
        else:
            status = "PASS"
        #print(f"{name:18} {status:5} {bad.sum():>10,}  {share:.2%}")
        level = {"PASS": logging.INFO, "WARN": logging.WARNING, "BLOCK": logging.ERROR}[status]
        logging.log(level, "%-18s %-5s %10s  %.2f%%", name, status, f"{bad.sum():,}", share * 100)
    return problems, blocked


def split_clean(df, problems):
    reject = pd.Series(False, index=df.index)
    for name in QUARANTINE:
        reject |= problems[name]
    return df[~reject], df[reject]


def compute_metrics(clean):
    clean = clean.assign(trip_date=clean["tpep_pickup_datetime"].dt.date.astype(str))
    daily = (
        clean.groupby("trip_date")
        .agg(trips=("total_amount", "size"),
             revenue=("total_amount", "sum"),
             avg_fare=("fare_amount", "mean"))
        .round(2)
        .reset_index()
    )
    zones = (
        clean.groupby("PULocationID")
        .agg(trips=("total_amount", "size"),
             revenue=("total_amount", "sum"),
             avg_fare=("fare_amount", "mean"))
        .round(2)
        .reset_index()
        .sort_values("revenue", ascending=False)
    )
    return daily, zones


def save(daily, zones, db_path="metrics.db"):
    with sqlite3.connect(db_path) as conn:
        daily.to_sql("daily_metrics", conn, if_exists="replace", index=False)
        zones.to_sql("zone_metrics", conn, if_exists="replace", index=False)


def setup_logging():
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler("logs/pipeline.log", encoding="utf-8")],
    )


def find_anomalies(daily, threshold=0.5):
    median = daily["revenue"].median()
    deviation = (daily["revenue"] - median) / median
    return daily.assign(deviation=deviation)[deviation.abs() > threshold]

if __name__ == "__main__":
    setup_logging()
    df = load("data/yellow_tripdata_2026-01.parquet")
    logging.info("Loaded %s rows", f"{len(df):,}")
    problems, blocked = run_gate(df)
    if blocked:
        logging.error("BLOCKED: validation failed, no metrics published")
        sys.exit(1)
    clean, rejected = split_clean(df, problems)
    logging.info("Clean rows: %s, quarantined: %s", f"{len(clean):,}", f"{len(rejected):,}")
    daily, zones = compute_metrics(clean)
    save(daily, zones)
    logging.info("Saved %s days and %s zones to metrics.db", len(daily), len(zones))
    for _, row in find_anomalies(daily).iterrows():
        logging.warning("ALERT: revenue on %s is %+.0f%% vs the median day",
                        row["trip_date"], row["deviation"] * 100)




