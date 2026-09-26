"""Text normalisation for TTS: numbers, currency, percent, abbreviations,
symbols -> speakable words. Pure stdlib, no heavy deps (no num2words).

The public entry point is ``normalize_for_speech``.
"""

from __future__ import annotations

import re

_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]
_SCALES = [
    (1_000_000_000_000, "trillion"),
    (1_000_000_000, "billion"),
    (1_000_000, "million"),
    (1_000, "thousand"),
]

_ABBREVIATIONS = {
    "dr.": "doctor",
    "mr.": "mister",
    "mrs.": "missus",
    "ms.": "miz",
    "prof.": "professor",
    "st.": "street",
    "ave.": "avenue",
    "jr.": "junior",
    "sr.": "senior",
    "vs.": "versus",
    "etc.": "et cetera",
    "e.g.": "for example",
    "i.e.": "that is",
    "approx.": "approximately",
    "no.": "number",
    "dept.": "department",
    "govt.": "government",
}

_CURRENCY_SYMBOLS = {
    "$": "dollar",
    "£": "pound",
    "€": "euro",
    "¥": "yen",
}

_SYMBOL_WORDS = {
    "&": "and",
    "@": "at",
    "%": "percent",
    "#": "number",
    "+": "plus",
    "=": "equals",
    "/": "slash",
}


def _int_to_words(n: int) -> str:
    if n < 0:
        return "negative " + _int_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, rem = divmod(n, 10)
        word = _TENS[tens]
        if rem:
            word += "-" + _ONES[rem]
        return word
    if n < 1000:
        hundreds, rem = divmod(n, 100)
        word = f"{_ONES[hundreds]} hundred"
        if rem:
            word += " " + _int_to_words(rem)
        return word
    for scale_value, scale_name in _SCALES:
        if n >= scale_value:
            major, rem = divmod(n, scale_value)
            word = f"{_int_to_words(major)} {scale_name}"
            if rem:
                word += " " + _int_to_words(rem)
            return word
    return str(n)  # pragma: no cover - unreachable for sane input


def number_to_words(value: str) -> str:
    """Convert a plain integer/decimal string (no symbols) to words."""
    value = value.replace(",", "")
    negative = value.startswith("-")
    if negative:
        value = value[1:]
    if "." in value:
        int_part, frac_part = value.split(".", 1)
        int_part = int_part or "0"
        words = _int_to_words(int(int_part))
        if frac_part:
            digit_words = " ".join(_ONES[int(d)] for d in frac_part if d.isdigit())
            words += " point " + digit_words
    else:
        words = _int_to_words(int(value)) if value else ""
    return ("negative " + words) if negative else words


def _currency_to_words(match: re.Match) -> str:
    symbol = match.group("symbol")
    amount = match.group("amount")
    unit = _CURRENCY_SYMBOLS.get(symbol, "")
    amount = amount.replace(",", "")
    if "." in amount:
        major, minor = amount.split(".", 1)
        major = major or "0"
        minor = (minor + "00")[:2]
        major_words = _int_to_words(int(major))
        minor_words = _int_to_words(int(minor))
        major_unit = unit if int(major) == 1 else unit + "s"
        result = f"{major_words} {major_unit}"
        if int(minor) > 0:
            cent_unit = "cent" if int(minor) == 1 else "cents"
            result += f" and {minor_words} {cent_unit}"
        return result
    n = int(amount)
    unit_word = unit if n == 1 else unit + "s"
    return f"{_int_to_words(n)} {unit_word}"


def _percent_to_words(match: re.Match) -> str:
    number = match.group("num")
    return f"{number_to_words(number)} percent"


def _plain_number_to_words(match: re.Match) -> str:
    return number_to_words(match.group(0))


def normalize_for_speech(text: str) -> str:
    """Normalise raw script text into speakable words for TTS.

    Order matters: currency and percent (which contain digits + symbols)
    are handled before the generic number rule, then abbreviations and any
    remaining stray symbols.
    """
    if not text:
        return text

    out = text

    # Currency: $5, $5.50, £12, etc.
    currency_pattern = re.compile(
        r"(?P<symbol>[" + re.escape("".join(_CURRENCY_SYMBOLS)) + r"])"
        r"(?P<amount>\d[\d,]*(?:\.\d+)?)"
    )
    out = currency_pattern.sub(_currency_to_words, out)

    # Percent: 23%, 4.5%
    percent_pattern = re.compile(r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*%")
    out = percent_pattern.sub(_percent_to_words, out)

    # Abbreviations (case-insensitive, word-boundary-ish on the dot form)
    def _abbrev_sub(m: re.Match) -> str:
        word = m.group(0)
        replacement = _ABBREVIATIONS.get(word.lower())
        return replacement if replacement else word

    abbrev_pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in _ABBREVIATIONS) + r")",
        re.IGNORECASE,
    )
    out = abbrev_pattern.sub(_abbrev_sub, out)

    # Plain numbers left over (ordinals kept simple: strip suffix then add words)
    ordinal_pattern = re.compile(r"\b(\d+)(st|nd|rd|th)\b", re.IGNORECASE)
    out = ordinal_pattern.sub(lambda m: number_to_words(m.group(1)), out)

    number_pattern = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
    out = number_pattern.sub(_plain_number_to_words, out)

    # Remaining stray symbols -> words (do this after numbers so "%"
    # already consumed by percent handling isn't double-converted).
    for sym, word in _SYMBOL_WORDS.items():
        if sym in out:
            out = out.replace(sym, f" {word} ")

    # Collapse whitespace
    out = re.sub(r"\s+", " ", out).strip()
    return out


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))
