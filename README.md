# Madplan

A Home Assistant add-on that plans vegetarian, kid-friendly meals for the current week and two weeks ahead. Powered by OpenAI.

## Features

- **3-week meal plan** — view and manage lunch and dinner for the current week plus two weeks ahead
- **AI generation** — one click generates a full week of varied, vegetarian meals tailored to your family size
- **Chat interface** — tell the assistant to make changes in plain language ("Make Thursday dinner a soup", "Replace all lunches next week with something quick")
- **Manual editing** — click any meal card to edit or clear it directly
- **Persistent storage** — the meal plan survives add-on restarts and updates

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
| `chat_model` | OpenAI model to use | `gpt-4.1` |
| `num_adults` | Number of adults in the family | `2` |
| `num_children` | Number of children in the family | `2` |

## Usage

Once running, open **Madplan** from the Home Assistant sidebar.

- Use the **This week / Next week / In 2 weeks** tabs to navigate
- Click **Generate week** to let the AI create a full week of meals
- Click any meal card to edit it manually
- Open the **Chat with assistant** panel at the bottom to request changes in natural language
