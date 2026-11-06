"""Small helpers to build Qt layouts from nested lists.

Items can be:
  - a string: shown as a label (rich text allowed, e.g. "<b>title</b>");
  - '*stretch*' (in box layouts): empty space that grows;
  - a QWidget or QLayout;
  - in grid layouts, Span(item, columns) to let an item cover several columns,
    and None for an empty cell (unlike "", which adds an empty label that
    still takes up space).
"""

from typing import NamedTuple

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLayout, QLabel, QGridLayout

_STRETCH_STRING_ = '*stretch*'


class Span(NamedTuple):
    """A grid item that covers `columns` columns."""
    item: object
    columns: int


def _as_widget_or_layout(item):
    """Turn a string into a QLabel; pass widgets and layouts through."""
    if isinstance(item, str):
        return QLabel(item)
    if isinstance(item, (QWidget, QLayout)):
        return item
    raise RuntimeError(f"Bad layout item: {item!r}")


def box_layout(layout_type, *items):
    layout = layout_type()
    for item in items:
        if item == _STRETCH_STRING_:
            layout.addStretch()
            continue
        item = _as_widget_or_layout(item)
        if isinstance(item, QWidget):
            layout.addWidget(item)
        else:
            layout.addLayout(item)
    return layout


def hbox_layout(*items):
    return box_layout(QHBoxLayout, *items)


def vbox_layout(*items):
    return box_layout(QVBoxLayout, *items)


def grid_layout(*rows):
    """Build a grid from rows of items; each row is a list of cells."""
    layout = QGridLayout()
    for row_index, row in enumerate(rows):
        column_index = 0
        for cell in row:
            if cell is None:
                column_index += 1
                continue
            columns = 1
            if isinstance(cell, Span):
                cell, columns = cell.item, cell.columns
            item = _as_widget_or_layout(cell)
            if isinstance(item, QWidget):
                layout.addWidget(item, row_index, column_index, 1, columns)
            else:
                layout.addLayout(item, row_index, column_index, 1, columns)
            column_index += columns
    return layout
