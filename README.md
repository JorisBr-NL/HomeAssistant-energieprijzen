# Jeroen.nl energieprijzen voor Home Assistant

Leest de dynamische stroomprijzen van [jeroen.nl](https://jeroen.nl) in Home Assistant in: vandaag en (vanaf ca. 13:00) morgen, per kwartier.

## Installatie via HACS

1. HACS → ⋮ → **Aangepaste repositories**
2. URL: `https://github.com/JorisBr-NL/HomeAssistant-energieprijzen.git`, type **Integratie**
3. Zoek **Jeroen.nl energieprijzen**, installeer en herstart Home Assistant
4. **Instellingen → Apparaten en diensten → Integratie toevoegen → Jeroen.nl energieprijzen**
5. Vul je API-sleutel in (het deel na `key=` in je API-URL)

## Sensoren

| Sensor | Uitleg |
|---|---|
| Huidige prijs | Prijs voor het huidige kwartier (all-in, zie opties) |
| Huidige prijs excl. belastingen | Kale prijs van jeroen.nl |
| Volgende prijs | Prijs voor het volgende kwartier |
| Laagste / hoogste / gemiddelde prijs vandaag | Met `start`/`end` als attribuut bij laagste/hoogste |
| Laagste / gemiddelde prijs morgen | Leeg tot de prijzen van morgen bekend zijn |
| Goedkoopste moment vandaag / morgen | Tijdstempel van het goedkoopste kwartier (attributen `end` en `price`), direct bruikbaar als tijd-trigger |

De sensor **Huidige prijs** heeft de attributen `prices_today`, `prices_tomorrow` (lijst met `start`, `end`, `price`) en `tomorrow_available`. Die zijn bruikbaar in bijvoorbeeld ApexCharts of automations. Ze worden niet in de database opgeslagen.

## All-in prijs

Via **Configureren** op de integratie stel je in:

- opslag/inkoopvergoeding leverancier (EUR/kWh, excl. btw)
- energiebelasting (EUR/kWh, excl. btw)
- btw (%)

Berekening: `(kale prijs + opslag + energiebelasting) × (1 + btw/100)`. Standaardwaarden: opslag € 0,016 (gemiddelde van Zonneplan, ANWB Energie en Frank Energie, excl. btw), energiebelasting € 0,09161 (2026, excl. btw) en btw 21%. Zet alles op 0 voor alleen de kale prijs. Let op: de energiebelasting verandert elk jaar per 1 januari.

## API-gebruik

De prijzen worden gecached. De API wordt alleen aangeroepen als de prijzen van vandaag of morgen nog ontbreken (controle elke 30 minuten). De sensorwaarden wisselen elk kwartier zonder extra API-aanroep.

## Voorbeeld: automation op het goedkoopste moment

```yaml
triggers:
  - trigger: time
    at: sensor.jeroen_nl_energieprijzen_goedkoopste_moment_vandaag
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.vaatwasser
```

## Voorbeeld: ApexCharts-kaart

```yaml
type: custom:apexcharts-card
graph_span: 48h
span:
  start: day
series:
  - entity: sensor.jeroen_nl_energieprijzen_huidige_prijs
    type: column
    data_generator: |
      return [...entity.attributes.prices_today, ...entity.attributes.prices_tomorrow]
        .map(p => [new Date(p.start).getTime(), p.price]);
```
