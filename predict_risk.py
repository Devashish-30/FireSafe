import pandas as pd
import joblib


# ==========================================
# 1. LOAD MODELS
# ==========================================

rf_model = joblib.load(
    "models/random_forest_model.pkl"
)

xgb_model = joblib.load(
    "models/xgboost_model.pkl"
)

print("FireSafe models loaded!")


# ==========================================
# 2. GET USER INPUT
# ==========================================

print("\n===================================")
print("🔥 FIRESAFE LIVE RISK PREDICTOR")
print("===================================\n")

precipitation = float(
    input("Precipitation: ")
)

max_temp = float(
    input("Maximum temperature: ")
)

min_temp = float(
    input("Minimum temperature: ")
)

avg_wind = float(
    input("Average wind speed: ")
)

year = int(
    input("Year: ")
)

month = int(
    input("Month (1-12): ")
)

season = int("Season (0=Winter, 1=Spring, 2=Summer, 3=Fall): ")


lagged_precipitation = float(
    input("Lagged precipitation: ")
)

lagged_wind = float(
    input("Lagged average wind speed: ")
)

day_of_year = int(
    input("Day of year: ")
)


# ==========================================
# 3. CALCULATE DERIVED FEATURES
# ==========================================

temp_range = max_temp - min_temp

if max_temp != 0:
    wind_temp_ratio = avg_wind / max_temp
else:
    wind_temp_ratio = 0


day = 1


# ==========================================
# 4. CREATE INPUT DATAFRAME
# ==========================================

input_data = pd.DataFrame([{

    "PRECIPITATION": precipitation,

    "MAX_TEMP": max_temp,

    "MIN_TEMP": min_temp,

    "AVG_WIND_SPEED": avg_wind,

    "YEAR": year,

    "TEMP_RANGE": temp_range,

    "WIND_TEMP_RATIO": wind_temp_ratio,

    "MONTH": month,

    "SEASON": season,

    "LAGGED_PRECIPITATION": lagged_precipitation,

    "LAGGED_AVG_WIND_SPEED": lagged_wind,

    "DAY_OF_YEAR": day_of_year,

    "DAY": day

}])


# ==========================================
# 5. MAKE PREDICTIONS
# ==========================================

rf_probability = rf_model.predict_proba(
    input_data
)[0][1]

xgb_probability = xgb_model.predict_proba(
    input_data
)[0][1]


# ==========================================
# 6. HYBRID RISK
# ==========================================

risk = (
    0.40 * rf_probability
    +
    0.60 * xgb_probability
)

risk_percentage = risk * 100


# ==========================================
# 7. RISK LEVEL
# ==========================================

if risk_percentage < 25:

    risk_level = "LOW"

elif risk_percentage < 50:

    risk_level = "MODERATE"

elif risk_percentage < 75:

    risk_level = "HIGH"

else:

    risk_level = "CRITICAL"


# ==========================================
# 8. DISPLAY RESULT
# ==========================================

print("\n===================================")
print("🔥 FIRESAFE PREDICTION")
print("===================================")

print(
    f"Random Forest Risk : {rf_probability * 100:.2f}%"
)

print(
    f"XGBoost Risk       : {xgb_probability * 100:.2f}%"
)

print(
    f"🔥 HYBRID FIRE RISK : {risk_percentage:.2f}%"
)

print(
    f"⚠️ RISK LEVEL       : {risk_level}"
)

print("===================================")