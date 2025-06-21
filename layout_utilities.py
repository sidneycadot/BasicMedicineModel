
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLayout, QLabel, QGridLayout, QGroupBox

_STRETCH_STRING_ = '*stretch*'

def box_layout(layout_type, *items):
    layout = layout_type()
    for item in items:
        if item == _STRETCH_STRING_:
            layout.addStretch()
        elif isinstance(item, str):
            layout.addWidget(QLabel(item))
        elif isinstance(item, QWidget):
            layout.addWidget(item)
        elif isinstance(item, QLayout):
            layout.addLayout(item)
        else:
            raise RuntimeError(f"Bad layout item: {item!r}")
    return layout


def hbox_layout(*items):
    return box_layout(QHBoxLayout, *items)


def vbox_layout(*items):
    return box_layout(QVBoxLayout, *items)


def grid_layout(*rows):
    layout = QGridLayout()
    for row_index, row in enumerate(rows):
        for column_index, item in enumerate(row):
            if isinstance(item, str):
                layout.addWidget(QLabel(item), row_index, column_index)
            elif isinstance(item, QWidget):
                layout.addWidget(item, row_index, column_index)
            elif isinstance(item, QLayout):
                layout.addLayout(item, row_index, column_index)
            else:
                raise RuntimeError(f"Bad layout item: {item!r}")
    return layout


def groupbox(title: str, layout):
    groupbox_widget = QGroupBox(title)
    groupbox_widget.setLayout(layout)
    return groupbox_widget
