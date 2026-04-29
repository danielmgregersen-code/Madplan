import json
from datetime import date, timedelta
from openai import OpenAI

_DANISH_DAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]
_DANISH_MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

TOOL_UPDATE_MEALS = {
    "type": "function",
    "function": {
        "name": "update_meals",
        "description": "Opdater en eller flere retter i madplanen.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Dato i YYYY-MM-DD format — aflæs direkte fra madplanen, beregn ikke selv"
                            },
                            "meal_type": {
                                "type": "string",
                                "enum": ["vegetarian", "kids"]
                            },
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "total_time": {
                                "type": "string",
                                "description": "Realistisk samlet tid inkl. forberedelse, fx '25 min', '1 time 10 min'"
                            },
                            "servings": {"type": "integer"},
                            "ingredients": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Mængder og ingredienser, fx ['200g fusilli', '1 dåse hakkede tomater']"
                            },
                            "instructions": {
                                "type": "string",
                                "description": "Nummererede trin adskilt af linjeskift"
                            },
                            "thaw": {
                                "type": "string",
                                "description": "Kun børneretter: hvad skal optøes AFTENEN FØR? Fx '400g hakket oksekød'. Tom streng hvis intet."
                            }
                        },
                        "required": ["date", "meal_type", "name", "description",
                                     "total_time", "servings", "ingredients", "instructions", "thaw"]
                    }
                }
            },
            "required": ["updates"]
        }
    }
}


def _build_system_prompt(num_adults: int, num_children: int, today: str, favorites: list = None) -> str:
    total = num_adults + num_children
    prompt = f"""Du er en madplansassistent for en familie. I dag er {today}.

Familien har {num_adults} voksen(e) og {num_children} barn/børn ({total} personer i alt).

For HVER dag planlægger du TO retter til aftensmad:
1. **vegetarian** – en vegetarret til de voksne. Ingen kød, ingen fisk.
2. **kids** – en børnevenlig ret (kan indeholde kød eller fisk, men skal være mild og let at spise for børn).

Alle retter skal:
- Skrives på DANSK
- Have ingredienser med præcise mængder til {total} personer
- Have klare, nummererede tilberedningstrin
- Have en realistisk total_time (inkl. forberedelse):
  - Enkle hverdagsretter: 20–35 min
  - Mellemstore retter: 35–55 min
  - Ovnretter og gryderetter: 55–90 min
  - Vær præcis — skriv "25 min" ikke "ca. 30 min"
- For børneretter: udfyld feltet **thaw** med hvad der evt. skal tages ud af fryseren AFTENEN FØR (fx "400g hakket oksekød"). Brug tom streng "" hvis intet skal optøes.

Uger starter ALTID på mandag (europæisk standard).
Slå altid datoen op direkte i madplanen nedenfor — beregn den ALDRIG ud fra ugedagsnummer.

**Ingen gentagelser:** Brug ALDRIG den samme ret inden for 14 dage. Tjek madplanen omhyggeligt."""

    if favorites:
        veg_favs = [f["name"] for f in favorites if f.get("meal_type") == "vegetarian"]
        kids_favs = [f["name"] for f in favorites if f.get("meal_type") == "kids"]
        if veg_favs or kids_favs:
            prompt += "\n\n**Favoritretter** (familien holder særligt af disse — brug dem gerne, men højst én gang pr. 14 dage):"
            if veg_favs:
                prompt += "\n- Vegetar: " + ", ".join(veg_favs)
            if kids_favs:
                prompt += "\n- Børn: " + ", ".join(kids_favs)

    prompt += "\n\nNår brugeren beder om ændringer, brug update_meals til at anvende dem og bekræft kort."
    return prompt


def _format_plan_for_context(meal_plan: dict, today: date) -> str:
    # Show 5-week window so agent can check for repeats within 14 days
    start = today - timedelta(days=14)
    lines = ["Madplan (uger starter mandag — brug dato-feltet direkte, beregn det ikke):"]
    for i in range(35):
        d = start + timedelta(days=i)
        key = d.isoformat()
        marker = " ← I DAG" if d == today else ""
        day_label = f"{_DANISH_DAYS[d.weekday()]} {d.day}. {_DANISH_MONTHS[d.month - 1]} ({key}){marker}"
        day_data = meal_plan.get(key, {})
        veg = day_data.get("vegetarian") or {}
        kids = day_data.get("kids") or {}
        veg_str = veg.get("name", "—")
        kids_str = kids.get("name", "—")
        lines.append(f"  {day_label}: vegetar={veg_str}, børn={kids_str}")
    return "\n".join(lines)


class MealPlanAgent:
    def __init__(self, api_key: str, model: str, num_adults: int, num_children: int):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.num_adults = num_adults
        self.num_children = num_children

    def generate_week(self, week_start: date, meal_plan: dict, today: date, favorites: list = None) -> dict:
        system = _build_system_prompt(self.num_adults, self.num_children, today.isoformat(), favorites)
        plan_context = _format_plan_for_context(meal_plan, today)

        days = [(week_start + timedelta(days=i)) for i in range(7)]
        start_label = f"{_DANISH_DAYS[week_start.weekday()]} {week_start.day}. {_DANISH_MONTHS[week_start.month-1]}"
        end = days[-1]
        end_label = f"{_DANISH_DAYS[end.weekday()]} {end.day}. {_DANISH_MONTHS[end.month-1]}"

        user_msg = (
            f"Lav en komplet madplan fra {start_label} ({days[0].isoformat()}) "
            f"til {end_label} ({days[-1].isoformat()}). "
            f"Sæt vegetarret og børneret for alle 7 dage med fuld opskrift. "
            f"Tjek at ingen retter gentages fra de seneste 14 dage i planen ovenfor."
        )

        messages = [
            {"role": "system", "content": f"{system}\n\n{plan_context}"},
            {"role": "user", "content": user_msg},
        ]

        updated = dict(meal_plan)
        self._run_tool_loop(messages, updated)
        return updated

    def chat(self, user_message: str, meal_plan: dict, history: list, today: date, favorites: list = None) -> tuple[str, dict]:
        system = _build_system_prompt(self.num_adults, self.num_children, today.isoformat(), favorites)
        plan_context = _format_plan_for_context(meal_plan, today)

        messages = [{"role": "system", "content": f"{system}\n\n{plan_context}"}]
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
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        return last_reply

    def _handle_tool_call(self, name: str, arguments_json: str, meal_plan: dict) -> str:
        if name != "update_meals":
            return json.dumps({"error": f"Ukendt værktøj: {name}"})
        try:
            args = json.loads(arguments_json)
        except json.JSONDecodeError as e:
            return json.dumps({"error": str(e)})

        applied = []
        for u in args.get("updates", []):
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
                "thaw": u.get("thaw", ""),
            }
            applied.append(f"{d} {meal_type}: {u.get('name', '')}")

        return json.dumps({"applied": applied, "count": len(applied)})

    # ── Shopping list ──

    def generate_shopping_list(
        self,
        start_date: date,
        meal_plan: dict,
        salling_offers: list,
        lidl_offers: list,
        loevbjerg_offers: list,
    ) -> dict:
        """Organise a 7-day ingredient list by store, using real offer data where available."""
        total = self.num_adults + self.num_children

        # Collect all ingredients for the 7-day window
        raw_ingredients: list[str] = []
        for i in range(7):
            d = start_date + timedelta(days=i)
            key = d.isoformat()
            day_data = meal_plan.get(key, {})
            for meal_type in ("vegetarian", "kids"):
                meal = day_data.get(meal_type) or {}
                raw_ingredients.extend(meal.get("ingredients", []))

        if not raw_ingredients:
            return {"foetex": [], "loevbjerg": [], "netto": [], "lidl": [], "other": []}

        end_date = start_date + timedelta(days=6)
        start_label = f"{_DANISH_DAYS[start_date.weekday()]} {start_date.day}. {_DANISH_MONTHS[start_date.month-1]}"
        end_label = f"{_DANISH_DAYS[end_date.weekday()]} {end_date.day}. {_DANISH_MONTHS[end_date.month-1]}"

        system = f"""Du er en indkøbsassistent for en dansk familie med {total} personer.
Du modtager en ingrediensliste for {start_label} til {end_label} og skal fordele varerne på følgende butikker:
- **foetex** (Føtex): friske råvarer, kvalitetsprodukter, større pakker
- **loevbjerg** (Løvbjerg): lokale/regionale produkter, slagterafdelingen
- **netto** (Netto): hverdagsbasics, mejeri, brød, dåsevarer
- **lidl** (Lidl): billige basisvarer, importerede varer, grøntsager, bageartikler
- **other** (Andre varer): varer der ikke passer til nogen bestemt butik

Regler:
- Konsolider lignende ingredienser (fx to tomat-poster → én linje)
- Skriv mængder på dansk, fx "400g hakket oksekød"
- Varer der er i tilbud i en bestemt butik → læg dem der, tilføj "(TILBUD: X kr)" sidst
- Fordel resten fornuftigt baseret på butiksprofil
- Svar KUN ved at kalde set_shopping_list — ingen tekst ved siden af"""

        offer_context_parts = []
        if salling_offers:
            foetex_s = [o for o in salling_offers if o["store"] == "foetex"]
            netto_s = [o for o in salling_offers if o["store"] == "netto"]
            if foetex_s:
                offer_context_parts.append("Føtex tilbud (Salling): " +
                    ", ".join(f"{o['product']} {o['price']}" for o in foetex_s[:20]))
            if netto_s:
                offer_context_parts.append("Netto tilbud (Salling): " +
                    ", ".join(f"{o['product']} {o['price']}" for o in netto_s[:20]))
        if lidl_offers:
            offer_context_parts.append("Lidl tilbud (scraped): " + ", ".join(lidl_offers[:30]))
        if loevbjerg_offers:
            offer_context_parts.append("Løvbjerg tilbud (scraped): " + ", ".join(loevbjerg_offers[:30]))

        user_msg = "Ingredienser:\n" + "\n".join(f"- {ing}" for ing in raw_ingredients)
        if offer_context_parts:
            user_msg += "\n\nAktuelle tilbud:\n" + "\n".join(offer_context_parts)

        tool = {
            "type": "function",
            "function": {
                "name": "set_shopping_list",
                "description": "Angiv den færdige indkøbsliste fordelt på butikker",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stores": {
                            "type": "object",
                            "properties": {
                                "foetex":    {"type": "array", "items": {"type": "string"}},
                                "loevbjerg": {"type": "array", "items": {"type": "string"}},
                                "netto":     {"type": "array", "items": {"type": "string"}},
                                "lidl":      {"type": "array", "items": {"type": "string"}},
                                "other":     {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["foetex", "loevbjerg", "netto", "lidl", "other"],
                        }
                    },
                    "required": ["stores"],
                },
            },
        }

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]

        for _ in range(4):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": "set_shopping_list"}},
            )
            msg = response.choices[0].message
            if msg.tool_calls:
                tc = msg.tool_calls[0]
                args = json.loads(tc.function.arguments)
                stores = args.get("stores", {})
                return {
                    "foetex":    stores.get("foetex", []),
                    "loevbjerg": stores.get("loevbjerg", []),
                    "netto":     stores.get("netto", []),
                    "lidl":      stores.get("lidl", []),
                    "other":     stores.get("other", []),
                }

        # Fallback: dump everything in other
        return {"foetex": [], "loevbjerg": [], "netto": [], "lidl": [], "other": list(set(raw_ingredients))}
