import pandas as pd
import joblib
import numpy as np

# ==========================================
# 1. LOAD DATA
# ==========================================

data_file = "data/processed/firesafe_training_data.csv"

df = pd.read_csv(data_file)

X = df.drop(columns=["FIRE_START_DAY"])
y = df["FIRE_START_DAY"]


# ==========================================
# 2. LOAD TRAINED MODELS
# ==========================================

rf_model = joblib.load(
    "models/random_forest_model.pkl"
)

xgb_model = joblib.load(
    "models/xgboost_model.pkl"
)

print("Models loaded successfully!")


# ==========================================
# 3. GET PROBABILITY FROM BOTH MODELS
# ==========================================

rf_probability = rf_model.predict_proba(X)[:, 1]

xgb_probability = xgb_model.predict_proba(X)[:, 1]


# ==========================================
# 4. HYBRID RISK SCORE
# ==========================================

# Random Forest = 40%
# XGBoost = 60%

hybrid_probability = (
    0.40 * rf_probability
    +
    0.60 * xgb_probability
)


# Convert to percentage

risk_percentage = hybrid_probability * 100


# ==========================================
# 5. CREATE RISK LEVEL
# ==========================================

def get_risk_level(score):

    if score < 25:
        return "LOW"

    elif score < 50:
        return "MODERATE"

    elif score < 75:
        return "HIGH"

    else:
        return "CRITICAL"


risk_level = [
    get_risk_level(score)
    for score in risk_percentage
]


# ==========================================
# 6. CREATE RESULTS
# ==========================================

results = pd.DataFrame({
    "RF_RISK": rf_probability * 100,
    "XGB_RISK": xgb_probability * 100,
    "FIRE_RISK": risk_percentage,
    "RISK_LEVEL": risk_level,
    "ACTUAL_FIRE": y
})


# ==========================================
# 7. DISPLAY RESULTS
# ==========================================

print("\n==========================================")
print("FIRESAFE HYBRID MODEL")
print("==========================================")

print(results.head(20))


# ==========================================
# 8. SAVE RESULTS
# ==========================================

output_file = "data/processed/firesafe_risk_predictions.csv"

results.to_csv(
    output_file,
    index=False
)

print("\nRisk predictions saved to:")
print(output_file)


# ==========================================
# 9. SUMMARY
# ==========================================

print("\nRisk level distribution:")

print(
    results["RISK_LEVEL"].value_counts()
)

print("\nAverage Fire Risk:")
print(
    round(results["FIRE_RISK"].mean(), 2),
    "%"
)

print("\n==========================================")
print("HYBRID MODEL COMPLETED")
print("==========================================")