import pandas as pd

import pipeline


def make_trips(n=200):
    rows = []
    for i in range(n):
        pickup = pd.Timestamp("2026-01-10 08:00") + pd.Timedelta(minutes=i)
        rows.append({
            "tpep_pickup_datetime": pickup,
            "tpep_dropoff_datetime": pickup + pd.Timedelta(minutes=15),
            "PULocationID": 132 + i % 4,
            "payment_type": 1,
            "trip_distance": 2.0 + i / 100,
            "fare_amount": 10.0 + i / 10,
            "extra": 1.0,
            "mta_tax": 0.5,
            "tip_amount": 2.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "congestion_surcharge": 2.5,
            "Airport_fee": 0.0,
            "cbd_congestion_fee": 0.75,
        })
    df = pd.DataFrame(rows)
    df["total_amount"] = df[pipeline.PARTS].sum(axis=1)
    return df


def test_clean_data_has_no_problems():
    problems = pipeline.find_problems(make_trips())
    assert all(bad.sum() == 0 for bad in problems.values())


def test_negative_fare_is_found():
    df = make_trips()
    df.loc[0, "fare_amount"] = -5.0
    assert pipeline.find_problems(df)["negative_amounts"].sum() == 1


def test_dropoff_before_pickup_is_found():
    df = make_trips()
    df.loc[1, "tpep_dropoff_datetime"] = df.loc[1, "tpep_pickup_datetime"] - pd.Timedelta(hours=1)
    assert pipeline.find_problems(df)["bad_timestamps"].sum() == 1


def test_missing_required_value_is_found():
    df = make_trips()
    df.loc[2, "fare_amount"] = None
    assert pipeline.find_problems(df)["missing_required"].sum() == 1


def test_duplicate_rows_are_found():
    df = make_trips()
    df = pd.concat([df, df.iloc[:3]], ignore_index=True)
    assert pipeline.find_problems(df)["duplicate_rows"].sum() == 3


def test_pickup_outside_month_is_found():
    df = make_trips()
    df.loc[3, "tpep_pickup_datetime"] = pd.Timestamp("2025-12-31 23:00")
    assert pipeline.find_problems(df)["outside_period"].sum() == 1


def test_fare_mismatch_is_found():
    df = make_trips()
    df.loc[4, "total_amount"] += 10
    assert pipeline.find_problems(df)["fare_mismatch"].sum() == 1


def test_one_bad_row_warns_but_does_not_block():
    df = make_trips()
    df.loc[0, "fare_amount"] = -5.0
    _, blocked = pipeline.run_gate(df)
    assert blocked is False


def test_many_bad_rows_block_the_run():
    df = make_trips()
    df.loc[:109, "total_amount"] += 10   # 110 of 200 rows (55%) no longer reconcile
    _, blocked = pipeline.run_gate(df)
    assert blocked is True


def test_bad_rows_are_quarantined():
    df = make_trips()
    df.loc[0, "fare_amount"] = -5.0
    problems = pipeline.find_problems(df)
    clean, rejected = pipeline.split_clean(df, problems)
    assert len(rejected) == 1
    assert len(clean) == len(df) - 1


def test_metrics_add_up():
    df = make_trips()
    daily, zones = pipeline.compute_metrics(df)
    assert daily["trips"].sum() == len(df)
    assert zones["trips"].sum() == len(df)
    assert abs(daily["revenue"].sum() - df["total_amount"].sum()) < 1


def test_collapsed_day_triggers_alert():
    daily = pd.DataFrame({
        "trip_date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
        "revenue": [1000.0, 1050.0, 980.0, 100.0],
    })
    flagged = pipeline.find_anomalies(daily)
    assert list(flagged["trip_date"]) == ["2026-01-04"]