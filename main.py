#! /usr/bin/env python3

import re
import sys
from typing import NamedTuple, Optional

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure

from layout_utilities import grid_layout, vbox_layout, hbox_layout, groupbox


class SimulationSettings(NamedTuple):
    halflife: float                 # halflife, in HOURS
    start_amount: float             # start amount, in UNITS
    startup_dosages: list[float]    # start dosages, in UNITS
    repeat_dosages: list[float]     # repeat dosages, in UNITS
    graph_start_time: float         # graph start time, in DAYS (24 hours)
    graph_end_time: float           # graph end time, in DAYS (24 hours)


Float = "(?:[0-9]+(?:[.][0-9]+)?)"
float_pattern = re.compile(f"{Float}")
float_list_pattern = re.compile(f"(?:(?:)|(?:{Float})|(?:{Float}(?:[-]{Float})*))")


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
    widget.setPalette(palette)


class CentralWidget(QWidget):

    color_good = QColor("#ccffcc")
    color_bad = QColor("#ffcccc")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basic Medicine Halflife Model")

        fig = Figure()
        self.axes = fig.add_axes(rect=(0.12, 0.12, 0.82, 0.82))
        (self.graph_plotline,) = self.axes.plot([], [])
        self.axes.set_xlabel("tijd [etmalen]")
        self.axes.set_ylabel("hoeveelheid medicijn in lichaam [eenheden]")
        self.axes.grid()

        self.plot_canvas = FigureCanvas(fig)

        self.halflife_widget = QLineEdit("160")
        self.start_amount_widget = QLineEdit("0")
        self.startup_dosages_widget = QLineEdit("4")
        self.repeat_dosages_widget = QLineEdit("1-2")
        self.graph_start_time_widget = QLineEdit("0")
        self.graph_end_time_widget = QLineEdit("30")

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
            widget.textEdited.connect(self.validate_settings_and_update_graph_if_ok)

        layout = vbox_layout(
            hbox_layout(
                "*stretch*",
                grid_layout(
                    ["Halfwaardetijd medicijn", self.halflife_widget, "uren"],
                    ["Hoeveelheid medicijn in lichaam voor eerste inname", self.start_amount_widget, "eenheden"],
                    ["Opstart-doseringen", self.startup_dosages_widget, "eenheden"],
                    ["Herhaal-doseringen", self.repeat_dosages_widget, "eenheden"],
                    ["Grafiek start-tijd", self.graph_start_time_widget, "etmalen"],
                    ["Grafiek eind-tijd", self.graph_end_time_widget, "etmalen"]
                ),
                "*stretch*"
            ),
            self.plot_canvas
        )

        self.setLayout(layout)

        self.validate_settings_and_update_graph_if_ok()

    def validate_settings_and_update_graph_if_ok(self):

        halflife = parse_and_validate_float(self.halflife_widget.text(), lambda x: x > 0.0)
        start_amount = parse_and_validate_float(self.start_amount_widget.text(), lambda x: x >= 0.0)
        startup_dosages = parse_and_validate_float_list(self.startup_dosages_widget.text(), lambda xlist: all(x >= 0.0 for x in xlist))
        repeat_dosages = parse_and_validate_float_list(self.repeat_dosages_widget.text(), lambda xlist: all(x >= 0.0 for x in xlist))
        graph_start_time = parse_and_validate_float(self.graph_start_time_widget.text(), lambda x: x >= 0.0)
        graph_end_time = parse_and_validate_float(self.graph_end_time_widget.text(), lambda x: 0.0 <= x <= 100.0)

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

        if any(x is None for x in (halflife, start_amount, startup_dosages, repeat_dosages, graph_start_time, graph_end_time)):
            # If any value is None, bail out.
            return

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

        x = []
        y = []

        decay_factor = 0.5 ** (1.0 / halflife_minutes)

        amount = settings.start_amount
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

        self.graph_plotline.set_data(x, y)
        self.axes.relim()
        self.axes.autoscale()
        self.plot_canvas.draw_idle()


def main():
    app = QApplication(sys.argv)
    widget = CentralWidget()
    widget.show()
    exitcode = app.exec()
    sys.exit(exitcode)


if __name__ == "__main__":
    main()
