import pandas as pd

df = pd.read_parquet("data/yellow_tripdata_2026-01.parquet")
print("Rows:", len(df))

print("\n--- Missing values (columns with any) ---")
missing = df.isna().sum()
print(missing[missing > 0])

print("\n--- Basic checks ---")
print("Duplicate rows:", df.duplicated().sum())
print("Negative fare_amount:", (df["fare_amount"] < 0).sum())
print("Negative total_amount:", (df["total_amount"] < 0).sum())
print("Zero or negative trip_distance:", (df["trip_distance"] <= 0).sum())
print("Dropoff before pickup:",
      (df["tpep_dropoff_datetime"] < df["tpep_pickup_datetime"]).sum())

outside = (df["tpep_pickup_datetime"] < "2026-01-01") | \
          (df["tpep_pickup_datetime"] >= "2026-02-01")
print("Pickups outside January 2026:", outside.sum())

print("\n--- Reconciliation: do the parts add up to total_amount? ---")
parts = ["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
         "improvement_surcharge", "congestion_surcharge", "Airport_fee",
         "cbd_congestion_fee"]
calc_total = df[parts].fillna(0).sum(axis=1)
mismatch = (calc_total - df["total_amount"]).abs() > 0.015
print("Rows that don't add up:", mismatch.sum(), f"({mismatch.mean():.2%})")
print(df.loc[mismatch, parts + ["total_amount"]].head())
print("\nMismatches by payment type:")
print(df.loc[mismatch, "payment_type"].value_counts())

print("\n--- Valid code checks ---")
print("Invalid VendorID:", (~df["VendorID"].isin({1, 2, 6, 7})).sum())
print("Invalid payment_type:", (~df["payment_type"].isin({0, 1, 2, 3, 4, 5, 6})).sum())
print("Invalid RatecodeID (non-null):",
      (~df["RatecodeID"].dropna().isin({1, 2, 3, 4, 5, 6, 99})).sum())