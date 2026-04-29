# Madplan

Et Home Assistant add-on der planlægger vegetariske og børnevenlige aftensmadsretter for den aktuelle uge og to uger frem. Drevet af OpenAI.

## Funktioner

- **Rullende ugevisning** — visningen starter fra i dag og viser 7 dage frem. Naviger mellem fem uger: 2 uger tilbage, forrige uge, denne uge, næste uge og om 2 uger
- **To retter hver aften** — en vegetarret til de voksne og en børnevenlig ret, planlagt separat
- **AI-generering** — ét klik genererer en fuld uge med varierede aftensmadsretter med komplette opskrifter
- **Fuld opskrift** — hver ret viser tilberedningstid, ingrediensliste med mængder og nummererede tilberedningstrin
- **Skalering af opskrifter** — juster antallet af portioner direkte i opskriftsvisningen; ingrediensmængder opdateres automatisk
- **Optøpåminder** — under børnerettens kolonne vises hvad der skal tages ud af fryseren til næste dags børneret
- **Favoritretter** — tilføj retter til en favoritleste fra opskriftsvisningen; AI'en bruger favoritterne lidt oftere, dog aldrig to gange inden for 14 dage
- **Ingen gentagelser** — AI'en tjekker de seneste 14 dage og bruger aldrig den samme ret to gange inden for den periode
- **Indkøbsliste** — søndagens kolonne viser en indkøbsliste-knap der genererer en samlet liste for søndag til lørdag, fordelt på butikker med aktuelle tilbud
- **Chatasssistent** — fortæl assistenten hvad du vil ændre på dansk, og madplanen opdateres med det samme
- **Manuel redigering** — klik på et dagskort for at se, redigere eller rydde en ret
- **Vedvarende opbevaring** — madplan, chathistorik og favoritter bevares på tværs af genstarter og opdateringer

## Installation

1. Gå til **Indstillinger → Tilføjelser → Tilføjelsesbutik** i Home Assistant
2. Klik på menuen med tre prikker og vælg **Repositories**
3. Tilføj `https://github.com/danielmgregersen-code/Madplan`
4. Find **Madplan** i butikken og installer den
5. Konfigurer tilføjelsen (se nedenfor) og start den

## Konfiguration

| Indstilling | Beskrivelse | Standard |
|---|---|---|
| `openai_api_key` | Din OpenAI API-nøgle | *(påkrævet)* |
| `chat_model` | OpenAI-model der bruges | `gpt-5.5` |
| `num_adults` | Antal voksne i familien | `2` |
| `num_children` | Antal børn i familien | `3` |
| `salling_api_key` | API-nøgle fra developer.sallinggroup.com (gratis) — giver rigtige tilbudspriser ved Føtex og Netto | *(valgfri)* |
| `postal_code` | Dit postnummer — bruges til at finde nærmeste Salling-butikker | *(valgfri)* |

## Brug

Åbn **Madplan** fra Home Assistants sidebjælke, når tilføjelsen kører.

### Ugenavigation
Brug fanerne **2 uger siden · Forrige uge · Denne uge · Næste uge · Om 2 uger** øverst til at skifte mellem uger. Standardvisningen starter fra i dag.

### Generering af madplan
Klik på **Generer uge** for at lade AI'en lave en fuld uges aftensmad. Hver dag får en vegetarret og en børneret med fuld opskrift. Generering tager typisk 1–2 minutter.

### Visning af opskrift
Klik på et retskort for at åbne den fulde opskrift. Her vises:
- Tilberedningstid øverst
- Portionsvælger — tryk **+** eller **−** for at skalere ingrediensmængder op eller ned med det samme
- Fuld ingrediensliste med mængder
- Nummererede tilberedningstrin

### Redigering
Klik på **Rediger** i opskriftsvisningen for at rette navn, beskrivelse, tilberedningstid, portioner, ingredienser, tilberedningstrin og optøinformation manuelt. Klik på **Ryd ret** for at slette en ret.

### Favoritretter
Klik på ⭐-knappen i headeren for at se din favoritleste. Tilføj eller fjern retter via ⭐-knappen i opskriftsvisningen. AI'en prioriterer favoritterne en smule, men bruger dem aldrig to gange inden for 14 dage.

### Optøpåminder
Hvis næste dags børneret kræver optøning, vises en blå 🧊-boks nederst i den aktuelle dags kolonne med hvad der skal tages ud af fryseren.

### Indkøbsliste
Søndagens kolonne viser et 🛒-kort. Klik på det for at generere en indkøbsliste der dækker søndag til lørdag. Listen er opdelt i butiksfaner:

- **Føtex** — varer i tilbud (fra Salling Group API, kræver API-nøgle)
- **Løvbjerg** — varer i tilbud (scraped fra lovbjerg.dk)
- **Netto** — varer i tilbud (fra Salling Group API, kræver API-nøgle)
- **Lidl** — varer i tilbud (scraped fra lidl.dk)
- **Rema 1000** — varer i tilbud (scraped fra rema1000.dk)
- **Generelt** — alle øvrige varer der ikke er i tilbud nogen steder

Kildebadges i toppen af listen viser hvilke butikker der har leveret live tilbudsdata. Uden Salling API-nøgle havner alle varer i **Generelt**.

### Chatasssistenten
Åbn panelet **Snak med assistenten** nederst på skærmen og skriv på dansk for at bede om ændringer — eksempelvis:

- *"Lav tirsdagens børneret om til noget med kylling"*
- *"Skift alle vegetarretter næste uge til noget med pasta"*
- *"Giv mig en ny ret til lørdag, gerne noget fra ovnen"*

Assistenten bruger den aktuelle madplan som kontekst og opdaterer de berørte retter direkte.
