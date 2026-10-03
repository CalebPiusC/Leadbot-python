import json
from click import prompt
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()
MODEL = "gemini-3-flash-preview"



def get_new_leads():
    return [
        {"name": "Ada", "need": "website", "budget": 150000},
        {"name": "Tunde", "need": "logo", "budget": 5000},
        {"name": "Zainab", "need": "automation", "budget": 80000},
        {"name": "Chidi", "need": "app", "budget": 30000},
    ]

def qualify_lead_by_budget(lead):
    if lead["budget"] >= 50000:
        return {"score": "hot"}
    elif lead["budget"] >= 20000:
        return {"score": "warm"}
    else:
        return {"score": "cold"}

def save_to_sheet(lead, result):
    print("SAVED:", lead["name"], "->", result["score"])

def send_slack(lead):
    print("SLACK ALERT: hot lead", lead["name"])

def send_email(lead):
    print("EMAIL FOLLOW-UP to", lead["name"])

def send_warm_message(lead):
    print("WARM: schedule a call with", lead["name"])

def run():
    for lead in get_new_leads():
        result = qualify_lead(lead)
        save_to_sheet(lead, result)
        if result["score"] == "hot":
            send_slack(lead)
        elif result["score"] == "warm":
            send_warm_message(lead)
        else:
            send_email(lead)

def qualify_lead(lead):
    prompt = f"""You qualify sales leads for a freelancer who builds automations.
Lead: name = {lead['name']}, need = {lead['need']}, budget in naira = {lead['budget']}.
Reply with ONLY a JSON object like {{"score": "hot", "reason": "short reason"}}.
The score must be exactly one of: hot, warm, cold."""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        result = json.loads(response.text)
        if result["score"] not in ("hot", "warm", "cold"):
            raise ValueError("unexpected score")
        return result
    except Exception as error:
        print("Gemini failed, using budget rule instead:", error)
        return qualify_lead_by_budget(lead)

run()