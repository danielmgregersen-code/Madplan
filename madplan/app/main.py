import json
import os
import uuid
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from agent import MealPlanAgent
from salling import find_store_ids, fetch_food_waste_offers
from scraper import fetch_lidl_offers, fetch_loevbjerg_offers

OPTIONS_FILE = "/data/options.json"
MEAL_PLAN_FILE = "/data/meal_plan.json"
CHAT_HISTORY_FILE = "/data/chat_history.json"
FAVORITES_FILE = "/data/favorites.json"
SHOPPING_LIST_FILE = "/data/shopping_list.json"
MAX_HISTORY_MESSAGES = 100

# Plan window: 2 weeks back + today + 2 weeks ahead = 35 days
DAYS_BACK = 14
DAYS_TOTAL = 35


def load_options() -> dict:
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE) as f:
            return json.load(f)
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "chat_model": os.getenv("CHAT_MODEL", "gpt-5.5"),
        "num_adults": int(os.getenv("NUM_ADULTS", "2")),
        "num_children": int(os.getenv("NUM_CHILDREN", "3")),
    }


def _load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default


def _save_json(path: str, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except IOError as e:
        print(f"Advarsel: kunne ikke gemme {path}: {e}", flush=True)


def load_meal_plan() -> dict:
    return _load_json(MEAL_PLAN_FILE, {})

def save_meal_plan(plan: dict):
    _save_json(MEAL_PLAN_FILE, plan)

def load_chat_history() -> list:
    return _load_json(CHAT_HISTORY_FILE, [])

def save_chat_history(history: list):
    _save_json(CHAT_HISTORY_FILE, history)

def load_favorites() -> list:
    return _load_json(FAVORITES_FILE, [])

def save_favorites(favs: list):
    _save_json(FAVORITES_FILE, favs)


def make_agent() -> MealPlanAgent:
    opts = load_options()
    api_key = opts.get("openai_api_key", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API-nøgle er ikke konfigureret. Angiv den i add-on konfigurationen."
        )
    return MealPlanAgent(
        api_key=api_key,
        model=opts.get("chat_model", "gpt-5.5"),
        num_adults=opts.get("num_adults", 2),
        num_children=opts.get("num_children", 3),
    )


app = FastAPI(title="Madplan")

EMPTY_DAY = {"vegetarian": None, "kids": None}


class GenerateRequest(BaseModel):
    week_offset: int = 0   # start = today + offset * 7 days


class ChatRequest(BaseModel):
    message: str


class UpdateMealRequest(BaseModel):
    date: str
    meal_type: str          # "vegetarian" or "kids"
    name: str
    description: str = ""
    total_time: str = ""
    servings: int = 0
    ingredients: List[str] = []
    instructions: str = ""
    thaw: str = ""          # what to take out of freezer the night before (kids meals)


class FavoriteRequest(BaseModel):
    name: str
    meal_type: str          # "vegetarian" or "kids"
    description: str = ""


# ── Plan ──

@app.get("/api/plan")
def get_plan():
    today = date.today()
    start = today - timedelta(days=DAYS_BACK)
    plan = load_meal_plan()
    result = {}
    for i in range(DAYS_TOTAL):
        d = start + timedelta(days=i)
        key = d.isoformat()
        result[key] = plan.get(key, dict(EMPTY_DAY))
    return result


@app.post("/api/generate")
async def generate_week(req: GenerateRequest):
    today = date.today()
    week_start = today + timedelta(days=req.week_offset * 7)
    plan = load_meal_plan()
    favorites = load_favorites()
    try:
        agent = make_agent()
        updated = agent.generate_week(week_start, plan, today, favorites)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    save_meal_plan(updated)
    result = {}
    for i in range(7):
        d = week_start + timedelta(days=i)
        key = d.isoformat()
        result[key] = updated.get(key, dict(EMPTY_DAY))
    return result


@app.post("/api/chat")
async def chat(req: ChatRequest):
    today = date.today()
    plan = load_meal_plan()
    history = load_chat_history()
    favorites = load_favorites()
    try:
        agent = make_agent()
        reply, updated_plan = agent.chat(req.message, plan, history, today, favorites)
    except HTTPException:
        raise
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
    if req.meal_type not in ("vegetarian", "kids"):
        raise HTTPException(status_code=400, detail="meal_type skal være 'vegetarian' eller 'kids'")
    plan = load_meal_plan()
    if req.date not in plan:
        plan[req.date] = {}
    plan[req.date][req.meal_type] = {
        "name": req.name,
        "description": req.description,
        "total_time": req.total_time,
        "servings": req.servings,
        "ingredients": req.ingredients,
        "instructions": req.instructions,
        "thaw": req.thaw,
    }
    save_meal_plan(plan)
    return {"ok": True}


@app.delete("/api/meal")
async def delete_meal(date_str: str, meal_type: str):
    plan = load_meal_plan()
    if date_str in plan and meal_type in plan[date_str]:
        plan[date_str][meal_type] = None
        save_meal_plan(plan)
    return {"ok": True}


# ── Favorites ──

@app.get("/api/favorites")
def get_favorites():
    return load_favorites()


@app.post("/api/favorites")
async def add_favorite(req: FavoriteRequest):
    favs = load_favorites()
    # Avoid exact duplicates by name + meal_type
    if any(f["name"] == req.name and f["meal_type"] == req.meal_type for f in favs):
        return {"ok": True, "duplicate": True}
    favs.append({
        "id": str(uuid.uuid4()),
        "name": req.name,
        "meal_type": req.meal_type,
        "description": req.description,
    })
    save_favorites(favs)
    return {"ok": True}


@app.delete("/api/favorites/{fav_id}")
async def remove_favorite(fav_id: str):
    favs = [f for f in load_favorites() if f["id"] != fav_id]
    save_favorites(favs)
    return {"ok": True}


# ── Chat history ──

@app.get("/api/chat-history")
def get_chat_history():
    return load_chat_history()


@app.delete("/api/chat-history")
def clear_chat_history():
    save_chat_history([])
    return {"ok": True}


# ── Shopping list ──

class ShoppingListRequest(BaseModel):
    start_date: str   # YYYY-MM-DD (should be a Sunday)


@app.post("/api/shopping-list")
async def create_shopping_list(req: ShoppingListRequest):
    try:
        start = date.fromisoformat(req.start_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldig dato — brug YYYY-MM-DD format")

    opts = load_options()
    salling_key = opts.get("salling_api_key", "").strip()
    postal_code = opts.get("postal_code", "").strip()
    plan = load_meal_plan()

    salling_offers: list = []
    if salling_key and postal_code:
        store_ids = find_store_ids(salling_key, postal_code)
        if store_ids:
            salling_offers = fetch_food_waste_offers(salling_key, store_ids)

    lidl_offers = fetch_lidl_offers()
    loevbjerg_offers = fetch_loevbjerg_offers()

    try:
        agent = make_agent()
        stores = agent.generate_shopping_list(start, plan, salling_offers, lidl_offers, loevbjerg_offers)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    payload = {
        "start_date": req.start_date,
        "end_date": (start + timedelta(days=6)).isoformat(),
        "stores": stores,
        "has_salling_data": bool(salling_offers),
        "has_lidl_data": bool(lidl_offers),
        "has_loevbjerg_data": bool(loevbjerg_offers),
    }
    _save_json(SHOPPING_LIST_FILE, payload)
    return payload


@app.get("/api/shopping-list/latest")
def get_latest_shopping_list(start_date: str):
    data = _load_json(SHOPPING_LIST_FILE, None)
    if data and data.get("start_date") == start_date:
        return data
    raise HTTPException(status_code=404, detail="Ingen gemt indkøbsliste for denne dato")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
