import requests

MAP_KEY = "96e5b5ebde3750c86f52b27e16802400"

url = (
    f"https://firms.modaps.eosdis.nasa.gov/"
    f"api/area/csv/"
    f"{MAP_KEY}/"
    f"VIIRS_NOAA21_NRT/"
    f"world/1"
)

print("Connecting to NASA FIRMS...")

response = requests.get(url, timeout=30)

print("Status Code:", response.status_code)

if response.status_code == 200:
    print("NASA FIRMS connection successful! ✅")

    print("\nFirst 500 characters:")
    print(response.text[:500])

else:
    print("NASA FIRMS connection failed ❌")
    print(response.text[:500])