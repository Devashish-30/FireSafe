import requests
import pandas as pd


# =====================================================
# NASA FIRMS SETTINGS
# =====================================================

MAP_KEY = "96e5b5ebde3750c86f52b27e16802400"

SOURCE = "VIIRS_NOAA21_NRT"

# India bounding box
# west, south, east, north
AREA = "68,6,98,36"

DAYS = 1


# =====================================================
# FETCH NASA FIRMS DATA
# =====================================================

def get_nasa_fire_data():

    url = (
        "https://firms.modaps.eosdis.nasa.gov/"
        f"api/area/csv/"
        f"{MAP_KEY}/"
        f"{SOURCE}/"
        f"{AREA}/"
        f"{DAYS}"
    )

    try:

        response = requests.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        from io import StringIO

        df = pd.read_csv(
            StringIO(response.text)
        )

        return df

    except Exception as e:

        print("NASA FIRMS ERROR:", e)

        return pd.DataFrame()


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    print("🔥 Connecting to NASA FIRMS...")

    fires = get_nasa_fire_data()

    if fires.empty:

        print("❌ No NASA fire data received.")

    else:

        print("✅ NASA FIRMS data received!")

        print(
            "Fire detections:",
            len(fires)
        )

        print("\nColumns:")

        print(
            list(fires.columns)
        )

        print("\nLatest detections:")

        print(
            fires.head(10)
        )