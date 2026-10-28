import pandas as pd

file_path = "data/raw/CA_Weather_Fire_Dataset_1984-2025.csv"

df = pd.read_csv(file_path)

print("\n========== FIRE_START_DAY VALUES ==========")
print(df["FIRE_START_DAY"].value_counts(dropna=False))

print("\n========== DATA TYPES ==========")
print(df.dtypes)

print("\n========== FIRE START EXAMPLES ==========")
print(
    df[df["FIRE_START_DAY"].notna()]
    [["DATE", "FIRE_START_DAY", "MAX_TEMP", "MIN_TEMP", "AVG_WIND_SPEED"]]
    .head(20)
)