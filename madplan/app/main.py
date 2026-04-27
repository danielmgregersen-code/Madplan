import json
import os
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from agent import MealPlanAgent

OPTIONS_FILE = "/data/options.json"
MEAL_PLAN_FILE = "/data/meal_plan.json"
CHAT_HISTORY_FILE = "/data/chat_history.json"
MAX_HISTORY_MESSAGES = 100


def load_options() -> dict:
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE) as f:
            return json.load(f)
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "chat_model": os.getenv("CHAT_MODEL", "gpt-4.1"),
        "num_adults": int(os.getenv("NUM_ADULTS", "2")),
        "num_children": int(os.getenv("NUM_CHILDREN", "2")),
    }


def load_meal_plan() -> dict:
    if os.path.exists(MEAL_PLAN_FILE):
        try:
            with open(MEAL_PLAN_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_meal_plan(plan: dict):
    try:
        with open(MEAL_PLAN_FILE, "w") as f:
            json.dump(plan, f)
    except IOError as e:
        print(f"Warning: could not save meal plan: {e}", flush=True)


def load_chat_history() -> list:
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_chat_history(history: list):
    try:
        with open(CHAT_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except IOError as e:
        print(f"Warning: could not save chat history: {e}", flush=True)


def monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def make_agent() -> MealPlanAgent:
    opts = load_options()
    return MealPlanAgent(
        api_key=opts["openai_api_key"],
        model=opts.get("chat_model", "gpt-4.1"),
        num_adults=opts.get("num_adults", 2),
        num_children=opts.get("num_children", 2),
    )


app = FastAPI(title="Madplan")


class GenerateRequest(BaseModel):
    week_offset: int = 0  # 0 = current week, 1 = next week, 2 = week after


class ChatRequest(BaseModel):
    message: str
    week_offset: int = 0


class UpdateMealRequest(BaseModel):
    date: str       # YYYY-MM-DD
    meal_type: str  # "lunch" or "dinner"
    name: str
    description: str = ""


@app.get("/api/plan")
def get_plan():
    today = date.today()
    week_start = monday_of_week(today)
    plan = load_meal_plan()
    result = {}
    for i in range(21):
        d = week_start + timedelta(days=i)
        key = d.isoformat()
        result[key] = plan.get(key, {"lunch": None, "dinner": None})
    return result


@app.post("/api/generate")
async def generate_week(req: GenerateRequest):
    today = date.today()
    week_start = monday_of_week(today) + timedelta(weeks=req.week_offset)
    agent = make_agent()
    plan = load_meal_plan()
    try:
        updated = agent.generate_week(week_start, plan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    save_meal_plan(updated)
    result = {}
    for i in range(7):
        d = week_start + timedelta(days=i)
        key = d.isoformat()
        result[key] = updated.get(key, {"lunch": None, "dinner": None})
    return result


@app.post("/api/chat")
async def chat(req: ChatRequest):
    today = date.today()
    week_start = monday_of_week(today)
    plan = load_meal_plan()
    history = load_chat_history()
    agent = make_agent()
    try:
        reply, updated_plan = agent.chat(req.message, plan, history, week_start)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    save_meal_plan(updated_plan)
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": reply})
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    save_chat_history(history)
    return {"reply": reply, "plan": updated_plan}


@app.put("/api/meal")
async def update_meal(req: UpdateMealRequest):
    if req.meal_type not in ("lunch", "dinner"):
        raise HTTPException(status_code=400, detail="meal_type must be 'lunch' or 'dinner'")
    plan = load_meal_plan()
    if req.date not in plan:
        plan[req.date] = {}
    plan[req.date][req.meal_type] = {"name": req.name, "description": req.description}
    save_meal_plan(plan)
    return {"ok": True}


@app.delete("/api/meal")
async def delete_meal(date_str: str, meal_type: str):
    plan = load_meal_plan()
    if date_str in plan and meal_type in plan[date_str]:
        plan[date_str][meal_type] = None
        save_meal_plan(plan)
    return {"ok": True}


@app.get("/api/chat-history")
def get_chat_history():
    return load_chat_history()


@app.delete("/api/chat-history")
def clear_chat_history():
    save_chat_history([])
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
