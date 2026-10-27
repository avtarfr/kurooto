"""Numbers as a person says them, for the voice only (voice.speak.numbers_as_words).

Kokoro takes its pronunciation from espeak-ng, which reads digits literally: "21:31" as "twenty one : thirty one",
"0.8.13" as "zero. eight point one three", "27/10/2026" with "slash", "₹3,000" as "rupee three thousand" and "12 GB"
as "gee bee". say() rewrites the numbers in a text into words before it's spoken, and before its waveform is estimated,
so the shape matches what's said. What's shown on screen never passes through here.

    times        21:31 → nine thirty-one P-M, 21:00 → nine P-M, 09:05 → nine oh five A-M, 00:00 → midnight,
                 12:00 → twelve noon, 9am / 9 a.m. → nine A-M; 9:30 (1 to 12, no leading zero, no AM or PM) → nine
                 thirty, since it could be either
    dates        27/10/2026, 2026-10-27, 27 Oct 2026 → the twenty-seventh of October twenty twenty-six (day first, as
                 in India); October 27 → October twenty-seventh
    years        1900 to 2099 (and 1100 to 1899 after "in", "since", "by" ...) → nineteen ninety-nine, twenty
                 twenty-six, two thousand and five; 1990s → nineteen nineties; a count in that range is best written
                 with a comma (2,026 people)
    versions     0.8.13 → zero point eight point thirteen, v0.8 → version zero point eight; four parts → dot
    money        ₹3,000 → three thousand rupees, Rs 500, INR, $, €, £; ₹1,00,000 → one lakh rupees (Indian commas
                 read as lakh and crore); $2.50 → two dollars and fifty cents; ₹2 lakh, $5k, $3m
    ranges       3-5 and 3–5 → three to five; 2025-26 → twenty twenty-five to twenty-six
    units        only right after a number: GB MB KB TB GHz MHz km kg cm mm °C K ms s min h and a few more
    the rest     1st → first, 45% → forty-five percent, -5 → minus five, 3.14 → three point one four, 3/4 → three
                 quarters, 7/10 → seven out of ten, 16:9 → sixteen to nine, 10x → ten times, 1,234 → one thousand two
                 hundred and thirty-four, 007 and ten or more digits → one digit at a time

Letters joined to digits are said naturally (L96 → L ninety-six, x86 → x eighty-six, 3D → three D); anything
code-like (7c12897, x86_64, 0x1F) is left as written. British-leaning words ("one hundred and five", "kilometres").
"""

from __future__ import annotations

import re

ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen"
).split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand"))
ORDINAL = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth", "nine": "ninth",
           "twelve": "twelfth"}  # fmt: skip
MONTHS = "January February March April May June July August September October November December".split()
MONTHS_3 = {m[:3] for m in MONTHS}
AM, PM = "A-M", "P-M"  # espeak reads a bare "AM" before a full stop as the word "am"; A-M is said "ay em" every time

SP = "[   ]?"  # an optional space (a no-break one too), never a newline: a number and a unit on one line
# a number as written: Indian (1,00,000) or Western (1,000,000) commas, or plain digits; then any decimals
NUM = r"(?:\d{1,3}(?:(?:,\d{2})+,\d{3}|(?:,\d{3})+)(?!\d)|\d+)(?:\.\d+)?"
LEFT = r"(?<![\w.,])"  # a number starts here: not inside a word, a decimal or a code-like token
RIGHT = r"(?![\w]|[.,]\d)"  # and ends here
MONTH = (
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?"
    r"|Nov(?:ember)?|Dec(?:ember)?)\b\.?"
)
YEAR_WORDS = {"in", "since", "by", "of", "from", "until", "till", "before", "after", "year", "during", "circa", "c"}


# ------------------------------------------------------------------------------------------------- the words
def _under_100(n: int) -> str:
    if n < 20:
        return ONES[n]
    t, o = divmod(n, 10)
    return TENS[t] + (f"-{ONES[o]}" if o else "")


def _under_1000(n: int) -> str:
    h, r = divmod(n, 100)
    out = [f"{ONES[h]} hundred"] if h else []
    if r:
        out += ["and", _under_100(r)] if h else [_under_100(r)]
    return " ".join(out)


def words(n: int) -> str:
    """An integer in words: 105 → one hundred and five, 1000005 → one million and five, -3 → minus three."""
    if n < 0:
        return "minus " + words(-n)
    if n < 1000:
        return _under_1000(n) or "zero"
    if n >= 10**15:
        return digits(str(n))
    out = []
    for size, name in SCALES:
        if n >= size:
            q, n = divmod(n, size)
            out.append(f"{_under_1000(q)} {name}")
    if n:
        out.append(("and " if n < 100 else "") + _under_1000(n))
    return " ".join(out)


def indian(n: int) -> str:
    """In lakhs and crores, as Indian commas are read: 1,00,000 → one lakh, 12,34,567 → twelve lakh thirty-four
    thousand five hundred and sixty-seven."""
    crore, n = divmod(n, 10**7)
    lakh, n = divmod(n, 10**5)
    thousand, n = divmod(n, 1000)
    out = [f"{words(crore)} crore"] if crore else []
    out += [f"{_under_100(lakh)} lakh"] if lakh else []
    out += [f"{_under_100(thousand)} thousand"] if thousand else []
    if n:
        out.append(("and " if n < 100 and out else "") + _under_1000(n))
    return " ".join(out) or "zero"


def digits(s: str) -> str:
    return " ".join(ONES[int(c)] for c in s if c.isdigit())


def ordinal(n: int) -> str:
    """1 → first, 22 → twenty-second, 100 → one hundredth."""
    w = words(n)
    head, sep, last = max(w.rpartition(" "), w.rpartition("-"), key=lambda p: len(p[0]))
    if last in ORDINAL:
        last = ORDINAL[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return head + sep + last


def year(n: int) -> str:
    """As a year: 1999 → nineteen ninety-nine, 2026 → twenty twenty-six, 2005 → two thousand and five, 1905 →
    nineteen oh five, 1900 → nineteen hundred."""
    if 2000 <= n <= 2009 or n < 1100 or n > 9999:
        return words(n)
    hi, lo = divmod(n, 100)
    if lo == 0:
        return f"{words(hi)} hundred"
    return f"{words(hi)} {'oh ' + ONES[lo] if lo < 10 else _under_100(lo)}"


def number(s: str) -> str:
    """A number as written (commas, decimals, a sign) in words."""
    s = s.strip()
    sign = ""
    if s[:1] in "-−":
        sign, s = "minus ", s[1:]
    whole, _, frac = s.partition(".")
    if re.fullmatch(r"\d{1,2}(,\d{2})+,\d{3}", whole):
        said = indian(int(whole.replace(",", "")))
    elif "," in whole:
        said = words(int(whole.replace(",", "")))
    elif len(whole) > 1 and whole[0] == "0" or len(whole) >= 10:
        said = digits(whole)  # 007, a phone or account number: one digit at a time
    else:
        said = words(int(whole))
    if frac:
        said += " point " + digits(frac)
    return sign + said


def _plural(w: str) -> str:
    return w[:-1] + "ies" if w.endswith("y") else w + "s"


def _value(s: str) -> float:
    return float(s.replace(",", "").replace("−", "-"))


# ------------------------------------------------------------------------------------------------ the passes
def _the(m: re.Match) -> str:
    """The word "the", unless the text already says it."""
    return "" if re.search(r"\bthe\s+$", m.string[: m.start()], re.I) else "the "


def _date(m: re.Match, d: int, mo: int, y: str | None, day_first: bool = True) -> str:
    if not (1 <= mo <= 12 and 1 <= d <= [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]):
        return m.group(0)
    said = f"{_the(m)}{ordinal(d)} of {MONTHS[mo - 1]}" if day_first else f"{MONTHS[mo - 1]} {ordinal(d)}"
    if y:
        said += f"{'' if day_first else ','} {year(int(y) if len(y) == 4 else 2000 + int(y))}"
    return said


def _month(name: str) -> int:
    return [m[:3] for m in MONTHS].index(name[:3].title()) + 1


def _dates(t: str) -> str:
    def iso(m):
        return _date(m, int(m.group(3)), int(m.group(2)), m.group(1)) + (" at " if m.group(4) else "")

    t = re.sub(r"(?<![\w.-])(\d{4})-(\d{2})-(\d{2})(?:(T)(?=\d{2}:\d{2})|(?![\w-]))", iso, t)
    # 27/10/2026, 27-10-26; with dots only a four-figure year, or 1.10.12 (a version) would be a date
    t = re.sub(
        r"(?<![\w./-])(\d{1,2})([/-])(\d{1,2})\2(\d{4}|\d{2})(?![\w/-]|\.\d)",  # a full stop after it is fine
        lambda m: _date(m, int(m.group(1)), int(m.group(3)), m.group(4)),
        t,
    )
    t = re.sub(
        r"(?<![\w.])(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\w|\.\d)",
        lambda m: _date(m, int(m.group(1)), int(m.group(2)), m.group(3)),
        t,
    )
    t = re.sub(
        rf"(?<![\w.])(\d{{1,2}})(?:st|nd|rd|th)?{SP}(?:of )?{MONTH}(?:,?{SP}(\d{{4}})(?!\d))?",
        lambda m: _date(m, int(m.group(1)), _month(m.group(2)), m.group(3)),
        t,
    )
    return re.sub(
        rf"\b{MONTH}{SP}(?:the )?(\d{{1,2}})(?:st|nd|rd|th)?(?![\w:.]|\.\d)(?:,?{SP}(\d{{4}})(?!\d))?",
        lambda m: _date(m, int(m.group(2)), _month(m.group(1)), m.group(3), day_first=False),
        t,
    )


def _versions(t: str) -> str:
    def say(m):
        parts = [int(p) for p in m.group(2).split(".")]
        joint = " dot " if len(parts) == 4 and all(p < 256 for p in parts) and not m.group(1) else " point "
        return ("version " if m.group(1) else "") + joint.join(words(p) for p in parts)

    t = re.sub(r"(?<![\w.])([vV](?=\d))?(\d+(?:\.\d+){2,})(?![\w]|\.\d)", say, t)
    # v0.8 or "version 0.12": its parts are whole numbers (point twelve), not a decimal (point one two)
    t = re.sub(
        r"(?<![\w.])[vV](\d+)\.(\d+)(?![\w]|\.\d)", lambda m: f"version {words(int(m[1]))} point {words(int(m[2]))}", t
    )
    return re.sub(
        r"\b([Vv]ersion )(\d+)\.(\d+)(?![\w]|\.\d)", lambda m: f"{m[1]}{words(int(m[2]))} point {words(int(m[3]))}", t
    )


def _ranges(t: str) -> str:
    def to(m):
        a, b = m.group(1), m.group(2)
        if len(a) >= 5 and len(b) >= 5 and "," not in a + b:
            return f"{digits(a)}, {digits(b)}"  # 12345-67890: a phone number, not a range
        return f"{a} to {b}"

    return re.sub(rf"(?<![\w.,-])({NUM})(?:-|{SP}[–—]{SP})({NUM})(?![\d-]|[.,]\d)", to, t)


def _clock(h: int, mi: int, sec: str | None, suffix: str | None, zero: bool) -> str | None:
    if h > 24 or (h == 24 and mi):
        return None
    if suffix:
        ap = AM if suffix[0] in "aA" else PM
    elif mi == 0 and h in (0, 24):
        return "midnight"
    elif mi == 0 and h == 12:
        return "twelve noon"
    elif h >= 13 or h == 0 or zero:
        ap = PM if 12 <= h < 24 else AM  # written the 24-hour way: its half of the day is known
    else:
        ap = ""  # 9:30 could be either: said as it's written
    said = words(h % 12 or 12)
    if mi:
        said += f" oh {ONES[mi]}" if mi < 10 else f" {_under_100(mi)}"
    elif not ap:
        said += " o'clock"
    said += f" {ap}" if ap else ""
    if sec and int(sec):
        said += f" and {words(int(sec))} second{'s' if int(sec) != 1 else ''}"
    return said


def _times(t: str) -> str:
    ampm = r"(?:(?i:a\.m\.|p\.m\.)|(?i:am|pm)(?!\w))"

    def hm(m):
        said = _clock(int(m[1]), int(m[2]), m[3], m[4], m[1][0] == "0" and len(m[1]) == 2)
        return m.group(0) if said is None else said + _stop(m)

    def h(m):
        n = int(m[1])
        return m.group(0) if not 1 <= n <= 12 else f"{words(n)} {AM if m[2][0] in 'aA' else PM}" + _stop(m)

    t = re.sub(rf"(?<![\w.:/])(\d{{1,2}}):([0-5]\d)(?::([0-5]\d))?(?![\d:])(?:{SP}({ampm}))?", hm, t)
    return re.sub(rf"(?<![\w.:/,])(\d{{1,2}}){SP}({ampm})", h, t)


def _stop(m: re.Match) -> str:
    """a.m. took the full stop with it: put one back where the sentence ends."""
    end = m.group(0).endswith(".") and re.match(r"\s*(?:$|\n|[A-Z])", m.string[m.end() :])
    return "." if end else ""


CURRENCY = {
    "₹": ("rupee", "rupees", "paisa", "paise"),
    "$": ("dollar", "dollars", "cent", "cents"),
    "€": ("euro", "euros", "cent", "cents"),
    "£": ("pound", "pounds", "penny", "pence"),
}
CODES = {"rs": "₹", "rs.": "₹", "inr": "₹", "usd": "$", "us$": "$", "eur": "€", "gbp": "£"}
SCALE = {"k": "thousand", "thousand": "thousand", "lakh": "lakh", "lakhs": "lakh", "crore": "crore",
         "crores": "crore", "cr": "crore", "m": "million", "mn": "million", "million": "million", "bn": "billion",
         "billion": "billion"}  # fmt: skip


def _money(amount: str, cur: str, scale: str | None) -> str:
    one, many, sub, subs = CURRENCY[cur]
    if scale:
        return f"{number(amount)} {SCALE[scale.lower()]} {many}"
    whole, _, frac = amount.partition(".")
    if len(frac) > 2:
        return f"{number(amount)} {many}"
    main, cents = _value(whole), int((frac + "00")[:2]) if frac else 0
    said = f"{number(whole)} {one if main == 1 else many}"
    if not cents:
        return said
    small = f"{words(cents)} {sub if cents == 1 else subs}"
    return small if main == 0 else f"{said} and {small}"


def _currency(t: str) -> str:
    scale = rf"(?:{SP}(k|K|thousand|lakhs?|crores?|cr|mn|bn|million|billion|m)(?!\w))?"

    def before(m):
        return _money(m[2], CODES.get((m[1] or "").lower().strip(), (m[1] or "").strip()), m[3])

    t = re.sub(rf"(₹|\$|€|£|\b(?:Rs\.?|INR|USD|US\$|EUR|GBP)){SP}({NUM}){scale}{RIGHT}", before, t)
    return re.sub(
        rf"{LEFT}({NUM}){SP}(INR|USD|EUR|GBP|Rs\.?)(?![\w])",
        lambda m: _money(m[1], CODES[m[2].lower()], None),
        t,
    )


UNITS = {  # the unit: (one, many); longest first, so km/h is found before km
    "km/h": ("kilometre per hour", "kilometres per hour"), "kmph": ("kilometre per hour", "kilometres per hour"),
    "mph": ("mile per hour", "miles per hour"), "m/s": ("metre per second", "metres per second"),
    "MB/s": ("megabyte per second", "megabytes per second"), "GB/s": ("gigabyte per second", "gigabytes per second"),
    "Mbps": ("megabit per second", "megabits per second"), "Gbps": ("gigabit per second", "gigabits per second"),
    "kbps": ("kilobit per second", "kilobits per second"),
    "GiB": ("gigabyte", "gigabytes"), "MiB": ("megabyte", "megabytes"), "KiB": ("kilobyte", "kilobytes"),
    "TB": ("terabyte", "terabytes"), "GB": ("gigabyte", "gigabytes"), "MB": ("megabyte", "megabytes"),
    "KB": ("kilobyte", "kilobytes"), "kB": ("kilobyte", "kilobytes"),
    "GHz": ("gigahertz", "gigahertz"), "MHz": ("megahertz", "megahertz"), "kHz": ("kilohertz", "kilohertz"),
    "Hz": ("hertz", "hertz"), "kWh": ("kilowatt hour", "kilowatt hours"), "kW": ("kilowatt", "kilowatts"),
    "mAh": ("milliamp hour", "milliamp hours"), "W": ("watt", "watts"), "V": ("volt", "volts"),
    "km": ("kilometre", "kilometres"), "kg": ("kilogram", "kilograms"), "cm": ("centimetre", "centimetres"),
    "mm": ("millimetre", "millimetres"), "ml": ("millilitre", "millilitres"), "mL": ("millilitre", "millilitres"),
    "°C": ("degree Celsius", "degrees Celsius"), "°F": ("degree Fahrenheit", "degrees Fahrenheit"),
    "°": ("degree", "degrees"), "K": ("kelvin", "kelvin"),
    "ms": ("millisecond", "milliseconds"), "secs": ("second", "seconds"), "sec": ("second", "seconds"),
    "s": ("second", "seconds"), "mins": ("minute", "minutes"), "min": ("minute", "minutes"),
    "hrs": ("hour", "hours"), "hr": ("hour", "hours"), "h": ("hour", "hours"),
    "fps": ("frame per second", "frames per second"), "px": ("pixel", "pixels"),
    "k": ("thousand", "thousand"), "x": ("times", "times"),
}  # fmt: skip
ATTACHED_ONLY = {"k", "x"}  # 5k steps, 10x faster; "5 k" and "5 x" are left alone
SPACED_ONLY = {"K"}  # 300 K is kelvin; 4K is a screen, said "four K"


def _units(t: str) -> str:
    names = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))

    def say(m):
        unit, spaced = m[3], bool(m[2])
        if (unit in ATTACHED_ONLY and spaced) or (unit in SPACED_ONLY and not spaced):
            return m.group(0)
        one, many = UNITS[unit]
        return f"{number(m[1])} {one if _value(m[1]) == 1 and '.' not in m[1] else many}"

    return re.sub(rf"{LEFT}(-?{NUM})({SP})({names})(?![\w°/])", say, t)


def _decades(t: str) -> str:
    def say(m):
        n = int(m[1])
        if n % 10 or not (len(m[1]) == 2 or 1100 <= n <= 2090):
            return m.group(0)
        said = year(n) if len(m[1]) == 4 else _under_100(n)
        return _plural(said)

    return re.sub(r"(?<![\w.])'?(\d{2}|\d{4})s\b", say, t)


def _years(t: str) -> str:
    def say(m):
        n = int(m[1])
        before = re.findall(r"(\w+)\W*$", m.string[: m.start()])
        if n < 1900 and not (before and (before[0].lower() in YEAR_WORDS or before[0][:3].title() in MONTHS_3)):
            return m.group(0)
        return year(n)

    return re.sub(rf"{LEFT}(1[1-9]\d\d|20\d\d){RIGHT}", say, t)


def _slash(m: re.Match) -> str:
    a, b = int(m[1]), int(m[2])
    if (a, b) == (24, 7):
        return "twenty-four seven"
    if a < b and b in (2, 3, 4):
        part = {2: ("half", "halves"), 3: ("third", "thirds"), 4: ("quarter", "quarters")}[b]
        return f"{words(a)} {part[0] if a == 1 else part[1]}"
    if a > b and a <= 31 and 1 <= b <= 12:
        return _date(m, a, b, None)  # 27/10: a day and a month
    if a <= b:
        return f"{words(a)} out of {words(b)}"
    return f"{words(a)} over {words(b)}"


def say(text: str) -> str:
    """The text with its numbers in words, ready for a speech engine (see the module's note)."""
    t = text or ""
    if not re.search(r"\d", t):
        return t
    t = _dates(t)
    t = _versions(t)
    t = _ranges(t)
    t = _times(t)
    t = _currency(t)
    t = re.sub(rf"{LEFT}([-−]?{NUM}){SP}%", lambda m: f"{number(m[1])} percent", t)
    t = _decades(t)
    t = _units(t)
    t = re.sub(
        r"(?<=\w)/(month|mo|day|week|wk|year|yr|hour|hr|night)\b",
        lambda m: " a " + {"mo": "month", "wk": "week", "yr": "year", "hr": "hour"}.get(m[1], m[1]),
        t,
    )
    t = re.sub(r"(?<![\w.])(\d+)(st|nd|rd|th)\b", lambda m: ordinal(int(m[1])), t, flags=re.I)
    t = _years(t)
    t = re.sub(r"(?<![\w.:/])(\d{1,3})/(\d{1,3})(?![\w/]|[.,]\d)", _slash, t)
    t = re.sub(r"(?<![\w.:])([1-9]\d*):(\d+)(?![\w:]|[.,]\d)", lambda m: f"{m[1]} to {m[2]}", t)  # 16:9, a ratio
    t = re.sub(rf"{LEFT}([1-9]\d*){SP}[x×]{SP}(\d+){RIGHT}", lambda m: f"{m[1]} by {m[2]}", t)  # 1920x1080; not 0x1F
    t = re.sub(r"(?<![\w.])±(?=\d)", "plus or minus ", t)
    t = re.sub(r"(?:^|(?<=[\s(\[]))[-−](?=\d)", "minus ", t, flags=re.M)
    t = re.sub(r"\b([A-Za-z]+)(\d+)\b", r"\1 \2", t)  # L96 → L 96, x86, Q5; x86_64 and a1b2 stay as they are
    t = re.sub(r"\b(\d+)([A-Za-z]{1,2})\b", r"\1 \2", t)  # 3D, 4K, 5G
    return re.sub(rf"{LEFT}({NUM}){RIGHT}", lambda m: number(m[1]), t)
