#! /usr/bin/env python3

"""Basic Medicine Halflife Model — desktop (PySide6) version.

Shows how the amount of a medicine in the body develops over time, given its
half-life and a daily dosing schedule. The model itself (parsing, validation,
simulation) lives in model.py; this file contains only the user interface.

The web version (web/index.html) offers the same functionality in a browser.
Keep both versions in sync when making changes.
"""

import sys
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPalette, QColor, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QLabel, QLineEdit, QMainWindow, QTabWidget,
                               QTextEdit, QWidget)

import model
from layout_utilities import Span, grid_layout, vbox_layout, hbox_layout

MANUAL_PATH = Path(__file__).resolve().parent / "manual.html"

# Graph colours (matplotlib defaults: 'C0' blue and 'm' magenta).
GRAPH_LINE_COLOR = "#1f77b4"
GRAPH_EQUILIBRIUM_COLOR = "#bf00bf"
GRAPH_HOVER_COLOR = "#ff7f0e"


def is_dark_mode() -> bool:
    """True if the application uses a dark colour scheme."""
    return QApplication.instance().palette().color(QPalette.Window).lightness() < 128


def set_widget_background_color(widget, color) -> None:
    palette = widget.palette()
    palette.setColor(QPalette.Base, color)
    palette.setColor(QPalette.Text, Qt.black)
    widget.setPalette(palette)


class PassiveLineEdit(QLineEdit):
    """A read-only field for calculated values."""
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAlignment(Qt.AlignCenter)


class ErrorLabel(QLabel):
    """A hint under an invalid field, explaining what is wrong.
    It is hidden (and takes no space) while there is no error."""
    def __init__(self):
        super().__init__()
        color = "#ff8a8a" if is_dark_mode() else "#b00020"
        self.setStyleSheet(f"color: {color}; font-size: small;")
        self.set_error(None)

    def set_error(self, error) -> None:
        self.setText(error or "")
        self.setVisible(error is not None)


class ExplanationWidget(QTextEdit):
    """The manual ("Uitleg"), read from manual.html next to this script."""
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        try:
            html = MANUAL_PATH.read_text(encoding="utf-8")
        except OSError as exception:
            html = f"<p>De uitleg kon niet worden geladen ({MANUAL_PATH}):<br>{exception}</p>"
        self.setHtml(html)


class CalculationsWidget(QWidget):
    """The 'Berekening' tab: input fields, calculated values, and the graph."""

    color_good = QColor("#ccffcc")
    color_good_static = QColor("#eeeeff")
    color_bad = QColor("#ffcccc")

    def __init__(self, texts: dict[str, str]):
        super().__init__()

        # The field texts of the most recent fully valid input; used by "Dupliceren".
        self.good_texts = dict(texts)

        # The data currently plotted, used by the hover read-out.
        self.plot_x = np.empty(0)
        self.plot_y = np.empty(0)
        self.hover_index = None

        self._make_graph()

        # ---- Input fields, one per setting (keys as in model.DEFAULT_TEXTS) ----
        self.fields = {key: QLineEdit(texts[key]) for key in model.DEFAULT_TEXTS}
        self.error_labels = {key: ErrorLabel() for key in model.DEFAULT_TEXTS}

        for field in self.fields.values():
            field.setMinimumWidth(60)
            field.setMaximumWidth(120)
            field.textEdited.connect(self.validate_settings_and_update_gui_if_ok)

        self.fields["halflife"].setToolTip("Acenocoumarol: 8 tot 14 uur, gemiddeld 11 uur\n"
                                           "Warfarine: 38 tot 42 uur, gemiddeld 40 uur\n"
                                           "Fenprocoumon: 120 tot 200 uur, gemiddeld 160 uur")

        # ---- Half-life presets -------------------------------------------------
        self.preset_combobox = QComboBox()
        self.preset_combobox.setToolTip("Kies de gemiddelde halfwaardetijd van een medicijn")
        self.preset_combobox.addItem("medicijn…", None)
        for name, halflife in model.HALFLIFE_PRESETS:
            self.preset_combobox.addItem(name, halflife)
        # 'activated' fires only on a user choice, not when the program changes it.
        self.preset_combobox.activated.connect(self.handle_preset_chosen)

        # ---- Calculated values -------------------------------------------------
        self.repeat_dosages_mean_widget = PassiveLineEdit()
        self.repeat_dosages_equilibrium_widget = PassiveLineEdit()
        for widget in (self.repeat_dosages_mean_widget, self.repeat_dosages_equilibrium_widget):
            widget.setMinimumWidth(60)
            widget.setMaximumWidth(120)

        # ---- Layout -----------------------------------------------------------
        def field_rows(key, label, unit):
            """A row with label, field and unit, and a row for the error hint."""
            return [
                [f"  {label}", self.fields[key], unit],
                [None, Span(self.error_labels[key], 2)],
            ]

        rows = [["<b>Invoervelden</b>"]]
        rows += field_rows("halflife", "Halfwaardetijd medicijn",
                           hbox_layout("uren", self.preset_combobox, "*stretch*"))
        rows += field_rows("start_amount", "Hoeveelheid medicijn in lichaam voor eerste inname", "eenheden")
        rows += field_rows("startup_dosages", "Opstart-doseringen", "eenheden per etmaal")
        rows += field_rows("repeat_dosages", "Herhaal-doseringen", "eenheden per etmaal")
        rows += field_rows("graph_start", "Grafiek start-tijd", "etmalen")
        rows += field_rows("graph_end", "Grafiek eind-tijd", "etmalen")
        rows += [
            [""],
            ["<b>Berekende waarden</b>"],
            ["  Gemiddelde herhaal-dosering", self.repeat_dosages_mean_widget, "eenheden per etmaal"],
            ["  Gemiddelde hoeveelheid medicijn in lichaam na inregelen",
             self.repeat_dosages_equilibrium_widget, "eenheden"],
            [""],
        ]

        layout = vbox_layout(
            hbox_layout("*stretch*", grid_layout(*rows), "*stretch*"),
            self.plot_canvas
        )
        layout.setStretch(1, 1)   # the graph gets all extra space
        self.setLayout(layout)

        self.validate_settings_and_update_gui_if_ok()

    # ---- Graph ------------------------------------------------------------------

    def _make_graph(self):
        """Create the figure, the (empty) lines, and the hover marker."""
        # 'constrained' layout keeps the axis labels visible at any window size.
        self.fig = Figure(layout="constrained")
        self.axes = self.fig.add_subplot()
        (self.graph_plotline,) = self.axes.plot([], [], c=GRAPH_LINE_COLOR)
        self.hline = self.axes.axhline(np.nan, c=GRAPH_EQUILIBRIUM_COLOR)
        self.axes.set_xlabel("tijd [etmalen]", fontsize="small")
        self.axes.set_ylabel("hoeveelheid medicijn in lichaam [eenheden]", fontsize="small")
        self.axes.grid()
        # Empty axes until the first valid input (same range as the web version).
        self.axes.set_xlim(0.0, 30.0)
        self.axes.set_ylim(0.0, 1.0)

        # Hover read-out: a vertical line, a dot on the curve, and a label.
        self.hover_line = self.axes.axvline(0.0, c=GRAPH_HOVER_COLOR, lw=1, visible=False)
        (self.hover_dot,) = self.axes.plot([], [], "o", c=GRAPH_HOVER_COLOR, ms=6, visible=False)
        self.hover_text = self.axes.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", ec="#bbbbbb", alpha=0.95), visible=False)

        self.plot_canvas = FigureCanvas(self.fig)
        self.plot_canvas.setMinimumHeight(300)
        self.plot_canvas.mpl_connect("motion_notify_event", self.handle_mouse_move)
        self.plot_canvas.mpl_connect("figure_leave_event", self.handle_mouse_leave)

    def update_graph(self, settings: model.SimulationSettings):
        x, y = model.simulate(settings)
        equilibrium = model.equilibrium_amount(settings.repeat_dosages, settings.halflife)

        self.plot_x, self.plot_y = x, y
        self.graph_plotline.set_data(x, y)
        self.hline.set_ydata([equilibrium])
        self.axes.set_xlim(settings.graph_start, settings.graph_end)
        self.axes.set_ylim(0.0, model.y_axis_top(max(np.amax(y), equilibrium)))

        # Keep the hover marker at the same time, with the new value.
        if self.hover_index is not None:
            self._show_hover(self.hover_line.get_xdata()[0], force=True)
        self.plot_canvas.draw_idle()

    def handle_mouse_move(self, event):
        if event.inaxes is self.axes and event.xdata is not None:
            self._show_hover(event.xdata)
        else:
            self.handle_mouse_leave(event)

    def handle_mouse_leave(self, event):
        if self.hover_index is not None:
            self.hover_index = None
            for artist in (self.hover_line, self.hover_dot, self.hover_text):
                artist.set_visible(False)
            self.plot_canvas.draw_idle()

    def _show_hover(self, xdata: float, force: bool = False):
        """Show the time and amount at the point closest to time `xdata`."""
        x, y = self.plot_x, self.plot_y
        if len(x) == 0:
            return
        # Of the two neighbouring points, take the closer one; on a tie (the
        # duplicated first point at time 0) take the later one, after the dose.
        hi = int(np.clip(np.searchsorted(x, xdata, side="right"), 1, len(x) - 1)) if len(x) > 1 else 0
        lo = max(hi - 1, 0)
        i = hi if abs(x[hi] - xdata) <= abs(x[lo] - xdata) else lo
        if i == self.hover_index and not force:
            return   # nothing changed; avoid a needless redraw
        self.hover_index = i

        self.hover_line.set_xdata([x[i], x[i]])
        self.hover_dot.set_data([x[i]], [y[i]])
        self.hover_text.xy = (x[i], y[i])
        self.hover_text.set_text(f"{model.describe_time(x[i])} — {model.fmt(y[i])} eenheden")
        # Put the label on the left of the marker in the right half of the graph.
        x_min, x_max = self.axes.get_xlim()
        on_right_half = x[i] > (x_min + x_max) / 2
        self.hover_text.set_position((-10, 10) if on_right_half else (10, 10))
        self.hover_text.set_horizontalalignment("right" if on_right_half else "left")
        for artist in (self.hover_line, self.hover_dot, self.hover_text):
            artist.set_visible(True)
        self.plot_canvas.draw_idle()

    # ---- Input handling --------------------------------------------------------

    def current_texts(self) -> dict[str, str]:
        return {key: field.text().strip() for key, field in self.fields.items()}

    def handle_preset_chosen(self, index: int):
        halflife = self.preset_combobox.itemData(index)
        if halflife is not None:
            self.fields["halflife"].setText(model.fmt(halflife))
            self.validate_settings_and_update_gui_if_ok()

    def validate_settings_and_update_gui_if_ok(self):
        texts = self.current_texts()
        values, errors = model.validate(texts)

        # Green for valid fields, red for invalid ones, with a hint under each
        # invalid field.
        for key, field in self.fields.items():
            set_widget_background_color(field, self.color_good if values[key] is not None else self.color_bad)
            self.error_labels[key].set_error(errors[key])

        # Calculated values (shown even if other fields are invalid).
        repeat_dosages, halflife = values["repeat_dosages"], values["halflife"]
        mean = None if repeat_dosages is None else model.mean_dosage(repeat_dosages)
        equilibrium = (None if repeat_dosages is None or halflife is None
                       else model.equilibrium_amount(repeat_dosages, halflife))

        for widget, value in ((self.repeat_dosages_mean_widget, mean),
                              (self.repeat_dosages_equilibrium_widget, equilibrium)):
            set_widget_background_color(widget, self.color_good_static if value is not None else self.color_bad)
            widget.setText(model.fmt(value) if value is not None else "")

        # Keep the half-life drop-down in step with the half-life field.
        index = self.preset_combobox.findData(halflife) if halflife is not None else -1
        self.preset_combobox.setCurrentIndex(max(index, 0))

        # Only redraw the graph if every field is valid.
        settings = model.settings_from_values(values)
        if settings is not None:
            self.good_texts = texts
            self.update_graph(settings)


class MainWindow(QMainWindow):

    def __init__(self, texts: dict[str, str]):
        super().__init__()
        self.setWindowTitle("Basic Medicine Halflife Model")

        self.calculations_widget = CalculationsWidget(texts)

        tab_widget = QTabWidget()
        tab_widget.addTab(self.calculations_widget, "Berekening")
        tab_widget.addTab(ExplanationWidget(), "Uitleg")
        self.setCentralWidget(tab_widget)

        # "Dupliceren": a toolbar button and Ctrl+D. The action belongs to the
        # window, so the shortcut works in both tabs.
        duplicate_action = QAction("Dupliceren", self)
        duplicate_action.setShortcut(QKeySequence(Qt.CTRL | Qt.Key_D))
        duplicate_action.setToolTip("Open een nieuw venster met dezelfde instellingen (Ctrl+D)")
        duplicate_action.triggered.connect(self.handle_duplicate_action)
        toolbar = self.addToolBar("Acties")
        toolbar.setMovable(False)
        toolbar.addAction(duplicate_action)

    def handle_duplicate_action(self):
        QApplication.instance().make_window(self.calculations_widget.good_texts, near=self)

    def closeEvent(self, event):
        # Report to the application that this window is closing.
        QApplication.instance().dispose_window(self)
        super().closeEvent(event)


class Application(QApplication):

    def __init__(self, argv):
        super().__init__(argv)
        self.windows = []
        self.make_window(model.DEFAULT_TEXTS)

    def make_window(self, texts: dict[str, str], near: QMainWindow = None):
        """Open a new window. If `near` is given, place the new window a bit
        below and to the right of it, so it is visibly a new window."""
        window = MainWindow(texts)
        if near is not None:
            window.resize(near.size())
            window.move(near.pos() + QPoint(40, 40))
        window.show()
        self.windows.append(window)

    def dispose_window(self, window):
        self.windows = [w for w in self.windows if w is not window]


def main():
    app = Application(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
