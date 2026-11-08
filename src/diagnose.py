import pandas as pd

df = pd.read_parquet("data/yellow_tripdata_2026-01.parquet")
parts = ["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
         "improvement_surcharge", "congestion_surcharge", "Airport_fee",
         "cbd_congestion_fee"]

diff = (df[parts].fillna(0).sum(axis=1) - df["total_amount"]).round(2)
bad = diff.abs() > 0.015

print("--- Most common differences (parts minus total) ---")
print(diff[bad].value_counts().head(8))

print("\n--- Mismatch by payment type: rows, bad rows, % bad ---")
g = bad.groupby(df["payment_type"]).agg(["size", "sum", "mean"])
print(g.round(3))

print("\n--- Missing congestion_surcharge by payment type ---")
print(df["congestion_surcharge"].isna().groupby(df["payment_type"]).sum())

print("\n--- Negative total_amount by payment type ---")
print((df["total_amount"] < 0).groupby(df["payment_type"]).sum())

print("\n--- Mismatch rate excluding payment type 0 ---")
rest = df["payment_type"] != 0
print(f"{bad[rest].mean():.2%} of {rest.sum():,} rows")