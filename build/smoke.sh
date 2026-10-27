#!/usr/bin/env bash
# Prueba de humo: corre el script como lo haría Alfred y muestra los resultados.
cd "$(dirname "$0")/../workflow" || exit 1
export BASE="${BASE:-CLP}"
export FAVORITES="USD,EUR,ARS,BRL,GBP,CNY,MXN,PEN,UYU,BOB"
export ORIENTATION="${ORIENTATION:-DEFAULT}"
export PRECISION="${PRECISION:-auto}"
export EXPIRE=3600
export ALIASES="${ALIASES:-lucas=CLP, verde=USD}"
export alfred_workflow_data="/tmp/simple-currency-test"

PRINTER=$(mktemp -t coincprinter)
cat > "$PRINTER" <<'PY'
import json
import sys

payload = json.load(sys.stdin)
items = payload.get("items") or []
if not items:
    print("  (vacío)")
for entry in items[:8]:
    print("  " + entry.get("title", ""))
    if entry.get("subtitle"):
        print("      " + entry["subtitle"])
    if entry.get("autocomplete"):
        print("      ⇥ " + entry["autocomplete"])
if len(items) > 8:
    print("  … %d ítems" % len(items))
PY

for query in "" "100" "usd" "100 usd" "yuan" "100 yuan" "peso" "peso mexicano" \
             "100 pesos chilenos a dolares" "1.000.000 clp a dolares" "dolar" \
             "dolares" "uf" "usd yuan" "100usd" "100 a yuan" "sol" "libra" \
             "euro" "5 lucas" "pes" "xyz" "btc"; do
  printf '\n\033[1m» cur %s\033[0m\n' "$query"
  /usr/bin/python3 ./simplecurrency.py "$query" | /usr/bin/python3 "$PRINTER"
done

rm -f "$PRINTER"
