"""The model behind the Basic Medicine Halflife Model: parsing and validation
of the input fields, the simulation, and number formatting.

This module has no GUI code, so it can be used and tested on its own.

The web version (web/index.html) implements exactly the same rules and
equations in JavaScript. When changing anything here, change it there too.
"""

import math
import re
from typing import Callable, NamedTuple, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MINUTES_PER_DAY = 1440      # the simulation steps one minute at a time

MAX_GRAPH_END_DAYS = 500    # largest allowed graph end time, in days
MAX_HALFLIFE_HOURS = 10000  # largest allowed half-life, in hours
MAX_AMOUNT = 1000000        # largest allowed start amount or dose, in units

# Default field contents, used for the first window.
DEFAULT_TEXTS = {
    "halflife":        "160",
    "start_amount":    "0",
    "startup_dosages": "4",
    "repeat_dosages":  "1-2",
    "graph_start":     "0",
    "graph_end":       "30",
}

# Average half-lives of common anticoagulants, offered in a drop-down.
# Source: "De kunst van het doseren", Federatie van Nederlandse Trombosediensten, 2024.
HALFLIFE_PRESETS = [
    ("Acenocoumarol (11 uur)", 11.0),
    ("Warfarine (40 uur)", 40.0),
    ("Fenprocoumon (160 uur)", 160.0),
]


class SimulationSettings(NamedTuple):
    """A complete, validated set of inputs."""
    halflife: float               # half-life, in HOURS
    start_amount: float           # amount before the first dose, in UNITS
    startup_dosages: list[float]  # start-up doses, one per day, in UNITS
    repeat_dosages: list[float]   # repeat doses, one per day, in UNITS
    graph_start: float            # graph start time, in DAYS
    graph_end: float              # graph end time, in DAYS


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def fmt(x: float) -> str:
    """Format a number for display, with a decimal comma: whole numbers
    without decimals, others with at most 3 decimals and no trailing zeros
    (e.g. 3, 2,5, 23,084)."""
    if x.is_integer():
        return str(int(x))
    s = f"{x:.3f}".rstrip("0")
    # A value like 2.0004 gives "2.000", which is now "2."; drop the dot.
    return s.rstrip(".").replace(".", ",")


def fmt_tick(x: float) -> str:
    """Format a graph tick label with a decimal comma, without
    floating-point noise (0.30000000000000004 becomes 0,3)."""
    return f"{x:.12g}".replace(".", ",")


def format_thousands(n: int) -> str:
    """Write a whole number the Dutch way, with dots between thousands (10.000)."""
    return f"{n:,}".replace(",", ".")


def describe_time(days: float) -> str:
    """Describe a time in days as e.g. 'dag 3, 06:30'."""
    minutes = round(days * MINUTES_PER_DAY)
    day, minute_of_day = divmod(minutes, MINUTES_PER_DAY)
    hours, minutes = divmod(minute_of_day, 60)
    return f"dag {day}, {hours:02d}:{minutes:02d}"


# ---------------------------------------------------------------------------
# Model equations
# ---------------------------------------------------------------------------

def mean_dosage(repeat_dosages: list[float]) -> float:
    """Mean of a list of doses; 0 for an empty list."""
    if len(repeat_dosages) == 0:
        return 0.0
    return sum(repeat_dosages) / len(repeat_dosages)


def equilibrium_amount(repeat_dosages: list[float], halflife: float) -> float:
    """Average amount of medicine in the body once the patient is stable on
    the repeat schedule: mean daily dose * (half-life in days) / ln(2)."""
    return (halflife / 24) / math.log(2) * mean_dosage(repeat_dosages)


def simulate(s: SimulationSettings) -> tuple[np.ndarray, np.ndarray]:
    """Run the simulation, one step per minute, and return the points to plot
    as two arrays: time (in days) and amount (in units).

    At each minute t, from 0 up to and including the graph end:
      - if t is the start of a day, that day's dose is taken: first the
        start-up doses one by one, then the repeat doses, cycling forever;
      - the amount becomes  decay * amount + dose,  where decay is chosen so
        that the amount halves in exactly one half-life.

    If the graph starts at time 0, an extra first point shows the amount just
    before the first dose, so the graph begins with a vertical jump.
    """
    t1 = round(s.graph_start * MINUTES_PER_DAY)  # first minute shown
    t2 = round(s.graph_end * MINUTES_PER_DAY)    # last minute simulated

    decay_factor = 0.5 ** (1.0 / (s.halflife * 60.0))  # per minute

    extra_point = 1 if 0 >= t1 else 0
    n = max(0, t2 - max(t1, 0) + 1) + extra_point
    x = np.empty(n)
    y = np.empty(n)
    k = 0

    amount = s.start_amount

    if extra_point:
        x[k] = 0.0
        y[k] = s.start_amount
        k += 1

    startup, repeat = s.startup_dosages, s.repeat_dosages

    for t in range(0, t2 + 1):
        dose = 0.0
        if t % MINUTES_PER_DAY == 0:
            day = t // MINUTES_PER_DAY
            if day < len(startup):
                dose = startup[day]
            elif len(repeat) != 0:
                dose = repeat[(day - len(startup)) % len(repeat)]

        amount = decay_factor * amount + dose

        if t >= t1:
            x[k] = t / MINUTES_PER_DAY
            y[k] = amount
            k += 1

    return x, y


def y_axis_top(highest_value: float) -> float:
    """Top of the vertical axis: 5% above the highest value, rounded up to a
    whole number, or for values below 1 to one significant digit (so small
    doses still fill the graph). An all-zero graph gets a top of 1."""
    top = highest_value * 1.05
    if not top > 0:
        return 1.0
    if top >= 1:
        return float(math.ceil(top))
    step = 10.0 ** math.floor(math.log10(top))
    return math.ceil(top / step) * step


# ---------------------------------------------------------------------------
# Parsing and validation
#
# Numbers are digits, optionally followed by '.' or ',' and more digits.
# Negative numbers and exponents are not accepted. Lists are numbers
# separated by '-'; an empty list is allowed.
#
# The parse functions return (value, error): for valid input the error is
# None; for invalid input the value is None and the error is a short Dutch
# explanation, shown under the field.
# ---------------------------------------------------------------------------

_FLOAT = r"[0-9]+(?:[.,][0-9]+)?"
_FLOAT_PATTERN = re.compile(_FLOAT)
_FLOAT_LIST_PATTERN = re.compile(rf"(?:{_FLOAT}(?:-{_FLOAT})*)?")

# An optional extra check on a parsed value: returns None if the value is
# fine, or an error message if not.
Check = Callable[[object], Optional[str]]


def _to_number(s: str) -> float:
    """Convert '4,5' or '4.5' to 4.5."""
    return float(s.replace(",", "."))


def _explain_bad_number(text: str) -> str:
    if text == "":
        return "Vul een getal in."
    if text.startswith("-"):
        return "Negatieve getallen zijn niet toegestaan."
    return "Geen geldig getal. Gebruik bijvoorbeeld 4 of 4,5."


def _explain_bad_list(text: str) -> str:
    if text.startswith("-"):
        return "De lijst mag niet beginnen met een minteken."
    if text.endswith("-"):
        return "De lijst mag niet eindigen met een minteken."
    if "--" in text:
        return "Er staan twee mintekens achter elkaar."
    return "Gebruik getallen gescheiden door een minteken, bijvoorbeeld 1-2-1,5."


def parse_float(text: str, check: Check = lambda x: None):
    """Parse a single number. Returns (value, error)."""
    if _FLOAT_PATTERN.fullmatch(text) is None:
        return None, _explain_bad_number(text)
    value = _to_number(text)
    error = check(value)
    return (value, None) if error is None else (None, error)


def parse_float_list(text: str, check: Check = lambda x: None):
    """Parse a '-'-separated list of numbers. Returns (value, error)."""
    if _FLOAT_LIST_PATTERN.fullmatch(text) is None:
        return None, _explain_bad_list(text)
    value = [] if text == "" else [_to_number(part) for part in text.split("-")]
    error = check(value)
    return (value, None) if error is None else (None, error)


def _max_amount(x: float) -> Optional[str]:
    return None if x <= MAX_AMOUNT else f"Maximaal {format_thousands(MAX_AMOUNT)} eenheden."


def _max_dose(doses: list[float]) -> Optional[str]:
    if all(x <= MAX_AMOUNT for x in doses):
        return None
    return f"Elke dosis mag maximaal {format_thousands(MAX_AMOUNT)} eenheden zijn."


def _check_halflife(x: float) -> Optional[str]:
    if not x > 0.0:
        return "De halfwaardetijd moet groter zijn dan 0."
    if x > MAX_HALFLIFE_HOURS:
        return f"Maximaal {format_thousands(MAX_HALFLIFE_HOURS)} uur."
    return None


def _check_graph_end(x: float) -> Optional[str]:
    return None if x <= MAX_GRAPH_END_DAYS else f"Maximaal {MAX_GRAPH_END_DAYS} etmalen."


def validate(texts: dict[str, str]) -> tuple[dict, dict]:
    """Parse and validate all field texts (keys as in DEFAULT_TEXTS).

    Returns (values, errors): two dicts with the same keys. values[key] is
    the parsed value or None if invalid; errors[key] is an explanation for
    an invalid field, or None if valid.
    """
    results = {
        "halflife":        parse_float(texts["halflife"], _check_halflife),
        "start_amount":    parse_float(texts["start_amount"], _max_amount),
        "startup_dosages": parse_float_list(texts["startup_dosages"], _max_dose),
        "repeat_dosages":  parse_float_list(texts["repeat_dosages"], _max_dose),
        "graph_start":     parse_float(texts["graph_start"]),
        "graph_end":       parse_float(texts["graph_end"], _check_graph_end),
    }

    # The start time must lie before the end time; if not, both are invalid.
    start, end = results["graph_start"][0], results["graph_end"][0]
    if start is not None and end is not None and not start < end:
        results["graph_start"] = (None, "De begintijd moet kleiner zijn dan de eindtijd.")
        results["graph_end"] = (None, "De eindtijd moet groter zijn dan de begintijd.")

    values = {key: value for key, (value, error) in results.items()}
    errors = {key: error for key, (value, error) in results.items()}
    return values, errors


def settings_from_values(values: dict) -> Optional[SimulationSettings]:
    """Make SimulationSettings from validated values, or None if any is invalid."""
    if any(v is None for v in values.values()):
        return None
    return SimulationSettings(**values)
