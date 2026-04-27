# Madplan

A Home Assistant add-on that plans vegetarian and kid-friendly dinners for the current week and two weeks ahead. Powered by OpenAI.

## Features

- **3-week dinner plan** — navigate the current week plus two weeks ahead with a tab bar
- **Two dishes every night** — a vegetarian dish for the adults and a kid-friendly dish, planned separately
- **AI generation** — one click generates a full week of varied dinners with complete recipes
- **Full recipes** — each dish includes a cooking time, ingredient list with amounts, and numbered instructions
- **Recipe scaling** — adjust the number of servings directly in the recipe view; ingredient amounts update instantly
- **Chat assistant** — modify the plan in plain Danish ("Lav torsdag om til suppe", "Byt alle børneretter næste uge")
- **Manual editing** — click any meal card to view, edit, or clear it
- **Persistent storage** — the meal plan and chat history survive add-on restarts and updates

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**
2. Click the three-dot menu and choose **Repositories**
3. Add `https://github.com/danielmgregersen-code/Madplan`
4. Find **Madplan** in the store and install it
5. Configure the add-on (see below) and start it

## Configuration

| Option | Description | Default |
|---|---|---|
| `openai_api_key` | Your OpenAI API key | *(required)* |
| `chat_model` | OpenAI model to use | `gpt-5.5` |
| `num_adults` | Number of adults in the family | `2` |
| `num_children` | Number of children in the family | `3` |

## Usage

Open **Madplan** from the Home Assistant sidebar once the add-on is running.

### Week navigation
Use the **Denne uge / Næste uge / Om 2 uger** tabs at the top to switch between weeks.

### Generating a meal plan
Click **Generer uge** to let the AI create a full week of dinners for the selected week. Each day gets a vegetarian dish and a kid-friendly dish, both with ingredients and step-by-step instructions. Generation takes 1–2 minutes.

### Viewing a recipe
Click any meal card to open the full recipe. It shows:
- Cooking time at the top
- A servings selector — tap **+** or **−** to scale ingredient amounts up or down instantly
- The full ingredient list with amounts
- Numbered cooking instructions

### Editing manually
Inside the recipe view, click **Rediger** to edit the name, description, cooking time, servings, ingredients, and instructions by hand. Click **Ryd ret** to clear a meal entirely.

### Chat assistant
Open the **Snak med assistenten** panel at the bottom of the screen and type in Danish to request changes — for example:

- *"Lav tirsdagens børneret om til noget med kylling"*
- *"Skift alle vegetarretter næste uge til noget med pasta"*
- *"Giv mig en ny ret til lørdag, gerne noget fra ovnen"*

The assistant uses the current plan as context and updates the affected meals directly.
