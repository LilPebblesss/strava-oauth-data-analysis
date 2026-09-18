import requests
import pandas as pd
import webbrowser
import urllib.parse as urlparse
import json
import os
from dotenv import load_dotenv


load_dotenv()

#credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
TOKEN_FILE = "tokens.json"

#login
def get_authorization_code():
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=read,activity:read_all"
    )
    webbrowser.open(auth_url)
    redirect_response = input("Paste URL here: ")
    parsed = urlparse.urlparse(redirect_response)
    return urlparse.parse_qs(parsed.query)['code'][0]

def get_tokens(code):
    response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    })
    tokens = response.json()
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f)
    return tokens

def refresh_token(refresh_token):
    response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    tokens = response.json()
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f)
    return tokens

#authentication
if os.path.exists(TOKEN_FILE):
    tokens = json.load(open(TOKEN_FILE))
    tokens = refresh_token(tokens["refresh_token"])
else:
    code = get_authorization_code()
    tokens = get_tokens(code)

access_token = tokens["access_token"]

# fetching activities (pagination)
activities = []
page = 1

while True:
    res = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": 200, "page": page}
    )
    data = res.json()

    if not data:
        break

    activities.extend(data)
    page += 1

#processing with pandas
df = pd.DataFrame(activities)

df = df[[
    "type",
    "distance",
    "moving_time",
    "total_elevation_gain",
    "start_date",
    "average_speed",
    "average_heartrate"
]].copy()

#cleaning
df = df[df["distance"].notna()]


df["distance_km"] = df["distance"] / 1000
df["duration_min"] = df["moving_time"] / 60
df["speed_kmh"] = df["average_speed"] * 3.6


df["date"] = pd.to_datetime(df["start_date"])
df = df[df["date"] >= "2022-01-01"]
df["month"] = df["date"].dt.to_period("M").astype(str)
df["weekday"] = df["date"].dt.day_name()
df["hour"] = df["date"].dt.hour


df.rename(columns={"average_heartrate": "avg_hr"}, inplace=True)


df = df[df["avg_hr"].notna()]

def hr_zone(hr):
    if hr < 120:
        return "Easy"
    elif hr < 150:
        return "Moderate"
    else:
        return "Hard"

df["hr_zone"] = df["avg_hr"].apply(hr_zone)


def intensity(s):
    if s < 8:
        return "Easy"
    elif s < 12:
        return "Moderate"
    else:
        return "Hard"

df["intensity"] = df["speed_kmh"].apply(intensity)


df = df[df["distance_km"] > 0]


df.drop(columns=[
    "distance",
    "moving_time",
    "average_speed",
    "start_date"
], inplace=True)


df = df[[
    "type",
    "date", "month", "weekday", "hour",
    "distance_km", "duration_min", "speed_kmh", "total_elevation_gain",
    "avg_hr", "hr_zone",
    "intensity"
]]

#exporting
df.to_csv("processed_activities.csv", index=False)

print("DONE")