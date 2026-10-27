#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera y empaqueta el workflow Simple Currency.

    python3 build/make.py            # recursos + .alfredworkflow
    python3 build/make.py --no-icon  # salta el icono (requiere Pillow)

Fuentes de datos:
  - Nombres ES / símbolos / banderas : build/currency_data.py
  - Nombres EN (búsqueda alternativa): vendor/currency_names.json
  - Banderas PNG                     : assets/flags (MIT, ver CREDITS.md)
"""
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from currency_data import CURRENCIES, POPULAR, SPECIAL_DECIMALS, ZERO_DECIMAL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, "workflow")
ASSETS = os.path.join(ROOT, "assets")
VENDOR = os.path.join(ROOT, "vendor")
OUTPUT = os.path.join(ROOT, "SimpleCurrency.alfredworkflow")

SETTINGS = {
    "BASE": "CLP",
    "FAVORITES": "USD,EUR,ARS,BRL,GBP,CNY,MXN,PEN,UYU,BOB",
    "ORIENTATION": "DEFAULT",
    "COMPARE": "FAVORITES",
    "LANGUAGE_UI": "auto",
    "PRECISION": "auto",
    "EXPIRE": "3600",
    "ALIASES": "",
}


# --------------------------------------------------------------------------
# datos
# --------------------------------------------------------------------------
# Banderas que no vienen en el set de Coinc: código ISO -> país de flagcdn
FALLBACK_FLAGS = {
    "FOK": "fo", "KID": "ki", "SHP": "sh", "SLE": "sl",
    "TVD": "tv", "XCG": "cw", "XPF": "pf", "ZWG": "zw",
}
FLAG_URL = "https://flagcdn.com/w640/{}.png"


def circleize(source, destination, size=512):
    """Recorta a cuadrado y aplica máscara circular, como el set original."""
    from PIL import Image, ImageDraw

    image = Image.open(source).convert("RGB")
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(image, (0, 0), mask)
    canvas.save(destination, "PNG")


def letter_flag(destination, code, size=512):
    """Último recurso si no hay bandera: iniciales sobre un círculo."""
    from PIL import Image, ImageDraw, ImageFont

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, size - 1, size - 1), fill=(38, 62, 84, 255))
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Futura.ttc", 150
        )
    except OSError:
        font = ImageFont.load_default()
    text = code[:3]
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((size - (box[2] - box[0])) / 2 - box[0],
               (size - (box[3] - box[1])) / 2 - box[1]),
              text, font=font, fill=(255, 255, 255, 235))
    canvas.save(destination, "PNG")


def english_names():
    path = os.path.join(VENDOR, "currency_names.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    return {code.upper(): name for code, name in raw.items()
            if isinstance(name, str) and len(code) <= 4}


def build_currencies():
    english = english_names()
    out = {}
    for code, (name_es, symbol, flag, aliases) in CURRENCIES.items():
        clean = []
        for alias in aliases:
            alias = alias.strip()
            if alias and alias.lower() != name_es.lower() and alias not in clean:
                clean.append(alias)
        out[code] = {
            "name": name_es,
            "name_en": english.get(code, ""),
            "symbol": symbol,
            "decimals": SPECIAL_DECIMALS.get(
                code, 0 if code in ZERO_DECIMAL else 2
            ),
            "flag": flag,
            "alias": clean,
        }
    return {
        "meta": {
            "generated": time.strftime("%Y-%m-%d"),
            "count": len(out),
            "note": "Nombres en español con tilde; la búsqueda normaliza acentos.",
        },
        "currencies": out,
    }


# --------------------------------------------------------------------------
# banderas e iconos
# --------------------------------------------------------------------------
def copy_flags(data):
    target = os.path.join(WORKFLOW, "flags")
    os.makedirs(target, exist_ok=True)
    source = os.path.join(ASSETS, "flags")
    missing = []
    for code, info in data["currencies"].items():
        origin = os.path.join(source, f"{code}.png")
        destination = os.path.join(target, f"{code}.png")
        if os.path.exists(origin):
            shutil.copy2(origin, destination)
        else:
            missing.append((code, info["flag"]))
    if missing:
        ensure_flags(missing, source)
    for name in ("info.png", "gear.png", "error.png"):
        origin = os.path.join(ASSETS, "hints", name)
        destination = os.path.join(WORKFLOW, "hints", name)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if os.path.exists(origin):
            shutil.copy2(origin, destination)


def ensure_flags(missing, source_dir):
    """Descarga y recorta las banderas que faltan (una sola vez)."""
    import urllib.request

    os.makedirs(source_dir, exist_ok=True)
    for code, _emoji in missing:
        destination = os.path.join(source_dir, f"{code}.png")
        country = FALLBACK_FLAGS.get(code)
        if country:
            temp = destination + ".tmp"
            try:
                request = urllib.request.Request(
                    FLAG_URL.format(country),
                    headers={"User-Agent": "SimpleCurrency/1.0"},
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    with open(temp, "wb") as handle:
                        handle.write(response.read())
                circleize(temp, destination)
                os.remove(temp)
                print(f"  · bandera descargada: {code} ({country})")
                continue
            except Exception as exc:                    # noqa: BLE001
                print(f"  ! {code}: {type(exc).__name__}, uso iniciales")
        letter_flag(destination, code)
        print(f"  · bandera de respaldo: {code}")


def render_icon(path):
    """Icono: dos monedas superpuestas, $ (teal) detrás y € (ámbar) delante."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  ! sin Pillow: uso el icono existente")
        return
    size = 512
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    try:
        glyph = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Avenir Next.ttc", 230, index=0
        )
    except OSError:
        glyph = ImageFont.load_default()
    draw.ellipse((24, 158, 330, 464), fill=(23, 116, 138, 255))
    draw.text((177, 311), "$", font=glyph, fill=(255, 255, 255, 225), anchor="mm")
    draw.ellipse((182, 34, 488, 340), fill=(226, 148, 38, 255),
                 outline=(255, 206, 122, 255), width=14)
    draw.text((335, 187), "€", font=glyph, fill=(255, 255, 255, 240), anchor="mm")
    image.save(path, "PNG")
    print(f"  · icono -> {os.path.relpath(path, ROOT)}")


# --------------------------------------------------------------------------
# info.plist
# --------------------------------------------------------------------------
def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"simple-currency.{name}")).upper()


def script_body(mode=None):
    """Busca un Python 3 real sin disparar el diálogo de Command Line Tools."""
    prefix = f"--mode {mode} " if mode else ""
    return (
        'PY=""\n'
        'if [ -n "$(/usr/bin/xcode-select -p 2>/dev/null)" ] '
        '&& [ -x /usr/bin/python3 ]; then\n'
        '    PY=/usr/bin/python3\n'
        'elif [ -x /opt/homebrew/bin/python3 ]; then\n'
        '    PY=/opt/homebrew/bin/python3\n'
        'elif [ -x /usr/local/bin/python3 ]; then\n'
        '    PY=/usr/local/bin/python3\n'
        "fi\n"
        'if [ -z "$PY" ]; then\n'
        '    printf \'{"items":[{"title":"Python 3 is required",'
        '"subtitle":"Install the Command Line Tools: xcode-select --install",'
        '"valid":false,"icon":{"path":"hints/error.png"}}]}\'\n'
        '    exit\n'
        "fi\n"
        f'"$PY" ./simplecurrency.py {prefix}"$1"\n'
    )


def script_filter(name, keyword, title, subtext, script):
    return {
        "config": {
            "alfredfiltersresults": False,
            "alfredfiltersresultsmatchmode": 0,
            "argumenttreatemptyqueryasnil": False,
            "argumenttrimmode": 0,
            "argumenttype": 1,
            "escaping": 126,
            "keyword": keyword,
            "queuedelaycustom": 2,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "queuemode": 1,
            "runningsubtext": "Converting…",
            "script": script,
            "scriptargtype": 1,
            "scriptfile": "",
            "subtext": subtext,
            "title": title,
            "type": 0,
            "withspace": True,
        },
        "type": "alfred.workflow.input.scriptfilter",
        "uid": uid(name),
        "version": 3,
    }


def textfield(variable, label, description, default, placeholder=""):
    return {
        "config": {"default": default, "placeholder": placeholder,
                   "required": False, "trim": True},
        "description": description,
        "label": label,
        "type": "textfield",
        "variable": variable,
    }


def popup(variable, label, description, default, pairs):
    return {
        "config": {"default": default, "pairs": pairs},
        "description": description,
        "label": label,
        "type": "popupbutton",
        "variable": variable,
    }


def build_info_plist():
    main_uid = uid("cur")
    alt_uid = uid("cambio")
    help_uid = uid("help")
    clipboard_uid = uid("clipboard")

    objects = [
        script_filter("cur", "cur", "Convert currency",
                      "100 yuan · 5 pesos chilenos · 1.000.000 clp a dolares",
                      script_body()),
        script_filter("cambio", "cambio", "Convert currency",
                      "100 yuan · 5 pesos chilenos · 1.000.000 clp a dolares",
                      script_body()),
        script_filter("help", "cur-help", "Simple Currency help",
                      "Examples and shortcuts", script_body()),
        script_filter("add", "cur-add", "Add favourites",
                      "Currencies you compare against by default",
                      script_body("add")),
        script_filter("rm", "cur-rm", "Remove favourites",
                      "Stop comparing against them", script_body("rm")),
        {
            "config": {"concurrently": False, "escaping": 0,
                       "script": '/usr/bin/python3 ./simplecurrency.py --toggle "$1"',
                       "scriptargtype": 1, "scriptfile": "", "type": 0},
            "type": "alfred.workflow.action.script",
            "uid": uid("toggle"),
            "version": 2,
        },
        {
            "config": {"concurrently": False, "escaping": 0,
                       "script": '/usr/bin/python3 ./simplecurrency.py --remove "$1"',
                       "scriptargtype": 1, "scriptfile": "", "type": 0},
            "type": "alfred.workflow.action.script",
            "uid": uid("untoggle"),
            "version": 2,
        },
        {
            "config": {"lastpathcomponent": False,
                       "onlyshowifquerypopulated": True,
                       "removeextension": False,
                       "text": "{query}",
                       "title": "Simple Currency"},
            "type": "alfred.workflow.output.notification",
            "uid": uid("notify"),
            "version": 1,
        },
        {
            "config": {
                "autopaste": False,
                "clipboardtext": "{query}",
                "ignoredynamicplaceholders": False,
                "transient": False,
            },
            "type": "alfred.workflow.output.clipboard",
            "uid": clipboard_uid,
            "version": 3,
        },
    ]

    connections = {}
    for source in (main_uid, alt_uid, help_uid):
        connections[source] = [
            {"destinationuid": clipboard_uid, "modifiers": modifiers,
             "modifiersubtext": "", "vitoclose": False}
            for modifiers in (0, 524288, 1048576)
        ]
    connections[uid("add")] = [{"destinationuid": uid("toggle"),
                                "modifiers": 0, "modifiersubtext": "",
                                "vitoclose": False}]
    connections[uid("rm")] = [{"destinationuid": uid("untoggle"),
                               "modifiers": 0, "modifiersubtext": "",
                               "vitoclose": False}]
    for action in (uid("toggle"), uid("untoggle")):
        connections[action] = [{"destinationuid": uid("notify"),
                                "modifiers": 0, "modifiersubtext": "",
                                "vitoclose": False}]

    uidata = {
        main_uid: {"xpos": 0, "ypos": 0},
        alt_uid: {"xpos": 0, "ypos": 180},
        help_uid: {"xpos": 0, "ypos": 360},
        clipboard_uid: {"xpos": 330, "ypos": 0},
        uid("add"): {"xpos": 0, "ypos": 540},
        uid("rm"): {"xpos": 0, "ypos": 720},
        uid("toggle"): {"xpos": 330, "ypos": 540},
        uid("untoggle"): {"xpos": 330, "ypos": 720},
        uid("notify"): {"xpos": 660, "ypos": 630},
    }

    userconfig = [
        popup("LANGUAGE_UI", "Interface language",
              "Follows the macOS language by default.",
              SETTINGS["LANGUAGE_UI"],
              [["Automatic", "auto"], ["English", "en"], ["Español", "es"]]),
        textfield("BASE", "Base currency",
                  "Everything is converted against this currency (ISO code).",
                  SETTINGS["BASE"], "CLP"),
        textfield("FAVORITES", "Favourites",
                  "Compared by default, comma separated; manage them with cur-add.",
                  SETTINGS["FAVORITES"], "USD,EUR,ARS"),
        popup("COMPARE", "When you type a currency",
              "Show it against the base currency and all your favourites.",
              SETTINGS["COMPARE"],
              [["Against my favourites", "FAVORITES"],
               ["Against the base currency only", "BASE"]]),
        popup("ORIENTATION", "Default list direction",
              "Which way round to show the favourites list.",
              SETTINGS["ORIENTATION"],
              [["Both ways", "DEFAULT"],
               ["Base → favourites", "TO_FAV"],
               ["Favourites → base", "FROM_FAV"]]),
        popup("PRECISION", "Decimals",
              "\u201cAutomatic\u201d uses each currency's own precision (CLP 0, USD 2).",
              SETTINGS["PRECISION"],
              [["Automatic", "auto"], ["0", "0"], ["2", "2"],
               ["4", "4"], ["6", "6"]]),
        popup("EXPIRE", "Refresh rates",
              "How often exchange rates are downloaded again.",
              SETTINGS["EXPIRE"],
              [["5 minutes", "300"], ["15 minutes", "900"],
               ["1 hour", "3600"], ["6 hours", "21600"],
               ["24 hours", "86400"]]),
        textfield("ALIASES", "Custom aliases",
                  "alias=CODE pairs, comma separated. e.g. lucas=CLP, verde=USD",
                  SETTINGS["ALIASES"], "lucas=CLP, verde=USD"),
    ]

    readme = (
        "Simple Currency \u2014 currency conversion by code or by name, in English "
        "and Spanish.\n\n"
        "USAGE\n"
        "cur                            your favourites against the base "
        "currency\n"
        "cur 100 usd                    100 US dollars to the base currency\n"
        "cur 100 yuan                   by name \u2014 codes are optional\n"
        "cur 1,000,000 clp a dolares    \u00aba\u00bb, \u00aben\u00bb or "
        "\u00abto\u00bb set the direction\n"
        "cur usd yuan                   between two currencies, both ways\n"
        "cur peso                       ambiguous names show a picker "
        "(\u21e5 completes)\n"
        "cur-add / cur-rm               choose the favourites you compare "
        "against\n"
        "cur-help                       every example\n\n"
        "\u21a9 copies the result \u00b7 \u2325 the full expression \u00b7 "
        "\u2318 the number only.\n\n"
        "LANGUAGES\n"
        "The interface follows the macOS language (English or Spanish); "
        "override it in Configure \u2192 Interface language. Currency names are "
        "searchable in both languages, with or without accents, singular or "
        "plural: dollar, d\u00f3lares, chilean peso, peso chileno, yuan, "
        "corona sueca, swiss franc.\n\n"
        "ESPA\u00d1OL\n"
        "cur                            tus favoritas contra la moneda "
        "principal\n"
        "cur 100 usd                    100 d\u00f3lares a la moneda principal\n"
        "cur 100 yuan                   por nombre, sin c\u00f3digos\n"
        "cur 1.000.000 clp a dolares    con \u00aba\u00bb o \u00aben\u00bb "
        "fijas la direcci\u00f3n\n"
        "cur-add / cur-rm               elegir las favoritas contra las que se "
        "compara\n\n"
        "DATA & PRIVACY\n"
        "Rates from open.er-api.com (no API key), cached on disk for an hour, "
        "with currency-api as a fallback. Nothing else leaves your Mac. "
        "Requires Python 3 (/usr/bin/python3, included with the Command Line "
        "Tools). Based on Coinc by Tomy Hsieh (MIT); the flag icons come from "
        "the same project.\n"
    )

    return {
        "bundleid": "com.github.claudiouvm.simplecurrency",
        "category": "Productivity",
        "connections": connections,
        "createdby": "Claudio",
        "description": "Convert currencies by ISO code or by name "
                       "(dollar, Chilean peso, yuan) \u2014 English and Spanish.",
        "disabled": False,
        "name": "Simple Currency",
        "objects": objects,
        "readme": readme,
        "uidata": uidata,
        "userconfigurationconfig": userconfig,
        "variablesdontexport": [],
        "version": "1.1.0",
        "webaddress": "https://github.com/claudiouvm/simple-currency",
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    os.makedirs(WORKFLOW, exist_ok=True)
    data = build_currencies()

    path = os.path.join(WORKFLOW, "currencies.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    print(f"  · {len(data['currencies'])} monedas -> {os.path.relpath(path, ROOT)}")

    copy_flags(data)

    if "--no-icon" not in sys.argv:
        render_icon(os.path.join(WORKFLOW, "icon.png"))

    with open(os.path.join(WORKFLOW, "info.plist"), "wb") as handle:
        plistlib.dump(build_info_plist(), handle)
    print("  · info.plist")

    if os.path.exists(OUTPUT):
        os.remove(OUTPUT)
    subprocess.run(
        ["zip", "-qr", "-X", OUTPUT,
         "info.plist", "simplecurrency.py", "currencies.json", "icon.png", "flags", "hints"],
        cwd=WORKFLOW, check=True,
    )
    size = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"\nOK  {os.path.relpath(OUTPUT, ROOT)}  ({size:.1f} MB)")


if __name__ == "__main__":
    main()
