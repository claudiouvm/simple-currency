# Simple Currency

An [Alfred](https://www.alfredapp.com/) workflow to convert currencies **by ISO
code or by name**, in **English and Spanish**. No API key, no dependencies
beyond the Python 3 that ships with macOS.

```
cur 100 yuan                →  100 CNY = 14,900 CLP
cur 100 dollars             →  100 USD = 99,585 CLP
cur 1,000,000 clp a dolares →  1,000,000 CLP = 1,004.17 USD
cur usd yuan                →  1 USD = 6.68 CNY
cur peso                    →  picker: Chilean, Argentine, Mexican…
```

## Why another currency converter

Most converters (including the excellent [Coinc](https://github.com/tomy0000000/Coinc),
which this project started from) only understand ISO codes: `usd`, `gbp`, `jpy`.
You have to remember the code, or register an alias first.

Simple Currency resolves **names** directly, in both languages, with or without
accents, singular or plural, and multi-word:

| You type | It resolves to |
| --- | --- |
| `yuan`, `renminbi`, `yuan chino` | CNY |
| `dollar`, `dollars`, `bucks` | USD |
| `peso chileno`, `pesos chilenos`, `chilean pesos` | CLP |
| `corona sueca`, `swedish krona` | SEK |
| `franco suizo`, `swiss franc` | CHF |
| `uf` | CLF (Chilean Unidad de Fomento) |
| `quid`, `libra`, `sterling` | GBP |

When a name is genuinely ambiguous — `peso`, `corona`, `dollar`, `franc` — it
shows a picker with your base currency and favourites first, and `⇥` completes
the query with the ISO code.

## Usage

| Query | Result |
| --- | --- |
| `cur` | your favourites against the base currency |
| `cur 100` | the same, with an amount |
| `cur 100 usd` | 100 USD → base currency, and back |
| `cur usd yuan` | between two currencies, both directions |
| `cur 100 yuan` | 100 CNY, one currency only |
| `cur 1.000.000 clp a dolares` | explicit direction (`a`, `en`, `to`, `>`, `=`) |
| `cur 100usd` | amount glued to the code |
| `cur peso` | ambiguous names show a picker |
| `cur-add` / `cur-rm` | add or remove favourites |
| `cur-help` | every example |

Each result:

- `↩` copies the result with its code (`1,004.17 USD`)
- `⌥` copies the whole expression (`1,000,000 CLP = 1,004.17 USD`)
- `⌘` copies the number only, unformatted (`1004.17`)
- `⌘L` shows it in Large Type

Keywords: `cur`, `cambio` (Spanish), `cur-add`, `cur-rm`, `cur-help`.

## Favourites

`cur-add` opens the full currency list with a ✓ on the ones you already follow;
`↩` toggles them, with a notification and a running count. `cur-rm` lists only
your current favourites. They are stored in Alfred's workflow data folder, so no
variable editing is needed, and they combine with the `FAVORITES` setting in
Configure:

```
favourites = (configured list − removed) + added
```

Once you type a currency, it is compared against the base **and** every
favourite:

```
cur 100 usd
  100 USD = 99,585 CLP
  100 USD = 89.39 EUR
  100 USD = 154,047.51 ARS
  ...
  100 CLP = 0.10 USD
```

Set `COMPARE` to *base only* in Configure for the classic two-row behaviour.

## Languages

The interface follows your macOS language (English or Spanish) and can be forced
in Configure → *Interface language*. That covers the strings **and** number
formatting — `1,054.32` in English, `1.054,32` in Spanish. Currency names are
always searchable in both languages, regardless of the interface language.

## Install

Download `SimpleCurrency.alfredworkflow` from the [latest release](../../releases/latest)
and double-click it.

Or build from source:

```bash
python3 build/make.py            # regenerates resources and packages the workflow
open SimpleCurrency.alfredworkflow
```

Requires **Alfred 5 with the Powerpack** and **Python 3**. The workflow looks for
`/usr/bin/python3` (Command Line Tools), then Homebrew's `python3`, and shows a
clear message instead of triggering the Xcode installer if neither exists.

## Configuration

Alfred → Workflows → Simple Currency → Configure:

| Variable | Default | What it does |
| --- | --- | --- |
| `LANGUAGE_UI` | auto | interface language: auto / en / es |
| `BASE` | `CLP` | base currency, everything compares against it |
| `FAVORITES` | 10 currencies | starting favourites (manage them with `cur-add`) |
| `COMPARE` | favourites | when you type a currency, compare against favourites or the base only |
| `ORIENTATION` | both ways | direction of the default list |
| `PRECISION` | automatic | decimals: each currency's own (CLP 0, USD 2) or fixed |
| `EXPIRE` | 1 hour | how often rates are refreshed |
| `ALIASES` | empty | your own aliases: `lucas=CLP, verde=USD` |

## How it works

```
workflow/simplecurrency.py   query parser, i18n and Alfred JSON (stdlib only)
workflow/currencies.json     166 currencies: es/en names, symbol, decimals, flag, aliases
workflow/info.plist          the workflow itself
build/currency_data.py       the editable currency table
build/make.py                regenerates resources and packages the .alfredworkflow
build/smoke.sh               23-query smoke test
assets/                      flag icons and hint icons
vendor/                      English currency names used as a secondary search term
```

Search normalises the query (lowercase, accents stripped, punctuation removed)
and matches it against codes, aliases, Spanish and English names, and plurals
generated with both languages' rules. An exact match converts; an ambiguous
prefix shows the picker. Conversion patterns (amount / one currency / two
currencies) follow Coinc's.

## Data & privacy

Rates come from [open.er-api.com](https://www.exchangerate-api.com/docs/free)
(no key, daily update), with
[`currency-api`](https://github.com/fawazahmed0/currency-api) as a fallback, and
are cached on disk for an hour in Alfred's workflow data folder. Nothing else
leaves your Mac, and the workflow never downloads or installs software.

## Credits

- Started from [Coinc](https://github.com/tomy0000000/Coinc) by Tomy Hsieh (MIT):
  same conversion patterns, and the circular flag icons come from that project.
- Eight missing flags (FOK, KID, SHP, SLE, TVD, XCG, XPF, ZWG) from
  [flagcdn](https://flagcdn.com).
- English currency names from
  [@fawazahmed0/currency-api](https://github.com/fawazahmed0/currency-api) (MIT).

## License

MIT — see [LICENSE](LICENSE). Portions © 2019 Tomy Hsieh (Coinc).

---

## Español

Workflow de Alfred para convertir divisas **por código o por nombre**, en inglés y
español, sin clave de API.

```
cur                     tus favoritas contra la moneda principal
cur 100 usd             100 dólares a la moneda principal
cur 100 yuan            por nombre, sin códigos ni tildes
cur 1.000.000 clp a dolares    con «a» o «en» fijas la dirección
cur usd yuan            entre dos monedas, ambas direcciones
cur peso                si hay varias, te deja elegir (⇥ completa)
cur-add / cur-rm        elegir las favoritas contra las que se compara
cur-help                todos los ejemplos
```

`↩` copia el resultado, `⌥` la expresión completa y `⌘` sólo el número. La
interfaz sigue el idioma de macOS y se puede forzar en Configure. Los nombres se
entienden con o sin tilde, en singular o plural: dólar, pesos chilenos, corona
sueca, franco suizo, uf.

Instalación: descarga el `.alfredworkflow` de la última release y ábrelo. Requiere
Alfred 5 con Powerpack y Python 3.
