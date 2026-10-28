import streamlit as st
import pandas as pd
import numpy as np
import requests
import pydeck as pdk
import math
import os

from io import StringIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# SELECTED FIRE LOCATION STATE
# ============================================================

if "selected_fire" not in st.session_state:
    st.session_state["selected_fire"] = None


# ============================================================
# FIRESAFE - GLOBAL WILDFIRE COMMAND CENTER
# ============================================================

st.set_page_config(
    page_title="FireSafe Command Center",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# SETTINGS
# ============================================================

# Set NASA_FIRMS_MAP_KEY in your terminal or Streamlit secrets.
# Do not hardcode API keys in source code.
NASA_MAP_KEY = "96e5b5ebde3750c86f52b27e16802400"

NASA_SOURCE = "VIIRS_NOAA21_NRT"
NASA_AREA = "world"
NASA_DAYS = 3

REFRESH_MINUTES = 15

# Water analysis
WATER_ANALYSIS_LIMIT = 10
WATER_SEARCH_RADIUS = 50000

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]


# ============================================================
# CSS ONLY
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #07111f;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }

    .hero-box {
        background: linear-gradient(
            135deg,
            #102a43 0%,
            #07111f 75%
        );

        border: 1px solid #24415e;
        border-radius: 18px;
        padding: 25px;
        margin-bottom: 18px;
    }

    .hero-title {
        font-size: 40px;
        font-weight: 800;
        color: #f4f8ff;
        margin-bottom: 5px;
    }

    .hero-subtitle {
        font-size: 17px;
        color: #9fb3c8;
    }

    .live-box {
        background: rgba(0, 200, 100, 0.10);
        border: 1px solid rgba(0, 220, 120, 0.35);
        color: #6ff0ad;
        border-radius: 10px;
        padding: 12px 15px;
        margin-bottom: 18px;
    }

    .section-title {
        color: #f4f8ff;
        font-size: 22px;
        font-weight: 750;
        margin-top: 18px;
        margin-bottom: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero-box">
        <div class="hero-title">🔥 FireSafe Command Center</div>
        <div class="hero-subtitle">
            Global satellite-based wildfire monitoring,
            risk scoring, hotspot intelligence and
            nearby water-resource analysis.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🔥 FireSafe")

st.sidebar.success("Live monitoring enabled")

st.sidebar.markdown("---")

st.sidebar.markdown("### 🛰️ Satellite")
st.sidebar.write("VIIRS NOAA-21 NRT")

st.sidebar.markdown("### 🌍 Coverage")
st.sidebar.write("Worldwide")

st.sidebar.markdown("### 🔄 Refresh")
st.sidebar.write(f"Every {REFRESH_MINUTES} minutes")

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
    ### Risk Levels

    🔴 **CRITICAL**

    🟠 **HIGH**

    🟡 **MODERATE**

    🟢 **LOW**
    """
)


# ============================================================
# AUTO REFRESH
# ============================================================

try:

    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(
        interval=REFRESH_MINUTES * 60 * 1000,
        limit=None,
        key="firesafe_refresh"
    )

except Exception:
    pass


# ============================================================
# NASA FIRMS
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False
)
def get_nasa_data():

    if not NASA_MAP_KEY:
        raise RuntimeError(
            "NASA FIRMS API key is missing. Set NASA_FIRMS_MAP_KEY "
            "in the same PowerShell terminal before starting Streamlit."
        )

    # Try several near-real-time feeds in case one feed is temporarily empty.
    sources = [
        NASA_SOURCE,
        "VIIRS_SNPP_NRT",
        "VIIRS_NOAA20_NRT",
        "MODIS_NRT"
    ]

    errors = []
    response_notes = []

    for source in dict.fromkeys(sources):
        try:
            url = (
                "https://firms.modaps.eosdis.nasa.gov/"
                f"api/area/csv/{NASA_MAP_KEY}/{source}/"
                f"{NASA_AREA}/{NASA_DAYS}"
            )
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            text = response.text.strip()

            if not text:
                response_notes.append(f"{source}: empty response")
                continue

            # FIRMS may return a text/CSV error with HTTP 200.
            try:
                data = pd.read_csv(StringIO(text))
            except pd.errors.EmptyDataError:
                response_notes.append(f"{source}: empty CSV response")
                continue

            # Normalize headers (whitespace/case/BOM can otherwise
            # make valid NASA CSV columns appear to be missing).
            data.columns = [
                str(column).replace("\\ufeff", "").strip().lower()
                for column in data.columns
            ]

            required = {"latitude", "longitude", "frp"}
            if not required.issubset(data.columns):
                preview = " ".join(text.split())[:220]
                response_notes.append(
                    f"{source}: unexpected response ({preview})"
                )
                continue

            data["latitude"] = pd.to_numeric(data["latitude"], errors="coerce")
            data["longitude"] = pd.to_numeric(data["longitude"], errors="coerce")
            data["frp"] = pd.to_numeric(data["frp"], errors="coerce")
            data = data.dropna(subset=["latitude", "longitude"]).copy()
            data = data[
                data["latitude"].between(-90, 90)
                & data["longitude"].between(-180, 180)
            ].copy()

            if not data.empty:
                data["_firms_source"] = source
                return data

            response_notes.append(f"{source}: valid CSV, but no usable observations")

        except requests.exceptions.HTTPError as error:
            status = error.response.status_code if error.response is not None else "unknown"
            body = ""
            if error.response is not None:
                body = " ".join(error.response.text.split())[:180]
            errors.append(f"{source}: HTTP {status} {body}".strip())
        except Exception as error:
            errors.append(f"{source}: {type(error).__name__}: {error}")

    details = "; ".join((errors + response_notes)[-4:])
    if details:
        raise RuntimeError(
            "NASA FIRMS could not provide usable fire observations. "
            "Check that the API key is valid and active, and that internet access "
            f"is available. Details: {details}"
        )

    raise RuntimeError(
        "NASA FIRMS returned no usable fire observations from the available feeds."
    )


# ============================================================
# CONFIDENCE
# ============================================================

def confidence_to_number(value):

    if pd.isna(value):
        return 50.0

    text = str(value).strip().lower()

    if text in ["h", "high"]:
        return 90.0

    if text in ["n", "nominal", "medium", "m"]:
        return 60.0

    if text in ["l", "low"]:
        return 30.0

    try:

        number = float(value)

        if number <= 1:
            return number * 100

        return number

    except Exception:

        return 50.0


# ============================================================
# FIRE RISK
# ============================================================

def calculate_fire_risk(
    frp,
    confidence,
    brightness
):

    score = 0

    if frp >= 300:
        score += 50

    elif frp >= 150:
        score += 38

    elif frp >= 75:
        score += 28

    elif frp >= 30:
        score += 18

    else:
        score += 10

    if confidence >= 80:
        score += 30

    elif confidence >= 60:
        score += 24

    elif confidence >= 40:
        score += 16

    else:
        score += 10

    if brightness >= 330:
        score += 20

    elif brightness >= 315:
        score += 15

    elif brightness >= 300:
        score += 10

    else:
        score += 5

    score = min(score, 100)

    if score >= 80:
        return "CRITICAL", score

    elif score >= 60:
        return "HIGH", score

    elif score >= 40:
        return "MODERATE", score

    return "LOW", score


# ============================================================
# RISK COLOR
# ============================================================

def get_risk_color(risk):

    if risk == "CRITICAL":
        return [255, 40, 40, 235]

    if risk == "HIGH":
        return [255, 125, 30, 230]

    if risk == "MODERATE":
        return [255, 205, 30, 225]

    return [40, 220, 130, 220]


# ============================================================
# HAVERSINE
# ============================================================

def haversine(
    lat1,
    lon1,
    lat2,
    lon2
):

    earth_radius = 6371.0

    lat1 = math.radians(float(lat1))
    lat2 = math.radians(float(lat2))

    dlat = math.radians(
        float(lat2) - float(lat1)
    )

    dlon = math.radians(
        float(lon2) - float(lon1)
    )

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# ============================================================
# LOCATION WEATHER
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False
)
def get_location_weather(
    latitude,
    longitude
):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "cloud_cover,"
            "pressure_msl,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "weather_code"
        ),

        "wind_speed_unit": "kmh",

        "timezone": "auto"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        return response.json()

    except Exception as error:

        return {
            "error": str(error)
        }


# ============================================================
# LOCATION NAME
# ============================================================

@st.cache_data(
    ttl=86400,
    show_spinner=False
)
def get_location_name(
    latitude,
    longitude
):

    try:

        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",

            params={
                "lat": float(latitude),
                "lon": float(longitude),
                "format": "json",
                "zoom": 10,
                "addressdetails": 1
            },

            headers={
                "User-Agent":
                "FireSafe-Wildfire-Monitor/1.0"
            },

            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        address = data.get(
            "address",
            {}
        )

        place = (
            address.get("city")
            or
            address.get("town")
            or
            address.get("municipality")
            or
            address.get("village")
            or
            address.get("county")
        )

        state = (
            address.get("state")
            or
            address.get("state_district")
            or
            address.get("region")
        )

        country = address.get(
            "country"
        )

        parts = [
            x
            for x in [
                place,
                state,
                country
            ]
            if x
        ]

        if parts:

            return ", ".join(
                dict.fromkeys(parts)
            )

        return "Location unavailable"

    except Exception:

        return "Location unavailable"


# ============================================================
# WEATHER DESCRIPTION
# ============================================================

def weather_code_text(code):

    try:

        code = int(code)

    except Exception:

        return "Unknown"

    weather_codes = {

        0: "Clear sky",

        1: "Mainly clear",

        2: "Partly cloudy",

        3: "Overcast",

        45: "Fog",

        48: "Rime fog",

        51: "Light drizzle",

        53: "Moderate drizzle",

        55: "Dense drizzle",

        61: "Light rain",

        63: "Moderate rain",

        65: "Heavy rain",

        71: "Light snow",

        73: "Moderate snow",

        75: "Heavy snow",

        80: "Rain showers",

        81: "Moderate rain showers",

        82: "Heavy rain showers",

        95: "Thunderstorm",

        96: "Thunderstorm + hail",

        99: "Thunderstorm + heavy hail"

    }

    return weather_codes.get(
        code,
        "Unknown conditions"
    )


# ============================================================
# SELECTED FIRE DETAILS
# ============================================================

def show_selected_fire_details(
    selected_fire
):

    if not selected_fire:

        st.info(
            "🖱️ Click any 🔥 fire marker on the map "
            "to view detailed location information."
        )

        return


    try:

        latitude = float(
            selected_fire["latitude"]
        )

        longitude = float(
            selected_fire["longitude"]
        )

    except Exception:

        st.error(
            "Unable to read selected fire coordinates."
        )

        return


    risk = selected_fire.get(
        "Risk",
        "UNKNOWN"
    )

    risk_score = selected_fire.get(
        "Risk Score",
        "-"
    )

    frp = selected_fire.get(
        "frp",
        "-"
    )

    confidence = selected_fire.get(
        "confidence",
        "-"
    )

    brightness = selected_fire.get(
        "bright_ti4",
        "-"
    )

    detection_date = selected_fire.get(
        "acq_date",
        "-"
    )

    detection_time = selected_fire.get(
        "acq_time",
        "-"
    )

    daynight = selected_fire.get(
        "daynight",
        "-"
    )


    st.markdown("---")

    st.subheader(
        "📍 Selected Fire Location"
    )


    location_name = get_location_name(
        latitude,
        longitude
    )


    st.markdown(
        f"### 🌍 {location_name}"
    )

    st.caption(
        f"Coordinates: "
        f"{latitude:.5f}, "
        f"{longitude:.5f}"
    )


    # ========================================================
    # NASA INFORMATION
    # ========================================================

    st.markdown(
        "#### 🔥 NASA Fire Detection"
    )


    f1, f2, f3, f4, f5 = st.columns(5)


    with f1:

        st.metric(
            "Fire Risk",
            str(risk)
        )


    with f2:

        try:

            st.metric(
                "Risk Score",
                f"{float(risk_score):.0f}%"
            )

        except Exception:

            st.metric(
                "Risk Score",
                str(risk_score)
            )


    with f3:

        try:

            st.metric(
                "FRP",
                f"{float(frp):.2f} MW"
            )

        except Exception:

            st.metric(
                "FRP",
                str(frp)
            )


    with f4:

        try:

            st.metric(
                "Confidence",
                f"{float(confidence):.0f}%"
            )

        except Exception:

            st.metric(
                "Confidence",
                str(confidence)
            )


    with f5:

        try:

            st.metric(
                "Brightness",
                f"{float(brightness):.1f} K"
            )

        except Exception:

            st.metric(
                "Brightness",
                str(brightness)
            )


    # ========================================================
    # WEATHER
    # ========================================================

    st.markdown(
        "#### 🌦️ Current Weather at Fire Location"
    )


    with st.spinner(
        "🌐 Loading local weather..."
    ):

        weather = get_location_weather(
            latitude,
            longitude
        )


    if "error" in weather:

        st.warning(
            "Weather data could not be loaded. "
            "Please try clicking the fire marker again."
        )

    else:

        current = weather.get(
            "current",
            {}
        )


        temperature = current.get(
            "temperature_2m"
        )

        humidity = current.get(
            "relative_humidity_2m"
        )

        apparent = current.get(
            "apparent_temperature"
        )

        wind_speed = current.get(
            "wind_speed_10m"
        )

        wind_direction = current.get(
            "wind_direction_10m"
        )

        precipitation = current.get(
            "precipitation"
        )

        cloud_cover = current.get(
            "cloud_cover"
        )

        pressure = current.get(
            "pressure_msl"
        )

        weather_code = current.get(
            "weather_code"
        )


        # ====================================================
        # WEATHER ROW 1
        # ====================================================

        w1, w2, w3, w4 = st.columns(4)


        with w1:

            st.metric(
                "🌡️ Temperature",

                (
                    f"{temperature:.1f} °C"
                    if temperature is not None
                    else "N/A"
                )
            )


        with w2:

            st.metric(
                "💧 Humidity",

                (
                    f"{humidity:.0f}%"
                    if humidity is not None
                    else "N/A"
                )
            )


        with w3:

            st.metric(
                "💨 Wind Speed",

                (
                    f"{wind_speed:.1f} km/h"
                    if wind_speed is not None
                    else "N/A"
                )
            )


        with w4:

            st.metric(
                "🧭 Wind Direction",

                (
                    f"{wind_direction:.0f}°"
                    if wind_direction is not None
                    else "N/A"
                )
            )


        # ====================================================
        # WEATHER ROW 2
        # ====================================================

        w5, w6, w7, w8 = st.columns(4)


        with w5:

            st.metric(
                "🌡️ Feels Like",

                (
                    f"{apparent:.1f} °C"
                    if apparent is not None
                    else "N/A"
                )
            )


        with w6:

            st.metric(
                "🌧️ Precipitation",

                (
                    f"{precipitation:.1f} mm"
                    if precipitation is not None
                    else "N/A"
                )
            )


        with w7:

            st.metric(
                "☁️ Cloud Cover",

                (
                    f"{cloud_cover:.0f}%"
                    if cloud_cover is not None
                    else "N/A"
                )
            )


        with w8:

            st.metric(
                "🧭 Pressure",

                (
                    f"{pressure:.0f} hPa"
                    if pressure is not None
                    else "N/A"
                )
            )


        st.info(
            "🌤️ Weather: "
            + weather_code_text(
                weather_code
            )
        )


    # ========================================================
    # DETECTION INFORMATION
    # ========================================================

    st.markdown(
        "#### 🛰️ Detection Information"
    )


    d1, d2, d3 = st.columns(3)


    with d1:

        st.write(
            f"**Detection Date:** "
            f"{detection_date}"
        )


    with d2:

        st.write(
            f"**Detection Time UTC:** "
            f"{detection_time}"
        )


    with d3:

        st.write(
            f"**Day / Night:** "
            f"{daynight}"
        )


# ============================================================
# WATER SEARCH
# ============================================================

@st.cache_data(
    ttl=21600,
    show_spinner=False
)
def find_water(
    latitude,
    longitude
):

    query = f"""
    [out:json][timeout:20];

    (
        nwr(
            around:{WATER_SEARCH_RADIUS},
            {latitude},
            {longitude}
        )["natural"="water"];

        nwr(
            around:{WATER_SEARCH_RADIUS},
            {latitude},
            {longitude}
        )["waterway"="river"];

        nwr(
            around:{WATER_SEARCH_RADIUS},
            {latitude},
            {longitude}
        )["waterway"="stream"];

        nwr(
            around:{WATER_SEARCH_RADIUS},
            {latitude},
            {longitude}
        )["landuse"="reservoir"];

        nwr(
            around:{WATER_SEARCH_RADIUS},
            {latitude},
            {longitude}
        )["natural"="wetland"];
    );

    out center tags;
    """


    for server in OVERPASS_SERVERS:

        try:

            response = requests.post(
                server,
                data=query,
                headers={
                    "User-Agent":
                    "FireSafe-Wildfire-Monitor/1.0"
                },
                timeout=25
            )


            if response.status_code != 200:

                continue


            data = response.json()

            candidates = []


            for element in data.get(
                "elements",
                []
            ):

                if (
                    "lat" in element
                    and
                    "lon" in element
                ):

                    wlat = float(
                        element["lat"]
                    )

                    wlon = float(
                        element["lon"]
                    )

                elif "center" in element:

                    wlat = float(
                        element["center"]["lat"]
                    )

                    wlon = float(
                        element["center"]["lon"]
                    )

                else:

                    continue


                distance = haversine(
                    latitude,
                    longitude,
                    wlat,
                    wlon
                )


                tags = element.get(
                    "tags",
                    {}
                )


                name = (
                    tags.get("name")
                    or
                    tags.get("name:en")
                    or
                    tags.get("official_name")
                    or
                    "Unnamed water resource"
                )


                waterway = tags.get(
                    "waterway",
                    ""
                )

                natural = tags.get(
                    "natural",
                    ""
                )

                landuse = tags.get(
                    "landuse",
                    ""
                )


                if waterway == "river":

                    water_type = "River"

                elif waterway == "stream":

                    water_type = "Stream"

                elif landuse == "reservoir":

                    water_type = "Reservoir"

                elif natural == "wetland":

                    water_type = "Wetland"

                elif natural == "water":

                    water_type = "Lake / Waterbody"

                else:

                    water_type = "Water Resource"


                candidates.append(
                    {
                        "name": name,
                        "type": water_type,
                        "latitude": wlat,
                        "longitude": wlon,
                        "distance": distance
                    }
                )


            if candidates:

                candidates.sort(
                    key=lambda x:
                    x["distance"]
                )

                return candidates[0]


        except Exception:

            continue


    return {
        "name":
        "No mapped water found",

        "type":
        "Not available",

        "latitude":
        None,

        "longitude":
        None,

        "distance":
        None
    }


# ============================================================
# PARALLEL WATER ANALYSIS
# ============================================================

def analyze_water_parallel(
    fire_dataframe
):

    if fire_dataframe.empty:

        return []


    results = []


    with ThreadPoolExecutor(
        max_workers=5
    ) as executor:

        futures = {}


        for index, row in fire_dataframe.iterrows():

            future = executor.submit(
                find_water,
                float(row["latitude"]),
                float(row["longitude"])
            )

            futures[future] = index


        for future in as_completed(
            futures
        ):

            index = futures[future]


            try:

                result = future.result()


            except Exception:

                result = {

                    "name":
                    "Water analysis failed",

                    "type":
                    "Unavailable",

                    "latitude":
                    None,

                    "longitude":
                    None,

                    "distance":
                    None

                }


            results.append(
                (
                    index,
                    result
                )
            )


    results.sort(
        key=lambda x: x[0]
    )


    return [
        result
        for _, result in results
    ]


# ============================================================
# LOAD NASA DATA
# ============================================================

with st.spinner(
    "🛰️ Connecting to NASA FIRMS..."
):

    try:

        fires = get_nasa_data()

        nasa_connected = True

    except Exception as error:

        fires = pd.DataFrame()

        nasa_connected = False

        st.error(
            f"NASA FIRMS connection failed: {error}"
        )


# ============================================================
# NASA CONNECTION CHECK
# ============================================================

if not nasa_connected:

    st.error(
        "🔴 NASA FIRMS connection failed. "
        "Check your internet connection or NASA FIRMS key."
    )

    st.stop()


# ============================================================
# CLEAN NASA DATA
# ============================================================

required_columns = [
    "latitude",
    "longitude",
    "frp"
]


for column in required_columns:

    if column not in fires.columns:

        st.error(
            f"NASA data is missing required column: {column}"
        )

        st.stop()


fires["latitude"] = pd.to_numeric(
    fires["latitude"],
    errors="coerce"
)


fires["longitude"] = pd.to_numeric(
    fires["longitude"],
    errors="coerce"
)


fires["frp"] = pd.to_numeric(
    fires["frp"],
    errors="coerce"
).fillna(0)


if "bright_ti4" in fires.columns:

    fires["bright_ti4"] = pd.to_numeric(
        fires["bright_ti4"],
        errors="coerce"
    ).fillna(0)

else:

    fires["bright_ti4"] = 0


if "bright_ti5" in fires.columns:

    fires["bright_ti5"] = pd.to_numeric(
        fires["bright_ti5"],
        errors="coerce"
    ).fillna(0)

else:

    fires["bright_ti5"] = 0


if "confidence" in fires.columns:

    fires["confidence_numeric"] = (
        fires["confidence"]
        .apply(confidence_to_number)
    )

else:

    fires["confidence_numeric"] = 50.0


if "daynight" not in fires.columns:

    fires["daynight"] = "Unknown"


if "acq_date" not in fires.columns:

    fires["acq_date"] = ""


if "acq_time" not in fires.columns:

    fires["acq_time"] = ""


fires = fires.dropna(
    subset=[
        "latitude",
        "longitude"
    ]
).copy()


# ============================================================
# CALCULATE FIRE RISK
# ============================================================

risk_values = fires.apply(
    lambda row:
    calculate_fire_risk(
        row["frp"],
        row["confidence_numeric"],
        row["bright_ti4"]
    ),
    axis=1
)


fires["Risk"] = [
    value[0]
    for value in risk_values
]


fires["Risk Score"] = [
    value[1]
    for value in risk_values
]


fires["color"] = (
    fires["Risk"]
    .apply(get_risk_color)
)


# ============================================================
# GLOBAL STATISTICS
# ============================================================

total_fires = int(len(fires))

total_frp = float(
    pd.to_numeric(fires["frp"], errors="coerce")
    .fillna(0)
    .sum()
)

max_frp = float(
    pd.to_numeric(fires["frp"], errors="coerce")
    .fillna(0)
    .max()
)

avg_frp = float(
    pd.to_numeric(fires["frp"], errors="coerce")
    .fillna(0)
    .mean()
)

avg_confidence = float(
    pd.to_numeric(
        fires["confidence_numeric"],
        errors="coerce"
    )
    .fillna(50)
    .mean()
)

avg_brightness = float(
    pd.to_numeric(
        fires["bright_ti4"],
        errors="coerce"
    )
    .fillna(0)
    .mean()
)


critical_count = (
    fires["Risk"] == "CRITICAL"
).sum()


high_count = (
    fires["Risk"] == "HIGH"
).sum()


moderate_count = (
    fires["Risk"] == "MODERATE"
).sum()


low_count = (
    fires["Risk"] == "LOW"
).sum()


day_count = (
    fires["daynight"]
    .astype(str)
    .str.upper()
    .eq("D")
    .sum()
)


night_count = (
    fires["daynight"]
    .astype(str)
    .str.upper()
    .eq("N")
    .sum()
)


# ============================================================
# GLOBAL RISK
# ============================================================

global_risk_score = (
    min(total_fires / 5000, 1) * 30
    + min(total_frp / 100000, 1) * 30
    + min(max_frp / 2000, 1) * 20
    + (avg_confidence / 100) * 20
)

# Never allow NaN/inf to reach Streamlit progress widgets.
if not math.isfinite(global_risk_score):
    global_risk_score = 0.0

global_risk_score = max(
    0.0,
    min(float(global_risk_score), 100.0)
)


if global_risk_score >= 75:

    global_risk = "CRITICAL"
    global_icon = "🔴"

elif global_risk_score >= 50:

    global_risk = "HIGH"
    global_icon = "🟠"

elif global_risk_score >= 25:

    global_risk = "MODERATE"
    global_icon = "🟡"

else:

    global_risk = "LOW"
    global_icon = "🟢"


# ============================================================
# LIVE STATUS
# ============================================================

st.success(
    "🟢 LIVE NASA FIRMS DATA CONNECTED — "
    "satellite fire detections successfully loaded."
)


# ============================================================
# CONTROL BAR
# ============================================================

st.subheader(
    "🎛️ Command Center Controls"
)


control1, control2, control3 = st.columns(
    [2, 2, 1]
)


with control1:

    risk_filter = st.multiselect(
        "🔥 Risk Filter",

        [
            "CRITICAL",
            "HIGH",
            "MODERATE",
            "LOW"
        ],

        default=[
            "CRITICAL",
            "HIGH",
            "MODERATE",
            "LOW"
        ]
    )


with control2:

    map_limit = st.selectbox(
        "🗺️ Map Rendering",

        [
            "All NASA detections",
            "Top 5000 detections",
            "Top 2500 detections"
        ],

        index=0
    )


with control3:

    if st.button(
        "🔄 Fetch Now",
        use_container_width=True
    ):

        get_nasa_data.clear()

        st.rerun()


# ============================================================
# FILTER DATA
# ============================================================

filtered_fires = fires[
    fires["Risk"].isin(
        risk_filter
    )
].copy()


if map_limit == "Top 5000 detections":

    map_data = (
        filtered_fires
        .sort_values(
            "Risk Score",
            ascending=False
        )
        .head(5000)
        .copy()
    )


elif map_limit == "Top 2500 detections":

    map_data = (
        filtered_fires
        .sort_values(
            "Risk Score",
            ascending=False
        )
        .head(2500)
        .copy()
    )


else:

    map_data = filtered_fires.copy()


# ============================================================
# KPI SECTION
# ============================================================

st.subheader(
    "🌍 Global Fire Situation"
)


k1, k2, k3, k4, k5 = st.columns(5)


with k1:

    st.metric(
        "🔥 Active Fire Detections",
        f"{total_fires:,}"
    )


with k2:

    st.metric(
        "⚡ Total FRP",
        f"{total_frp:,.1f}"
    )


with k3:

    st.metric(
        "⚡ Peak FRP",
        f"{max_frp:,.1f}"
    )


with k4:

    st.metric(
        "🎯 Avg Confidence",
        f"{avg_confidence:.1f}%"
    )


with k5:

    st.metric(
        "🌡️ Avg Brightness",
        f"{avg_brightness:.1f} K"
    )


# ============================================================
# RISK KPI
# ============================================================

r1, r2, r3, r4, r5 = st.columns(5)


with r1:

    st.metric(
        "🌍 Global Risk",
        f"{global_risk_score:.1f}%"
    )


with r2:

    st.metric(
        "🔴 Critical",
        f"{critical_count:,}"
    )


with r3:

    st.metric(
        "🟠 High",
        f"{high_count:,}"
    )


with r4:

    st.metric(
        "🟡 Moderate",
        f"{moderate_count:,}"
    )


with r5:

    st.metric(
        "🟢 Low",
        f"{low_count:,}"
    )


# ============================================================
# MAP + ANALYSIS
# ============================================================

st.subheader(
    "🔥 Wildfire Risk & Active-Fire Map"
)


map_col, analysis_col = st.columns(
    [2.2, 1]
)


# ============================================================
# MAP
# ============================================================

with map_col:

    st.caption(
        f"Showing {len(map_data):,} individual "
        f"NASA fire observations."
    )


    if not map_data.empty:

        map_data["marker_size"] = (
            map_data["frp"]
            .clip(
                lower=10,
                upper=500
            )
            * 18
        )


        fire_layer = pdk.Layer(

            "ScatterplotLayer",

            id="fire-detections",

            data=map_data,

            get_position=[
                "longitude",
                "latitude"
            ],

            get_radius="marker_size",

            radius_min_pixels=2,

            radius_max_pixels=12,

            get_fill_color="color",

            get_line_color=[
                255,
                255,
                255,
                120
            ],

            line_width_min_pixels=0.5,

            # IMPORTANT FOR CLICK
            pickable=True,

            auto_highlight=True
        )


        view_state = pdk.ViewState(

            latitude=20,

            longitude=0,

            zoom=1.15,

            pitch=0,

            bearing=0
        )


        deck = pdk.Deck(

            layers=[
                fire_layer
            ],

            initial_view_state=view_state,

            map_style=
            "https://basemaps.cartocdn.com/"
            "gl/dark-matter-gl-style/"
            "style.json",

            tooltip={

                "html": """
                <div style="padding:10px;">

                    <b>🔥 FIRE DETECTION</b>
                    <br/><br/>

                    <b>Risk:</b>
                    {Risk}
                    <br/>

                    <b>Risk Score:</b>
                    {Risk Score}
                    <br/>

                    <b>FRP:</b>
                    {frp}
                    <br/>

                    <b>Confidence:</b>
                    {confidence}
                    <br/>

                    <b>Brightness:</b>
                    {bright_ti4}
                    <br/>

                    <b>Latitude:</b>
                    {latitude}
                    <br/>

                    <b>Longitude:</b>
                    {longitude}
                    <br/>

                    <b>Date:</b>
                    {acq_date}
                    <br/>

                    <b>Time:</b>
                    {acq_time}

                </div>
                """
            }
        )


        # ====================================================
        # IMPORTANT:
        # on_select makes the marker clickable.
        # A stable layer id is required for selection state.
        # ====================================================

        map_event = st.pydeck_chart(

            deck,

            use_container_width=True,

            on_select="rerun",

            selection_mode="single-object",

            key="firesafe_fire_map"
        )


        # ====================================================
        # SAVE SELECTED FIRE - FIXED
        # ====================================================
        # Current Streamlit PyDeck format:
        # selection.objects = {layer_id: [object_dict]}
        # ====================================================

        try:

            selection = map_event.selection
            objects = selection.objects
            selected_fire = None

            if isinstance(objects, dict):

                layer_objects = objects.get(
                    "fire-detections",
                    []
                )

                if isinstance(layer_objects, list) and layer_objects:
                    selected_fire = layer_objects[0]

                elif isinstance(layer_objects, dict):
                    selected_fire = layer_objects

                # Fallback for unexpected layer keys.
                if selected_fire is None:
                    for value in objects.values():
                        if isinstance(value, list) and value:
                            selected_fire = value[0]
                            break

                        if isinstance(value, dict) and value:
                            selected_fire = value
                            break

            elif isinstance(objects, list) and objects:

                selected_fire = objects[0]

            if isinstance(selected_fire, dict):

                st.session_state[
                    "selected_fire"
                ] = dict(selected_fire)


        except Exception:

            pass


    else:

        st.warning(
            "No fire detections match "
            "the selected risk filters."
        )


# ============================================================
# SELECTED FIRE LOCATION DETAILS
# ============================================================

show_selected_fire_details(

    st.session_state.get(
        "selected_fire"
    )

)


# ============================================================
# FIRE ANALYSIS
# ============================================================

with analysis_col:

    st.markdown(
        "### 🤖 Fire Risk Analysis"
    )


    st.metric(
        "Global Risk",
        f"{global_risk_score:.1f}%"
    )


    st.markdown(
        f"## {global_icon} {global_risk}"
    )


    st.progress(
        max(0, min(100, int(round(global_risk_score))))
    )


    st.markdown(
        "### Risk Distribution"
    )


    st.write(
        f"🔴 Critical: "
        f"**{critical_count:,}**"
    )


    st.write(
        f"🟠 High: "
        f"**{high_count:,}**"
    )


    st.write(
        f"🟡 Moderate: "
        f"**{moderate_count:,}**"
    )


    st.write(
        f"🟢 Low: "
        f"**{low_count:,}**"
    )


    st.markdown(
        "### Satellite Statistics"
    )


    st.write(
        f"☀️ Day detections: "
        f"**{day_count:,}**"
    )


    st.write(
        f"🌙 Night detections: "
        f"**{night_count:,}**"
    )


    st.write(
        f"⚡ Average FRP: "
        f"**{avg_frp:.1f}**"
    )


# ============================================================
# WATER RESOURCE ANALYSIS
# ============================================================

st.subheader(
    "💧 Fast Water Resource Analysis"
)


st.caption(
    f"Analysis is performed for the top "
    f"{WATER_ANALYSIS_LIMIT} highest-priority "
    f"fire hotspots using parallel requests."
)


priority_fires = (

    filtered_fires

    .sort_values(
        [
            "Risk Score",
            "frp"
        ],

        ascending=False
    )

    .head(
        WATER_ANALYSIS_LIMIT
    )

    .copy()
)


if st.button(
    "💧 Analyze Nearby Water",
    use_container_width=False
):

    with st.spinner(
        "💧 Running water-resource analysis..."
    ):

        water_results = analyze_water_parallel(
            priority_fires
        )


    priority_fires = (
        priority_fires
        .reset_index(drop=True)
    )


    priority_fires[
        "Water Resource"
    ] = [

        item["name"]

        for item in water_results

    ]


    priority_fires[
        "Water Type"
    ] = [

        item["type"]

        for item in water_results

    ]


    priority_fires[
        "Water Distance (km)"
    ] = [

        item["distance"]

        for item in water_results

    ]


    priority_fires[
        "Water Latitude"
    ] = [

        item["latitude"]

        for item in water_results

    ]


    priority_fires[
        "Water Longitude"
    ] = [

        item["longitude"]

        for item in water_results

    ]


    st.session_state[
        "water_results"
    ] = priority_fires


# ============================================================
# WATER RESULTS
# ============================================================

if "water_results" in st.session_state:

    water_data = st.session_state[
        "water_results"
    ]


    valid_water = (
        water_data[
            "Water Distance (km)"
        ]
        .dropna()
    )


    wa, wb, wc, wd = st.columns(4)


    with wa:

        st.metric(
            "🔥 Hotspots Analyzed",
            len(water_data)
        )


    with wb:

        if len(valid_water):

            st.metric(
                "📏 Average Distance",
                f"{valid_water.mean():.2f} km"
            )

        else:

            st.metric(
                "📏 Average Distance",
                "No data"
            )


    with wc:

        if len(valid_water):

            st.metric(
                "💧 Nearest Water",
                f"{valid_water.min():.2f} km"
            )

        else:

            st.metric(
                "💧 Nearest Water",
                "No data"
            )


    with wd:

        if len(valid_water):

            st.metric(
                "📏 Farthest Water",
                f"{valid_water.max():.2f} km"
            )

        else:

            st.metric(
                "📏 Farthest Water",
                "No data"
            )


    water_display = water_data[
        [
            "Risk",
            "Risk Score",
            "frp",
            "latitude",
            "longitude",
            "Water Resource",
            "Water Type",
            "Water Distance (km)"
        ]
    ].rename(

        columns={

            "Risk":
            "Fire Risk",

            "frp":
            "FRP",

            "latitude":
            "Fire Latitude",

            "longitude":
            "Fire Longitude",

            "Water Resource":
            "Nearest Water Resource",

            "Water Distance (km)":
            "Distance to Water (km)"

        }
    )


    st.dataframe(
        water_display,
        use_container_width=True,
        hide_index=True
    )


else:

    st.info(
        "Click **Analyze Nearby Water** "
        "to run the water-resource analysis."
    )


# ============================================================
# FIRE ACTIVITY CHARTS
# ============================================================

st.subheader(
    "📈 Fire Activity Analysis"
)


chart1, chart2 = st.columns(2)


with chart1:

    st.markdown(
        "### ☀️ Day vs 🌙 Night"
    )


    day_night_df = pd.DataFrame(

        {
            "Hotspots": [

                day_count,

                night_count

            ]
        },

        index=[

            "Day",

            "Night"

        ]
    )


    st.bar_chart(
        day_night_df
    )


with chart2:

    st.markdown(
        "### 🚨 Risk Distribution"
    )


    risk_df = pd.DataFrame(

        {
            "Hotspots": [

                critical_count,

                high_count,

                moderate_count,

                low_count

            ]
        },

        index=[

            "Critical",

            "High",

            "Moderate",

            "Low"

        ]
    )


    st.bar_chart(
        risk_df
    )


# ============================================================
# MODEL BENCHMARK
# ============================================================

st.subheader(
    "🤖 Wildfire Model Benchmark"
)


st.caption(
    "Reference benchmark values are included for "
    "comparison and should be replaced with metrics "
    "from your final trained models."
)


benchmark = pd.DataFrame(

    {

        "Model": [

            "Random Forest",

            "XGBoost",

            "KNN",

            "Decision Tree",

            "Multiple Linear Regression",

            "SVM",

            "ANN / MLP",

            "Hybrid RF + XGBoost"

        ],

        "Accuracy": [

            "96.4%",

            "97.9%",

            "88.7%",

            "91.2%",

            "84.5%",

            "92.8%",

            "95.6%",

            "98.4%"

        ],

        "F1": [

            "96.1%",

            "97.7%",

            "88.1%",

            "90.9%",

            "83.7%",

            "92.5%",

            "95.2%",

            "98.2%"

        ],

        "ROC-AUC": [

            "99.0%",

            "99.2%",

            "93.4%",

            "95.8%",

            "89.6%",

            "97.0%",

            "98.5%",

            "99.5%"

        ]

    }
)


st.dataframe(
    benchmark,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# PRIORITY FIRE TABLE
# ============================================================

st.subheader(
    "🚨 Highest-Priority Fire Hotspots"
)


priority_table = (

    filtered_fires

    .sort_values(

        [
            "Risk Score",
            "frp"
        ],

        ascending=False

    )

    .head(50)

    .copy()

)


priority_table = priority_table[

    [

        "Risk",

        "Risk Score",

        "frp",

        "confidence",

        "bright_ti4",

        "latitude",

        "longitude",

        "acq_date",

        "acq_time"

    ]

].rename(

    columns={

        "Risk":
        "Fire Risk",

        "frp":
        "FRP",

        "confidence":
        "Confidence",

        "bright_ti4":
        "Brightness K",

        "latitude":
        "Latitude",

        "longitude":
        "Longitude",

        "acq_date":
        "Detection Date",

        "acq_time":
        "Detection Time UTC"

    }

)


st.dataframe(
    priority_table,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# FULL NASA DATA
# ============================================================

st.subheader(
    "🛰️ NASA FIRMS Fire Detection Data"
)


st.caption(
    f"Total NASA observations loaded: "
    f"{len(fires):,}"
)


full_table = fires.copy()


display_columns = [

    "Risk",

    "Risk Score",

    "latitude",

    "longitude",

    "frp",

    "confidence",

    "bright_ti4",

    "bright_ti5",

    "acq_date",

    "acq_time",

    "daynight"

]


display_columns = [

    column

    for column in display_columns

    if column in full_table.columns

]


full_table = (

    full_table[

        display_columns

    ]

    .head(5000)

    .copy()

)


full_table = full_table.rename(

    columns={

        "Risk":
        "Fire Risk",

        "latitude":
        "Latitude",

        "longitude":
        "Longitude",

        "frp":
        "Fire Radiative Power",

        "confidence":
        "Detection Confidence",

        "bright_ti4":
        "Brightness Temperature",

        "bright_ti5":
        "Background Temperature",

        "acq_date":
        "Detection Date",

        "acq_time":
        "Detection Time UTC",

        "daynight":
        "Day / Night"

    }

)


st.dataframe(

    full_table,

    use_container_width=True,

    hide_index=True,

    height=500

)


# ============================================================
# DOWNLOAD
# ============================================================

st.subheader(
    "📥 Export Data"
)


csv_data = (

    fires

    .to_csv(index=False)

    .encode("utf-8")

)


st.download_button(

    "⬇️ Download NASA Fire Data CSV",

    data=csv_data,

    file_name=
    "firesafe_nasa_fire_detections.csv",

    mime="text/csv",

    use_container_width=True

)


# ============================================================
# DATA PREVIEW
# ============================================================

st.subheader(
    "📋 Data Preview"
)


preview = fires[

    [

        "latitude",

        "longitude",

        "frp",

        "Risk",

        "Risk Score",

        "confidence_numeric",

        "bright_ti4",

        "daynight"

    ]

].head(20).copy()


preview = preview.rename(

    columns={

        "latitude":
        "Latitude",

        "longitude":
        "Longitude",

        "frp":
        "FRP",

        "confidence_numeric":
        "Confidence %",

        "bright_ti4":
        "Brightness K",

        "daynight":
        "Day/Night"

    }

)


st.dataframe(

    preview,

    use_container_width=True,

    hide_index=True

)


# ============================================================
# FOOTER
# ============================================================

st.divider()


current_time = datetime.now().strftime(

    "%d %b %Y, %I:%M:%S %p"

)


st.caption(

    f"🕐 Last dashboard refresh: "
    f"{current_time}"

)


st.caption(

    "🛰️ Fire data: "
    "NASA FIRMS / VIIRS NOAA-21 NRT"

)


st.caption(

    "💧 Water data: "
    "OpenStreetMap / Overpass API"

)


st.caption(

    "🔥 FireSafe — "
    "Global Satellite Wildfire Intelligence"

)