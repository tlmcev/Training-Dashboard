import requests
import os
import json
from datetime import datetime, timedelta

CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY")

MAX_HR = 190
HR_ZONES = {
    'Z1': (0,    124, 'Recovery'),
    'Z2': (124,  155, 'Endurance'),
    'Z3': (155,  170, 'Tempo'),
    'Z4': (170,  185, 'Threshold'),
    'Z5': (185,  220, 'Anaerobic'),
}

def get_strava_access_token():
    resp = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_recent_activity(access_token, minutes=35):
    since = int((datetime.now() - timedelta(minutes=minutes)).timestamp())
    resp = requests.get(
        f"https://www.strava.com/api/v3/athlete/activities?after={since}&per_page=5",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    activities = resp.json()
    runs = [a for a in activities if a.get("type") == "Run" or a.get("sport_type") == "Run"]
    return runs[0] if runs else None


def classify_hr_zone(avg_hr):
    if not avg_hr:
        return None
    for zone, (low, high, name) in HR_ZONES.items():
        if low <= avg_hr < high:
            return zone
    return 'Z5'


def sec_to_time(s):
    s = int(s)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}:{str(m).zfill(2)}:{str(sec).zfill(2)}"
    return f"{m}:{str(sec).zfill(2)}"


def get_post_run_analysis(activity):
    dist_mi   = round(activity.get("distance", 0) / 1609.34, 2)
    move_sec  = activity.get("moving_time", 0)
    pace_sec  = (move_sec / 60) / dist_mi * 60 if dist_mi > 0 else 0
    pace_min  = int(pace_sec // 60)
    pace_s    = int(pace_sec % 60)
    pace_str  = f"{pace_min}:{str(pace_s).zfill(2)}/mi"
    elev_ft   = round(activity.get("total_elevation_gain", 0) * 3.28084)
    hr        = activity.get("average_heartrate")
    max_hr_act = activity.get("max_heartrate")
    hr_zone   = classify_hr_zone(round(hr) if hr else None)
    suffer    = activity.get("suffer_score")
    name      = activity.get("name", "Run")
    date      = activity.get("start_date_local", "")[:10]

    hr_block = f"Avg HR: {round(hr)}bpm ({hr_zone}), Max HR: {round(max_hr_act)}bpm" if hr else "No HR data"

    prompt = f"""You are a marathon coach giving Tom a short post-run analysis.

Run details:
- Name: {name}
- Date: {date}
- Distance: {dist_mi} miles
- Pace: {pace_str}
- Moving time: {sec_to_time(move_sec)}
- {hr_block}
- Elevation gain: {elev_ft}ft
- Suffer score: {suffer or 'N/A'}

HR zones (max HR 190): Z1 <124 | Z2 124-154 | Z3 155-169 | Z4 170-184 | Z5 >185
Easy runs should be Z2. Tom is in base building phase until June 29, 2026.

Write a post-run analysis in exactly 3 short paragraphs:
1. **Effort Check** — Was the HR zone appropriate for this type of run? One sentence assessment.
2. **Standout Stat** — Call out one interesting number from the data and what it means.
3. **Next Run Tip** — One specific thing Tom should focus on in his next run based on this effort.

Keep it under 120 words total. Be direct and specific."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.65, "maxOutputTokens": 300},
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    result = resp.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]


def main():
    print("→ Fetching Strava token...")
    token = get_strava_access_token()

    print("→ Checking for recent runs...")
    activity = get_recent_activity(token, minutes=35)

    if not activity:
        print("  No recent run found. Exiting.")
        return

    print(f"  Found: {activity.get('name')} — {round(activity.get('distance',0)/1609.34, 2)} miles")

    print("→ Calling Gemini for post-run analysis...")
    for attempt in range(1, 4):
        try:
            analysis = get_post_run_analysis(activity)
            print(f"✓ Analysis received (attempt {attempt})")
            break
        except Exception as e:
            print(f"✗ Attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                import time
                time.sleep(15)
            else:
                print("  All attempts failed.")
                return

    dist_mi  = round(activity.get("distance", 0) / 1609.34, 2)
    move_sec = activity.get("moving_time", 0)
    pace_sec = (move_sec / 60) / dist_mi * 60 if dist_mi > 0 else 0
    hr       = activity.get("average_heartrate")

    latest_run = {
        "analyzed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "activity": {
            "name":           activity.get("name"),
            "date":           activity.get("start_date_local", "")[:10],
            "distance_miles": dist_mi,
            "pace_per_mile":  f"{int(pace_sec//60)}:{str(int(pace_sec%60)).zfill(2)}",
            "moving_time":    move_sec,
            "avg_hr":         round(hr) if hr else None,
            "hr_zone":        classify_hr_zone(round(hr) if hr else None),
            "elevation_ft":   round(activity.get("total_elevation_gain", 0) * 3.28084),
        },
        "analysis": analysis,
    }

    with open("latest_run.json", "w") as f:
        json.dump(latest_run, f, indent=2)
    print("✓ latest_run.json written")


if __name__ == "__main__":
    main()
