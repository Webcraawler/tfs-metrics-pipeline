import pandas as pd

df = pd.read_parquet("data/yellow_tripdata_2026-01.parquet")

print(df.shape)
print(df.columns.tolist())
print(df.head())
df.info()