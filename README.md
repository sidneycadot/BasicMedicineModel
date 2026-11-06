# Basic Medicine Halflife Model

A simple model that shows how the amount of a medicine in the body develops
over time, given the medicine's half-life and a daily dosing schedule. It was
made to give insight into dosing anticoagulants (trombose-medicatie). The user
interface and manual are in Dutch.

The graph shows the *amount of medicine in the body*, not its effect (such as
the INR). See the manual ("Uitleg") for the model's limitations.

There are two versions with the same functionality:

## Web version

Open `web/index.html` in any modern browser (Firefox, Edge, Chrome, Safari).
It is a single, self-contained file: no installation or internet connection
is needed, and the file can be copied anywhere.

## Desktop version (Python)

Requires Python 3.10 or newer.

```
pip install -r requirements.txt
python3 main.py
```

## Files

| File                  | Contents                                                  |
|-----------------------|-----------------------------------------------------------|
| `model.py`            | Parsing, validation and simulation (no GUI code)          |
| `main.py`             | The desktop user interface (PySide6 + matplotlib)         |
| `layout_utilities.py` | Small helpers to build Qt layouts                         |
| `manual.html`         | The manual shown in the desktop version's "Uitleg" tab    |
| `web/index.html`      | The complete web version, including its own manual        |

When changing the model, the input rules or the manual, change both versions:
`model.py`/`manual.html` and `web/index.html` implement the same rules and text.
