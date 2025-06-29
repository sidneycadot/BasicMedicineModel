#! /usr/bin/env python3

import re
import sys
from typing import NamedTuple, Optional

import numpy as np
from PySide6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QMainWindow, QLabel

from layout_utilities import grid_layout, vbox_layout, hbox_layout, groupbox


def mean_dosage(repeat_dosages: list[float]) -> float:
    if len(repeat_dosages) == 0:
        return 0.0
    return sum(repeat_dosages) / len(repeat_dosages)


def equilibrium_amount(repeat_dosages: list[float], halflife: float) -> float:
    """Gemiddelde hoeveelheid werkzame stof in lichaam na bereiken evenwicht."""
    return (halflife / 24) / np.log(2) * mean_dosage(repeat_dosages)


class SimulationSettings(NamedTuple):
    halflife: float               # halflife, in HOURS
    start_amount: float           # start amount, in UNITS
    startup_dosages: list[float]  # start dosages, in UNITS
    repeat_dosages: list[float]   # repeat dosages, in UNITS
    graph_start_time: float       # graph start time, in DAYS (24 hours)
    graph_end_time: float         # graph end time, in DAYS (24 hours)

    def equilibrium(self):
        """Gemiddelde hoeveelheid werkzame stof in lichaam na bereiken evenwicht."""
        return equilibrium_amount(self.repeat_dosages, self.halflife)


DecimalDigit = "(?:[0-9]+)"
NonEmptyDecimalDigitSequence = f"(?:{DecimalDigit}+)"
Float = f"(?:{NonEmptyDecimalDigitSequence}(?:[.]{NonEmptyDecimalDigitSequence})?)"
NonEmptyFloatList = f"(?:{Float}(?:[-]{Float})*)"
PossiblyEmptyFloatList = f"(?:{NonEmptyFloatList}?)"

float_pattern = re.compile(Float)
float_list_pattern = re.compile(PossiblyEmptyFloatList)


def parse_and_validate_float(s: str, validate_func) -> Optional[float]:
    if float_pattern.fullmatch(s) is not None:
        value = float(s)
        if validate_func(value):
            return value
    return None


def parse_and_validate_float_list(s: str, validate_func) -> Optional[list[float]]:
    if float_list_pattern.fullmatch(s) is not None:
        if len(s) == 0:
            value = []
        else:
            value = [float(x) for x in s.split("-")]
        if validate_func(value):
            return value
    return None


def set_widget_background_color(widget, color) -> None:
    palette = widget.palette()
    palette.setColor(QPalette.Base, color)
    palette.setColor(QPalette.Text, Qt.black)
    widget.setPalette(palette)


def fmt(x) -> str:
    """Format number as integer or float string."""
    if x.is_integer():
        return str(int(x))

    s = f"{x:.3f}"
    while s.endswith("0"):
        s = s[:-1]
    return s


class PassiveLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignCenter)


class CentralWidget(QWidget):

    color_good = QColor("#ccffcc")
    color_good_static = QColor("#eeeeff")
    color_bad = QColor("#ffcccc")

    def __init__(self):
        super().__init__()

        self.fig = Figure()
        self.axes = self.fig.add_axes(rect=(0.12, 0.12, 0.82, 0.82))
        (self.graph_plotline,) = self.axes.plot([], [])
        self.axes.set_xlabel("tijd [etmalen]")
        self.hline = self.axes.axhline(np.nan, c='m')
        self.axes.set_ylabel("hoeveelheid medicijn in lichaam [eenheden]")
        self.axes.grid()

        self.plot_canvas = FigureCanvas(self.fig)

        self.halflife_widget = QLineEdit("160")
        self.start_amount_widget = QLineEdit("0")
        self.startup_dosages_widget = QLineEdit("4")
        self.repeat_dosages_widget = QLineEdit("1-2")
        self.graph_start_time_widget = QLineEdit("0")
        self.graph_end_time_widget = QLineEdit("30")

        self.repeat_dosages_mean_widget = PassiveLineEdit()
        self.repeat_dosages_equilibrium_widget = PassiveLineEdit()

        self.halflife_widget.setToolTip("Acenocoumarol: 8 tot 11 uur\n"
                                        "Warfarine: 40 uur\n"
                                        "Fenprocoumon: 160 uur")

        edit_widgets = (self.halflife_widget,
                        self.start_amount_widget,
                        self.startup_dosages_widget,
                        self.repeat_dosages_widget,
                        self.graph_start_time_widget,
                        self.graph_end_time_widget)

        for widget in edit_widgets:
            widget.setMinimumWidth(60)
            widget.setMaximumWidth(120)
            widget.textEdited.connect(self.validate_settings_and_update_gui_if_ok)

        show_widgets = (self.repeat_dosages_mean_widget,
                        self.repeat_dosages_equilibrium_widget)

        for widget in show_widgets:
            widget.setMinimumWidth(60)
            widget.setMaximumWidth(120)

        layout = vbox_layout(
            "*stretch*",
            hbox_layout(
                "*stretch*",
                grid_layout(
                    ["<b>Invoervelden</b>"],
                    ["  Halfwaardetijd medicijn", self.halflife_widget, "uren"],
                    ["  Hoeveelheid medicijn in lichaam voor eerste inname", self.start_amount_widget, "eenheden"],
                    ["  Opstart-doseringen", self.startup_dosages_widget, "eenheden per etmaal"],
                    ["  Herhaal-doseringen", self.repeat_dosages_widget, "eenheden per etmaal"],
                    ["  Grafiek start-tijd", self.graph_start_time_widget, "etmalen"],
                    ["  Grafiek eind-tijd", self.graph_end_time_widget, "etmalen"],
                    [""],
                    ["<b>Berekende waarden</b>"],
                    ["  Gemiddelde herhaal-dosering", self.repeat_dosages_mean_widget, "eenheden per etmaal"],
                    ["  Gemiddelde hoeveelheid medicijn in lichaam na inregelen", self.repeat_dosages_equilibrium_widget, "eenheden"],
                    [""]
                ),
                "*stretch*"
            ),
            "*stretch*",
            self.plot_canvas
        )

        self.setLayout(layout)

        self.validate_settings_and_update_gui_if_ok()

    def validate_settings_and_update_gui_if_ok(self):

        halflife = parse_and_validate_float(self.halflife_widget.text(), lambda x: x > 0.0)
        start_amount = parse_and_validate_float(self.start_amount_widget.text(), lambda x: x >= 0.0)
        startup_dosages = parse_and_validate_float_list(self.startup_dosages_widget.text(), lambda xlist: all(x >= 0.0 for x in xlist))
        repeat_dosages = parse_and_validate_float_list(self.repeat_dosages_widget.text(), lambda xlist: all(x >= 0.0 for x in xlist))
        graph_start_time = parse_and_validate_float(self.graph_start_time_widget.text(), lambda x: x >= 0.0)
        graph_end_time = parse_and_validate_float(self.graph_end_time_widget.text(), lambda x: 0.0 <= x <= 100.0)

        repeat_dosage_mean = None if repeat_dosages is None else mean_dosage(repeat_dosages)
        repeat_dosage_equilibrium = None if repeat_dosages is None or halflife is None else equilibrium_amount(repeat_dosages, halflife)

        if (graph_start_time is not None) and (graph_end_time is not None):
            if not (graph_start_time < graph_end_time):
                graph_start_time = None
                graph_end_time = None

        set_widget_background_color(self.halflife_widget, self.color_good if halflife is not None else self.color_bad)
        set_widget_background_color(self.start_amount_widget, self.color_good if start_amount is not None else self.color_bad)
        set_widget_background_color(self.startup_dosages_widget, self.color_good if startup_dosages is not None else self.color_bad)
        set_widget_background_color(self.repeat_dosages_widget, self.color_good if repeat_dosages is not None else self.color_bad)
        set_widget_background_color(self.graph_start_time_widget, self.color_good if graph_start_time is not None else self.color_bad)
        set_widget_background_color(self.graph_end_time_widget, self.color_good if graph_end_time is not None else self.color_bad)

        set_widget_background_color(self.repeat_dosages_mean_widget, self.color_good_static if repeat_dosage_mean is not None else self.color_bad)
        set_widget_background_color(self.repeat_dosages_equilibrium_widget, self.color_good_static if repeat_dosage_equilibrium is not None else self.color_bad)

        self.repeat_dosages_mean_widget.setText(f"{fmt(repeat_dosage_mean)}" if repeat_dosage_mean is not None else "")
        self.repeat_dosages_equilibrium_widget.setText(f"{fmt(repeat_dosage_equilibrium)}" if repeat_dosage_equilibrium is not None else "")

        if all(x is not None for x in (halflife, start_amount, startup_dosages, repeat_dosages, graph_start_time, graph_end_time)):
            settings = SimulationSettings(
                halflife = halflife,
                start_amount = start_amount,
                startup_dosages = startup_dosages,
                repeat_dosages = repeat_dosages,
                graph_start_time = graph_start_time,
                graph_end_time = graph_end_time
            )

            self.update_graph(settings)

    def update_graph(self, settings: SimulationSettings):

        t1 = round(settings.graph_start_time * 1440.0)
        t2 = round(settings.graph_end_time * 1440.0)

        startup_dosages = settings.startup_dosages
        repeat_dosages = settings.repeat_dosages

        halflife_minutes = settings.halflife * 60.0

        # The decay factor per minute.
        decay_factor = 0.5 ** (1.0 / halflife_minutes)

        x = []
        y = []

        amount = settings.start_amount

        if 0 >= t1:
            x.append(0.0)
            y.append(settings.start_amount)

        for t in range(0, t2 + 1):
            if t % 1440 == 0:
                index = t // 1440
                if index < len(startup_dosages):
                    dose = startup_dosages[index]
                elif len(repeat_dosages) != 0:
                    index = (index - len(startup_dosages)) % len(repeat_dosages)
                    dose = repeat_dosages[index]
                else:
                    dose = 0.0
            else:
                dose = 0.0

            amount = decay_factor * amount + dose

            if t >= t1:
                x.append(t / 1440.0)
                y.append(amount)

        x = np.asarray(x)
        y = np.asarray(y)

        equilibrium = settings.equilibrium()

        self.hline.set_ydata([equilibrium])

        self.graph_plotline.set_data(x, y)
        self.axes.relim()
        self.axes.autoscale()
        self.axes.set_ylim(0.0, np.ceil(max(np.amax(y), equilibrium) + 0.5))
        self.plot_canvas.draw_idle()


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basic Medicine Halflife Model")

        central_widget = CentralWidget()
        self.setCentralWidget(central_widget)


class Application(QApplication):
    def __init__(self):
        super().__init__()
        window = MainWindow()
        window.show()
        self.window = window


def main():
    app = Application()
    exitcode = app.exec()
    if exitcode != 0:
        sys.exit(exitcode)


if __name__ == "__main__":
    main()
