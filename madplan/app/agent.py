import json
from datetime import date, timedelta
from openai import OpenAI

_DANISH_DAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]
_DANISH_MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

TOOL_UPDATE_MEALS = {
    "type": "function",
    "function": {
        "name": "update_meals",
        "description": "Opdater en eller flere retter i madplanen. Kald dette for at sætte eller ændre retter på bestemte datoer.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "description": "Liste af opdateringer der skal anvendes",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Dato i YYYY-MM-DD format"
                            },
                            "meal_type": {
                                "type": "string",
                                "enum": ["vegetarian", "kids"],
                                "description": "'vegetarian' for vegetarretten, 'kids' for børneretten"
                            },
                            "name": {
                                "type": "string",
                                "description": "Kortnavnet på retten, fx 'Pasta med tomatsauce'"
                            },
                            "description": {
                                "type": "string",
                                "description": "Kort beskrivelse af retten på én linje"
                            },
                            "total_time": {
                                "type": "string",
                                "description": "Realistisk samlet tilberedningstid inkl. forberedelse, fx '25 min', '45 min', '1 time 10 min'"
                            },
                            "servings": {
                                "type": "integer",
                                "description": "Antal personer opskriften er beregnet til"
                            },
                            "ingredients": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Ingrediensliste med præcise mængder, fx ['200g fusilli', '1 dåse hakkede tomater', '2 fed hvidløg']"
                            },
                            "instructions": {
                                "type": "string",
                                "description": "Nummererede tilberedningstrin adskilt af linjeskift, fx '1. Kog pasta...\n2. Svits løg...'"
                            }
                        },
                        "required": ["date", "meal_type", "name", "description", "total_time", "servings", "ingredients", "instructions"]
                    }
                }
            },
            "required": ["updates"]
        }
    }
}


def _build_system_prompt(num_adults: int, num_children: int, today: str) -> str:
    total = num_adults + num_children
    return f"""Du er en madplansassistent for en familie. I dag er {today}.

Familien har {num_adults} voksen(e) og {num_children} barn/børn ({total} personer i alt).

For HVER dag planlægger du TWO retter til aftensmad:
1. **vegetarian** – en vegetarret til de voksne. Ingen kød, ingen fisk.
2. **kids** – en børnevenlig ret (kan være med eller uden kød, men skal være mild og let at spise for børn).

Alle retter skal:
- Skrives på DANSK (navne, beskrivelser, ingredienser og tilberedningstrin)
- Have ingredienser med præcise mængder tilpasset {total} personer
- Have klare, nummererede tilberedningstrin
- Være varierede hen over ugen – undgå at gentage retter
- Have en realistisk og præcis total_time (inkl. forberedelse og tilberedning):
  - Enkle hverdagsretter: 20–35 min
  - Mellemstore retter: 35–55 min
  - Mere elaborate retter (fx ovnretter, gryderetter): 55–90 min
  - Weekendretter må gerne tage op til 90 min
  - Vær præcis — skriv "25 min" ikke "ca. 30 min"

Uger starter ALTID på mandag (europæisk standard). Når brugeren nævner en ugedag, slå datoen op direkte i madplanen nedenfor — beregn den aldrig ud fra ugedagsnummer.

Når brugeren beder om ændringer, brug update_meals-værktøjet til at anvende dem, og bekræft kort hvad du ændrede."""


def _format_plan_for_context(meal_plan: dict, week_start: date, weeks: int = 3) -> str:
    # Use Danish day names derived from weekday() (0=Mandag … 6=Søndag, Monday-first).
    # The ISO date is included explicitly so the agent never has to compute it.
    lines = ["Nuværende madplan (uger starter mandag):"]
    for i in range(weeks * 7):
        d = week_start + timedelta(days=i)
        key = d.isoformat()
        day_label = f"{_DANISH_DAYS[d.weekday()]} {d.day}. {_DANISH_MONTHS[d.month - 1]} ({key})"
        day_data = meal_plan.get(key, {})
        veg = day_data.get("vegetarian", {})
        kids = day_data.get("kids", {})
        veg_str = veg.get("name", "—") if veg else "—"
        kids_str = kids.get("name", "—") if kids else "—"
        lines.append(f"  {day_label}: vegetar={veg_str}, børn={kids_str}")
    return "\n".join(lines)


class MealPlanAgent:
    def __init__(self, api_key: str, model: str, num_adults: int, num_children: int):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.num_adults = num_adults
        self.num_children = num_children

    def generate_week(self, week_start: date, meal_plan: dict) -> dict:
        today = date.today().isoformat()
        system = _build_system_prompt(self.num_adults, self.num_children, today)

        days = [(week_start + timedelta(days=i)).isoformat() for i in range(7)]
        week_label = week_start.strftime("%d. %B %Y")

        user_msg = (
            f"Lav en komplet madplan for ugen der starter {week_label} "
            f"({days[0]} til {days[6]}). "
            f"Sæt både vegetarret og børneret for alle 7 dage. "
            f"Husk fuld opskrift med ingredienser og tilberedningstrin for hver ret."
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]

        updated = dict(meal_plan)
        self._run_tool_loop(messages, updated)
        return updated

    def chat(self, user_message: str, meal_plan: dict, history: list, week_start: date) -> tuple[str, dict]:
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
            return json.dumps({"error": f"Ukendt værktøj: {name}"})

        try:
            args = json.loads(arguments_json)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Ugyldig JSON: {e}"})

        updates = args.get("updates", [])
        applied = []
        for u in updates:
            d = u.get("date")
            meal_type = u.get("meal_type")
            if not d or not meal_type:
                continue
            if d not in meal_plan:
                meal_plan[d] = {}
            meal_plan[d][meal_type] = {
                "name": u.get("name", ""),
                "description": u.get("description", ""),
                "total_time": u.get("total_time", ""),
                "servings": u.get("servings", 0),
                "ingredients": u.get("ingredients", []),
                "instructions": u.get("instructions", ""),
            }
            applied.append(f"{d} {meal_type}: {u.get('name', '')}")

        return json.dumps({"applied": applied, "count": len(applied)})
