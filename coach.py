import requests
import os
import json
from datetime import datetime, timedelta

# ── 1. SETUP & SECRETS ────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY")

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


def get_activities(access_token, days=14):
    since = int((datetime.now() - timedelta(days=days)).timestamp())
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
    hr       = act.get("average_heartrate")

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


def pace_zones(avg_pace_sec):
    """Return training pace zones based on average race pace."""
    return {
        "easy":      f"{sec_to_time(int(avg_pace_sec * 1.20))}/mi  (conversational)",
        "long_run":  f"{sec_to_time(int(avg_pace_sec * 1.15))}/mi  (comfortable)",
        "marathon":  f"{sec_to_time(int(avg_pace_sec * 1.05))}/mi  (goal marathon pace)",
        "threshold": f"{sec_to_time(int(avg_pace_sec * 0.95))}/mi  (comfortably hard)",
        "tempo":     f"{sec_to_time(int(avg_pace_sec * 0.90))}/mi  (10K effort)",
    }


# ── 4. CURRENT TRAINING WEEK ──────────────────────────────────────────────────
def get_current_week():
    plan_start = datetime(2026, 6, 28)
    delta = datetime.now() - plan_start
    week  = max(1, min(18, int(delta.days / 7) + 1))
    return week


# ── 5. GEMINI COACHING ────────────────────────────────────────────────────────
HAL_HIGDON_N2 = """
Week 1:  Mon Rest | Tue 3mi | Wed 3mi | Thu 3mi | Fri Rest | Sat 4mi | Sun Cross
Week 2:  Mon Rest | Tue 3mi | Wed 3mi | Thu 3mi | Fri Rest | Sat 5mi | Sun Cross
Week 3:  Mon Rest | Tue 3mi | Wed 3mi | Thu 3mi | Fri Rest | Sat 6mi | Sun Cross
Week 4:  Mon Rest | Tue 3mi | Wed 4mi | Thu 3mi | Fri Rest | Sat 7mi | Sun Cross
Week 5:  Mon Rest | Tue 3mi | Wed 4mi | Thu 3mi | Fri Rest | Sat 8mi | Sun Cross
Week 6:  Mon Rest | Tue 3mi | Wed 4mi | Thu 3mi | Fri Rest | Sat 9mi | Sun Cross
Week 7:  Mon Rest | Tue 3mi | Wed 5mi | Thu 3mi | Fri Rest | Sat 10mi | Sun Cross
Week 8:  Mon Rest | Tue 3mi | Wed 5mi | Thu 3mi | Fri Rest | Sat 11mi | Sun Cross
Week 9:  Mon Rest | Tue 3mi | Wed 5mi | Thu 3mi | Fri Rest | Sat 12mi | Sun Cross
Week 10: Mon Rest | Tue 3mi | Wed 5mi | Thu 3mi | Fri Rest | Sat 13mi | Sun Cross
Week 11: Mon Rest | Tue 3mi | Wed 6mi | Thu 3mi | Fri Rest | Sat 14mi | Sun Cross
Week 12: Mon Rest | Tue 3mi | Wed 6mi | Thu 3mi | Fri Rest | Sat 15mi | Sun Cross
Week 13: Mon Rest | Tue 3mi | Wed 6mi | Thu 3mi | Fri Rest | Sat 16mi | Sun Cross
Week 14: Mon Rest | Tue 3mi | Wed 7mi | Thu 3mi | Fri Rest | Sat 17mi | Sun Cross
Week 15: Mon Rest | Tue 3mi | Wed 7mi | Thu 3mi | Fri Rest | Sat 18mi | Sun Cross
Week 16: Mon Rest | Tue 3mi | Wed 8mi | Thu 3mi | Fri Rest | Sat 19mi | Sun Cross
Week 17: Mon Rest | Tue 3mi | Wed 4mi | Thu 2mi | Fri Rest | Sat 8mi  | Sun Cross
Week 18: Mon Rest | Tue 3mi | Wed 2mi | Thu Rest | Fri Rest | Sat 2mi | Sun NYC MARATHON
"""


def get_gemini_advice(activities, current_week, avg_pace_sec):
    today = datetime.now().strftime("%A, %B %d, %Y")

    # Build rich run summary
    run_lines = []
    for r in activities[:10]:
        hr_str = f" | HR {r['avg_hr']}bpm" if r['avg_hr'] else ""
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
        zones     = pace_zones(avg_pace_sec)
        predictor_block = f"""
  Predicted Finish Times (Riegel formula from avg pace {sec_to_time(int(avg_pace_sec))}/mi):
    5K:     {pred_5k}
    Half:   {pred_half}
    Full:   {pred_full}

  Training Pace Zones:
    Easy/Long Run:  {zones['easy']}
    Marathon Pace:  {zones['marathon']}
    Threshold:      {zones['threshold']}
    Tempo:          {zones['tempo']}
"""
    else:
        predictor_block = "  (Insufficient pace data for predictions)"

    prompt = f"""You are an elite marathon coach specializing in Hal Higdon's Novice 2 program.
Today is {today}. The athlete is targeting the NYC Marathon on {MARATHON_DATE}.

═══ ATHLETE'S RECENT STRAVA DATA (Last 14 Days) ═══
{runs_block}

═══ PERFORMANCE METRICS ═══
{predictor_block}

═══ TRAINING CONTEXT ═══
  Current Week: {current_week} of 18 (official plan starts {PLAN_START})
  Plan: Hal Higdon Novice 2
  Days until NYC Marathon: {(datetime(2026,11,1) - datetime.now()).days}

═══ HAL HIGDON NOVICE 2 SCHEDULE ═══
{HAL_HIGDON_N2}

═══ YOUR COACHING RESPONSE ═══
Write a focused, data-driven coaching brief with these sections:

**Fitness Assessment**
Analyze pacing trends, consistency, volume, and any heart rate data. Be specific — reference actual numbers from their Strava data.

**This Week's Focus (Week {current_week})**
Exact paces for each run type this week. What should easy runs feel like? How should they approach Saturday's long run? Any drills or cross-training suggestions?

**Key Priorities**
2–3 actionable bullet points for this week based on where they are in the plan.

**Watch Out For**
Any red flags in the data — overtraining, pacing too fast, too little recovery, etc.

**Upcoming Milestones**
What to look forward to or prepare for in the next 2–3 weeks of training.

Keep it under 450 words. Be direct, specific, and encouraging. Reference their actual run data by name or date where relevant."""

    url     = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.65, "maxOutputTokens": 700},
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
    print(f"  Training week: {current_week}/18")

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
    zones = pace_zones(avg_pace_sec) if avg_pace_sec else {}

    # Gemini advice
    advice = ""
    print("→ Calling Gemini…")
    try:
        advice = get_gemini_advice(activities, current_week, avg_pace_sec)
        print("✓ Gemini advice received")
        with open("latest_advice.txt", "w") as f:
            f.write(advice)
    except Exception as e:
        print(f"✗ Gemini error: {e}")

    # Write coach_data.json (consumed by index.html dashboard)
    coach_data = {
        "updated_at":    updated_at,
        "current_week":  current_week,
        "activities":    activities,
        "avg_pace_sec":  round(avg_pace_sec, 1),
        "predictions":   predictions,
        "pace_zones":    zones,
        "advice":        advice,
    }
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "coach_data.json"), "w") as f:
        json.dump(coach_data, f, indent=2)
    print("✓ coach_data.json written")

    # Update README
    update_readme(activities, current_week, advice, run_id, updated_at)


if __name__ == "__main__":
    main()
