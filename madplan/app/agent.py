import json
from datetime import date, timedelta
from openai import OpenAI

TOOL_UPDATE_MEALS = {
    "type": "function",
    "function": {
        "name": "update_meals",
        "description": "Update one or more meals in the meal plan. Call this to set or change lunch and/or dinner for specific dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "description": "List of meal updates to apply",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Date in YYYY-MM-DD format"
                            },
                            "meal_type": {
                                "type": "string",
                                "enum": ["lunch", "dinner"],
                                "description": "Which meal to update"
                            },
                            "name": {
                                "type": "string",
                                "description": "Short meal name, e.g. 'Pasta with tomato sauce'"
                            },
                            "description": {
                                "type": "string",
                                "description": "One-sentence description of the dish"
                            }
                        },
                        "required": ["date", "meal_type", "name", "description"]
                    }
                }
            },
            "required": ["updates"]
        }
    }
}


def _build_system_prompt(num_adults: int, num_children: int, today: str) -> str:
    return f"""You are a family meal planner assistant. Today is {today}.

You plan vegetarian meals that are:
- Kid-friendly and appealing to children
- Nutritious and varied across the week
- Practical to cook (weekday dinners ~30 min, weekend dinners can be more elaborate)
- Free of meat and fish — vegetarian only

The family has {num_adults} adult(s) and {num_children} child(ren).

When generating a meal plan for a week:
- Plan both lunch and dinner for every day (Monday–Sunday)
- Avoid repeating the same dish within a week
- Mix cuisines and ingredients: pasta, soup, rice, lentils, wraps, casseroles, etc.
- Keep kid-friendly flavours: not too spicy, familiar textures
- Weekend meals (Saturday/Sunday) can be slightly more special

When the user asks you to change something, use the update_meals tool to apply changes, then briefly confirm what you changed.

Always use update_meals when making any changes to the plan — never just describe changes without calling the tool."""


def _format_plan_for_context(meal_plan: dict, week_start: date, weeks: int = 3) -> str:
    lines = ["Current meal plan:"]
    for i in range(weeks * 7):
        d = week_start + timedelta(days=i)
        key = d.isoformat()
        day_name = d.strftime("%A %d %b")
        day_data = meal_plan.get(key, {})
        lunch = day_data.get("lunch", {})
        dinner = day_data.get("dinner", {})
        lunch_str = lunch.get("name", "—") if lunch else "—"
        dinner_str = dinner.get("name", "—") if dinner else "—"
        lines.append(f"  {day_name}: lunch={lunch_str}, dinner={dinner_str}")
    return "\n".join(lines)


class MealPlanAgent:
    def __init__(self, api_key: str, model: str, num_adults: int, num_children: int):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.num_adults = num_adults
        self.num_children = num_children

    def generate_week(self, week_start: date, meal_plan: dict) -> dict:
        """Generate a full week of meals (lunch + dinner for 7 days). Returns updated meal_plan."""
        today = date.today().isoformat()
        system = _build_system_prompt(self.num_adults, self.num_children, today)

        days = [(week_start + timedelta(days=i)).isoformat() for i in range(7)]
        week_label = week_start.strftime("%B %d, %Y")

        user_msg = (
            f"Please generate a complete meal plan for the week starting {week_label} "
            f"({days[0]} to {days[6]}). "
            f"Set both lunch and dinner for all 7 days. "
            f"Make it varied, kid-friendly, and vegetarian."
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]

        updated = dict(meal_plan)
        self._run_tool_loop(messages, updated)
        return updated

    def chat(self, user_message: str, meal_plan: dict, history: list, week_start: date) -> tuple[str, dict]:
        """Process a chat message. Returns (assistant_reply, updated_meal_plan)."""
        today = date.today().isoformat()
        system = _build_system_prompt(self.num_adults, self.num_children, today)
        plan_context = _format_plan_for_context(meal_plan, week_start)
        system_with_plan = f"{system}\n\n{plan_context}"

        messages = [{"role": "system", "content": system_with_plan}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        updated = dict(meal_plan)
        reply = self._run_tool_loop(messages, updated)
        return reply, updated

    def _run_tool_loop(self, messages: list, meal_plan: dict) -> str:
        last_reply = ""
        for _ in range(8):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[TOOL_UPDATE_MEALS],
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if msg.content:
                last_reply = msg.content

            if not msg.tool_calls:
                break

            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})

            for tc in msg.tool_calls:
                result = self._handle_tool_call(tc.function.name, tc.function.arguments, meal_plan)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return last_reply

    def _handle_tool_call(self, name: str, arguments_json: str, meal_plan: dict) -> str:
        if name != "update_meals":
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            args = json.loads(arguments_json)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        updates = args.get("updates", [])
        applied = []
        for u in updates:
            d = u.get("date")
            meal_type = u.get("meal_type")
            name_val = u.get("name", "")
            desc = u.get("description", "")
            if not d or not meal_type:
                continue
            if d not in meal_plan:
                meal_plan[d] = {}
            meal_plan[d][meal_type] = {"name": name_val, "description": desc}
            applied.append(f"{d} {meal_type}: {name_val}")

        return json.dumps({"applied": applied, "count": len(applied)})
