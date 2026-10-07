import csv
import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

# ---------- SETTINGS (change these for each client) ----------
MODEL = "gemini-3-flash-preview"
CSV_FILE = "leads.csv"

SETTINGS = {
    "business": "a freelancer",
    "services": ["automation", "website", "app"],
    "hot_min": 50000,
    "warm_min": 20000,
}

CSV_COLUMNS = ["time", "id", "name", "message", "budget", "score", "urgent", "reason"]


# ---------- INPUT ----------
def get_new_leads():
    # Later: replace this with a CSV, Google Sheet, or webhook.
    # Each lead needs a unique "id" so we never save the same lead twice.
    return [
        {"id": "1", "name": "Ada", "budget": "150,000",
         "message": "I need a website for my bakery, launching in 2 weeks"},
        {"id": "2", "name": "Tunde", "budget": "5k",
         "message": "Can you design a logo for my shop?"},
        {"id": "3", "name": "Zainab", "budget": 80000,
         "message": "I want to automate my customer replies on WhatsApp"},
        {"id": "4", "name": "Chidi", "budget": "30k",
         "message": "Looking for someone to build a mobile app, no rush"},
    ]


# ---------- HELPERS ----------
def parse_budget(value):
    """Turns 50000, '50,000', '50k', '1.5m' into a number."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).lower().replace(",", "").replace("₦", "").replace("naira", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(k|m)?", text)
    if not match:
        return 0
    number = float(match.group(1))
    if match.group(2) == "k":
        number *= 1000
    elif match.group(2) == "m":
        number *= 1_000_000
    return int(number)


def matches_service(text):
    """True if the message mentions one of our services (whole words only)."""
    text = text.lower()
    for service in SETTINGS["services"]:
        if re.search(r"\b" + re.escape(service.lower()) + r"s?\b", text):
            return True
    return False


def already_saved_ids():
    if not os.path.exists(CSV_FILE):
        return set()
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        return {row["id"] for row in csv.DictReader(f)}


# ---------- SCORING ----------
def qualify_lead_by_rules(lead, budget):
    """Backup scoring if Gemini fails. Same rules as the prompt."""
    matches = matches_service(lead["message"])
    if matches and budget >= SETTINGS["hot_min"]:
        score = "hot"
    elif matches and budget >= SETTINGS["warm_min"]:
        score = "warm"
    else:
        score = "cold"
    return {"score": score, "urgent": False, "reason": "fallback rule"}


def qualify_lead(lead, budget):
    prompt = f"""You qualify sales leads for {SETTINGS['business']}.
Services offered: {", ".join(SETTINGS['services'])}.

Scoring rules:
- hot: the request matches a service offered AND the budget is {SETTINGS['hot_min']} naira or more
- warm: the request matches a service offered AND the budget is {SETTINGS['warm_min']} to {SETTINGS['hot_min'] - 1} naira
- cold: everything else
Use only these rules. Do not assume market rates.

Also set "urgent" to true only if the lead says they need it soon (within about 2 weeks).
Urgency does NOT change the score.

Lead name: {lead['name']}
Lead message: {json.dumps(lead['message'])}
Budget in naira: {budget}

Reply with ONLY a JSON object like:
{{"score": "hot", "urgent": false, "reason": "short reason"}}"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        result = json.loads(response.text)
        result["score"] = str(result["score"]).lower().strip()
        if result["score"] not in ("hot", "warm", "cold"):
            raise ValueError("unexpected score")
        result["urgent"] = bool(result.get("urgent", False))
        result["reason"] = str(result.get("reason", ""))
        return result
    except Exception as error:
        print("Gemini failed, using fallback rules:", error)
        return qualify_lead_by_rules(lead, budget)


# ---------- SAVING ----------
def save_to_sheet(lead, budget, result):
    file_exists = os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_COLUMNS)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            lead["id"],
            lead["name"],
            lead["message"],
            budget,
            result["score"],
            result["urgent"],
            result["reason"],
        ])

    print("SAVED:", lead["name"], "->", result["score"])


# ---------- ACTIONS (replace the prints with real sending later) ----------
def send_slack(lead):
    print("SLACK ALERT: hot lead", lead["name"])


def send_warm_message(lead):
    print("WARM: schedule a call with", lead["name"])


def send_email(lead):
    print("EMAIL FOLLOW-UP to", lead["name"])


# ---------- MAIN ----------
def run():
    seen = already_saved_ids()

    for lead in get_new_leads():
        if lead["id"] in seen:
            print("SKIPPED (already saved):", lead["name"])
            continue

        try:
            budget = parse_budget(lead["budget"])
            result = qualify_lead(lead, budget)
            save_to_sheet(lead, budget, result)

            if result["score"] == "hot":
                send_slack(lead)
            elif result["score"] == "warm":
                send_warm_message(lead)
            else:
                send_email(lead)
        except Exception as error:
            print("FAILED on", lead.get("name", "?"), ":", error)


if __name__ == "__main__":
    run()