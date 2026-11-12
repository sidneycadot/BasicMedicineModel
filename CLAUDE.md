# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small teaching tool that shows how the amount of a medicine in the body develops over time, given a half-life and a daily dosing schedule (aimed at anticoagulant dosing). The user interface, error messages and manual are in **Dutch**; code, comments and README are in English.

## Commands

```
pip install -r requirements.txt   # PySide6, matplotlib, numpy (Python 3.10+)
python3 main.py                   # desktop version
```

The web version needs no build step: open `web/index.html` in a browser.

There are no tests, linter or build configuration. `model.py` has no GUI imports, so the model can be exercised without PySide6:

```
python3 -c "import model; v, e = model.validate(model.DEFAULT_TEXTS); print(model.simulate(model.settings_from_values(v)))"
```

## Two versions, kept in sync by hand

The same application exists twice, with the same functionality:

- **Desktop:** `model.py` (parsing, validation, simulation, formatting) + `main.py` (PySide6/matplotlib UI) + `manual.html` (shown in the "Uitleg" tab).
- **Web:** `web/index.html`, a single self-contained file (CSS, HTML, manual text and a JavaScript port of `model.py`, with a hand-written canvas plotter). It must stay dependency-free and work offline from a local file.

**Any change to the model, input rules, limits, defaults, error texts, axis scaling or manual text must be made in both versions.** Nothing checks this automatically. The places that mirror each other:

| Desktop | Web (`web/index.html`) |
|---|---|
| constants and `DEFAULT_TEXTS` in `model.py` | section 4.1 of the script |
| `fmt`, `fmt_tick`, `format_thousands`, `describe_time` | `fmt`, `formatTick`, `formatThousands`, `describeTime` |
| `simulate`, `equilibrium_amount`, `y_axis_top` | `simulate`, `equilibriumAmount`, `yAxisTop` |
| `validate` and the `_check_*` functions | `readSettings` |
| `HALFLIFE_PRESETS` | the `<option>`s of `#halflife-preset` |
| `manual.html` | `<section id="panel-manual">` |

The intended differences are listed in the header comment of `web/index.html`: "Dupliceren" opens a new browser tab (settings travel in the URL hash, with Dutch key names from `URL_KEYS`) instead of a new window; the web version follows light/dark mode; and manual section 5 differs accordingly.

The manual quotes the default values and a worked example calculated from them (sections "Snel aan de slag", 1.1 and 4.2), so changing `DEFAULT_TEXTS` means updating those passages in both manuals too.

## Details that are easy to get wrong

- The web version aims for results identical to the Python version, hence `roundHalfEven` in JavaScript (Python's `round()` rounds ties to even).
- Displayed numbers use a decimal comma and dots between thousands; input accepts both `.` and `,` as decimal separator. Dose lists are separated by `-`, so negative numbers and exponents are deliberately not accepted.
- Parse functions return `(value, error)` (Python) or `{ value, error }` (JavaScript); exactly one of the two is null. The graph is only redrawn when every field is valid, and "Dupliceren" uses the last fully valid set of field texts.
- The simulation always starts at day 0, one step per minute; the graph start time only changes what is shown.
- `manual.html` is rendered by Qt's `QTextEdit`, which supports only a limited subset of HTML and CSS.
