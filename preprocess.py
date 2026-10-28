import pandas as pd

# ==============================
# 1. LOAD DATASET
# ==============================

input_file = "data/raw/CA_Weather_Fire_Dataset_1984-2025.csv"

df = pd.read_csv(input_file)

print("Original dataset:")
print("Rows:", len(df))
print("Columns:", len(df.columns))


# ==============================
# 2. CONVERT DATE
# ==============================

df["DATE"] = pd.to_datetime(df["DATE"])

# Extract useful date features
df["DAY"] = df["DATE"].dt.day
df["MONTH"] = df["DATE"].dt.month
df["YEAR"] = df["DATE"].dt.year


# ==============================
# 3. HANDLE MISSING NUMERIC DATA
# ==============================

numeric_columns = df.select_dtypes(include=["int64", "float64"]).columns

for column in numeric_columns:
    df[column] = df[column].fillna(df[column].median())


# ==============================
# 4. CONVERT TARGET TO 0/1
# ==============================

df["FIRE_START_DAY"] = df["FIRE_START_DAY"].astype(int)


# ==============================
# 5. CONVERT SEASON TO NUMERIC
# ==============================

season_mapping = {
    "Winter": 0,
    "Spring": 1,
    "Summer": 2,
    "Fall": 3,
    "Autumn": 3
}

df["SEASON"] = df["SEASON"].map(season_mapping)

# If any season value was not recognized
df["SEASON"] = df["SEASON"].fillna(0)


# ==============================
# 6. REMOVE DATE
# ==============================

df = df.drop(columns=["DATE"])


# ==============================
# 7. CHECK DATA
# ==============================

print("\nMissing values after cleaning:")
print(df.isnull().sum())

print("\nTarget distribution:")
print(df["FIRE_START_DAY"].value_counts())

print("\nFinal columns:")
print(df.columns.tolist())


# ==============================
# 8. SAVE PROCESSED DATA
# ==============================

output_file = "data/processed/firesafe_training_data.csv"

df.to_csv(output_file, index=False)

print("\n================================")
print("DATA CLEANING COMPLETED")
print("================================")
print("Saved to:")
print(output_file)

print("\nFinal shape:")
print(df.shape)