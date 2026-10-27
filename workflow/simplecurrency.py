#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple Currency — conversor de divisas para Alfred (inglés y español).

Acepta códigos ISO (usd, clp) y nombres (yuan, peso chileno, dollar).

    simplecurrency.py "100 yuan"
    simplecurrency.py "1.000.000 clp a dolares"
    simplecurrency.py --mode add ""     # gestor de favoritas
    simplecurrency.py --toggle EUR

Escribe Alfred Script Filter JSON por stdout. Sin dependencias externas:
solo biblioteca estándar de Python 3.
"""
import json
import os
import plistlib
import re
import sys
import time
import unicodedata
from decimal import Decimal, ROUND_HALF_UP, localcontext
from difflib import SequenceMatcher
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "currencies.json")

ICON_INFO = "hints/info.png"
ICON_ERROR = "hints/error.png"
ICON_GEAR = "hints/gear.png"

DEFAULT_FAVORITES = [
    "USD", "EUR", "ARS", "BRL", "GBP", "CNY", "MXN", "PEN", "UYU", "BOB",
]

# Fuentes sin API key, en orden de preferencia
SOURCES = (
    ("open.er-api.com", "https://open.er-api.com/v6/latest/USD"),
    ("currency-api", "https://cdn.jsdelivr.net/npm/@fawazahmed0/"
                     "currency-api@latest/v1/currencies/usd.json"),
)

USER_AGENT = "SimpleCurrency/1.0 (Alfred workflow)"
HTTP_TIMEOUT = 8

EXACT = 850          # a partir de aquí se considera una moneda identificada
MAX_LIST_ITEMS = 40
SEPARATORS = {"a", "al", "en", "to", "hacia", "->", "→", "=>", ">", "="}

NUMBER_RE = re.compile(r"^[+-]?[\d][\d.,]*$")
GLUED_LEFT_RE = re.compile(r"^([+-]?[\d][\d.,]*)([^\d\s.,+\-].*)$")
GLUED_RIGHT_RE = re.compile(r"^(.*?[^\d\s.,+\-])\s*([+-]?[\d][\d.,]*)$")


# --------------------------------------------------------------------------
# idioma
# --------------------------------------------------------------------------
def detect_language():
    """LANGUAGE_UI=auto|es|en, si no, el primer idioma del sistema."""
    forced = os.getenv("LANGUAGE_UI", "auto").strip().lower()[:2]
    if forced in ("es", "en"):
        return forced
    try:
        path = os.path.expanduser("~/Library/Preferences/.GlobalPreferences.plist")
        with open(path, "rb") as handle:
            languages = plistlib.load(handle).get("AppleLanguages") or []
        if languages:
            return "es" if str(languages[0]).lower().startswith("es") else "en"
    except Exception:                                   # noqa: BLE001
        pass
    return "en"


LANGUAGE = detect_language()


def t(key, **values):
    """Traduce una cadena de la interfaz."""
    entry = STRINGS[key]
    text = entry.get(LANGUAGE) or entry["en"]
    return text.format(**values) if values else text


STRINGS = {
    # resultados
    "item_subtitle": {
        "en": "\u21a9 copy {value}   \u2325 expression   \u2318 number",
        "es": "\u21a9 copiar {value}   \u2325 expresión   \u2318 número",
    },
    "copy_expression": {
        "en": "copy \u201c{expr}\u201d",
        "es": "copiar \u00ab{expr}\u00bb",
    },
    "copy_number": {
        "en": "copy the number only, unformatted",
        "es": "copiar sólo el número, sin formato",
    },
    "complete": {
        "en": "\u21e5 complete",
        "es": "\u21e5 completar",
    },
    # estado de las tasas
    "rates_title": {
        "en": "Rates {age} · {count} currencies",
        "es": "Tasas {age} · {count} monedas",
    },
    "rates_sub": {
        "en": "{source} · refresh every {minutes} min",
        "es": "{source} · se actualizan cada {minutes} min",
    },
    "rates_stale_title": {
        "en": "Rates out of date ({age})",
        "es": "Tasas sin actualizar ({age})",
    },
    "rates_stale_sub": {
        "en": "Couldn't refresh · {error}",
        "es": "No pude bajar tasas nuevas · {error}",
    },
    "no_rates_title": {
        "en": "Couldn't fetch exchange rates",
        "es": "No pude obtener las tasas de cambio",
    },
    "no_rates_sub": {
        "en": "{error} · check your connection and try again",
        "es": "{error} · revisa tu internet y reintenta",
    },
    "base_missing_title": {
        "en": "Base currency ({base}) has no exchange rate",
        "es": "La moneda principal ({base}) no tiene tasa disponible",
    },
    "base_missing_sub": {
        "en": "Change it in Configure (Alfred \u2192 Workflows \u2192 Simple Currency)",
        "es": "Cámbiala en Configure (Alfred \u2192 Workflows \u2192 Simple Currency)",
    },
    # errores de consulta
    "unknown_title": {
        "en": "I don't know \u201c{query}\u201d",
        "es": "No conozco \u00ab{query}\u00bb",
    },
    "unknown_guess": {
        "en": "Maybe you meant:",
        "es": "Quizá quisiste decir:",
    },
    "unknown_hint": {
        "en": "Try a code (USD, CLP) or a name (dollar, Chilean peso)",
        "es": "Prueba un código (USD, CLP) o un nombre (dólar, peso chileno)",
    },
    "no_pair_title": {
        "en": "No rates for that combination",
        "es": "Sin tasas para esa combinación",
    },
    "no_pair_sub": {
        "en": "Check your base currency and favourites",
        "es": "Revisa la moneda principal y los favoritos",
    },
    "crash_title": {
        "en": "Simple Currency failed",
        "es": "Simple Currency falló",
    },
    "unknown_currency": {
        "en": "Unknown currency",
        "es": "Moneda desconocida",
    },
    "rates_loading": {
        "en": "downloading rates, try again in a second",
        "es": "descargando tasas, prueba de nuevo en un segundo",
    },
    "offline": {
        "en": "offline",
        "es": "sin conexión",
    },
    # favoritas
    "fav_add": {
        "en": "\u21a9 add to favourites",
        "es": "\u21a9 añadirla a favoritas",
    },
    "fav_remove": {
        "en": "\u21a9 remove from favourites",
        "es": "\u21a9 quitarla de favoritas",
    },
    "fav_added": {
        "en": "{name} added",
        "es": "{name} añadida",
    },
    "fav_removed": {
        "en": "{name} removed",
        "es": "{name} quitada",
    },
    "fav_count_one": {"en": "1 favourite", "es": "1 favorita"},
    "fav_count_many": {"en": "{count} favourites", "es": "{count} favoritas"},
    "fav_empty_title": {
        "en": "No favourites yet",
        "es": "No tienes favoritas guardadas",
    },
    "fav_empty_sub": {
        "en": "Type cur-add to pick the currencies you compare against",
        "es": "Escribe cur-add y elige las monedas a comparar",
    },
    "fav_empty_hint": {
        "en": "Add them with cur-add",
        "es": "Añádelas con cur-add",
    },
    "fav_manage_title": {
        "en": "Add or remove favourites",
        "es": "Añadir o quitar favoritas",
    },
    "fav_manage_sub": {
        "en": "cur-add · comparing against {count} ({names})",
        "es": "cur-add · ahora comparas contra {count} ({names})",
    },
    # edades
    "age_now": {"en": "just now", "es": "recién"},
    "age_min": {"en": "{n} min ago", "es": "hace {n} min"},
    "age_hour": {"en": "{n} h ago", "es": "hace {n} h"},
    "age_day": {"en": "{n} days ago", "es": "hace {n} días"},
    # ayuda
    "help_footer_title": {
        "en": "\u21a9 copies the result · \u2325 the expression · \u2318 the number",
        "es": "\u21a9 copia el resultado · \u2325 la expresión · \u2318 el número",
    },
    "help_footer_sub": {
        "en": "Configure: Alfred \u2192 Workflows \u2192 Simple Currency",
        "es": "Configure: Alfred \u2192 Workflows \u2192 Simple Currency",
    },
}

HELP_EXAMPLES = {
    "en": [
        ("cur", "Your favourites against the base currency"),
        ("cur 100 usd", "100 US dollars to your base currency"),
        ("cur 100 yuan", "by name — no codes, no accents"),
        ("cur 100 pesos chilenos", "plurals and multi-word names"),
        ("cur 1.000.000 clp a dolares", "«a», «en» or «to» set the direction"),
        ("cur usd yuan", "between two currencies, both ways"),
        ("cur uf", "Chilean Unidad de Fomento"),
        ("cur peso", "ambiguous names show a picker"),
        ("cur-add", "pick the favourites you compare against"),
        ("cur-rm", "remove favourites"),
    ],
    "es": [
        ("cur", "Tus favoritas contra la moneda principal"),
        ("cur 100 usd", "100 dólares a tu moneda principal"),
        ("cur 100 yuan", "por nombre, sin códigos ni tildes"),
        ("cur 100 pesos chilenos", "plurales y nombres compuestos"),
        ("cur 1.000.000 clp a dolares", "con «a» o «en» fijas la dirección"),
        ("cur usd yuan", "entre dos monedas, ambas direcciones"),
        ("cur uf", "unidad de fomento chilena"),
        ("cur peso", "si hay varias, te deja elegir"),
        ("cur-add", "elegir las favoritas que se comparan por defecto"),
        ("cur-rm", "quitar favoritas"),
    ],
}


# --------------------------------------------------------------------------
# utilidades de texto
# --------------------------------------------------------------------------
def normalize(text):
    """Minúsculas, sin tildes, sin puntuación: 'Dólar EE.UU.' -> 'dolar ee uu'"""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = stripped.lower().replace("’", "'").replace("´", "'")
    stripped = re.sub(r"[^a-z0-9]+", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def plural_forms(name):
    """Plurales en inglés y español: 'peso chileno' -> 'pesos chilenos',
    'us dollar' -> 'us dollars'."""
    words = name.split()
    if not words:
        return []

    def plural(word):
        if len(word) < 3 or not word.isalpha():
            return []
        if word.endswith("z"):
            return [word + "es", word[:-1] + "ces"]
        if word.endswith("s"):
            return [word]
        if word.endswith(("a", "e", "i", "o", "u")):
            return [word + "s"]
        return [word + "s", word + "es"]

    forms = set()
    if len(words) == 1:
        forms.update(plural(words[0]))
    else:
        for head in [words[0]] + plural(words[0]):
            for tail in [words[-1]] + plural(words[-1]):
                forms.add(f"{head} {tail}")
    forms.discard(name)
    return [normalize(form) for form in forms if form]


# --------------------------------------------------------------------------
# carga de datos
# --------------------------------------------------------------------------
def load_currencies():
    with open(DATA_FILE, encoding="utf-8") as handle:
        return json.load(handle)["currencies"]


CURRENCIES = load_currencies()


def display_name(code):
    """Nombre de la moneda en el idioma activo."""
    info = CURRENCIES.get(code) or {}
    if LANGUAGE == "en":
        return info.get("name_en") or info.get("name") or code
    return info.get("name") or info.get("name_en") or code


def decimals_for(code):
    precision = os.getenv("PRECISION", "auto").strip().lower()
    if precision not in ("", "auto"):
        try:
            return max(0, min(int(precision), 10))
        except ValueError:
            pass
    return int(CURRENCIES.get(code, {}).get("decimals", 2))


# --------------------------------------------------------------------------
# índice de búsqueda
# --------------------------------------------------------------------------
class Index:
    """Términos por moneda con puntaje base: código > alias > nombre."""

    def __init__(self):
        self.terms = {}
        for code, info in CURRENCIES.items():
            weighted = [(normalize(code), 1000)]
            for alias in info.get("alias", []):
                alias = normalize(alias)
                weighted.append((alias, 880))
                weighted.extend((form, 878) for form in plural_forms(alias))
            for key, weight in (("name", 900), ("name_en", 840)):
                value = normalize(info.get(key, ""))
                if not value:
                    continue
                weighted.append((value, weight))
                weighted.extend((form, weight - 2) for form in plural_forms(value))
            best = {}
            for term, weight in weighted:
                if term and weight > best.get(term, 0):
                    best[term] = weight
            self.terms[code] = sorted(best.items(), key=lambda kv: -kv[1])
        self._add_user_aliases()

    def _add_user_aliases(self):
        """Alias propios: variable ALIASES = "lucas=CLP, verde=USD"."""
        for chunk in re.split(r"[;,]", os.getenv("ALIASES", "")):
            if "=" not in chunk:
                continue
            alias, _, code = chunk.partition("=")
            code = code.strip().upper()
            alias = normalize(alias)
            if alias and code in CURRENCIES:
                self.terms[code] = [(alias, 1010)] + [
                    (term, weight) for term, weight in self.terms[code]
                    if term != alias
                ]

    def match(self, query):
        """Devuelve {code: score} según código, alias, nombre y plurales."""
        query = normalize(query)
        if not query:
            return {}
        hits = {}
        for code, terms in self.terms.items():
            best = 0
            for term, weight in terms:
                if term == query:
                    score = weight
                elif term.startswith(query):
                    score = weight - 150 - min(len(term) - len(query), 80)
                elif len(query) >= 2 and any(word.startswith(query)
                                             for word in term.split()):
                    score = weight - 270
                elif len(query) >= 3 and query in term:
                    score = weight - 520
                else:
                    continue
                if score > best:
                    best = score
            if best > 0:
                hits[code] = best
        return hits


INDEX = Index()
POPULAR_ORDER = set(DEFAULT_FAVORITES)


# --------------------------------------------------------------------------
# favoritas persistentes
# --------------------------------------------------------------------------
def data_dir():
    path = os.getenv("alfred_workflow_data") or os.path.join(
        os.path.expanduser("~"), ".cache", "coinc-es"
    )
    os.makedirs(path, exist_ok=True)
    return path


def favorites_file():
    return os.path.join(data_dir(), "favorites.json")


def read_favorite_delta():
    """Cambios guardados desde cur-add / cur-rm: {"added": [...], "removed": [...]}"""
    try:
        with open(favorites_file(), encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:                                   # noqa: BLE001
        return {"added": [], "removed": []}
    added = [c for c in payload.get("added", []) if c in CURRENCIES]
    removed = [c for c in payload.get("removed", []) if c in CURRENCIES]
    return {"added": added, "removed": removed}


def write_favorite_delta(delta):
    try:
        with open(favorites_file(), "w", encoding="utf-8") as handle:
            json.dump(delta, handle)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# configuración
# --------------------------------------------------------------------------
class Config:
    def __init__(self):
        self.base = self._base()
        self.delta = read_favorite_delta()
        self.favorites = self._favorites()
        self.orientation = os.getenv("ORIENTATION", "DEFAULT").strip().upper()
        if self.orientation not in ("DEFAULT", "FROM_FAV", "TO_FAV"):
            self.orientation = "DEFAULT"
        # al escribir una moneda: comparar contra la base + todas las favoritas
        self.compare_favorites = \
            os.getenv("COMPARE", "FAVORITES").strip().upper() != "BASE"
        try:
            self.expire = int(os.getenv("EXPIRE", "3600"))
        except ValueError:
            self.expire = 3600

    @staticmethod
    def _base():
        raw = os.getenv("BASE", "CLP").strip().upper()
        # se acepta cualquier código: si la fuente no lo trae, main() avisa
        return raw if re.fullmatch(r"[A-Z0-9]{2,4}", raw) else "CLP"

    def _favorites(self):
        """Favoritas = lista de Configure + las añadidas − las quitadas."""
        raw = os.getenv("FAVORITES", "")
        declared = [c.strip().upper() for c in re.split(r"[,\s;]+", raw) if c.strip()]
        declared = [c for c in declared if c in CURRENCIES]
        removed = set(self.delta["removed"])
        if not declared:
            # Configure en blanco: partir de una lista razonable
            declared = list(DEFAULT_FAVORITES)
        codes = [c for c in declared if c not in removed]
        for code in self.delta["added"]:
            if code not in codes and code not in removed:
                codes.append(code)
        codes = [c for c in codes if c != self.base]
        unique = []
        for code in codes:
            if code not in unique:
                unique.append(code)
        return unique

    def toggle(self, code, add=True):
        delta = read_favorite_delta()
        added, removed = delta["added"], delta["removed"]
        if add:
            if code in removed:
                removed.remove(code)
            if code not in added:
                added.append(code)
            message = t("fav_added", name=display_name(code))
        else:
            if code in added:
                added.remove(code)
            if code not in removed:
                removed.append(code)
            message = t("fav_removed", name=display_name(code))
        write_favorite_delta({"added": added, "removed": removed})
        self.delta = {"added": added, "removed": removed}
        self.favorites = self._favorites()
        count = len(self.favorites)
        if count == 1:
            tail = t("fav_count_one")
        else:
            tail = t("fav_count_many", count=count)
        return f"{message} · {tail}"


# --------------------------------------------------------------------------
# montos
# --------------------------------------------------------------------------
def parse_amount(text):
    """'1.000.000' -> 1000000 ; '1,5' -> 1.5 ; '1,234.56' -> 1234.56"""
    text = text.strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") == 1:
        head, _, tail = text.partition(",")
        # 1,000 son mil; 1,5 es uno con cinco
        if len(tail) == 3 and head.lstrip("+-"):
            text = head + tail
        else:
            text = head + "." + tail
    elif text.count(",") > 1:
        text = text.replace(",", "")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    else:
        head, _, tail = text.partition(".")
        if len(tail) == 3 and head.lstrip("+-"):
            text = head + tail
    try:
        return Decimal(text)
    except Exception:                                   # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# tasas de cambio
# --------------------------------------------------------------------------
CACHE_FILE = os.path.join(data_dir(), "rates.json")
LOCK_FILE = os.path.join(data_dir(), "rates.lock")


def _fetch(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=HTTP_TIMEOUT) as response:
        payload = json.load(response)
    if isinstance(payload.get("rates"), dict):           # open.er-api.com
        rates = payload["rates"]
    else:                                                # currency-api (base usd)
        raw = payload.get("usd") or {}
        rates = {k: v for k, v in raw.items() if isinstance(v, (int, float))}
    normalized = {str(k).upper(): float(v) for k, v in rates.items()
                  if isinstance(v, (int, float)) and v}
    if len(normalized) < 20:
        raise ValueError("respuesta incompleta")
    normalized.setdefault("USD", 1.0)
    return normalized


def fetch_rates():
    last_error = t("offline")
    for name, url in SOURCES:
        try:
            return _fetch(url), name
        except Exception as exc:                        # noqa: BLE001
            last_error = f"{name}: {type(exc).__name__}"
    return None, last_error


def read_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("rates"):
            return payload
    except Exception:                                   # noqa: BLE001
        pass
    return None


def lock_is_fresh():
    try:
        return (time.time() - os.path.getmtime(LOCK_FILE)) < 20
    except OSError:
        return False


def get_rates(config):
    """Devuelve (rates, fuente, fetched_at, error_de_red)."""
    cache = read_cache()
    if cache and (time.time() - cache.get("fetched_at", 0)) < config.expire:
        return cache["rates"], cache.get("source", "?"), cache["fetched_at"], None
    if lock_is_fresh():
        if cache:
            return cache["rates"], cache.get("source", "?"), \
                cache.get("fetched_at", 0), None
        return None, None, 0, t("rates_loading")
    try:
        with open(LOCK_FILE, "w") as handle:
            handle.write(str(os.getpid()))
        fresh, source = fetch_rates()
        if fresh:
            payload = {"fetched_at": time.time(), "source": source, "rates": fresh}
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
            except OSError:
                pass
            return fresh, source, payload["fetched_at"], None
        if cache:
            return cache["rates"], cache.get("source", "?"), \
                cache.get("fetched_at", 0), source
        return None, None, 0, source
    finally:
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


# --------------------------------------------------------------------------
# formato
# --------------------------------------------------------------------------
def format_number(value, decimals):
    with localcontext() as ctx:
        ctx.prec = 60
        quantized = value.quantize(Decimal(1).scaleb(-decimals),
                                   rounding=ROUND_HALF_UP)
    text = f"{quantized:,.{decimals}f}"
    if LANGUAGE == "en":
        return text
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_result(value, code):
    decimals = decimals_for(code)
    if value != 0 and abs(value) < Decimal(1).scaleb(-decimals):
        # dos cifras significativas cuando el monto es más chico que un centavo
        decimals = min(max(abs(value.adjusted()) + 1, decimals), 10)
    return format_number(value, decimals)


def format_amount(value):
    """Monto escrito por el usuario, sin ceros de relleno."""
    text = format_number(value, 6)
    separator = "." if LANGUAGE == "en" else ","
    if separator in text:
        text = text.rstrip("0").rstrip(separator)
    return text or "0"


def plain_number(value, code):
    """Número crudo para pegar en una planilla: 1054.32"""
    decimals = decimals_for(code)
    if value != 0 and abs(value) < Decimal(1).scaleb(-decimals):
        decimals = min(max(abs(value.adjusted()) + 1, decimals), 10)
    text = format_number(value, decimals)
    if LANGUAGE == "en":
        return text.replace(",", "")
    return text.replace(".", "").replace(",", ".")


def human_age(seconds):
    seconds = max(0, int(seconds))
    if seconds < 90:
        return t("age_now")
    if seconds < 3600:
        return t("age_min", n=seconds // 60)
    if seconds < 86400:
        return t("age_hour", n=seconds // 3600)
    return t("age_day", n=seconds // 86400)


# --------------------------------------------------------------------------
# Alfred
# --------------------------------------------------------------------------
def item(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}


def emit(items):
    sys.stdout.write(json.dumps({"items": items}, ensure_ascii=False))
    sys.stdout.flush()


def error_item(title, subtitle, icon=ICON_ERROR):
    return [item(title=title, subtitle=subtitle, icon={"path": icon}, valid=False)]


def flag_icon(code):
    path = os.path.join(HERE, "flags", f"{code}.png")
    return {"path": path if os.path.exists(path)
            else os.path.join(HERE, "icon.png")}


def conversion_item(value, source_code, target_code, rates):
    with localcontext() as ctx:
        ctx.prec = 60
        result = value * Decimal(str(rates[target_code])) / Decimal(
            str(rates[source_code])
        )
    source_text = format_amount(value)
    result_text = format_result(result, target_code)
    expression = f"{source_text} {source_code} = {result_text} {target_code}"
    copy_value = f"{result_text} {target_code}"
    return item(
        uid=f"simple-currency-{source_code}-{target_code}",
        title=expression,
        subtitle=t("item_subtitle", value=copy_value),
        arg=copy_value,
        text={"copy": copy_value, "largetype": expression},
        icon=flag_icon(target_code),
        mods={
            "alt": {"arg": expression,
                    "subtitle": t("copy_expression", expr=expression)},
            "cmd": {"arg": plain_number(result, target_code),
                    "subtitle": t("copy_number")},
        },
    )


def picker_items(hits, amount=None, config=None):
    """Lista para elegir moneda; ⇥ completa la consulta con el código."""
    base = config.base if config else None
    favorites = set(config.favorites) if config else set()

    def rank(entry):
        code, score = entry
        boost = 2 if code == base else 1 if code in favorites else 0
        return (-boost, -score, display_name(code))

    ordered = sorted(hits.items(), key=rank)
    prefix = f"{format_amount(amount)} " if amount is not None else ""
    items = []
    for code, _score in ordered[:MAX_LIST_ITEMS]:
        symbol = CURRENCIES[code].get("symbol") or code
        items.append(item(
            uid=f"simple-currency-pick-{code}",
            title=f"{display_name(code)}  ({code})",
            subtitle=f"{t('complete')}   ·   {symbol}",
            autocomplete=f"{prefix}{code}",
            valid=False,
            icon=flag_icon(code),
        ))
    return items


def info_rows(rates, source, fetched_at, stale_error, expire):
    age = human_age(time.time() - fetched_at) if fetched_at else "—"
    if stale_error:
        return [item(
            title=t("rates_stale_title", age=age),
            subtitle=t("rates_stale_sub", error=stale_error),
            icon={"path": ICON_ERROR}, valid=False,
        )]
    minutes = max(1, int(expire) // 60)
    return [item(
        title=t("rates_title", age=age, count=len(rates)),
        subtitle=t("rates_sub", source=source, minutes=minutes),
        icon={"path": ICON_INFO}, valid=False,
    )]


# --------------------------------------------------------------------------
# parseo de la consulta
# --------------------------------------------------------------------------
def extract_amount(token):
    """Token aislado -> (monto, palabra). Acepta 100usd y usd100."""
    if NUMBER_RE.match(token):
        return parse_amount(token), ""
    glued = GLUED_LEFT_RE.match(token)
    if glued:
        return parse_amount(glued.group(1)), glued.group(2)
    glued = GLUED_RIGHT_RE.match(token)
    if glued:
        return parse_amount(glued.group(2)), glued.group(1)
    return None, token


def tokenize(raw):
    """-> (monto, texto izquierda, texto derecha, monto_pegado_a_moneda)"""
    amount = None
    glued = False
    left, right = [], []
    side = left
    for token in re.findall(r"->|=>|→|>|=|\S+", raw or ""):
        if token.lower() in SEPARATORS:
            side = right
            continue
        token_amount, word = extract_amount(token)
        if token_amount is not None and amount is None:
            amount = token_amount
            if not word:
                continue
            glued = True
        if word:
            side.append(word)
    return amount, " ".join(left).strip(), " ".join(right).strip(), glued


def candidates(text):
    """(código, exacto, hits): código sólo si hay un ganador claro."""
    hits = INDEX.match(text)
    if not hits:
        return None, False, {}
    top = max(hits.values())
    winners = [code for code, score in hits.items() if score >= top - 5]
    if len(winners) == 1:
        code = winners[0]
        return code, (top >= EXACT or len(hits) == 1), hits
    return None, False, hits


def choose(text, config):
    """Como candidates(); el empate («peso») queda para que el usuario elija."""
    return candidates(text)


def split_pair(text, config):
    """Dos monedas dentro de un texto sin separador: 'dolar yuan'."""
    words = text.split()
    for cut in range(1, len(words)):
        first, first_exact, _ = choose(" ".join(words[:cut]), config)
        second, second_exact, _ = choose(" ".join(words[cut:]), config)
        if first and second and first_exact and second_exact and first != second:
            return first, second
    return None


def parse_query(raw, config):
    """Devuelve dict con monto, monedas, swap, binding y modo."""
    result = {"amount": None, "codes": [], "swap": False, "binding": False,
              "free": "", "mode": "convert"}
    if not (raw or "").strip():
        return result

    amount, left, right, glued = tokenize(raw)
    result["amount"] = amount
    result["binding"] = glued
    # «100 a yuan» = monto en la moneda base, destino yuan
    swap = bool(right) and not left and amount is not None

    if left and right:
        first, first_exact, _ = choose(left, config)
        second, second_exact, _ = choose(right, config)
        if first and second and first_exact and second_exact and first != second:
            result["codes"] = [first, second]
            return result
        if second and second_exact and not (first and first_exact):
            result.update(codes=[second], swap=True)
            return result
        if first and first_exact:
            result.update(codes=[first])
            return result

    text = " ".join(part for part in (left, right) if part)
    if not text:
        return result

    code, exact, hits = choose(text, config)
    if code and exact:
        result.update(codes=[code], swap=swap)
        return result

    pair = split_pair(text, config)
    if pair:
        result["codes"] = list(pair)
        return result

    if hits:
        result.update(mode="pick", free=text)
        return result

    target = normalize(text)
    suggestions = {}
    for code, info in CURRENCIES.items():
        for term in (normalize(info.get("name", "")),
                     normalize(info.get("name_en", "")), normalize(code)):
            if not term:
                continue
            ratio = SequenceMatcher(None, target, term).ratio()
            if ratio > 0.75:
                suggestions[code] = max(suggestions.get(code, 0), ratio * 100)
    result.update(mode="none", free=text)
    result["suggestions"] = suggestions
    return result


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------
def build_pairs(parsed, config):
    """Lista de (monto, origen, destino) siguiendo los patrones de Coinc (MIT)."""
    value = parsed["amount"] if parsed["amount"] is not None else Decimal(1)
    codes = parsed["codes"]
    base = config.base
    pairs = []

    if not codes:
        for code in config.favorites:
            if config.orientation in ("DEFAULT", "FROM_FAV"):
                pairs.append((value, code, base))
            if config.orientation in ("DEFAULT", "TO_FAV"):
                pairs.append((value, base, code))
        return pairs

    if len(codes) == 1:
        code = codes[0]
        if code == base:
            for other in config.favorites:
                pairs.append((value, base, other))
                pairs.append((value, other, base))
            return pairs
        origin = base if parsed["swap"] else code
        first = (value, origin, code if parsed["swap"] else base)
        pairs.append(first)
        if config.compare_favorites:
            # la moneda ingresada, vista en todas las favoritas
            for other in config.favorites:
                if other not in (origin, first[2]):
                    pairs.append((value, origin, other))
        if not parsed["binding"]:
            pairs.append((value, first[2], first[1]))
        return pairs

    first_code, second_code = codes[0], codes[1]
    pairs.append((value, first_code, second_code))
    if not parsed["binding"]:
        pairs.append((value, second_code, first_code))
    return pairs


def render_favorites(query, config, mode):
    """Lista para añadir (mode 'add') o quitar (mode 'rm') favoritas."""
    if mode == "rm":
        pool = list(config.favorites)
        if not pool:
            return error_item(t("fav_empty_title"), t("fav_empty_hint"))
    else:
        pool = list(CURRENCIES)

    hits = INDEX.match(query) if query else {}
    if query and not hits:
        return error_item(t("unknown_title", query=query), t("unknown_hint"))
    if hits:
        ordered = [c for c in hits if c in pool]
        ordered.sort(key=lambda c: -hits[c])
    else:
        ordered = sorted(
            pool,
            key=lambda c: (c not in config.favorites,
                           c not in POPULAR_ORDER,
                           display_name(c)),
        )

    items = []
    for code in ordered[:MAX_LIST_ITEMS]:
        is_favorite = code in config.favorites
        title = f"{display_name(code)}  ({code})"
        if is_favorite:
            title = f"✓ {title}"
        items.append(item(
            uid=f"simple-currency-fav-{code}",
            title=title,
            subtitle=t("fav_remove") if (is_favorite or mode == "rm")
            else t("fav_add"),
            arg=code,
            valid=True,
            icon=flag_icon(code),
            text={"copy": code,
                  "largetype": f"{display_name(code)} ({code})"},
        ))
    return items


def render_help():
    items = [
        item(uid=f"help-{example}", title=example, subtitle=subtitle,
             arg=example, text={"copy": example},
             icon={"path": ICON_GEAR}, valid=True)
        for example, subtitle in HELP_EXAMPLES[LANGUAGE]
    ]
    items.append(item(
        title=t("help_footer_title"),
        subtitle=t("help_footer_sub"),
        icon={"path": ICON_INFO}, valid=False,
    ))
    return items


def main():
    args = sys.argv[1:]
    mode = "convert"
    if len(args) > 1 and args[0] == "--mode":
        mode = args[1]
        query = " ".join(args[2:]).strip()
    elif args and args[0] in ("--toggle", "--remove"):
        code = (args[1] if len(args) > 1 else "").strip().upper()
        if code not in CURRENCIES:
            sys.stdout.write(t("unknown_currency"))
            return
        sys.stdout.write(Config().toggle(code, add=args[0] == "--toggle"))
        return
    else:
        query = " ".join(args).strip()

    if mode == "convert" and query in ("-h", "--help", "help", "ayuda"):
        emit(render_help())
        return

    config = Config()

    if mode in ("add", "rm"):
        emit(render_favorites(query, config, mode))
        return

    rates, source, fetched_at, stale_error = get_rates(config)
    if not rates:
        emit(error_item(t("no_rates_title"),
                        t("no_rates_sub", error=stale_error or "—")))
        return

    if config.base not in rates:
        emit(error_item(t("base_missing_title", base=config.base),
                        t("base_missing_sub")))
        return

    parsed = parse_query(query, config)

    if parsed["mode"] == "pick":
        hits = INDEX.match(parsed["free"])
        if len(hits) == 1:
            parsed.update(mode="convert", codes=[next(iter(hits))])
        else:
            emit(picker_items(hits, parsed["amount"], config)
                 + info_rows(rates, source, fetched_at, stale_error, config.expire))
            return

    if parsed["mode"] == "none":
        suggestions = parsed.get("suggestions") or {}
        if suggestions:
            best = dict(sorted(suggestions.items(), key=lambda kv: -kv[1])[:6])
            items = [item(
                title=t("unknown_title", query=parsed["free"]),
                subtitle=t("unknown_guess"),
                icon={"path": ICON_ERROR}, valid=False,
            )]
            items += picker_items(best, parsed["amount"], config)
        else:
            items = error_item(t("unknown_title", query=parsed["free"]),
                               t("unknown_hint"))
        emit(items + info_rows(rates, source, fetched_at, stale_error,
                               config.expire))
        return

    items = [conversion_item(value, origin, target, rates)
             for value, origin, target in build_pairs(parsed, config)
             if origin in rates and target in rates]

    if not parsed["codes"] and parsed["amount"] is None:
        if not config.favorites:
            items.insert(0, item(
                title=t("fav_empty_title"),
                subtitle=t("fav_empty_sub"),
                icon={"path": ICON_GEAR}, valid=False,
            ))
        else:
            shown = ", ".join(config.favorites[:6])
            if len(config.favorites) > 6:
                shown += "…"
            items.append(item(
                title=t("fav_manage_title"),
                subtitle=t("fav_manage_sub", count=len(config.favorites),
                           names=shown),
                icon={"path": ICON_GEAR}, valid=False,
            ))

    if not items:
        if not config.favorites:
            emit(error_item(t("fav_empty_title"), t("fav_empty_sub")))
        else:
            emit(error_item(t("no_pair_title"), t("no_pair_sub")))
        return
    emit(items + info_rows(rates, source, fetched_at, stale_error,
                           config.expire))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
    except Exception as exc:                            # noqa: BLE001
        try:
            emit(error_item(t("crash_title"), f"{type(exc).__name__}: {exc}"))
        except BrokenPipeError:
            pass
