#! /usr/bin/env python3

import re
import sys
from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit
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

class CentralWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basic Medicine Model")

        maak_grafiek_button = QPushButton("Maak grafiek")

        fig = Figure()
        self.axes = fig.add_axes(rect=(0.12, 0.12, 0.82, 0.82))
        (self.graph_plotline,) = self.axes.plot([], [])
        self.axes.set_xlabel("tijd [etmalen]")
        self.axes.set_ylabel("hoeveelheid medicijn in lichaam [eenheden]")
        self.axes.grid()

        self.grafiek_canvas = FigureCanvas(fig)

        self.halflife_widget = QLineEdit("160.0")
        self.start_amount_widget = QLineEdit("0.0")
        self.startup_dosages_widget = QLineEdit("4")
        self.repeat_dosages_widget = QLineEdit("1,2")
        self.graph_starttime_widget = QLineEdit("0")
        self.graph_endtime_widget = QLineEdit("30")
        self.halflife_widget.setMinimumWidth(60)

        layout = vbox_layout(
            groupbox("Invoervelden",
                 hbox_layout(
                     "*stretch*",
                    grid_layout(
                        ["Halfwaardetijd medicijn", self.halflife_widget, "uren"],
                        ["Hoeveelheid medicijn voor eerste inname", self.start_amount_widget, "eenheden"],
                        ["Opstart-doseringen", self.startup_dosages_widget, "eenheden"],
                        ["Herhaal-doseringen", self.repeat_dosages_widget, "eenheden"],
                        ["Grafiek start-tijd", self.graph_starttime_widget, "etmalen"],
                        ["Grafiek eind-tijd", self.graph_endtime_widget, "etmalen"]
                    ),
                    "*stretch*"
                ),
            ),
            hbox_layout(
               "*stretch*",
                maak_grafiek_button,
                "*stretch*"
            ),
            self.grafiek_canvas
        )

        self.setLayout(layout)

        maak_grafiek_button.clicked.connect(self.check_settings_and_update)

        self.check_settings_and_update()

    def check_settings_and_update(self):

        float_pattern = re.compile("[0-9]+([.][0-9]+)?")

        halflife_value = None
        halflife_text = self.halflife_widget.text()
        if float_pattern.fullmatch(halflife_text) is not None:
            value = float(halflife_text)
            if 0.0 < value <= 10000.0:
                halflife_value = value

        error = False

        if halflife_value is not None:
            palette = self.halflife_widget.palette()
            palette.setColor(QPalette.Base, Qt.green)
            self.halflife_widget.setPalette(palette)
        else:
            error = True
            palette = self.halflife_widget.palette()
            palette.setColor(QPalette.Base, Qt.red)
            self.halflife_widget.setPalette(palette)

        # If any error occured, bail out.
        if error:
            return

        settings = SimulationSettings(
            halflife = halflife_value,
            start_amount = 0.0,
            startup_dosages = [4.0, 2.0, 1.0],
            repeat_dosages = [1.0, 0.5],
            graph_start_time = 0.0,
            graph_end_time = 25.0
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
        for t in range(t1, t2 + 1):
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
        self.grafiek_canvas.draw_idle()


def main():
    app = QApplication(sys.argv)
    widget = CentralWidget()
    widget.show()
    exitcode = app.exec()
    sys.exit(exitcode)

if __name__ == "__main__":
    main()
