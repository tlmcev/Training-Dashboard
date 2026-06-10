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
PLAN_START    = "June 28, 2026"

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


def get_activities(access_token):
    since = int(datetime(2026, 3, 1).timestamp())
    resp = requests.get(
        f"https://www.strava.com/api/v3/athlete/activities?after={since}&per_page=100",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "errors" in data:
        raise RuntimeError(f"Strava error: {data}")
    return data


def get_activity_detail(access_token, activity_id):
    """Fetch detailed performance data for a single activity."""
    try:
        resp = requests.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ⚠ Detail fetch failed for {activity_id}: {e}")
        return {}


def format_activity(act, detail=None):
    """Return a cleaned dict for one Strava activity, enriched with detail data."""
    dist_m   = act.get("distance", 0)
    dist_mi  = round(dist_m / 1609.34, 2)
    move_sec = act.get("moving_time", 0)

    pace_sec = (move_sec / 60) / dist_mi * 60 if dist_mi > 0 else 0
    pace_min = int(pace_sec // 60)
    pace_s   = int(pace_sec % 60)
    pace_str = f"{pace_min}:{str(pace_s).zfill(2)}" if dist_mi > 0 else "—"

    elev_ft = round(act.get("total_elevation_gain", 0) * 3.28084, 0)
    hr      = act.get("average_heartrate")
    hr_zone = classify_hr_zone(round(hr) if hr else None)

    result = {
        "id":              act.get("id"),
        "name":            act.get("name", "Run"),
        "date":            act.get("start_date_local", "")[:10],
        "distance_miles":  dist_mi,
        "moving_time_sec": move_sec,
        "pace_per_mile":   pace_str,
        "pace_seconds":    round(pace_sec, 1),
        "elevation_ft":    elev_ft,
        "avg_hr":          round(hr) if hr else None,
        "hr_zone":         hr_zone,
        "suffer_score":    act.get("suffer_score"),
        "max_hr":          None,
        "avg_watts":       None,
        "avg_cadence":     None,
        "fastest_mile":    None,
        "fastest_5k":      None,
        "pr_count":        act.get("pr_count", 0),
    }

    # Enrich with detail data if available
    if detail:
        result["max_hr"]    = detail.get("max_heartrate")
        result["avg_watts"] = round(detail.get("average_watts", 0)) or None
        result["avg_cadence"] = round(detail.get("average_cadence", 0) * 2) or None  # spm

        # Best efforts — extract fastest mile and 5K
        for effort in detail.get("best_efforts", []):
            if effort.get("name") == "1 mile":
                secs = effort.get("elapsed_time", 0)
                m, s = divmod(secs, 60)
                result["fastest_mile"] = f"{m}:{str(s).zfill(2)}"
            if effort.get("name") == "5K":
                secs = effort.get("elapsed_time", 0)
                h, rem = divmod(secs, 3600)
                m, s = divmod(rem, 60)
                result["fastest_5k"] = f"{m}:{str(s).zfill(2)}"

    return result


# ── 3. RACE PREDICTOR (Riegel formula) ────────────────────────────────────────
def riegel_predict(hm_pace_sec, distance_miles):
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
    if not avg_hr:
        return None
    for zone, (low, high, name) in HR_ZONES.items():
        if low <= avg_hr < high:
            return zone
    return 'Z5'


def hr_zone_distribution(activities):
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
        return 0
    delta = now - plan_start
    week = max(1, min(18, int(delta.days / 7) + 1))
    return week


# ── 5. GEMINI COACHING ────────────────────────────────────────────────────────
def get_gemini_advice(activities, current_week, avg_pace_sec, hr_distribution, weather):
    today = datetime.now().strftime("%A, %B %d, %Y")

    # Build rich run summary for the 10 most recent runs
    run_lines = []
    for r in activities[:10]:
        parts = [f"  • {r['date']} — {r['name']}"]
        parts.append(f"{r['distance_miles']}mi @ {r['pace_per_mile']}/mi")

        # HR: avg / max / zone
        if r.get('avg_hr'):
            hr_str = f"HR {r['avg_hr']}"
            if r.get('max_hr'):
                hr_str += f"/{r['max_hr']} bpm"
            else:
                hr_str += " bpm"
            hr_str += f" ({r['hr_zone']})"
            parts.append(hr_str)

        # Running power
        if r.get('avg_watts'):
            parts.append(f"{r['avg_watts']}W")

        # Cadence
        if r.get('avg_cadence'):
            parts.append(f"{r['avg_cadence']}spm")

        # Best efforts
        efforts = []
        if r.get('fastest_mile'):
            efforts.append(f"mile {r['fastest_mile']}")
        if r.get('fastest_5k'):
            efforts.append(f"5K {r['fastest_5k']}")
        if efforts:
            parts.append(f"[best: {', '.join(efforts)}]")

        # Elevation
        if r.get('elevation_ft'):
            parts.append(f"+{int(r['elevation_ft'])}ft")

        # PRs
        if r.get('pr_count') and r['pr_count'] > 0:
            parts.append(f"🏆 {r['pr_count']} PR{'s' if r['pr_count'] > 1 else ''}")

        run_lines.append(" | ".join(parts))

    runs_block = "\n".join(run_lines) if run_lines else "  (No runs found)"

    # Weekly mileage summary (last 4 weeks)
    weekly = aggregate_weekly_mileage(activities)
    recent_weeks = weekly[-4:] if len(weekly) >= 4 else weekly
    weekly_block = "  " + " | ".join([f"{w['week_start']}: {w['miles']}mi" for w in recent_weeks])

    # Current week schedule
    HH_SCHEDULE = [
        ['Rest','3m run','5m pace','3m run','Rest','8m','Cross'],
        ['Rest','3m run','5m run', '3m run','Rest','9m','Cross'],
        ['Rest','3m run','5m pace','3m run','Rest','6m','Cross'],
        ['Rest','3m run','6m pace','3m run','Rest','11m','Cross'],
        ['Rest','3m run','6m run', '3m run','Rest','12m','Cross'],
        ['Rest','3m run','6m pace','3m run','Rest','9m','Cross'],
        ['Rest','4m run','7m pace','4m run','Rest','14m','Cross'],
        ['Rest','4m run','7m run', '4m run','Rest','15m','Cross'],
        ['Rest','4m run','7m pace','4m run','Rest','Rest','Half Marathon'],
        ['Rest','4m run','8m pace','4m run','Rest','17m','Cross'],
        ['Rest','5m run','8m run', '5m run','Rest','18m','Cross'],
        ['Rest','5m run','8m pace','5m run','Rest','13m','Cross'],
        ['Rest','5m run','5m pace','5m run','Rest','19m','Cross'],
        ['Rest','5m run','8m run', '5m run','Rest','12m','Cross'],
        ['Rest','5m run','5m pace','5m run','Rest','20m','Cross'],
        ['Rest','5m run','4m pace','5m run','Rest','12m','Cross'],
        ['Rest','4m run','3m run', '4m run','Rest','8m','Cross'],
        ['Rest','3m run','2m run', 'Rest',  'Rest','2m run','Marathon'],
    ]
    DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    if current_week > 0 and current_week <= 18:
        week_sched = HH_SCHEDULE[current_week - 1]
        week_block = "  " + " | ".join([f"{DAYS[i]}: {week_sched[i]}" for i in range(7)])
    else:
        week_block = "  Base building — easy aerobic running, no structured plan yet"

    # Predictions
    if avg_pace_sec and avg_pace_sec > 0:
        pred_5k   = sec_to_time(riegel_predict(avg_pace_sec, 3.1))
        pred_half = sec_to_time(riegel_predict(avg_pace_sec, 13.1))
        pred_full = sec_to_time(riegel_predict(avg_pace_sec, 26.2))
        predictor_block = f"""  Predicted finish times (Riegel, avg pace {sec_to_time(int(avg_pace_sec))}/mi):
    5K: {pred_5k} | Half: {pred_half} | Marathon: {pred_full}"""
    else:
        predictor_block = "  (Insufficient pace data for predictions)"

    # HR drift signal — flag if avg HR creeping up week over week
    recent_hrs = [a['avg_hr'] for a in activities[:6] if a.get('avg_hr')]
    hr_trend = ""
    if len(recent_hrs) >= 4:
        early_avg = sum(recent_hrs[-3:]) / 3
        late_avg  = sum(recent_hrs[:3]) / 3
        diff = late_avg - early_avg
        if diff > 5:
            hr_trend = f"  ⚠ HR trending UP +{diff:.0f}bpm over last 6 runs (fatigue signal)"
        elif diff < -5:
            hr_trend = f"  ✓ HR trending DOWN {abs(diff):.0f}bpm over last 6 runs (aerobic adaptation)"

    prompt = f"""You are an expert marathon coach for an athlete named Tom.
Today is {today}. Goal: NYC Marathon on {MARATHON_DATE}.
Phase: {"BASE BUILDING — official plan starts June 29, 2026" if current_week == 0 else f"Week {current_week} of 18, Hal Higdon Novice 2"}
Days to plan start: {max(0, (datetime(2026,6,29) - datetime.now()).days)} | Days to marathon: {(datetime(2026,11,1) - datetime.now()).days}

This week's Hal Higdon Novice 2 plan:
{week_block}

Tom's recent runs (date | name | distance @ pace | avg/max HR (zone) | watts | cadence | best efforts | elevation | PRs):
{runs_block}

Weekly mileage trend (last 4 weeks):
{weekly_block}

HR zone distribution (recent runs): {hr_distribution}
{hr_trend}

{predictor_block}

HR zones (max HR {MAX_HR}bpm): Z1 <124 | Z2 124-154 | Z3 155-169 | Z4 170-184 | Z5 >185
Easy runs and base building should target Z2. Pace runs target Z3.

Upcoming NYC weather:
{chr(10).join([f"  {w['date']}: {weather_description(w['code'], w['low'])[1]}, High {w['high']}F / Low {w['low']}F, Wind {w['windspeed']}mph" for w in weather]) if weather else "  (unavailable)"}

Write a specific, data-driven coaching brief for Tom. Reference actual numbers from his runs. Keep each section to 2-3 sentences.

**Fitness Assessment** — use the pace, HR, watts and cadence data to assess current fitness and aerobic development.
**This Week's Focus** — specific paces and HR targets for each workout type this week based on the plan above.
**Key Priorities** — 2-3 bullet points with specific targets (e.g. "keep Z2 runs below 154bpm", not generic advice).
**Watch Out For** — one specific red flag from the data.
**Upcoming Milestones** — one concrete thing to look forward to.
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
    rows = ["| Workout | Distance | Pace | HR | Date |", "| :--- | :--- | :--- | :--- | :--- |"]
    if not activities:
        return "No recent runs found. Time to hit the road!"
    for r in activities[:5]:
        hr_str = f"{r['avg_hr']}bpm ({r['hr_zone']})" if r.get('avg_hr') else "—"
        rows.append(f"| {r['name']} | {r['distance_miles']}mi | {r['pace_per_mile']}/mi | {hr_str} | {r['date']} |")
    return "\n".join(rows)


def update_readme(activities, current_week, advice, run_id, updated_at):
    table = generate_activity_table(activities)
    base  = os.path.dirname(os.path.abspath(__file__))

    novice_2_plan = """| Week | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Rest | 3m run | 5m pace | 3m run | Rest | 8m | Cross |
| 2 | Rest | 3m run | 5m run | 3m run | Rest | 9m | Cross |
| 3 | Rest | 3m run | 5m pace | 3m run | Rest | 6m | Cross |
| 4 | Rest | 3m run | 6m pace | 3m run | Rest | 11m | Cross |
| 5 | Rest | 3m run | 6m run | 3m run | Rest | 12m | Cross |
| 6 | Rest | 3m run | 6m pace | 3m run | Rest | 9m | Cross |
| 7 | Rest | 4m run | 7m pace | 4m run | Rest | 14m | Cross |
| 8 | Rest | 4m run | 7m run | 4m run | Rest | 15m | Cross |
| 9 | Rest | 4m run | 7m pace | 4m run | Rest | Rest | Half Marathon |
| 10 | Rest | 4m run | 8m pace | 4m run | Rest | 17m | Cross |
| 11 | Rest | 5m run | 8m run | 5m run | Rest | 18m | Cross |
| 12 | Rest | 5m run | 8m pace | 5m run | Rest | 13m | Cross |
| 13 | Rest | 5m run | 5m pace | 5m run | Rest | 19m | Cross |
| 14 | Rest | 5m run | 8m run | 5m run | Rest | 12m | Cross |
| 15 | Rest | 5m run | 5m pace | 5m run | Rest | 20m | Cross |
| 16 | Rest | 5m run | 4m pace | 5m run | Rest | 12m | Cross |
| 17 | Rest | 4m run | 3m run | 4m run | Rest | 8m | Cross |
| 18 | Rest | 3m run | 2m run | Rest | Rest | 2m run | **NYC Marathon** |"""

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


def calculate_aerobic_efficiency(activities):
    MARATHON_HR_TARGET = 155
    results = []
    for a in activities:
        if not a.get('avg_hr') or a['avg_hr'] == 0:
            continue
        if not a.get('moving_time_sec') or a['moving_time_sec'] == 0:
            continue
        dist_meters = a['distance_miles'] * 1609.34
        speed_mpm   = dist_meters / (a['moving_time_sec'] / 60)
        ae          = round(speed_mpm / a['avg_hr'], 3)

        projected_speed_mpm = ae * MARATHON_HR_TARGET
        projected_speed_mps = projected_speed_mpm / 60
        projected_pace_sec  = 1609.34 / projected_speed_mps
        marathon_sec        = riegel_predict(projected_pace_sec, 26.2)
        marathon_pred       = sec_to_time(marathon_sec)

        results.append({
            'date':          a['date'],
            'name':          a['name'],
            'ae':            ae,
            'hr':            a['avg_hr'],
            'dist':          a['distance_miles'],
            'marathon_pred': marathon_pred,
            'marathon_sec':  marathon_sec,
        })
    return sorted(results, key=lambda x: x['date'])


def get_nyc_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=40.7128&longitude=-74.0060"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max"
        "&temperature_unit=fahrenheit"
        "&wind_speed_unit=mph"
        "&precipitation_unit=inch"
        "&timezone=America%2FNew_York"
        "&forecast_days=7"
    )
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()['daily']
    days = []
    for i in range(7):
        days.append({
            'date':      data['time'][i],
            'high':      round(data['temperature_2m_max'][i]),
            'low':       round(data['temperature_2m_min'][i]),
            'precip':    round(data['precipitation_sum'][i], 2),
            'windspeed': round(data['windspeed_10m_max'][i]),
            'code':      data['weathercode'][i],
        })
    return days


def weather_description(code, low=32):
    if code == 0:                    return ('☀️',  'Clear')
    if code in [1, 2]:               return ('🌤️',  'Partly Cloudy')
    if code == 3:                    return ('☁️',  'Overcast')
    if code in [45, 48]:             return ('🌫️',  'Foggy')
    if code in [51, 53, 55]:         return ('🌦️',  'Drizzle')
    if code in [61, 63, 65]:         return ('🌧️',  'Rain')
    if code in [71, 73, 75]:         return ('❄️' if low < 32 else '🌧️', 'Snow' if low < 32 else 'Cold Rain')
    if code in [80, 81, 82]:         return ('🌧️',  'Showers')
    if code in [95, 96, 99]:         return ('⛈️',  'Thunderstorm')
    return ('🌡️', 'Mixed')


# ── 7. MAIN ───────────────────────────────────────────────────────────────────
def aggregate_weekly_mileage(activities):
    from collections import defaultdict
    weeks = defaultdict(float)
    for a in activities:
        date   = datetime.strptime(a['date'], '%Y-%m-%d')
        monday = date - timedelta(days=date.weekday())
        week_key = monday.strftime('%Y-%m-%d')
        weeks[week_key] += a['distance_miles']
    return [
        {'week_start': k, 'miles': round(v, 1)}
        for k, v in sorted(weeks.items())
    ]


def main():
    run_id     = os.getenv("GITHUB_RUN_ID", "local")
    updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    print("→ Fetching Strava token…")
    token = get_strava_access_token()

    print("→ Fetching activities…")
    raw = get_activities(token)
    runs_raw = [a for a in raw if a.get("type") == "Run" or a.get("sport_type") == "Run"]

    # Enrich the 10 most recent runs with detailed data (max_hr, watts, cadence, best efforts)
    print(f"→ Fetching detailed data for up to 10 most recent runs…")
    activities = []
    for i, a in enumerate(sorted(runs_raw, key=lambda x: x['start_date_local'], reverse=True)):
        if i < 10:
            detail = get_activity_detail(token, a['id'])
            activities.append(format_activity(a, detail))
            print(f"  ✓ {a.get('name', 'Run')} ({a.get('start_date_local','')[:10]})")
        else:
            activities.append(format_activity(a))

    activities.sort(key=lambda x: x["date"], reverse=True)
    print(f"  {len(activities)} total runs, {min(10, len(activities))} enriched")

    current_week = get_current_week()
    phase = "Base Building (pre-plan)" if current_week == 0 else f"Week {current_week}/18"
    print(f"  Training phase: {phase}")

    paces        = [a["pace_seconds"] for a in activities if a["pace_seconds"] > 0]
    avg_pace_sec = sum(paces) / len(paces) if paces else 0

    predictions = {}
    if avg_pace_sec:
        predictions = {
            "5k":       sec_to_time(riegel_predict(avg_pace_sec, 3.1)),
            "10k":      sec_to_time(riegel_predict(avg_pace_sec, 6.2)),
            "half":     sec_to_time(riegel_predict(avg_pace_sec, 13.1)),
            "marathon": sec_to_time(riegel_predict(avg_pace_sec, 26.2)),
        }
        print(f"  Predicted marathon: {predictions['marathon']}")

    zones            = hr_pace_zones(avg_pace_sec)
    hr_distribution  = hr_zone_distribution(activities)

    print("→ Fetching NYC weather…")
    try:
        weather = get_nyc_weather()
        print(f"  {len(weather)} day forecast fetched")
    except Exception as e:
        print(f"✗ Weather error: {e}")
        weather = []

    # Gemini advice with retry
    advice = ""
    print("→ Calling Gemini…")
    for attempt in range(1, 4):
        try:
            advice = get_gemini_advice(activities, current_week, avg_pace_sec, hr_distribution, weather)
            print(f"✓ Gemini advice received (attempt {attempt})")
            with open("latest_advice.txt", "w") as f:
                f.write(advice)
            break
        except Exception as e:
            print(f"✗ Gemini attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                import time
                print(f"  Retrying in 30 seconds…")
                time.sleep(30)
            else:
                print("  All 3 attempts failed.")

    # Write coach_data.json
    weekly_mileage = aggregate_weekly_mileage(activities)
    ae_trend       = calculate_aerobic_efficiency(activities)
    coach_data = {
        "updated_at":         updated_at,
        "current_week":       current_week,
        "phase":              "base_building" if current_week == 0 else "training",
        "days_to_plan_start": max(0, (datetime(2026, 6, 29) - datetime.now()).days),
        "activities":         activities,
        "weekly_mileage":     weekly_mileage,
        "ae_trend":           ae_trend,
        "weather":            weather,
        "avg_pace_sec":       round(avg_pace_sec, 1),
        "predictions":        predictions,
        "pace_zones":         zones,
        "hr_distribution":    hr_distribution,
        "max_hr":             MAX_HR,
        "advice":             advice,
    }
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "coach_data.json"), "w") as f:
        json.dump(coach_data, f, indent=2)
    print("✓ coach_data.json written")

    update_readme(activities, current_week, advice, run_id, updated_at)


if __name__ == "__main__":
    main()
