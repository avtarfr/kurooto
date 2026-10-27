"""Numbers as words for the voice (modules/voice/numbers.py, voice.speak.numbers_as_words): times, dates, years,
versions, money, ranges, units and the rest said as a person would, code-like tokens left alone, and nothing changed
when the switch is off or for what's shown. Pure text: no speech engine is touched."""

import pytest

from kurooto.modules.voice import numbers
from kurooto.modules.voice import shape as shape_mod

CASES = [
    # times: the owner's screen is 24-hour; said the 12-hour way
    ("It is 21:31.", "It is nine thirty-one P-M."),
    ("21:00", "nine P-M"),
    ("09:05", "nine oh five A-M"),
    ("05:30", "five thirty A-M"),
    ("00:00", "midnight"),
    ("24:00", "midnight"),
    ("00:15", "twelve fifteen A-M"),
    ("12:00", "twelve noon"),
    ("12:30", "twelve thirty"),
    ("13:05", "one oh five P-M"),
    ("9:30", "nine thirty"),
    ("9:00", "nine o'clock"),
    ("9:30 pm", "nine thirty P-M"),
    ("9:30PM", "nine thirty P-M"),
    ("9am", "nine A-M"),
    ("at 9 am", "at nine A-M"),
    ("at 10 a.m. tomorrow", "at ten A-M tomorrow"),
    ("10:00 a.m. Then", "ten A-M. Then"),
    ("9-11am", "nine to eleven A-M"),
    ("9:00-10:00", "nine o'clock to ten o'clock"),
    ("21:31:05", "nine thirty-one P-M and five seconds"),
    ("25:00", "twenty-five to zero zero"),  # not a time: left a ratio rather than a wrong hour
    # dates: day first, as in India
    ("27/10/2026", "the twenty-seventh of October twenty twenty-six"),
    ("on the 27/10/2026", "on the twenty-seventh of October twenty twenty-six"),
    ("Lab on 27/10/2026.", "Lab on the twenty-seventh of October twenty twenty-six."),
    ("Due 27.10.2026.", "Due the twenty-seventh of October twenty twenty-six."),
    ("Due 2026-10-27.", "Due the twenty-seventh of October twenty twenty-six."),
    ("1-1-26", "the first of January twenty twenty-six"),
    ("27.10.2026", "the twenty-seventh of October twenty twenty-six"),
    ("2026-10-27", "the twenty-seventh of October twenty twenty-six"),
    ("2026-10-27T21:31", "the twenty-seventh of October twenty twenty-six at nine thirty-one P-M"),
    ("27 Oct 2026", "the twenty-seventh of October twenty twenty-six"),
    ("the 27th of October", "the twenty-seventh of October"),
    ("October 27, 2026", "October twenty-seventh, twenty twenty-six"),
    ("May 1st", "May first"),
    ("27/10", "the twenty-seventh of October"),
    # years and decades
    ("In 2026.", "In twenty twenty-six."),
    ("2026 was good", "twenty twenty-six was good"),
    ("2000", "two thousand"),
    ("2005", "two thousand and five"),
    ("2010", "twenty ten"),
    ("1999", "nineteen ninety-nine"),
    ("1905", "nineteen oh five"),
    ("1900", "nineteen hundred"),
    ("in 1850", "in eighteen fifty"),
    ("1850 people", "one thousand eight hundred and fifty people"),
    ("2,026 people", "two thousand and twenty-six people"),
    ("1990s", "nineteen nineties"),
    ("the 80s", "the eighties"),
    ("'90s music", "nineties music"),
    ("2025-26", "twenty twenty-five to twenty-six"),
    ("1990-2000", "nineteen ninety to two thousand"),
    # versions
    ("0.8.13", "zero point eight point thirteen"),
    ("Kurooto 0.8.13 is out.", "Kurooto zero point eight point thirteen is out."),
    ("v0.8.13", "version zero point eight point thirteen"),
    ("v0.8", "version zero point eight"),
    ("version 0.12", "version zero point twelve"),
    ("203.0.113.5", "two hundred and three dot zero dot one hundred and thirteen dot five"),
    # money
    ("₹3,000", "three thousand rupees"),
    ("It costs ₹3,000.", "It costs three thousand rupees."),
    ("₹1", "one rupee"),
    ("₹ 250", "two hundred and fifty rupees"),
    ("Rs. 500", "five hundred rupees"),
    ("Rs 500 a day", "five hundred rupees a day"),
    ("INR 750", "seven hundred and fifty rupees"),
    ("500 INR", "five hundred rupees"),
    ("₹1,00,000", "one lakh rupees"),
    ("₹12,34,567", "twelve lakh thirty-four thousand five hundred and sixty-seven rupees"),
    ("₹2,50,00,000", "two crore fifty lakh rupees"),
    ("₹2 lakh", "two lakh rupees"),
    ("₹5 crore", "five crore rupees"),
    ("₹3.5", "three rupees and fifty paise"),
    ("₹0.50", "fifty paise"),
    ("$5", "five dollars"),
    ("$1", "one dollar"),
    ("$0.01", "one cent"),
    ("$5k", "five thousand dollars"),
    ("$3m budget", "three million dollars budget"),
    ("$1.5 billion", "one point five billion dollars"),
    ("$5 more", "five dollars more"),
    ("$1.234", "one point two three four dollars"),
    ("€2.50", "two euros and fifty cents"),
    ("£0.99", "ninety-nine pence"),
    ("£1.01", "one pound and one penny"),
    ("₹3,000/month", "three thousand rupees a month"),
    # ranges
    ("3-5 minutes", "three to five minutes"),
    ("3–5 minutes", "three to five minutes"),
    ("3 – 5", "three to five"),
    ("3–5%", "three to five percent"),
    ("2-3 GB", "two to three gigabytes"),
    ("12345-67890", "one two three four five, six seven eight nine zero"),  # a phone number, not a range
    ("COVID-19", "COVID-nineteen"),
    # percentages, decimals, negatives, separators
    ("45%", "forty-five percent"),
    ("12.5 %", "twelve point five percent"),
    ("-3%", "minus three percent"),
    ("3.14", "three point one four"),
    ("0.5", "zero point five"),
    ("between -5 and 3", "between minus five and three"),
    ("-12", "minus twelve"),
    ("±2", "plus or minus two"),
    ("1,234", "one thousand two hundred and thirty-four"),
    ("1,234,567", "one million two hundred and thirty-four thousand five hundred and sixty-seven"),
    ("5,000.", "five thousand."),
    ("1, 2, 3", "one, two, three"),
    ("1000005", "one million and five"),
    ("007", "zero zero seven"),
    ("1234567890", "one two three four five six seven eight nine zero"),
    ("0", "zero"),
    ("105", "one hundred and five"),
    # ordinals
    ("1st 2nd 3rd 4th", "first second third fourth"),
    ("21st", "twenty-first"),
    ("22nd", "twenty-second"),
    ("100th", "one hundredth"),
    ("112th", "one hundred and twelfth"),
    ("40th", "fortieth"),
    # units, only right after a number
    ("12 GB", "twelve gigabytes"),
    ("12GB", "twelve gigabytes"),
    ("1 GB", "one gigabyte"),
    ("1.0 GB", "one point zero gigabytes"),
    ("512 MB", "five hundred and twelve megabytes"),
    ("2 TB", "two terabytes"),
    ("64 KB", "sixty-four kilobytes"),
    ("2.4 GHz", "two point four gigahertz"),
    ("900 MHz", "nine hundred megahertz"),
    ("60 km/h", "sixty kilometres per hour"),
    ("5 km", "five kilometres"),
    ("70 kg", "seventy kilograms"),
    ("15 cm", "fifteen centimetres"),
    ("3 mm", "three millimetres"),
    ("-5°C", "minus five degrees Celsius"),
    ("1°C", "one degree Celsius"),
    ("30°", "thirty degrees"),
    ("300 K", "three hundred kelvin"),
    ("250 ms", "two hundred and fifty milliseconds"),
    ("5 s", "five seconds"),
    ("45s", "forty-five seconds"),
    ("10 min", "ten minutes"),
    ("1 min", "one minute"),
    ("2h", "two hours"),
    ("8 hrs", "eight hours"),
    ("5k steps", "five thousand steps"),
    ("10x faster", "ten times faster"),
    ("1920x1080", "one thousand nine hundred and twenty by one thousand and eighty"),
    ("GB free", "GB free"),  # a unit with no number is left alone
    # fractions and ratios
    ("3/4", "three quarters"),
    ("1/2", "one half"),
    ("2/3", "two thirds"),
    ("24/7", "twenty-four seven"),
    ("7/10", "seven out of ten"),
    ("16:9", "sixteen to nine"),
    # letters and digits: said naturally; code-like tokens left as written
    ("L96", "L ninety-six"),
    ("Q5", "Q five"),
    ("F1", "F one"),
    ("x86", "x eighty-six"),
    ("sha256", "sha two hundred and fifty-six"),
    ("3D", "three D"),
    ("4K screen", "four K screen"),
    ("5G", "five G"),
    ("x86_64", "x86_64"),
    ("7c12897", "7c12897"),
    ("0x1F", "0x1F"),
    ("a1b2", "a1b2"),
    # nothing to do
    ("", ""),
    ("No numbers here.", "No numbers here."),
]


@pytest.mark.parametrize(("written", "said"), CASES)
def test_numbers_are_said_as_a_person_would(written, said):
    assert numbers.say(written) == said


def test_nothing_the_engine_reads_badly_is_left():
    # what espeak-ng turned into ":" pauses, "slash", "dash", "gee bee" or "rupee three thousand"
    text = "At 21:31 on 27/10/2026, 3-5 minutes, ₹3,000, 12 GB, 0.8.13 and 2026."
    out = numbers.say(text)
    assert not any(c in out for c in ":/₹0123456789") and "GB" not in out
    assert out == (
        "At nine thirty-one P-M on the twenty-seventh of October twenty twenty-six, three to five minutes, "
        "three thousand rupees, twelve gigabytes, zero point eight point thirteen and twenty twenty-six."
    )


def test_words_ordinals_years_and_indian_grouping():
    assert numbers.words(0) == "zero" and numbers.words(-7) == "minus seven"
    assert numbers.words(1_000_000_000) == "one billion"
    assert numbers.words(2_000_100) == "two million one hundred"
    assert numbers.words(10**15).startswith("one zero zero")  # past trillions: one digit at a time
    assert numbers.ordinal(1) == "first" and numbers.ordinal(12) == "twelfth" and numbers.ordinal(90) == "ninetieth"
    assert numbers.year(2026) == "twenty twenty-six" and numbers.year(1066) == "one thousand and sixty-six"
    assert numbers.indian(100000) == "one lakh" and numbers.indian(10**7) == "one crore"
    assert numbers.indian(10**7 + 5) == "one crore and five"


def test_the_switch_off_leaves_the_text_as_it_was():
    text = "At 21:31 it's ₹3,000 for 12 GB, v0.8.13."
    assert shape_mod.sentences(text) == ["At 21:31 it's ₹3,000 for 12 GB, v0.8.13."]
    assert shape_mod.spoken(text) == text
    assert shape_mod.sentences(text, numbers=True) == [
        "At nine thirty-one P-M it's three thousand rupees for twelve gigabytes, "
        "version zero point eight point thirteen."
    ]


def test_sentences_are_split_after_the_numbers_are_words():
    # "a.m." is no longer taken for the end of a sentence; a version's dots never were
    assert shape_mod.sentences("Lab at 10 a.m. tomorrow. Kurooto 0.8.13 is out.", numbers=True) == [
        "Lab at ten A-M tomorrow.",
        "Kurooto zero point eight point thirteen is out.",
    ]
    assert shape_mod.sentences("Lab at 10 a.m. tomorrow.") == ["Lab at 10 a.m.", "tomorrow."]


def test_the_estimate_follows_what_is_said():
    said = shape_mod.estimate(shape_mod.spoken("21:31", numbers=True))
    assert said == shape_mod.estimate("nine thirty-one P-M") and len(said) > len(shape_mod.estimate("21:31"))
