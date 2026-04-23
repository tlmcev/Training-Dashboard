import requests
import os
import json
from datetime import datetime, timedelta

# ── 1. SETUP & SECRETS ────────────────────────────────────────────────────────
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

MARATHON_DATE = "November 1, 2026"
PLAN_START    = "June 28, 2026"        # 18 weeks out from Nov 1

# ── 2. STRAVA ─────────────────────────────────────────────────────────────────
def get_strava_access_token():
    resp = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_activities(access_token, days=120):
    since = int(datetime(2026, 3, 1).timestamp())
    resp = requests.get(
        f"https://www.strava.com/api/v3/athlete/activities?after={since}&per_page=30",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "errors" in data:
        raise RuntimeError(f"Strava error: {data}")
    return data


def format_activity(act):
    """Return a cleaned dict for one Strava activity."""
    dist_m   = act.get("distance", 0)
    dist_mi  = round(dist_m / 1609.34, 2)
    move_sec = act.get("moving_time", 0)

    pace_sec = (move_sec / 60) / dist_mi * 60 if dist_mi > 0 else 0  # seconds per mile
    pace_min = int(pace_sec // 60)
    pace_s   = int(pace_sec % 60)
    pace_str = f"{pace_min}:{str(pace_s).zfill(2)}" if dist_mi > 0 else "—"

    elev_ft  = round(act.get("total_elevation_gain", 0) * 3.28084, 0)

    hr = act.get("average_heartrate")
    hr_zone = classify_hr_zone(round(hr) if hr else None)

    return {
        "id":             act.get("id"),
        "name":           act.get("name", "Run"),
        "date":           act.get("start_date_local", "")[:10],
        "distance_miles": dist_mi,
        "moving_time_sec": move_sec,
        "pace_per_mile":  pace_str,
        "pace_seconds":   round(pace_sec, 1),
        "elevation_ft":   elev_ft,
        "avg_hr":         round(hr) if hr else None,
        "hr_zone":        hr_zone,
        "suffer_score":   act.get("suffer_score"),
    }


# ── 3. RACE PREDICTOR (Riegel formula) ────────────────────────────────────────
def riegel_predict(hm_pace_sec, distance_miles):
    """Predict finish time in seconds for a given distance using half marathon pace."""
    hm_time_sec = hm_pace_sec * 13.1
    pred_sec    = hm_time_sec * (distance_miles / 13.1) ** 1.06
    return round(pred_sec)


def sec_to_time(s):
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}:{str(m).zfill(2)}:{str(sec).zfill(2)}"
    return f"{m}:{str(sec).zfill(2)}"


def hr_pace_zones(avg_pace_sec):
    return {
        'Z1': {'name': 'Recovery',   'hr': '<124 bpm',    'pct': '<65%',   'desc': 'Very easy, warm up/cool down'},
        'Z2': {'name': 'Endurance',  'hr': '124-154 bpm', 'pct': '65-89%', 'desc': 'Easy runs, base building — most of your miles'},
        'Z3': {'name': 'Tempo',      'hr': '155-169 bpm', 'pct': '90-94%', 'desc': 'Moderate — marathon to half marathon effort'},
        'Z4': {'name': 'Threshold',  'hr': '170-184 bpm', 'pct': '95-97%', 'desc': 'Comfortably hard — 10K effort'},
        'Z5': {'name': 'Anaerobic',  'hr': '>185 bpm',    'pct': '>97%',   'desc': 'Hard — short intervals only'},
    }

def classify_hr_zone(avg_hr):
    """Return zone name for a given average HR."""
    if not avg_hr:
        return None
    for zone, (low, high, name) in HR_ZONES.items():
        if low <= avg_hr < high:
            return zone
    return 'Z5'


def hr_zone_distribution(activities):
    """Count how many runs fell in each HR zone."""
    dist = {z: 0 for z in HR_ZONES}
    for a in activities:
        zone = classify_hr_zone(a.get('avg_hr'))
        if zone:
            dist[zone] += 1
    return dist   


# ── 4. CURRENT TRAINING WEEK ──────────────────────────────────────────────────
def get_current_week():
    plan_start = datetime(2026, 6, 29)
    now = datetime.now()
    if now < plan_start:
        return 0  # 0 = pre-plan / base building
    delta = now - plan_start
    week = max(1, min(18, int(delta.days / 7) + 1))
    return week


# ── 5. GEMINI COACHING ────────────────────────────────────────────────────────

def get_gemini_advice(activities, current_week, avg_pace_sec, hr_distribution):
    today = datetime.now().strftime("%A, %B %d, %Y")

    # Build rich run summary
    run_lines = []
    for r in activities[:10]:
        hr_str = f" | HR {r['avg_hr']}bpm ({r['hr_zone']})" if r['avg_hr'] else ""
        elev   = f" | +{r['elevation_ft']}ft" if r['elevation_ft'] else ""
        run_lines.append(
            f"  • {r['date']} — {r['name']}: {r['distance_miles']}mi @ {r['pace_per_mile']}/mi{hr_str}{elev}"
        )
    runs_block = "\n".join(run_lines) if run_lines else "  (No runs in the last 14 days)"

    # Predicted race times
    if avg_pace_sec and avg_pace_sec > 0:
        pred_5k   = sec_to_time(riegel_predict(avg_pace_sec, 3.1))
        pred_half = sec_to_time(riegel_predict(avg_pace_sec, 13.1))
        pred_full = sec_to_time(riegel_predict(avg_pace_sec, 26.2))
        zones     = hr_pace_zones(avg_pace_sec)
        predictor_block = f"""
  Predicted Finish Times (Riegel formula from avg pace {sec_to_time(int(avg_pace_sec))}/mi):
    5K:     {pred_5k}
    Half:   {pred_half}
    Full:   {pred_full}

  HR-Based Training Zones (max HR 190):
    Z2 Endurance: 124-154 bpm (easy runs target)
    Z3 Tempo:     155-169 bpm (moderate)
    Z4 Threshold: 170-184 bpm (hard)
"""
    else:
        predictor_block = "  (Insufficient pace data for predictions)"

    prompt = f"""You are an expert marathon coach for an athlete named Tom.
Today is {today}. Goal: NYC Marathon on {MARATHON_DATE}.
Phase: {"BASE BUILDING" if current_week == 0 else f"Week {current_week} of 18, Hal Higdon Novice 2"}
Days to plan start: {max(0, (datetime(2026,6,29) - datetime.now()).days)}
Days to marathon: {(datetime(2026,11,1) - datetime.now()).days}

Tom's recent runs:
{runs_block}

HR zone context (max HR 190):
- Z1 Recovery: <124 bpm | Z2 Endurance: 124-154 bpm | Z3 Tempo: 155-169 bpm | Z4 Threshold: 170-184 bpm | Z5 Anaerobic: >185 bpm
- Easy runs should be Z2. Flag any easy runs running hot (Z3+).
- Recent zone distribution: {hr_distribution}

Performance:
{predictor_block}

Write a concise coaching brief for Tom with these sections:
**Fitness Assessment** — analyze his recent runs with specific numbers.
**This Week's Focus** — exact target paces, what to prioritize.
**Key Priorities** — 2-3 bullet points.
**Watch Out For** — any red flags.
**Upcoming Milestones** — next 2-3 weeks preview.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.65, "maxOutputTokens": 4096},
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    result = resp.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]


# ── 6. README UPDATER ─────────────────────────────────────────────────────────
def generate_activity_table(activities):
    rows = ["| Workout | Distance | Pace | Date |", "| :--- | :--- | :--- | :--- |"]
    if not activities:
        return "No recent runs found. Time to hit the road!"
    for r in activities[:5]:
        rows.append(f"| {r['name']} | {r['distance_miles']} mi | {r['pace_per_mile']}/mi | {r['date']} |")
    return "\n".join(rows)


def update_readme(activities, current_week, advice, run_id, updated_at):
    table = generate_activity_table(activities)
    base  = os.path.dirname(os.path.abspath(__file__))

    novice_2_plan = """| Week | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Rest | 3m | 3m | 3m | Rest | 4m | Cross |
| 2 | Rest | 3m | 3m | 3m | Rest | 5m | Cross |
| 3 | Rest | 3m | 3m | 3m | Rest | 6m | Cross |
| 4 | Rest | 3m | 4m | 3m | Rest | 7m | Cross |
| 5 | Rest | 3m | 4m | 3m | Rest | 8m | Cross |
| 6 | Rest | 3m | 4m | 3m | Rest | 9m | Cross |
| 7 | Rest | 3m | 5m | 3m | Rest | 10m | Cross |
| 8 | Rest | 3m | 5m | 3m | Rest | 11m | Cross |
| 9 | Rest | 3m | 5m | 3m | Rest | 12m | Cross |
| 10 | Rest | 3m | 5m | 3m | Rest | 13m | Cross |
| 11 | Rest | 3m | 6m | 3m | Rest | 14m | Cross |
| 12 | Rest | 3m | 6m | 3m | Rest | 15m | Cross |
| 13 | Rest | 3m | 6m | 3m | Rest | 16m | Cross |
| 14 | Rest | 3m | 7m | 3m | Rest | 17m | Cross |
| 15 | Rest | 3m | 7m | 3m | Rest | 18m | Cross |
| 16 | Rest | 3m | 8m | 3m | Rest | 19m | Cross |
| 17 | Rest | 3m | 4m | 2m | Rest | 8m | Cross |
| 18 | Rest | 3m | 2m | Rest | Rest | 2m | **NYC Marathon** |"""

    # Short advice excerpt for README (first 3 lines)
    advice_excerpt = "\n".join(advice.split("\n")[:6]) if advice else "No advice yet."

    readme = f"""# 🏃 NYC Marathon Training Dashboard

> **[→ View the live visual dashboard](https://tlmcev.github.io/Training-Dashboard/)** ← New!

[Full AI coaching advice](./latest_advice.txt)

## Recent Runs

{table}

## AI Coach Snapshot

{advice_excerpt}

*[Read full coaching advice →](./latest_advice.txt)*

## Hal Higdon Novice 2 Schedule

**Current week: {current_week} of 18**

{novice_2_plan}

---
*Last updated: {updated_at} UTC | Run ID: {run_id}*
"""

    with open(os.path.join(base, "README.md"), "w") as f:
        f.write(readme)
    print("✓ README.md updated")


# ── 7. MAIN ───────────────────────────────────────────────────────────────────
def aggregate_weekly_mileage(activities):
    """Group activities into Mon–Sun weeks, return list of {week_start, miles}."""
    from collections import defaultdict
    weeks = defaultdict(float)
    for a in activities:
        date = datetime.strptime(a['date'], '%Y-%m-%d')
        # Find the Monday of this week
        monday = date - timedelta(days=date.weekday())
        week_key = monday.strftime('%Y-%m-%d')
        weeks[week_key] += a['distance_miles']
    # Sort by date and round
    return [
        {'week_start': k, 'miles': round(v, 1)}
        for k, v in sorted(weeks.items())
    ]

def main():
    run_id     = os.getenv("GITHUB_RUN_ID", "local")
    updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    print("→ Fetching Strava token…")
    token      = get_strava_access_token()

    print("→ Fetching activities…")
    raw        = get_activities(token, days=14)
    activities = [
        format_activity(a)
        for a in raw
        if a.get("type") == "Run" or a.get("sport_type") == "Run"
    ]
    activities.sort(key=lambda x: x["date"], reverse=True)
    print(f"  {len(activities)} runs found")

    current_week = get_current_week()
    phase = "Base Building (pre-plan)" if current_week == 0 else f"Week {current_week}/18"
    print(f"  Training phase: {phase}")

    # Average pace from recent runs (exclude 0-pace entries)
    paces = [a["pace_seconds"] for a in activities if a["pace_seconds"] > 0]
    avg_pace_sec = sum(paces) / len(paces) if paces else 0

    # Race predictions
    predictions = {}
    if avg_pace_sec:
        predictions = {
            "5k":       sec_to_time(riegel_predict(avg_pace_sec, 3.1)),
            "10k":      sec_to_time(riegel_predict(avg_pace_sec, 6.2)),
            "half":     sec_to_time(riegel_predict(avg_pace_sec, 13.1)),
            "marathon": sec_to_time(riegel_predict(avg_pace_sec, 26.2)),
        }
        print(f"  Predicted marathon: {predictions['marathon']}")

    # Pace zones
    zones = hr_pace_zones(avg_pace_sec)
    hr_distribution = hr_zone_distribution(activities)

    # Gemini advice (with retry)
    advice = ""
    print("→ Calling Gemini…")
    for attempt in range(1, 4):
        try:
            advice = get_gemini_advice(activities, current_week, avg_pace_sec, hr_distribution)
            print(f"✓ Gemini advice received (attempt {attempt})")
            with open("latest_advice.txt", "w") as f:
                f.write(advice)
            break
        except Exception as e:
            print(f"✗ Gemini attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                print(f"  Retrying in 30 seconds…")
                import time
                time.sleep(30)
            else:
                print("  All 3 attempts failed. Advice left empty.")

    # Write coach_data.json (consumed by index.html dashboard)
    weekly_mileage = aggregate_weekly_mileage(activities)
    coach_data = {
        "updated_at":       updated_at,
        "current_week":     current_week,
        "phase":            "base_building" if current_week == 0 else "training",
        "days_to_plan_start": max(0, (datetime(2026, 6, 29) - datetime.now()).days),
        "activities":       activities,
        "weekly_mileage":   weekly_mileage,
        "avg_pace_sec":     round(avg_pace_sec, 1),
        "predictions":      predictions,
        "pace_zones":    zones,
        "hr_distribution": hr_distribution,
        "max_hr":        MAX_HR,
        "advice":           advice,
    }
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "coach_data.json"), "w") as f:
        json.dump(coach_data, f, indent=2)
    print("✓ coach_data.json written")

    # Update README
    update_readme(activities, current_week, advice, run_id, updated_at)


if __name__ == "__main__":
    main()
