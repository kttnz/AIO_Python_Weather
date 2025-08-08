import json
import os
import math
import sys
from datetime import datetime

import requests
from colorama import Fore, Style, init

init(autoreset=True)


# --------------------
# HELPERS
# --------------------
def ua():
    """NOAA requires a custom user agent."""
    return {"User-Agent": "(myweatherapp, email@example.com)"}


def condition_color(cond):
    cond_lower = cond.lower()
    if "rain" in cond_lower:
        return Fore.CYAN
    if "snow" in cond_lower:
        return Fore.LIGHTWHITE_EX
    if "sun" in cond_lower or "clear" in cond_lower:
        return Fore.YELLOW
    if "cloud" in cond_lower:
        return Fore.LIGHTBLACK_EX
    return Fore.GREEN


def moon_phase(date):
    """Return moon phase name for a given date."""
    year, month, day = date.year, date.month, date.day
    c = e = jd = b = 0
    if month < 3:
        year -= 1
        month += 12
    month += 1
    c = 365.25 * year
    e = 30.6 * month
    jd = c + e + day - 694039.09  # JD base
    jd /= 29.53
    b = int(jd)
    jd -= b
    phase_index = round(jd * 8)
    if phase_index >= 8:
        phase_index = 0
    phases = [
        "New Moon",
        "Waxing Crescent",
        "First Quarter",
        "Waxing Gibbous",
        "Full Moon",
        "Waning Gibbous",
        "Last Quarter",
        "Waning Crescent",
    ]
    return phases[phase_index]


# --------------------
# LOCATION
# --------------------
def get_location():
    env_lat = os.getenv("LAT")
    env_lon = os.getenv("LON")
    if env_lat and env_lon:
        try:
            latitude = float(env_lat)
            longitude = float(env_lon)
            return latitude, longitude, os.getenv("CITY"), os.getenv("REGION")
        except ValueError as e:
            raise RuntimeError(f"Invalid LAT/LON environment variables: {e}")
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        loc = data["loc"].split(",")
        latitude, longitude = map(float, loc)
        return latitude, longitude, data.get("city"), data.get("region")
    except Exception as e:
        raise RuntimeError(
            f"Error detecting location: {e}. "
            "Set LAT and LON environment variables."
        )


# --------------------
# CURRENT WEATHER
# --------------------
def get_current_weather(lat, lon):
    try:
        points_url = f"https://api.weather.gov/points/{lat},{lon}"
        points_resp = requests.get(points_url, headers=ua(), timeout=10)
        points_resp.raise_for_status()
        station_url = points_resp.json()["properties"]["observationStations"]
        stations_resp = requests.get(station_url, headers=ua(), timeout=10)
        stations_resp.raise_for_status()
        stations = stations_resp.json()["features"]
        if not stations:
            raise RuntimeError(
                "No observation stations found for this location."
            )
        station_id = stations[0]["properties"]["stationIdentifier"]

        obs_url = (
            "https://api.weather.gov/stations/"
            f"{station_id}/observations/latest"
        )
        obs_resp = requests.get(obs_url, headers=ua(), timeout=10)
        obs_resp.raise_for_status()
        data = obs_resp.json()["properties"]

        desc = data.get("textDescription", "N/A")
        temp_c = data["temperature"]["value"]
        temp_f = temp_c * 9 / 5 + 32 if temp_c is not None else None
        humidity = data["relativeHumidity"]["value"]
        wind_speed = data["windSpeed"]["value"]
        wind_speed_mph = wind_speed * 2.237 if wind_speed is not None else None
        sunrise, sunset = get_sun_times(lat, lon)

        print(Fore.CYAN + Style.BRIGHT + "\n=== Current Conditions ===")
        print(Fore.YELLOW + f"Condition: {desc}")
        if temp_c is not None:
            color = (
                Fore.RED
                if temp_f > 85
                else Fore.BLUE
                if temp_f < 50
                else Fore.GREEN
            )
            print(color + f"Temperature: {temp_c:.1f}°C / {temp_f:.1f}°F")
        if humidity is not None:
            print(Fore.BLUE + f"Humidity: {humidity:.1f}%")
        if wind_speed is not None:
            print(Fore.MAGENTA + f"Wind Speed: {wind_speed_mph:.1f} mph")
        print(Fore.LIGHTYELLOW_EX + f"Sunrise: {sunrise} | Sunset: {sunset}")
        print(
            Fore.LIGHTWHITE_EX
            + f"Moon Phase: {moon_phase(datetime.utcnow())}"
        )
    except requests.HTTPError as e:
        print(Fore.RED + f"HTTP error fetching current weather: {e}")
    except Exception as e:
        print(Fore.RED + f"Error fetching current weather: {e}")


# --------------------
# SUNRISE / SUNSET
# --------------------
def get_sun_times(lat, lon):
    try:
        url = (
            "https://api.sunrise-sunset.org/json"
            f"?lat={lat}&lng={lon}&formatted=0"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()["results"]
        sunrise = datetime.fromisoformat(data["sunrise"]).strftime("%I:%M %p")
        sunset = datetime.fromisoformat(data["sunset"]).strftime("%I:%M %p")
        return sunrise, sunset
    except (requests.RequestException, KeyError, ValueError) as e:
        print(Fore.RED + f"Error fetching sun times: {e}")
        return "N/A", "N/A"


# --------------------
# FORECAST
# --------------------
def get_forecasts(lat, lon):
    try:
        points_url = f"https://api.weather.gov/points/{lat},{lon}"
        points_resp = requests.get(points_url, headers=ua(), timeout=10)
        points_resp.raise_for_status()
        properties = points_resp.json()["properties"]

        hourly_url = properties["forecastHourly"]
        hourly_resp = requests.get(hourly_url, headers=ua(), timeout=10)
        hourly_resp.raise_for_status()
        hourly_periods = hourly_resp.json()["properties"]["periods"]

        print(Fore.CYAN + Style.BRIGHT + "\n=== Next 12 Hours ===")
        for hour in hourly_periods[:12]:
            t = datetime.fromisoformat(
                hour["startTime"]
            ).astimezone().strftime("%I %p")
            temp = f"{hour['temperature']}°{hour['temperatureUnit']}"
            cond = hour["shortForecast"]
            color = condition_color(cond)
            print(f"{t:>6} | {color}{temp:<6} | {cond}")

        daily_url = properties["forecast"]
        daily_resp = requests.get(daily_url, headers=ua(), timeout=10)
        daily_resp.raise_for_status()
        daily_periods = daily_resp.json()["properties"]["periods"]

        print(Fore.CYAN + Style.BRIGHT + "\n=== 7-Day Forecast ===")
        for day in daily_periods:
            temp = f"{day['temperature']}°{day['temperatureUnit']}"
            cond = day["shortForecast"]
            color = condition_color(cond)
            print(f"{day['name']:<12} | {color}{temp:<6} | {cond}")

    except requests.HTTPError as e:
        print(Fore.RED + f"HTTP error fetching forecasts: {e}")
    except Exception as e:
        print(Fore.RED + f"Error fetching forecasts: {e}")


# --------------------
# ALERTS
# --------------------
def get_alerts(lat, lon):
    try:
        alerts_url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        resp = requests.get(alerts_url, headers=ua(), timeout=10)
        resp.raise_for_status()
        alerts = resp.json()["features"]

        print(Fore.CYAN + Style.BRIGHT + "\n=== Active Alerts ===")
        if not alerts:
            print(Fore.GREEN + "No active alerts.")
            return

        for alert in alerts:
            props = alert["properties"]
            print(Fore.RED + Style.BRIGHT + f"{props['event']}")
            print(Fore.LIGHTWHITE_EX + f"  {props['headline']}")
            print(Fore.YELLOW + f"  {props['description']}\n")
    except Exception as e:
        print(Fore.RED + f"Error fetching alerts: {e}")


# --------------------
# RADAR
# --------------------
RADAR_CACHE_FILE = "radar_stations.json"


def haversine(lat1, lon1, lat2, lon2):
    radius = 6371  # km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_radar_stations():
    if os.path.exists(RADAR_CACHE_FILE):
        with open(RADAR_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    url = "https://api.weather.gov/radar/stations"
    resp = requests.get(url, headers=ua(), timeout=10)
    resp.raise_for_status()
    stations = [
        {
            "id": s["properties"]["id"],
            "lat": s["geometry"]["coordinates"][1],
            "lon": s["geometry"]["coordinates"][0],
        }
        for s in resp.json()["features"]
    ]
    with open(RADAR_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(stations, f)
    return stations


def get_nearest_radar(lat, lon):
    try:
        stations = load_radar_stations()
    except requests.RequestException as e:
        print(Fore.RED + f"Error fetching radar stations: {e}")
        return None
    return min(
        stations,
        key=lambda s: haversine(lat, lon, s["lat"], s["lon"]),
    )["id"]


def get_radar_image(lat, lon):
    try:
        radar_id = get_nearest_radar(lat, lon)
        if not radar_id:
            print(Fore.RED + "Radar station not found.")
            return
        url = f"https://radar.weather.gov/ridge/lite/N0R/{radar_id}_loop.gif"
        with requests.get(url, headers=ua(), stream=True, timeout=10) as r:
            r.raise_for_status()
            with open("radar.gif", "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(
            Fore.LIGHTGREEN_EX
            + f"Radar loop saved as radar.gif (station {radar_id})"
        )
    except requests.HTTPError as e:
        print(Fore.RED + f"HTTP error fetching radar: {e}")
    except Exception as e:
        print(Fore.RED + f"Error fetching radar: {e}")


# --------------------
# MAIN
# --------------------
if __name__ == "__main__":
    try:
        lat, lon, city, region = get_location()
    except RuntimeError as e:
        print(Fore.RED + str(e))
        sys.exit(1)
    print(
        Fore.WHITE
        + Style.BRIGHT
        + f"Location detected: {city}, {region} ({lat}, {lon})"
    )
    get_current_weather(lat, lon)
    get_forecasts(lat, lon)
    get_alerts(lat, lon)
    get_radar_image(lat, lon)
