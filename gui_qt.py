"""
Py Mod (PyVoiceMod) — interface graphique Qt (PySide6).

Lancement :  python gui_qt.py

Pages :  Voix · Sons (tous les sons) · Mes soundboards · un soundboard · Labo de voix · Réglages audio
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import random
import shutil
import sys
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import (QEasingCurve, QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation,
                            Signal)
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetrics, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPalette, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog, QFileDialog, QFrame, QGraphicsDropShadowEffect,
                               QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QStackedWidget, QStyle, QStyleOptionComboBox,
                               QStylePainter, QVBoxLayout, QWidget)

from engine import Engine, list_devices
from hotkeys import MOD_ALT, MOD_CTRL, MOD_SHIFT, GlobalHotkeys, key_label
from presets import VOICES
from soundboard import MODES, ROOT_BOARD, Library
import virtualmic as vm

APP_DIR = Path(__file__).resolve().parent
SOUNDS_DIR = APP_DIR / "sons"
CONFIG = APP_DIR / "config.json"

# --------------------------------------------------------------------------- #
#  Thème
# --------------------------------------------------------------------------- #
BG = "#040606"          # fond de la zone centrale
PANEL = "#171919"       # rail, barre du haut, panneau de droite
CARD = "#181a1a"        # cartes
CARD2 = "#262828"       # listes déroulantes, boîtes de valeur
BTN = "#363838"         # boutons clairs
LINE = "#2a2c2c"
CYAN = "#00fff6"
PURPLE = "#8b5cf6"
MAGENTA = "#e040fb"
YELLOW = "#eeff31"
GREEN = "#4ade80"
ORANGE = "#f59e0b"
RED = "#f43f5e"
TEXT = "#f4f4f4"
MUTED = "#9da1a3"
DIM = "#6b6f71"
DARK_TXT = "#031617"
FONT = "Segoe UI"
EMOJI = "Segoe UI Emoji"
ICON = "Segoe MDL2 Assets"  # remplacé par Segoe Fluent Icons si dispo

G = {k: chr(v) for k, v in dict(
    voices=0xE720, sounds=0xE945, library=0xE8F1, lab=0xE9E9, settings=0xE713, search=0xE721, add=0xE710,
    folder=0xE838, refresh=0xE72C, upload=0xE898, shuffle=0xE8B1, headphone=0xE7F6, mic=0xE720, power=0xE7E8,
    more=0xE712, play=0xE768, delete=0xE74D, keyboard=0xE765, reset=0xE777, check=0xE73E, back=0xE72B,
    chevron_up=0xE70E, chevron_down=0xE70D, edit=0xE70F, help=0xE897, star=0xE735, music=0xEC4F, speaker=0xE767,
    image=0xEB9F, mixer=0xE9E9, record=0xE7C8, user=0xE77B, ear=0xE7F6, hotkey=0xE765, warning=0xE7BA,
    equalizer=0xE9E9, bolt=0xE945, wave=0xE9D9).items()}

CAT_COLORS = {"Basiques": CYAN, "Créatures": RED, "Machines": PURPLE, "Ambiances": ORANGE}
SOUND_COLORS = (CYAN, PURPLE, MAGENTA, ORANGE, GREEN, RED, "#3b82f6", YELLOW)
MODE_BADGE = {"overlap": "⧉", "restart": "↺", "play_stop": "■", "play_pause": "❚❚", "loop": "∞"}
ICONS = ["🔊", "📢", "🎺", "🥁", "🎉", "😂", "👏", "💥", "🔔", "🚨", "🐐", "🐶", "🐱", "🦆",
         "💨", "⚡", "🔥", "💀", "👻", "🤖", "🎮", "🏆", "❌", "✅", "❤️", "⭐", "🎵", "🎬"]
PLACEHOLDER = "Rechercher une voix ou un son…"
ALL, FAVS = "Tous les sons", "Favoris"
GAIN_KEYS = ("voice_gain", "voice_out", "voice_head", "sound_head", "out_gain", "head_gain")
GAIN_DEFAULTS = {"mic_gain": 100, "sound_gain": 80, "voice_gain": 100, "voice_out": 100, "voice_head": 100,
                 "sound_head": 80, "out_gain": 100, "head_gain": 100}

QSS = """
QWidget { color: @TEXT; }
QLabel { background: transparent; }
#rail, #topbar { background: @PANEL; }
#right { background: transparent; }
#center { background: @BG; }
#rightcard { background: @PANEL; border-radius: 8px; }
#card { background: @CARD; border: none; border-radius: 8px; }
#mixcard { background: @CARD; border-radius: 6px; }
#notice { background: @CARD; border-radius: 6px; color: #e9dcc0; padding: 9px 14px; }
QComboBox#mixcombo { background: @CARD2; border: 1px solid transparent; border-radius: 6px; padding: 7px 10px; }
QComboBox#mixcombo:hover { background: #2e3030; }
#muted { color: @MUTED; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: #2e3030; border-radius: 3px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: #3c3e3e; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QLineEdit { background: @CARD2; border: 1px solid @LINE; border-radius: 6px; padding: 6px 10px;
            selection-background-color: @CYAN; selection-color: @DARK; }
QLineEdit:focus { border-color: @CYAN; }
QLineEdit#search { background: #0b0c0c; border: 1px solid #242626; border-radius: 6px; padding: 6px 10px; }
QLineEdit#search:focus { border-color: #3a3c3c; }
QComboBox { background: @CARD2; border: 1px solid @LINE; border-radius: 6px; padding: 7px 10px; }
QComboBox:hover, QComboBox:focus { border-color: #3a3c3c; }
QComboBox::drop-down { border: none; width: 30px; }
QComboBox::down-arrow { image: url(@ARROW); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: @CARD2; border: 1px solid #343636; outline: 0; padding: 4px;
                              selection-background-color: @CYAN; selection-color: @DARK; }
QMenu { background: #202222; border: 1px solid #343636; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 7px 26px 7px 14px; border-radius: 4px; }
QMenu::item:selected { background: #303232; }
QMenu::separator { height: 1px; background: #343636; margin: 5px 8px; }
QMenu::indicator { width: 14px; height: 14px; left: 6px; }
QToolTip { background: #202222; color: @TEXT; border: 1px solid #343636; padding: 5px 8px; }
QDialog, QMessageBox, QInputDialog { background: @PANEL; }
QPushButton { background: @CARD2; border: none; border-radius: 6px; padding: 7px 18px; min-width: 70px; }
QPushButton:hover { background: #343636; }
QPushButton:default { background: @CYAN; color: @DARK; font-weight: 600; }
QPushButton#emoji { font-family: "Segoe UI Emoji"; font-size: 14pt; padding: 0; min-width: 0; border-radius: 6px; }
QPushButton#emoji:checked { background: @CYAN; }
"""
for _k, _v in dict(TEXT=TEXT, PANEL=PANEL, BG=BG, CARD2=CARD2, CARD=CARD, LINE=LINE, CYAN=CYAN, MUTED=MUTED,
                   DARK=DARK_TXT).items():
    QSS = QSS.replace("@" + _k, _v)


# --------------------------------------------------------------------------- #
#  Petits outils de dessin
# --------------------------------------------------------------------------- #
def qc(c, a=None):
    col = QColor(c)
    if a is not None:
        col.setAlphaF(max(0.0, min(1.0, a)))
    return col


def mix(a, b, t):
    a, b, t = QColor(a), QColor(b), max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t)).name()


def color_for(name):
    return SOUND_COLORS[sum(map(ord, name)) % len(SOUND_COLORS)]


def font(size, weight=QFont.Normal, family=FONT):
    f = QFont(family)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def ifont(size):
    return font(size, family=ICON)


def efont(size):
    return font(size, family=EMOJI)


def rpath(rect, r):
    p = QPainterPath()
    p.addRoundedRect(QRectF(rect), r, r)
    return p


def painter(w):
    p = QPainter(w)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    return p


def glyph_icon(glyph, color=MUTED, px=16):
    pm = QPixmap(px * 2, px * 2)
    pm.fill(Qt.transparent)
    p = painter(pm)
    f = QFont(ICON)
    f.setPixelSize(int(px * 1.3))
    p.setFont(f)
    p.setPen(qc(color))
    p.drawText(pm.rect(), Qt.AlignCenter, glyph)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def dark_titlebar(w):
    try:
        hwnd = int(w.winId())
        on = ctypes.c_int(1)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), 4)
        cap = ctypes.c_int(0x00151212)  # #121215 en COLORREF
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cap), 4)
    except Exception:
        pass


def make_menu(parent):
    m = QMenu(parent)
    m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    m.setAttribute(Qt.WA_TranslucentBackground)
    return m


def shadow(w, blur=28, alpha=.6, dy=6):
    e = QGraphicsDropShadowEffect(w)
    e.setBlurRadius(blur)
    e.setColor(qc("#000000", alpha))
    e.setOffset(0, dy)
    w.setGraphicsEffect(e)


class DarkTitles(QObject):
    """Barre de titre sombre pour chaque fenêtre / boîte de dialogue qui s'ouvre."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and isinstance(obj, QDialog) and not obj.property("dark"):
            obj.setProperty("dark", True)
            dark_titlebar(obj)
        return False


# --------------------------------------------------------------------------- #
#  Widgets de base
# --------------------------------------------------------------------------- #
class Clickable(QAbstractButton):
    """Bouton dessiné à la main : gère le survol et ne prend pas le focus clavier."""

    def __init__(self, parent=None, command=None, tip=None):
        super().__init__(parent)
        self.hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        if command:
            self.clicked.connect(lambda: command())
        if tip:
            self.setToolTip(tip)

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()


class Btn(Clickable):
    """kinds : primary, white, glass, ghost, danger, icon, warn, tab, chip, dark, panel, flat, mode, round, grp, adv"""

    BOLD = ("chip", "mode", "dark", "panel", "flat", "adv", "grp")
    SQUARE = {"chip": 4, "dark": 4, "panel": 6, "flat": 6, "mode": 6, "grp": 6, "adv": 6, "icon": 6, "warn": 6}

    def __init__(self, text="", glyph=None, kind="ghost", command=None, h=34, size=10, tip=None, after=False,
                 parent=None):
        super().__init__(parent, command, tip)
        self.setText(text)
        self.glyph, self.kind, self.h, self.fsize, self.selected, self.after = glyph, kind, h, size, False, after
        self.fg = None  # couleur de texte forcée (ex. bouton grisé)
        self.setFixedHeight(h)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_kind(self, k):
        self.kind = k
        self.update()

    def set_selected(self, v):
        self.selected = v
        self.update()

    def _fonts(self):
        return font(self.fsize, QFont.Bold if self.kind in self.BOLD else QFont.DemiBold), ifont(self.fsize + 1)

    def sizeHint(self):
        f, gf = self._fonts()
        w = QFontMetrics(gf).horizontalAdvance(self.glyph) if self.glyph else 0
        if self.text():
            w += QFontMetrics(f).horizontalAdvance(self.text()) + (9 if self.glyph else 0)
        pad = 10 if not self.text() else 16
        return QSize(max(w + 2 * pad, self.h), self.h)

    def _colors(self):
        h, k = self.hover or self.isDown(), self.kind
        if k == "primary":
            return qc("#66fff9" if h else CYAN), qc(DARK_TXT)
        if k == "white":
            return qc("#e2e6e6" if h else "#ffffff"), qc("#0a0a0c")
        if k == "glass":
            return qc("#ffffff", .26 if h else .14), qc("#ffffff")
        if k == "danger":
            return qc("#4a1a28" if h else "#33141d"), qc(RED)
        if k == "icon":
            return qc("#ffffff", .08 if h else 0), qc(TEXT if h else "#d8d8d8")
        if k == "warn":
            return qc("#ffffff", .08 if h else 0), qc(ORANGE)
        if k == "tab":
            if self.selected:
                return qc(CARD2), qc(TEXT)
            return qc("#ffffff", .05 if h else 0), qc(TEXT if h else MUTED)
        if k == "chip":
            if self.selected:
                return qc(CYAN), qc("#000000")
            return qc(CARD2 if h else CARD), qc("#f0f0f0")
        if k == "dark":
            return qc("#2a2c2c" if h else "#0f1012"), qc("#ffffff")
        if k == "panel":
            return qc("#3e4040" if h else "#2a2c2c"), qc(TEXT)
        if k == "flat":
            return qc(CARD2 if h else CARD), qc(TEXT)
        if k == "mode":
            if self.selected:
                return qc(CARD), qc(CYAN)
            return qc("#3e4040" if h else BTN), qc(TEXT)
        if k == "round":
            return qc(BTN if h else CARD2), qc(TEXT)
        if k == "grp":
            return qc("#555a5a" if self.selected else "#3a3c3c" if h else "#2a2c2c", 1 if (self.selected or h) else 0), \
                qc(TEXT)
        if k == "adv":
            return qc("#ffffff", .04 if h else 0), qc(TEXT)
        return qc("#343636" if h else CARD2), qc(TEXT)

    def paintEvent(self, e):
        p = painter(self)
        bg, fg = self._colors()
        if self.fg and not (self.hover or self.isDown()):
            fg = qc(self.fg)
        rad = self.h / 2 if self.kind in ("tab", "glass", "primary", "white", "round") else self.SQUARE.get(self.kind, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()), rad, rad)
        f, gf = self._fonts()
        gw = QFontMetrics(gf).horizontalAdvance(self.glyph) if self.glyph else 0
        tw = QFontMetrics(f).horizontalAdvance(self.text()) if self.text() else 0
        gap = 9 if self.glyph and self.text() else 0
        x = (self.width() - gw - gap - tw) / 2
        p.setPen(fg)
        if self.after:  # texte puis glyphe (ex. « Paramètres avancés ⌄ »)
            if self.text():
                p.setFont(f)
                p.drawText(QRectF(x, 0, tw + 4, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
            if self.glyph:
                p.setFont(gf)
                p.drawText(QRectF(x + tw + gap, 0, gw + 2, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.glyph)
            return
        if self.glyph:
            p.setFont(gf)
            p.drawText(QRectF(x, 0, gw + 2, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.glyph)
        if self.text():
            p.setFont(f)
            p.drawText(QRectF(x + gw + gap, 0, tw + 4, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class RailBtn(Clickable):
    def __init__(self, glyph, command, tip, parent=None):
        super().__init__(parent, command, tip)
        self.glyph, self.selected = glyph, False
        self.setFixedSize(40, 40)

    def set_selected(self, v):
        self.selected = v
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(self.rect())
        if self.selected or self.hover:
            p.setPen(Qt.NoPen)
            p.setBrush(qc(CYAN) if self.selected else qc("#2a2c2c"))
            p.drawRoundedRect(r, 8, 8)
        p.setFont(ifont(13))
        p.setPen(qc(DARK_TXT if self.selected else "#f0f0f0"))
        p.drawText(r, Qt.AlignCenter, self.glyph)


class BoardIcon(Clickable):
    def __init__(self, name, icon, command, parent=None):
        super().__init__(parent, command, name)
        self.name, self.icon, self.selected = name, icon, False
        self.setFixedSize(40, 40)

    def set_selected(self, v):
        self.selected = v
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        c = color_for(self.name)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, qc(mix(c, "#ffffff", .1 if self.hover else 0)))
        g.setColorAt(1, qc(mix(c, "#000000", .6)))
        p.fillPath(rpath(r, 8), g)
        if self.selected:
            p.setPen(QPen(qc(CYAN), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, 8, 8)
        p.setFont(efont(13))
        p.drawText(r, Qt.AlignCenter, self.icon)


class Logo(QWidget):
    """Petite onde cyan en haut du rail."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)

    def paintEvent(self, e):
        p = painter(self)
        p.setPen(QPen(qc(CYAN), 3.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        pts = [(5, 20), (10, 11), (15, 27), (20, 9), (25, 29), (30, 13), (35, 20)]
        path = QPainterPath(QPointF(*pts[0]))
        for x, y in pts[1:]:
            path.lineTo(x, y)
        p.drawPath(path)


class Toggle(Clickable):
    def __init__(self, text, value=False, command=None, width=236, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(bool(value))
        self.setText(text)
        self.setFixedSize(width, 34)
        self.command = command
        self._pos = 1.0 if value else 0.0
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._step)
        self.toggled.connect(self._animate)
        self.clicked.connect(lambda: self.command and self.command(self.isChecked()))

    @property
    def value(self):
        return self.isChecked()

    def set(self, v, notify=False):
        self.setChecked(bool(v))
        if notify and self.command:
            self.command(bool(v))

    def _animate(self, v):
        self.anim.stop()
        self.anim.setStartValue(self._pos)
        self.anim.setEndValue(1.0 if v else 0.0)
        self.anim.start()

    def _step(self, v):
        self._pos = float(v)
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        p.setFont(font(10))
        p.setPen(qc(TEXT if self.hover else "#dcdce2"))
        p.drawText(QRectF(0, 0, self.width() - 50, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        tr = QRectF(self.width() - 42, (self.height() - 22) / 2, 42, 22)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(mix("#3a3c3c", CYAN, self._pos)))
        p.drawRoundedRect(tr, 11, 11)
        kx = tr.left() + 3 + (tr.width() - 22) * self._pos
        p.setBrush(qc(mix("#9a9aa6", "#ffffff", self._pos)))
        p.drawEllipse(QRectF(kx, tr.top() + 3, 16, 16))


class Slider(QWidget):
    def __init__(self, lo, hi, value, command=None, length=200, orient="h", colors=(CYAN, CYAN), res=1.0,
                 fmt=None, show_value=True, parent=None):
        super().__init__(parent)
        self.lo, self.res, self.cmd = lo, res, command
        self.fmt = fmt or (lambda v: f"{v:.0f}")
        horiz = orient == "h"
        self.s = QSlider(Qt.Horizontal if horiz else Qt.Vertical)
        self.s.setFocusPolicy(Qt.NoFocus)
        self.s.setCursor(Qt.PointingHandCursor)
        self.s.setRange(0, round((hi - lo) / res))
        self.s.setValue(round((value - lo) / res))
        c1, c2 = colors
        if horiz:
            self.s.setFixedWidth(length)
            self.s.setStyleSheet(f"""
                QSlider {{ height: 22px; }}
                QSlider::groove:horizontal {{ height: 6px; background: #2a2a32; border-radius: 3px; }}
                QSlider::sub-page:horizontal {{ border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {mix(c1, '#000000', .25)}, stop:1 {c2}); }}
                QSlider::add-page:horizontal {{ background: #2a2a32; border-radius: 3px; }}
                QSlider::handle:horizontal {{ background: #ffffff; width: 10px; margin: -6px 0; border-radius: 8px;
                    border: 3px solid {c2}; }}""")
        else:
            self.s.setFixedHeight(length)
            self.s.setStyleSheet(f"""
                QSlider {{ width: 26px; }}
                QSlider::groove:vertical {{ width: 6px; background: #2a2a32; border-radius: 3px; }}
                QSlider::add-page:vertical {{ border-radius: 3px; background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
                    stop:0 {c1}, stop:1 {c2}); }}
                QSlider::sub-page:vertical {{ background: #2a2a32; border-radius: 3px; }}
                QSlider::handle:vertical {{ background: #ffffff; height: 10px; margin: 0 -6px; border-radius: 8px;
                    border: 3px solid {c2}; }}""")
        self.lbl = QLabel()
        self.lbl.setFont(font(9, QFont.DemiBold))
        self.lbl.setStyleSheet(f"color: {CYAN};")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setMinimumWidth(48)
        lay = QHBoxLayout(self) if horiz else QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        if horiz:
            lay.addWidget(self.s)
            if show_value:
                lay.addWidget(self.lbl)
        else:
            if show_value:
                lay.addWidget(self.lbl, 0, Qt.AlignHCenter)
            lay.addWidget(self.s, 0, Qt.AlignHCenter)
        self.lbl.setVisible(show_value)
        self._label()
        self.s.valueChanged.connect(self._changed)

    def get(self):
        return self.lo + self.s.value() * self.res

    def set(self, v):
        self.s.blockSignals(True)
        self.s.setValue(round((v - self.lo) / self.res))
        self.s.blockSignals(False)
        self._label()

    def _label(self):
        self.lbl.setText(self.fmt(self.get()))

    def _changed(self, _v):
        self._label()
        if self.cmd:
            self.cmd(self.get())


class Meter(QWidget):
    def __init__(self, length=236, orient="h", segs=24, thick=10, parent=None):
        super().__init__(parent)
        self.orient, self.segs, self.lvl = orient, segs, 0.0
        self.setFixedSize(length, thick) if orient == "h" else self.setFixedSize(thick + 14, length)

    def set(self, lvl):
        if abs(lvl - self.lvl) > .01:
            self.lvl = lvl
            self.update()

    def paintEvent(self, e):
        p = painter(self)
        p.setPen(Qt.NoPen)
        horiz = self.orient == "h"
        n = self.segs
        L = self.width() if horiz else self.height()
        T = self.height() if horiz else self.width() - 14
        step = L / n
        on = round(self.lvl * n)
        for i in range(n):
            t = i / (n - 1)
            col = GREEN if t < .6 else YELLOW if t < .85 else RED
            c = qc(col) if i < on else qc(col, .14)
            if horiz:
                r = QRectF(i * step, 0, step - 3, T)
            else:
                r = QRectF(7, L - (i + 1) * step + 3, T, step - 3)
            p.setBrush(c)
            p.drawRoundedRect(r, 2, 2)


class Card(QFrame):
    def __init__(self, pad=16, spacing=8, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(pad, pad, pad, pad)
        self.lay.setSpacing(spacing)


def label(text, size=10, weight=QFont.Normal, color=None, wrap=False):
    lb = QLabel(text)
    lb.setFont(font(size, weight))
    if color:
        lb.setStyleSheet(f"color: {color};")
    lb.setWordWrap(wrap)
    return lb


def scroll_area(widget):
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sc.setWidget(widget)
    return sc


class TileGrid(QWidget):
    """Grille de vignettes à cellules fixes, qui se réorganise selon la largeur."""

    def __init__(self, cw, ch, bottom=110, parent=None):
        super().__init__(parent)
        self.cw, self.ch, self.bottom, self._ws = cw, ch, bottom, []

    def set_widgets(self, ws):
        keep = set(map(id, ws))
        for w in self._ws:
            if id(w) not in keep:
                try:
                    w.hide()
                except RuntimeError:  # déjà détruit
                    pass
        self._ws = list(ws)
        for w in self._ws:
            if w.parent() is not self:
                w.setParent(self)
            w.show()
        self._relayout()

    def resizeEvent(self, e):
        self._relayout()

    def _relayout(self):
        cols = max(1, self.width() // self.cw)
        for i, w in enumerate(self._ws):
            w.move((i % cols) * self.cw, (i // cols) * self.ch)
        rows = (len(self._ws) + cols - 1) // cols
        self.setMinimumHeight(rows * self.ch + self.bottom)


# --------------------------------------------------------------------------- #
#  Vignettes
# --------------------------------------------------------------------------- #
CELL_W, CELL_H, THUMB = 118, 152, 76
_PIX = {}


def load_pix(path):
    """Image perso (mise en cache) ou None."""
    if not path:
        return None
    if path not in _PIX:
        pm = QPixmap(path)
        _PIX[path] = None if pm.isNull() else pm
    return _PIX[path]


def draw_cover(p, pm, rect, radius):
    """Dessine l'image en la recadrant pour remplir le rectangle (coins arrondis)."""
    path = rpath(rect, radius)
    p.save()
    p.setClipPath(path)
    sc = max(rect.width() / pm.width(), rect.height() / pm.height())
    w, h = pm.width() * sc, pm.height() * sc
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawPixmap(QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h), pm, QRectF(pm.rect()))
    p.restore()
    return path


class Avatar(QWidget):
    W, H = 128, 160

    def __init__(self, icon, title, sub, color, command=None, parent=None):
        super().__init__(parent)
        self.icon, self.title, self.sub, self.color, self.command = icon, title, sub, color, command
        self.selected = self.hover = False
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.hide()

    def set_selected(self, v):
        if v != self.selected:
            self.selected = v
            self.update()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.command:
            self.command()

    def paintEvent(self, e):
        p = painter(self)
        cx, cy, r = self.W / 2, 56, 42 + (2 if self.hover else 0)
        if self.selected:
            halo = QRadialGradient(QPointF(cx, cy), r + 20)
            halo.setColorAt(r / (r + 20), qc(CYAN, .55))
            halo.setColorAt(1, qc(CYAN, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(cx, cy), r + 20, r + 20)
        g = QRadialGradient(QPointF(cx - r * .35, cy - r * .45), r * 1.6)
        g.setColorAt(0, qc(mix(self.color, "#ffffff", .06)))
        g.setColorAt(.6, qc(mix(self.color, "#000000", .42)))
        g.setColorAt(1, qc(mix(self.color, "#000000", .78)))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), r, r)
        if self.selected:
            p.setPen(QPen(qc(CYAN), 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r + 4, r + 4)
        elif self.hover:
            p.setPen(QPen(qc("#ffffff", .45), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)
        p.setFont(efont(25))
        p.setPen(qc("#ffffff"))
        p.drawText(QRectF(cx - r, cy - r, 2 * r, 2 * r), Qt.AlignCenter, self.icon)
        p.setFont(font(10, QFont.DemiBold))
        p.setPen(qc(CYAN if self.selected else TEXT))
        p.drawText(QRectF(2, 114, self.W - 4, 20), Qt.AlignCenter, self.title)
        p.setFont(font(8.5))
        p.setPen(qc(DIM))
        p.drawText(QRectF(2, 134, self.W - 4, 18), Qt.AlignCenter, self.sub)


class Tile(QWidget):
    """Vignette carrée (son) : clic = jouer, ⋯ / clic droit = menu, clic sur la légende = action."""

    def __init__(self, icon, title, sub, color, command=None, menu=None, on_sub=None, parent=None):
        super().__init__(parent)
        self.icon, self.title, self.sub, self.color = icon, title, sub, color
        self.command, self.menu, self.on_sub = command, menu, on_sub
        self.fav = self.sub_dim = self.hover = self.hover_more = self.hover_sub = False
        self.glow, self.progress, self.image = None, None, ""
        self.setFixedSize(CELL_W, CELL_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.hide()

    def thumb(self):
        return QRectF((CELL_W - THUMB) / 2, 12, THUMB, THUMB)

    def more_rect(self):
        t = self.thumb()
        return QRectF(t.right() - 24, t.top() + 4, 20, 20)

    def sub_rect(self):
        return QRectF(2, 121, CELL_W - 4, 18)

    def set_info(self, icon=None, title=None, sub=None, fav=None, sub_dim=None, image=None):
        for k, v in dict(icon=icon, title=title, sub=sub, fav=fav, sub_dim=sub_dim, image=image).items():
            if v is not None:
                setattr(self, k, v)
        self.update()

    def set_glow(self, c):
        if c != self.glow:
            self.glow = c
            self.update()

    def set_progress(self, v):
        if (v is None) != (self.progress is None) or (v is not None and abs(v - self.progress) > .003):
            self.progress = v
            self.update()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = self.hover_more = self.hover_sub = False
        self.update()

    def mouseMoveEvent(self, e):
        pos = e.position()
        hm = bool(self.menu) and self.more_rect().contains(pos)
        hs = bool(self.on_sub) and self.sub_rect().contains(pos)
        if (hm, hs) != (self.hover_more, self.hover_sub):
            self.hover_more, self.hover_sub = hm, hs
            self.update()

    def mousePressEvent(self, e):
        pos = e.position()
        if e.button() == Qt.RightButton and self.menu:
            self.menu(e.globalPosition().toPoint())
        elif e.button() == Qt.LeftButton:
            if self.menu and self.more_rect().contains(pos):
                self.menu(self.mapToGlobal(self.more_rect().bottomLeft().toPoint()))
            elif self.on_sub and self.sub_rect().contains(pos):
                self.on_sub()
            elif self.command:
                self.command()

    def paint_thumb(self, p, t):
        pm = load_pix(getattr(self, "image", ""))
        if pm:
            return draw_cover(p, pm, t, 8)
        g = QLinearGradient(t.topLeft(), t.bottomRight())
        g.setColorAt(0, qc(mix(self.color, "#3a3c3c", .3)))
        g.setColorAt(1, qc(mix(self.color, "#000000", .7)))
        path = rpath(t, 8)
        p.fillPath(path, g)
        p.setFont(efont(t.width() * .3))
        p.setPen(qc("#ffffff"))
        p.drawText(t, Qt.AlignCenter, self.icon)
        return path

    def paintEvent(self, e):
        p = painter(self)
        t = self.thumb()
        if self.hover:
            t = t.adjusted(-2, -2, 2, 2)
        if self.glow:
            for i in range(7, 0, -1):
                p.setPen(QPen(qc(self.glow, .07 * (8 - i)), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(t.adjusted(-i * 1.3, -i * 1.3, i * 1.3, i * 1.3), 8 + i, 8 + i)
        path = self.paint_thumb(p, t)
        if self.glow:
            p.setPen(QPen(qc(self.glow), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        elif self.hover:
            p.setPen(QPen(qc("#ffffff", .55), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        if self.progress is not None:
            p.save()
            p.setClipPath(path)
            p.fillRect(QRectF(t.left(), t.bottom() - 4, t.width(), 4), qc("#000000", .55))
            p.fillRect(QRectF(t.left(), t.bottom() - 4, t.width() * self.progress, 4), qc(self.glow or CYAN))
            p.restore()
        if self.fav:
            p.setFont(ifont(10))
            p.setPen(qc(YELLOW))
            p.drawText(QRectF(t.left() + 4, t.top() + 4, 18, 18), Qt.AlignCenter, G["star"])
        if self.menu and self.hover:
            m = self.more_rect()
            p.setPen(Qt.NoPen)
            p.setBrush(qc(CYAN) if self.hover_more else qc("#000000", .6))
            p.drawEllipse(m)
            p.setFont(ifont(9))
            p.setPen(qc(DARK_TXT if self.hover_more else "#ffffff"))
            p.drawText(m, Qt.AlignCenter, G["more"])
        f = font(9, QFont.Bold)
        p.setFont(f)
        p.setPen(qc(TEXT))
        p.drawText(QRectF(2, 102, CELL_W - 4, 18), Qt.AlignCenter,
                   QFontMetrics(f).elidedText(self.title, Qt.ElideRight, CELL_W - 6))
        p.setFont(font(9))
        p.setPen(qc(CYAN if self.hover_sub else DIM if self.sub_dim else "#8f9395"))
        p.drawText(self.sub_rect(), Qt.AlignCenter, self.sub)


class SoundTile(Tile):
    def __init__(self, sound, app, show_board=False, parent=None):
        self.sound, self.app, self.show_board = sound, app, show_board
        super().__init__(sound.opts.icon, sound.name, "", color_for(sound.path.stem),
                         command=lambda: app.play_sound(sound),
                         menu=lambda pos: app.sound_menu(sound, pos),
                         on_sub=None if show_board else lambda: app.open_sound_settings(sound, record=True),
                         parent=parent)
        self.update_labels()

    def update_labels(self):
        o = self.sound.opts
        if self.show_board:
            sub, dim = self.sound.board, False
        elif o.hotkey:
            sub, dim = key_label(*o.hotkey), False
        else:
            sub, dim = "Ajouter raccourci", True
        self.set_info(icon=o.icon, title=self.sound.name, sub=sub, fav=o.favorite, sub_dim=dim,
                      image=getattr(o, "image", "") or "")

    def refresh(self):
        mixer = self.app.engine.mixer
        st = mixer.state(self.sound)
        self.set_glow(None if st is None else CYAN if st == "playing" else YELLOW)
        self.set_progress(mixer.progress(self.sound) if st else None)


class AddTile(Tile):
    def __init__(self, command, parent=None):
        super().__init__("", "Ajouter", "un son", CARD2, command=command, parent=parent)

    def paint_thumb(self, p, t):
        path = rpath(t, 8)
        p.fillPath(path, qc("#ffffff", .05 if self.hover else .02))
        p.setPen(QPen(qc(CYAN if self.hover else DIM), 1.5, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setFont(ifont(20))
        p.setPen(qc(CYAN if self.hover else MUTED))
        p.drawText(t, Qt.AlignCenter, G["add"])
        return path


class Thumb(QWidget):
    """Aperçu d'une icône de son (fenêtre de réglages)."""

    def __init__(self, icon, color, size=72, parent=None):
        super().__init__(parent)
        self.icon, self.color, self.image = icon, color, ""
        self.setFixedSize(size, size)

    def set_icon(self, ic):
        self.icon = ic
        self.update()

    def set_image(self, path):
        self.image = path or ""
        self.update()

    paint_thumb = Tile.paint_thumb

    def paintEvent(self, e):
        self.paint_thumb(painter(self), QRectF(self.rect()))


class BoardCard(QWidget):
    """Carte de soundboard : couverture 290×150 (image, mosaïque des sons ou dégradé), nom et nombre de sons."""
    W, H, COVER = 290, 206, 150

    def __init__(self, name, icon, count, command, images=(), cover="", menu=None, create=False, parent=None):
        super().__init__(parent)
        self.name, self.icon, self.count, self.command, self.create = name, icon, count, command, create
        self.images, self.cover, self.menu = list(images)[:4], cover, menu
        self.hover = False
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.hide()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.command()
        elif e.button() == Qt.RightButton and self.menu:
            self.menu(e.globalPosition().toPoint())

    def _paint_cover(self, p, r, path):
        pm = load_pix(self.cover)
        if pm:
            draw_cover(p, pm, r, 8)
            return
        pms = [x for x in map(load_pix, self.images) if x]
        if pms:
            p.save()
            p.setClipPath(path)
            if len(pms) == 1:
                draw_cover(p, pms[0], r, 0)
            elif len(pms) == 2:
                for i, pm in enumerate(pms):
                    draw_cover(p, pm, QRectF(r.left() + i * r.width() / 2, r.top(), r.width() / 2, r.height()), 0)
            else:
                cells = [QRectF(r.left() + (i % 2) * r.width() / 2, r.top() + (i // 2) * r.height() / 2,
                                r.width() / 2, r.height() / 2) for i in range(4)]
                for i, cell in enumerate(cells):
                    if i < len(pms):
                        draw_cover(p, pms[i], cell, 0)
                    else:
                        p.fillRect(cell, qc(mix(color_for(self.name), "#000000", .6)))
            p.restore()
            return
        c = color_for(self.name)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, qc(mix(c, "#3a3c3c", .25)))
        g.setColorAt(1, qc(mix(c, "#000000", .72)))
        p.fillPath(path, g)
        p.save()
        p.setClipPath(path)
        p.setPen(QPen(qc("#ffffff", .05), 2))
        for i in range(7):
            x = r.width() * .4 + i * 34
            p.drawLine(QPointF(x, r.bottom()), QPointF(x + 90, r.top()))
        p.restore()
        p.setFont(efont(46))
        p.setPen(qc("#ffffff"))
        p.drawText(r, Qt.AlignCenter, self.icon)

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(0, 0, self.W, self.COVER)
        path = rpath(r, 8)
        if self.create:
            p.fillPath(path, qc("#232525" if self.hover else "#1c1e1e"))
            p.setPen(QPen(qc("#ffffff", .5 if self.hover else .35), 1.6, Qt.SolidLine, Qt.RoundCap))
            c = r.center()
            p.drawLine(QPointF(c.x() - 11, c.y()), QPointF(c.x() + 11, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - 11), QPointF(c.x(), c.y() + 11))
            p.setFont(font(10, QFont.Bold))
            p.setPen(qc(TEXT))
            p.drawText(QRectF(0, self.COVER + 8, self.W, 20), Qt.AlignCenter, "Créer un soundboard")
            return
        self._paint_cover(p, r, path)
        if self.hover:
            p.setPen(QPen(qc("#ffffff", .55), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        f = font(10, QFont.Bold)
        p.setFont(f)
        p.setPen(qc(TEXT))
        p.drawText(QRectF(4, self.COVER + 8, self.W - 8, 20), Qt.AlignCenter,
                   QFontMetrics(f).elidedText(self.name, Qt.ElideRight, self.W - 12))
        txt = f"{self.count} son{'s' if self.count != 1 else ''}"
        f2 = font(9)
        tw = QFontMetrics(f2).horizontalAdvance(txt)
        x = (self.W - tw - 18) / 2
        p.setPen(qc("#9a9ea0"))
        p.setFont(ifont(9))
        p.drawText(QRectF(x, self.COVER + 28, 14, 18), Qt.AlignCenter, G["bolt"])
        p.setFont(f2)
        p.drawText(QRectF(x + 18, self.COVER + 28, tw + 4, 18), Qt.AlignVCenter | Qt.AlignLeft, txt)


# --------------------------------------------------------------------------- #
#  Bandeau (hero), onglets, sélecteur
# --------------------------------------------------------------------------- #
class Hero(QWidget):
    def __init__(self, title, subtitle="", actions=(), height=170, stops=None, light=False, deco="", parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.stops = stops or ("#0bd3e3", "#0f2f5c", "#141033", "#2a1470", "#0bd3e3")
        self.light, self.deco, self.image = light, deco, ""
        self.phase, self.lvl = 0.0, 0.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(4)
        if not light:
            lay.addStretch()
        self.t = label(title, 20 if light else 24, QFont.Black, "#0f1012" if light else "#ffffff")
        self.st = label(subtitle, 10, color="#3a3632" if light else "#d6e4ec")
        lay.addWidget(self.t)
        lay.addWidget(self.st)
        self.st.setVisible(bool(subtitle))
        self.buttons = []
        if actions:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(0, 10, 0, 0)
            for i, (text, glyph, cb) in enumerate(actions):
                if light:
                    b = Btn(text.upper(), glyph, "dark", cb, h=32, size=8.5)
                else:
                    b = Btn(text, glyph, "white" if i == 0 else "glass", cb, h=34, size=9.5)
                row.addWidget(b)
                self.buttons.append(b)
            row.addStretch()
            lay.addLayout(row)
        if light:
            lay.addStretch()

    def set_title(self, title, subtitle=None, stops=None):
        self.t.setText(title)
        if subtitle is not None:
            self.st.setText(subtitle)
            self.st.setVisible(bool(subtitle))
        if stops:
            self.stops = stops
        self.update()

    def set_image(self, path):
        self.image = path or ""
        self.update()

    def animate(self, lvl):
        self.lvl = .7 * self.lvl + .3 * lvl
        self.phase += .09
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(self.rect())
        path = rpath(r, 8)
        p.setClipPath(path)
        if self.light:
            return self._paint_light(p, r)
        pm = load_pix(self.image)
        if pm:  # image de couverture + voile sombre à gauche pour garder le texte lisible
            draw_cover(p, pm, r, 8)
            h = QLinearGradient(r.topLeft(), r.topRight())
            for t, a in ((0, .9), (.3, .8), (.55, .45), (1, .15)):
                h.setColorAt(t, qc("#000000", a))
            p.fillRect(r, h)
            return
        g = QLinearGradient(r.topLeft(), r.topRight())
        for i, c in enumerate(self.stops):
            g.setColorAt(i / (len(self.stops) - 1), qc(c))
        p.fillRect(r, g)
        v = QLinearGradient(r.topLeft(), r.bottomLeft())
        v.setColorAt(0, qc("#000000", 0))
        v.setColorAt(1, qc("#000000", .45))
        p.fillRect(r, v)
        h = QLinearGradient(r.topLeft(), r.topRight())
        for t, a in ((0, .55), (.2, .42), (.4, .22), (.6, .07), (.75, 0)):
            h.setColorAt(t, qc("#000000", a))
        p.fillRect(r, h)
        p.setPen(QPen(qc("#ffffff", .06), 2))
        for i in range(9):
            x = r.width() * .35 + i * 60
            p.drawLine(QPointF(x, r.bottom()), QPointF(x + r.height() * .8, r.top()))
        # barres d'onde animées (suivent le niveau du micro)
        n, x0, x1 = 44, r.width() * .52, r.width() - 34
        bw = (x1 - x0) / n
        amp = .25 + min(1.0, self.lvl * 2.2) * .75
        mid = r.height() * .5
        p.setPen(Qt.NoPen)
        for i in range(n):
            env = math.sin(math.pi * i / (n - 1)) ** .7
            wv = .35 + .65 * abs(math.sin(i * .55 + self.phase) * math.cos(i * .21 - self.phase * .6))
            hh = max(4.0, r.height() * .62 * env * wv * amp)
            p.setBrush(qc("#ffffff", .22 + .3 * env))
            p.drawRoundedRect(QRectF(x0 + i * bw, mid - hh / 2, bw * .5, hh), 2, 2)

    def _paint_light(self, p, r):
        p.fillRect(r, qc("#f5ead7"))
        # décor : anneaux sonores discrets + onde orange animée (suit le micro)
        cx, cy = r.width() - 150, r.height() * .5
        p.setBrush(Qt.NoBrush)
        for i, rad in enumerate((70, 112, 154, 196)):
            p.setPen(QPen(qc("#0f1012", .07 - i * .012), 1.5))
            p.drawEllipse(QPointF(cx, cy), rad, rad)
        n, x0, x1 = 40, r.width() * .56, r.width() * .56 + 240
        bw = (x1 - x0) / n
        amp = .35 + min(1.0, self.lvl * 2.2) * .65
        p.setPen(Qt.NoPen)
        for i in range(n):
            env = math.sin(math.pi * i / (n - 1)) ** .6
            wv = .35 + .65 * abs(math.sin(i * .5 + self.phase) * math.cos(i * .23 - self.phase * .7))
            hh = max(4.0, r.height() * .58 * env * wv * amp)
            grad = QLinearGradient(0, cy - hh / 2, 0, cy + hh / 2)
            grad.setColorAt(0, qc("#ea580c"))
            grad.setColorAt(1, qc("#1c1917"))
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(x0 + i * bw, cy - hh / 2, bw * .55, hh), 2, 2)


class Tabs(QWidget):
    def __init__(self, items, command, parent=None):
        super().__init__(parent)
        self.command, self.btns = command, {}
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)
        self.set_items(items, items[0] if items else None)

    def set_items(self, items, selected):
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.btns = {}
        self.lay.addStretch()
        for it in items:
            b = Btn(it, kind="chip", command=lambda it=it: self.command(it), h=30, size=9.5)
            self.lay.addWidget(b)
            self.btns[it] = b
        self.lay.addStretch()
        self.select(selected)

    def select(self, sel):
        for k, b in self.btns.items():
            b.set_selected(k == sel)


class Segmented(QWidget):
    SEG = 124

    def __init__(self, items, command, glyphs=None, parent=None):
        super().__init__(parent)
        self.items, self.command, self.glyphs, self.sel, self.hov = items, command, glyphs or [], 0, -1
        self.setFixedSize(self.SEG * len(items), 40)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    def _idx(self, x):
        return min(len(self.items) - 1, int(x // self.SEG))

    def mouseMoveEvent(self, e):
        i = self._idx(e.position().x())
        if i != self.hov:
            self.hov = i
            self.update()

    def leaveEvent(self, e):
        self.hov = -1
        self.update()

    def mousePressEvent(self, e):
        self.sel = self._idx(e.position().x())
        self.update()
        self.command(self.items[self.sel])

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(qc(CARD))
        p.drawRoundedRect(r, 20, 20)
        for i, it in enumerate(self.items):
            seg = QRectF(i * self.SEG + 3, 3, self.SEG - 6, 34)
            if i == self.sel:
                p.setBrush(qc("#3d3f3f"))
                p.drawRoundedRect(seg, 17, 17)
            elif i == self.hov:
                p.setBrush(qc("#222424"))
                p.drawRoundedRect(seg, 17, 17)
            f = font(9.5, QFont.Bold)
            tw = QFontMetrics(f).horizontalAdvance(it)
            glyph = self.glyphs[i] if i < len(self.glyphs) else ""
            x = seg.center().x() - (tw + (24 if glyph else 0)) / 2
            col = qc(CYAN if i == self.sel else "#e8e8e8")
            if glyph:
                p.setFont(ifont(11))
                p.setPen(col)
                p.drawText(QRectF(x, seg.top(), 18, seg.height()), Qt.AlignCenter, glyph)
                x += 24
            p.setFont(f)
            p.setPen(col)
            p.drawText(QRectF(x, seg.top(), tw + 4, seg.height()), Qt.AlignVCenter | Qt.AlignLeft, it)


# --------------------------------------------------------------------------- #
#  Barre de contrôle (bas) et panneau de sélection (droite)
# --------------------------------------------------------------------------- #
class RoundBtn(Clickable):
    def __init__(self, glyph, d, kind, command, tip, parent=None):
        super().__init__(parent, command, tip)
        self.glyph, self.kind, self.on, self.d = glyph, kind, False, d
        self.setFixedSize(d, d)

    def set_on(self, v):
        if v != self.on:
            self.on = v
            self.update()

    @staticmethod
    def _draw_mic(p, c, col):
        """Micro de studio stylisé : capsule, grille, étrier, pied."""
        x, y = c.x(), c.y()
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(x - 10, y - 28, 20, 34), 10, 10)          # capsule
        p.setPen(QPen(qc("#ffffff", .22), 1.2))
        for dy in (-20, -14, -8, -2):                                        # grille
            p.drawLine(QPointF(x - 7, y + dy), QPointF(x + 7, y + dy))
        p.setPen(QPen(col, 3.2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(x - 16, y - 18, 32, 32), 180 * 16, 180 * 16)        # étrier
        p.drawLine(QPointF(x, y + 14), QPointF(x, y + 25))                   # pied
        p.drawLine(QPointF(x - 9, y + 26), QPointF(x + 9, y + 26))           # base
        p.setPen(Qt.NoPen)

    def paintEvent(self, e):
        p = painter(self)
        c = QPointF(self.width() / 2, self.height() / 2)
        h = self.hover
        p.setPen(Qt.NoPen)
        if self.kind == "mic":  # gros bouton central : halo cyan, anneau sombre, disque cyan
            r = self.d / 2 - 9
            if self.on:
                halo = QRadialGradient(c, r + 9)
                halo.setColorAt((r + 2) / (r + 9), qc(CYAN, .5))
                halo.setColorAt(1, qc(CYAN, 0))
                p.setBrush(halo)
                p.drawEllipse(c, r + 9, r + 9)
            p.setBrush(qc(PANEL))
            p.drawEllipse(c, r + 4, r + 4)
            if self.on:
                g = QRadialGradient(c - QPointF(r * .3, r * .35), r * 1.5)
                g.setColorAt(0, qc("#7afffa" if h else "#3dfff7"))
                g.setColorAt(1, qc(CYAN))
                bg, fg = g, qc("#052a2c")
            else:
                bg, fg = qc("#3e4040" if h else BTN), qc(MUTED)
            p.setBrush(bg)
            p.drawEllipse(c, r, r)
            self._draw_mic(p, c, fg)
            if not self.on:
                p.setPen(QPen(qc(RED), 3, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(c.x() - r * .45, c.y() - r * .45), QPointF(c.x() + r * .45, c.y() + r * .45))
            return
        r = self.d / 2
        if self.kind == "power":
            bg, fg = (qc("#3e4040" if h else BTN), qc("#ffffff")) if self.on else \
                (qc("#ff4d6d" if h else RED), qc("#ffffff"))
        elif self.kind == "toggle":
            bg, fg = (qc(mix(CYAN, "#000000", .72 if h else .78)), qc(CYAN)) if self.on else \
                (qc("#3e4040" if h else BTN), qc("#ffffff"))
        else:
            bg, fg = qc("#ffffff", .08 if h else 0), qc("#e8e8e8")
        p.setBrush(bg)
        p.drawEllipse(c, r, r)
        p.setFont(ifont(14 if self.kind != "plain" else 9))
        p.setPen(fg)
        p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, self.glyph)


class LastBtn(Clickable):
    def __init__(self, command, parent=None):
        super().__init__(parent, command, "Dernier son joué (clic pour rejouer)")
        self.sound = None
        self.setFixedSize(60, 60)

    def set_sound(self, s):
        self.sound = s
        self.setToolTip(f"Rejouer « {s.name} »" if s else "Aucun son joué")
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(self.rect())
        s = self.sound
        pm = load_pix(getattr(s.opts, "image", "")) if s else None
        if pm:
            draw_cover(p, pm, r, 6)
        elif s:
            c = color_for(s.path.stem)
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, qc(c))
            g.setColorAt(1, qc(mix(c, "#000000", .65)))
            p.fillPath(rpath(r, 6), g)
            p.setFont(efont(20))
            p.setPen(qc("#ffffff"))
            p.drawText(r, Qt.AlignCenter, s.opts.icon)
        else:
            p.fillPath(rpath(r, 6), qc("#eceeee"))
            p.setFont(ifont(18))
            p.setPen(qc("#55585a"))
            p.drawText(r, Qt.AlignCenter, G["music"])
        if self.hover:
            p.setPen(QPen(qc(CYAN), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 6, 6)


class ControlBar(QWidget):
    """Barre du bas : marche/arrêt, gros micro, m'entendre, options, dernier son."""
    W, H = 372, 124

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setFixedSize(self.W, self.H)
        self.power = RoundBtn(G["power"], 48, "power", lambda: app.on_bar("power", self.power),
                              "Audio marche / arrêt", self)
        self.mic = RoundBtn(G["mic"], 108, "mic", lambda: app.on_bar("voice_on", self.mic),
                            "Changeur de voix (Ctrl+Alt+V)", self)
        self.hear = RoundBtn(G["ear"], 48, "toggle", lambda: app.on_bar("hear_myself", self.hear),
                             "M'entendre (Ctrl+Alt+M)", self)
        self.menu = RoundBtn(G["chevron_down"], 24, "plain", lambda: app.on_bar("menu", self.menu),
                             "Plus d'options", self)
        self.last = LastBtn(lambda: app.on_bar("last", self.last), self)
        cy = 62
        self.power.move(30, cy - 24)
        self.mic.move(82, cy - 54)
        self.hear.move(193, cy - 24)
        self.menu.move(252, cy - 12)
        self.last.move(298, cy - 30)
        shadow(self, 30, .7, 6)

    def set_state(self, key, v):
        btn = {"running": self.power, "voice_on": self.mic, "hear_myself": self.hear}.get(key)
        if btn:
            btn.set_on(v)

    def paintEvent(self, e):
        p = painter(self)
        outer = QRectF(10.5, 12.5, 351, 99)
        p.setPen(QPen(qc("#3a3c3c"), 1))
        p.setBrush(qc(CARD2))
        p.drawRoundedRect(outer, 14, 14)
        inner = QRectF(24, 24, 262, 76)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(PANEL))
        p.drawRoundedRect(inner, 38, 38)


class ParamRow(QWidget):
    """Ligne de réglage (Voice Volume, Bass…) : glisser dans la ligne pour changer la valeur."""
    VAL_W = 40

    def __init__(self, text, value, lo, hi, command=None, glyph=None, default=None, parent=None):
        super().__init__(parent)
        self.text, self.value, self.lo, self.hi, self.command, self.glyph = text, value, lo, hi, command, glyph
        self.default = value if default is None else default
        self.hover = False
        self.setFixedHeight(38)
        self.setCursor(Qt.SizeHorCursor)
        self.setToolTip("Glisse ou utilise la molette · double-clic = valeur par défaut")

    def set(self, v):
        self.value = v
        self.update()

    def _bar(self):
        return QRectF(1, 1, self.width() - 2 - self.VAL_W, self.height() - 2)

    def _apply(self, v):
        v = int(max(self.lo, min(self.hi, round(v))))
        if v != self.value:
            self.value = v
            self.update()
            if self.command:
                self.command(v)

    def _from_x(self, x):
        b = self._bar()
        t = max(0.0, min(1.0, (x - b.left()) / b.width()))
        self._apply(self.lo + t * (self.hi - self.lo))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._from_x(e.position().x())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._from_x(e.position().x())

    def mouseDoubleClickEvent(self, e):
        self._apply(self.default)

    def wheelEvent(self, e):
        self._apply(self.value + (2 if e.angleDelta().y() > 0 else -2))

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        path = rpath(r, 4)
        p.save()
        p.setClipPath(path)
        p.fillRect(r, qc("#070808"))
        b = self._bar()
        t = (self.value - self.lo) / (self.hi - self.lo)
        p.fillRect(QRectF(b.left(), 0, b.width() * t, r.height() + 1), qc("#3c3e3e" if self.hover else "#363838"))
        p.fillRect(QRectF(r.right() - self.VAL_W, 0, 1, r.height() + 1), qc("#4c4d4d"))
        p.restore()
        p.setPen(QPen(qc("#4c4d4d"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        x = 14
        p.setPen(qc(TEXT))
        if self.glyph:
            p.setFont(ifont(13))
            p.drawText(QRectF(x, 0, 22, r.height()), Qt.AlignCenter, self.glyph)
            x += 30
        p.setFont(font(10, QFont.DemiBold))
        p.drawText(QRectF(x, 0, 120, r.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text)
        p.setFont(font(10.5, QFont.Bold))
        p.drawText(QRectF(r.width() - self.VAL_W, 0, self.VAL_W, r.height()), Qt.AlignCenter, str(int(self.value)))


class VoicePanel(QWidget):
    """En-tête du panneau de droite : bannière, avatar de la voix, nom, raccourci."""
    H = 214

    def __init__(self, on_lab, on_random, parent=None):
        super().__init__(parent)
        self.icon, self.title, self.sub, self.color = "🎙️", "", "", CYAN
        self.setFixedHeight(self.H)
        self.b_lab = Btn(glyph=G["mixer"], kind="grp", command=on_lab, h=36, size=12, tip="Réglages audio",
                         parent=self)
        self.b_rand = Btn(glyph=G["shuffle"], kind="grp", command=on_random, h=36, size=12,
                          tip="Voix aléatoire", parent=self)
        self.b_hk = Btn("", G["hotkey"], "panel", h=28, size=8.5, parent=self)
        self.b_hk.setToolTip("Raccourci global de cette voix")

    def resizeEvent(self, e):
        w = self.width()
        self.b_lab.setFixedWidth(36)
        self.b_rand.setFixedWidth(36)
        self.b_lab.move(w - 86, 14)
        self.b_rand.move(w - 48, 14)
        self.b_hk.move(w - self.b_hk.width() - 12, 168)

    def set_info(self, icon, title, sub, color, hotkey=""):
        self.icon, self.title, self.sub, self.color = icon, title, sub, color
        self.b_hk.setText(hotkey or "Ajouter raccourci")
        self.b_hk.fg = None if hotkey else MUTED
        self.b_hk.setFixedWidth(self.b_hk.sizeHint().width())
        self.resizeEvent(None)
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        w = self.width()
        banner = QRectF(0, 0, w, 120)
        p.save()
        p.setClipPath(rpath(QRectF(0, 0, w, 140), 8))
        g = QLinearGradient(banner.topLeft(), banner.bottomRight())
        g.setColorAt(0, qc(mix(self.color, "#000000", .5)))
        g.setColorAt(.6, qc(mix(self.color, "#0a1618", .8)))
        g.setColorAt(1, qc("#0c1214"))
        p.fillRect(banner, g)
        p.setPen(QPen(qc("#ffffff", .05), 1.5))
        for i in range(10):
            x = i * 36
            p.drawLine(QPointF(x, banner.bottom()), QPointF(x + 70, banner.top()))
        p.setOpacity(.28)
        p.setFont(efont(84))
        p.drawText(QRectF(w * .28, 2, w * .62, 150), Qt.AlignCenter, self.icon)
        p.setOpacity(1)
        p.restore()
        # groupe de boutons (haut droite)
        p.setPen(Qt.NoPen)
        p.setBrush(qc("#2a2c2c"))
        p.drawRoundedRect(QRectF(w - 90, 10, 80, 44), 8, 8)
        # avatar rond à cheval sur la bannière
        c = QPointF(52, 120)
        rg = QRadialGradient(c - QPointF(12, 14), 56)
        rg.setColorAt(0, qc(mix(self.color, "#ffffff", .15)))
        rg.setColorAt(1, qc(mix(self.color, "#000000", .75)))
        p.setPen(QPen(qc(PANEL), 4))
        p.setBrush(rg)
        p.drawEllipse(c, 40, 40)
        p.setFont(efont(24))
        p.setPen(qc("#ffffff"))
        p.drawText(QRectF(c.x() - 40, c.y() - 40, 80, 80), Qt.AlignCenter, self.icon)
        f = font(11, QFont.Bold)
        p.setFont(f)
        p.drawText(QRectF(12, 166, w - 160, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f).elidedText(self.title, Qt.ElideRight, int(w - 160)))
        fi = font(9)
        fi.setItalic(True)
        p.setFont(fi)
        p.setPen(qc(MUTED))
        p.drawText(QRectF(12, 186, w - 160, 18), Qt.AlignLeft | Qt.AlignVCenter, self.sub)
        p.fillRect(QRectF(0, self.H - 1, w, 1), qc("#2a2c2c"))


class MixFader(QWidget):
    """Fader vertical de table de mixage : colonne de points (VU-mètre), rail épais, curseur, valeur en bas."""
    W, H = 76, 296
    DX, CX, TOP, BOT = 12, 50, 24, 250

    def __init__(self, value, hi=100, color=CYAN, command=None, meter=False, default=100, parent=None):
        super().__init__(parent)
        self.value, self.hi, self.color, self.cmd = value, hi, color, command
        self.meter, self.lvl, self.default, self.hover = meter, 0.0, default, False
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Glisse ou molette · double-clic = valeur par défaut")

    def _y(self):
        return self.BOT - self.value / self.hi * (self.BOT - self.TOP)

    def get(self):
        return self.value

    def set(self, v):
        v = max(0, min(self.hi, round(v)))
        if v != self.value:
            self.value = v
            self.update()

    def set_level(self, lvl):
        if abs(lvl - self.lvl) > .02:
            self.lvl = lvl
            self.update()

    def _apply(self, v):
        v = int(max(0, min(self.hi, round(v))))
        if v != self.value:
            self.value = v
            self.update()
            if self.cmd:
                self.cmd(v)

    def _from_y(self, y):
        self._apply((self.BOT - y) / (self.BOT - self.TOP) * self.hi)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._from_y(e.position().y())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._from_y(e.position().y())

    def mouseDoubleClickEvent(self, e):
        self._apply(self.default)

    def wheelEvent(self, e):
        self._apply(self.value + (2 if e.angleDelta().y() > 0 else -2))

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def paintEvent(self, e):
        p = painter(self)
        cx, top, bot, y, dx = self.CX, self.TOP, self.BOT, self._y(), self.DX
        # colonne de points (VU-mètre vert pour le micro)
        n = int((bot - top) / 8) + 1
        lit = round(self.lvl * n) if self.meter else 0
        p.setPen(Qt.NoPen)
        for i in range(n):
            p.setBrush(qc(GREEN) if i < lit else qc("#3a3c3c"))
            p.drawEllipse(QPointF(dx, bot - i * 8), 2, 2)
        if lit:
            p.setPen(QPen(qc(GREEN), 1.2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(dx - 7, bot - (lit - 1) * 8 - 7, 14, (lit - 1) * 8 + 14), 7, 7)
            p.setPen(Qt.NoPen)
        # rail épais
        p.setBrush(qc("#4a4c4c"))
        p.drawRoundedRect(QRectF(cx - 5, top - 6, 10, bot - top + 12), 5, 5)
        # remplissage lumineux
        for k, a in ((9, .09), (6, .18)):
            p.setBrush(qc(self.color, a))
            p.drawRoundedRect(QRectF(cx - k, y, 2 * k, bot + 4 - y), k, k)
        fill = QLinearGradient(0, y, 0, bot)
        fill.setColorAt(0, qc(mix(self.color, "#ffffff", .25)))
        fill.setColorAt(1, qc(self.color))
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(cx - 3, y, 6, bot + 4 - y), 3, 3)
        # curseur : clair pour le casque (jaune), sombre pour la sortie (cyan)
        k = QRectF(cx - 16, y - 19, 32, 38)
        kg = QLinearGradient(k.topLeft(), k.bottomLeft())
        if self.color == YELLOW:
            for t, c in ((0, "#e6e8e8" if self.hover else "#d6d8d8"), (.44, "#c6c9c9"), (.56, "#a6a9a9"), (1, "#cbcece")):
                kg.setColorAt(t, qc(c))
            band, border = "#767979", "#9c9f9f"
        else:
            for t, c in ((0, "#5c5e5e" if self.hover else "#505252"), (.44, "#474949"), (.56, "#393b3b"), (1, "#4a4c4c")):
                kg.setColorAt(t, qc(c))
            band, border = self.color, "#262828"
        p.setBrush(kg)
        p.setPen(QPen(qc(border), 1))
        p.drawRoundedRect(k, 3, 3)
        p.setPen(QPen(qc("#000000", .16), 1))
        for dy in (-12, -8, 8, 12):
            p.drawLine(QPointF(k.left() + 4, y + dy), QPointF(k.right() - 4, y + dy))
        p.setPen(QPen(qc(band), 3))
        p.drawLine(QPointF(k.left() + 3, y), QPointF(k.right() - 3, y))
        # valeur + petit haut-parleur sous la colonne de points
        vb = QRectF(cx - 23, 258, 46, 24)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(CARD2))
        p.drawRoundedRect(vb, 4, 4)
        p.setFont(font(10, QFont.Bold))
        p.setPen(qc(TEXT))
        p.drawText(vb, Qt.AlignCenter, str(int(self.value)))
        p.setFont(ifont(10))
        p.setPen(qc("#c4c7c7"))
        p.drawText(QRectF(dx - 12, vb.top(), 24, vb.height()), Qt.AlignCenter, G["speaker"])


class UnderTabs(QWidget):
    """Onglets soulignés (page Réglages)."""

    def __init__(self, items, command, parent=None):
        super().__init__(parent)
        self.items, self.command, self.sel, self.hov = items, command, 0, -1
        self.setFixedHeight(50)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._rects = []

    def _layout(self):
        x, self._rects = 0, []
        for glyph, text in self.items:
            w = 16 + 22 + 10 + QFontMetrics(font(11)).horizontalAdvance(text) + 18
            self._rects.append(QRectF(x, 0, w, 48))
            x += w
        return self._rects

    def _at(self, pos):
        return next((i for i, r in enumerate(self._layout()) if r.contains(pos)), -1)

    def mouseMoveEvent(self, e):
        i = self._at(e.position())
        if i != self.hov:
            self.hov = i
            self.update()

    def leaveEvent(self, e):
        self.hov = -1
        self.update()

    def mousePressEvent(self, e):
        i = self._at(e.position())
        if i >= 0:
            self.sel = i
            self.update()
            self.command(i)

    def paintEvent(self, e):
        p = painter(self)
        p.fillRect(QRectF(0, self.height() - 1, self.width(), 1), qc("#262828"))
        for i, (r, (glyph, text)) in enumerate(zip(self._layout(), self.items)):
            on = i == self.sel
            col = qc(CYAN if on else "#ffffff" if i == self.hov else "#dcdcdc")
            p.setFont(ifont(14))
            p.setPen(col)
            p.drawText(QRectF(r.left() + 16, 0, 22, 48), Qt.AlignCenter, glyph)
            p.setFont(font(11))
            p.drawText(QRectF(r.left() + 48, 0, r.width() - 48, 48), Qt.AlignVCenter | Qt.AlignLeft, text)
            if on:
                p.fillRect(QRectF(r.left(), self.height() - 2, r.width(), 2), qc(CYAN))


class ElideCombo(QComboBox):
    """Liste déroulante dont le texte trop long est tronqué avec « … »."""

    def paintEvent(self, e):
        p = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = self.fontMetrics().elidedText(opt.currentText, Qt.ElideRight, self.width() - 44)
        p.drawComplexControl(QStyle.CC_ComboBox, opt)
        p.drawControl(QStyle.CE_ComboBoxLabel, opt)


class SearchEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("search")
        self.setPlaceholderText(PLACEHOLDER)
        self.addAction(glyph_icon(G["search"], "#c4c4cc", 14), QLineEdit.LeadingPosition)
        self.setClearButtonEnabled(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setFixedWidth(380)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clear()
            self.clearFocus()
        else:
            super().keyPressEvent(e)


# --------------------------------------------------------------------------- #
#  Fenêtre de réglages d'un son
# --------------------------------------------------------------------------- #
class SoundSettings(QDialog):
    def __init__(self, app, sound, record=False):
        super().__init__(app)
        self.app, self.sound = app, sound
        o = sound.opts
        self.setWindowTitle(f"Réglages — {sound.name}")
        self.setModal(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.hotkey = list(o.hotkey) if o.hotkey else []
        self.icon, self.mode, self.recording = o.icon, o.mode, False
        self.image = getattr(o, "image", "") or ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(16)
        self.preview = Thumb(o.icon, color_for(sound.path.stem), 72)
        head.addWidget(self.preview)
        col = QVBoxLayout()
        col.addStretch()
        col.addWidget(label("Réglages du son", 17, QFont.Black))
        col.addWidget(label(f"{sound.board} · {sound.path.name}", 9, color=MUTED))
        imgs = QHBoxLayout()
        imgs.setSpacing(6)
        imgs.addWidget(Btn("Mettre une image…", G["image"], "panel", self._pick_image, h=28, size=9))
        imgs.addWidget(Btn("Retirer l'image", kind="panel", command=lambda: self._set_image(""), h=28, size=9))
        imgs.addStretch()
        col.addSpacing(4)
        col.addLayout(imgs)
        col.addStretch()
        head.addLayout(col)
        head.addStretch()
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        lay.addLayout(grid)

        def row(r, text, w):
            lb = label(text, 10, color=MUTED)
            grid.addWidget(lb, r, 0, Qt.AlignLeft | Qt.AlignVCenter)
            if isinstance(w, QWidget):
                grid.addWidget(w, r, 1, Qt.AlignLeft)
            else:
                grid.addLayout(w, r, 1, Qt.AlignLeft)

        self.e_name = QLineEdit(sound.name)
        self.e_name.setFixedWidth(360)
        row(0, "Nom", self.e_name)

        icons = QGridLayout()
        icons.setSpacing(4)
        self.icon_btns = {}
        for i, ic in enumerate(ICONS):
            b = QPushButton(ic)
            b.setObjectName("emoji")
            b.setCheckable(True)
            b.setFixedSize(34, 34)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, ic=ic: self._pick_icon(ic))
            icons.addWidget(b, i // 14, i % 14)
            self.icon_btns[ic] = b
        row(1, "Icône", icons)
        self._pick_icon(self.icon)
        self.preview.set_image(self.image)

        self.s_vol = Slider(0, 200, o.volume * 100, length=320, fmt=lambda v: f"{v:.0f} %")
        row(2, "Volume", self.s_vol)

        modes = QGridLayout()
        modes.setSpacing(6)
        self.mode_btns = {}
        for i, (k, text) in enumerate(MODES.items()):
            b = Btn(f"{MODE_BADGE[k]}  {text}", kind="tab", command=lambda k=k: self._pick_mode(k), h=32, size=9)
            modes.addWidget(b, i // 3, i % 3, Qt.AlignLeft)
            self.mode_btns[k] = b
        row(3, "Mode de lecture", modes)
        self._pick_mode(self.mode)

        self.s_fi = Slider(0, 3000, o.fade_in, length=320, res=50, fmt=lambda v: f"{v:.0f} ms")
        row(4, "Fondu d'entrée", self.s_fi)
        self.s_fo = Slider(0, 3000, o.fade_out, length=320, res=50, fmt=lambda v: f"{v:.0f} ms")
        row(5, "Fondu de sortie", self.s_fo)

        tg = QGridLayout()
        tg.setHorizontalSpacing(30)
        self.t_stop = Toggle("Arrêter les autres sons", o.stop_others, width=240)
        self.t_mute = Toggle("Couper les autres sons", o.mute_others, width=240)
        self.t_voice = Toggle("Couper ma voix", o.mute_voice, width=240)
        self.t_fav = Toggle("Favori", o.favorite, width=240)
        for i, t in enumerate((self.t_stop, self.t_mute, self.t_voice, self.t_fav)):
            tg.addWidget(t, i // 2, i % 2)
        row(6, "Options", tg)

        hk = QHBoxLayout()
        hk.setSpacing(8)
        self.l_hk = QLabel()
        self.l_hk.setFixedSize(200, 34)
        self.l_hk.setAlignment(Qt.AlignCenter)
        self.l_hk.setFont(font(10, QFont.DemiBold))
        hk.addWidget(self.l_hk)
        hk.addWidget(Btn("Définir", G["keyboard"], command=self._record, h=34))
        hk.addWidget(Btn("Effacer", command=self._clear_hk, h=34))
        row(7, "Raccourci global", hk)
        self._show_hk()

        foot = QHBoxLayout()
        foot.setContentsMargins(0, 10, 0, 0)
        foot.addWidget(Btn("Tester", G["play"], command=self._test))
        foot.addWidget(Btn("Supprimer", G["delete"], "danger", command=self._delete))
        foot.addStretch()
        foot.addWidget(Btn("Annuler", command=self.reject))
        foot.addWidget(Btn("Enregistrer", G["check"], "primary", command=self._save))
        lay.addLayout(foot)
        if record:
            QTimer.singleShot(60, self._record)

    def _pick_icon(self, ic):
        self.icon = ic
        for k, b in self.icon_btns.items():
            b.setChecked(k == ic)
        self.preview.set_icon(ic)

    def _pick_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        if not f:
            return
        dest_dir = SOUNDS_DIR / "_images"
        dest_dir.mkdir(exist_ok=True)
        src = Path(f)
        dest = dest_dir / f"{self.sound.path.stem}{src.suffix.lower()}"
        i = 1
        while dest.exists() and dest.resolve() != src.resolve():
            dest, i = dest_dir / f"{self.sound.path.stem}_{i}{src.suffix.lower()}", i + 1
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        _PIX.pop(str(dest), None)
        self._set_image(str(dest))

    def _set_image(self, path):
        self.image = path
        self.preview.set_image(path)

    def _pick_mode(self, k):
        self.mode = k
        for m, b in self.mode_btns.items():
            b.set_selected(m == k)

    def _show_hk(self, msg=None, color=None):
        if msg:
            text, col = msg, color
        elif self.recording:
            text, col = "Appuie sur une touche…", YELLOW
        else:
            text, col = (key_label(*self.hotkey) if self.hotkey else "aucun"), CYAN
        self.l_hk.setText(text)
        self.l_hk.setStyleSheet(f"color: {col}; background: {CARD2}; border-radius: 8px;"
                                f"border: 1px solid {YELLOW if self.recording else LINE};")

    def _record(self):
        self.recording = True
        self._show_hk()
        self.setFocus()

    def _clear_hk(self):
        self.hotkey, self.recording = [], False
        self._show_hk()

    def keyPressEvent(self, e):
        if not self.recording:
            return super().keyPressEvent(e)
        if e.key() in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr):
            return
        if e.key() == Qt.Key_Escape:
            self.recording = False
            self._show_hk()
            return
        m = e.modifiers()
        mods = (MOD_CTRL if m & Qt.ControlModifier else 0) | (MOD_SHIFT if m & Qt.ShiftModifier else 0) | \
               (MOD_ALT if m & Qt.AltModifier else 0)
        vk = e.nativeVirtualKey()
        if not (0x70 <= vk <= 0x87 or 0x60 <= vk <= 0x6F) and not mods:
            return self._show_hk("Ajoute Ctrl / Alt / Maj", RED)
        if (mods, vk) in App.RESERVED:
            return self._show_hk("Réservé aux voix", RED)
        self.hotkey, self.recording = [mods, vk], False
        self._show_hk()

    def _apply(self):
        o = self.sound.opts
        default = self.sound.path.stem.replace("_", " ")
        name = self.e_name.text().strip()
        o.name = "" if name == default else name
        o.icon, o.volume, o.mode = self.icon, self.s_vol.get() / 100, self.mode
        o.image = self.image
        o.fade_in, o.fade_out = self.s_fi.get(), self.s_fo.get()
        o.stop_others, o.mute_others = self.t_stop.value, self.t_mute.value
        o.mute_voice, o.favorite = self.t_voice.value, self.t_fav.value
        if self.hotkey:  # un raccourci ne peut appartenir qu'à un seul son
            for s in self.app.sounds:
                if s is not self.sound and s.opts.hotkey and list(s.opts.hotkey) == self.hotkey:
                    s.opts.hotkey = []
        o.hotkey = list(self.hotkey)

    def _test(self):
        self._apply()
        self.app.play_sound(self.sound)

    def _save(self):
        self._apply()
        self.app.library.save()
        self.app.refresh_sound_labels()
        self.app._setup_hotkeys()
        self.accept()

    def _delete(self):
        if self.app.delete_sound(self.sound, self):
            self.accept()


# --------------------------------------------------------------------------- #
#  Application
# --------------------------------------------------------------------------- #
class CableInstaller(QObject):
    """Installe VB-CABLE dans un thread et renvoie l'avancement au thread Qt."""
    progress = Signal(str)
    done = Signal(bool, str)

    def start(self):
        vm.install_vb_cable_async(lambda ok, msg: self.done.emit(ok, msg), self.progress.emit)


class App(QWidget):
    RESERVED = {(MOD_CTRL | MOD_ALT, 0x31 + n) for n in range(9)} | {
        (MOD_CTRL | MOD_ALT, ord("V")), (MOD_CTRL | MOD_ALT, ord("M")), (MOD_CTRL | MOD_SHIFT, ord("S"))}

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Py Mod")
        self.resize(1560, 900)
        self.setMinimumSize(1200, 720)

        self.cfg = self._load_cfg()
        self.engine = Engine()
        self.engine.mic_gain = self.cfg.get("mic_gain", 1.0)
        self.engine.sound_gain = self.cfg.get("sound_gain", 0.8)
        self.engine.hear_myself = self.cfg.get("hear_myself", False)
        self.engine.sounds_to_me = self.cfg.get("sounds_to_me", True)
        for k in GAIN_KEYS:
            setattr(self.engine, k, float(self.cfg.get(k, getattr(self.engine, k))))
        self.eq = list(self.cfg.get("eq", [50, 50, 50]))
        self._apply_eq()

        SOUNDS_DIR.mkdir(exist_ok=True)
        if not any(SOUNDS_DIR.iterdir()):
            from demo_sounds import make_demo_sounds
            make_demo_sounds(SOUNDS_DIR)
        self.library = Library(SOUNDS_DIR, self.engine.sr)
        self.sounds, self.hk = [], None
        self.page, self.history = None, []
        self.pages, self.heroes, self.meters = {}, {}, []
        self.flag_widgets = {"voice_on": [], "hear_myself": [], "sounds_to_me": []}
        self.gain_widgets = {k: [] for k in ("mic_gain", "sound_gain") + GAIN_KEYS}
        self.tiles = {"sounds": {}, "board": {}}
        self.board = ROOT_BOARD
        self.sounds_filter, self.sounds_favs = "Tous", False
        self._running = None
        self.default_mic = vm.DefaultMic()   # micro par défaut Windows (Discord...)
        self.cable = None                    # câble virtuel utilisé (virtualmic.Cable)
        self.installer = None

        self._build_layout()
        self._build_right_panel()
        self._build_voices_page()
        self._build_sounds_page()
        self._build_library_page()
        self._build_board_page()
        self._build_settings_page()
        self.go("voices", push=False)
        for k in self.flag_widgets:
            self.set_flag(k, getattr(self.engine, k))

        self._start_audio()
        self.reload_sounds()
        self.select_voice(self.cfg.get("voice", "normal"))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    # -- config ------------------------------------------------------------
    def _load_cfg(self):
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_cfg(self):
        e = self.engine
        self.cfg.update(voice=e.voice_id if e.voice_id != "custom" else "normal",
                        mic_gain=e.mic_gain, sound_gain=e.sound_gain,
                        hear_myself=e.hear_myself, sounds_to_me=e.sounds_to_me, eq=self.eq,
                        **{k: getattr(e, k) for k in GAIN_KEYS})
        try:
            CONFIG.write_text(json.dumps(self.cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # -- états partagés ----------------------------------------------------
    def set_flag(self, key, v, src=None):
        setattr(self.engine, key, bool(v))
        for w in self.flag_widgets[key]:
            if w is not src:
                w.set(bool(v))
        self.bar.set_state(key, bool(v))

    def flag_toggle(self, key, text, width=236):
        t = Toggle(text, getattr(self.engine, key), width=width)
        t.command = lambda v, t=t: self.set_flag(key, v, t)
        self.flag_widgets[key].append(t)
        return t

    def gain_slider(self, key, hi, **kw):
        s = Slider(0, hi, getattr(self.engine, key) * 100, **kw)
        return self._register_gain(key, s)

    def gain_fader(self, key, hi=100, color=CYAN, **kw):
        v = min(hi, round(getattr(self.engine, key) * 100))
        return self._register_gain(key, MixFader(v, hi, color, default=GAIN_DEFAULTS.get(key, 100), **kw))

    def _register_gain(self, key, w):
        def changed(v, w=w):
            setattr(self.engine, key, v / 100)
            for o in self.gain_widgets[key]:
                if o is not w:
                    o.set(v)
            self._sync_param_rows()
        w.cmd = changed
        self.gain_widgets[key].append(w)
        return w

    def _apply_eq(self):
        self.engine.set_eq(*[(v - 50) / 50 * 12 for v in self.eq])

    def _set_eq(self, i, v):
        self.eq[i] = v
        self._apply_eq()

    def _set_voice_volume(self, v):
        self.engine.voice_gain = v / 100
        for o in self.gain_widgets["voice_gain"]:
            o.set(v)

    def _sync_param_rows(self):
        if hasattr(self, "row_vol"):
            self.row_vol.set(round(self.engine.voice_gain * 100))

    def on_bar(self, key, btn):
        if key == "power":
            if self.engine.streams:
                self.engine.stop()
            else:
                self._apply_devices()
        elif key == "menu":
            m = make_menu(self)
            a = m.addAction("Entendre les sons dans mon casque")
            a.setCheckable(True)
            a.setChecked(self.engine.sounds_to_me)
            a.toggled.connect(lambda v: self.set_flag("sounds_to_me", v))
            m.addAction("Arrêter tous les sons   (Ctrl+Maj+S)", self.engine.mixer.stop_all)
            m.addSeparator()
            m.addAction("Réglages audio", lambda: self.go("settings"))
            pos = btn.mapToGlobal(QPoint(0, 0))
            m.exec(QPoint(pos.x() - 40, pos.y() - m.sizeHint().height() - 14))
        elif key == "last":
            if self.bar.last.sound:
                self.play_sound(self.bar.last.sound)
        else:
            self.set_flag(key, not getattr(self.engine, key))

    # -- squelette ---------------------------------------------------------
    def _build_layout(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QFrame(objectName="topbar")
        top.setFixedHeight(48)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(10, 0, 12, 0)
        tl.setSpacing(2)
        self.btn_more = Btn(glyph=G["more"], kind="icon", command=self._app_menu, h=36, size=11, tip="Menu")
        tl.addWidget(self.btn_more)
        tl.addWidget(Btn(glyph=G["back"], kind="icon", command=self.back, h=36, size=10, tip="Retour"))
        tl.addSpacing(6)
        self.search = SearchEdit()
        self.search.textChanged.connect(lambda _t: self._on_search())
        tl.addWidget(self.search)
        tl.addStretch()
        self.warn = Btn(glyph=G["warning"], kind="warn", command=lambda: self.go("settings"), h=36, size=11)
        self.warn.hide()
        tl.addWidget(self.warn)
        tl.addWidget(Btn(glyph=G["help"], kind="icon", command=self._show_help, h=36, size=11,
                         tip="Raccourcis clavier"))
        tl.addSpacing(10)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        tl.addWidget(self.dot)
        tl.addSpacing(6)
        root.addWidget(top)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        rail = QFrame(objectName="rail")
        rail.setFixedWidth(56)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(8, 10, 8, 12)
        rl.setSpacing(8)
        rl.addWidget(Logo(), 0, Qt.AlignHCenter)
        rl.addSpacing(4)
        self.nav = {}
        for key, glyph, tip in (("voices", "voices", "Voix"), ("sounds", "sounds", "Tous les sons"),
                                ("library", "library", "Mes soundboards"),
                                ("settings", "settings", "Réglages audio")):
            b = RailBtn(G[glyph], lambda k=key: self.go(k), tip)
            rl.addWidget(b, 0, Qt.AlignHCenter)
            self.nav[key] = b
        sep = QFrame()
        sep.setFixedSize(32, 1)
        sep.setStyleSheet("background: #2e3030;")
        rl.addSpacing(2)
        rl.addWidget(sep, 0, Qt.AlignHCenter)
        rl.addSpacing(2)
        self.rail_boards = QVBoxLayout()
        self.rail_boards.setSpacing(8)
        rl.addLayout(self.rail_boards)
        rl.addStretch()
        self.board_icons = {}
        body.addWidget(rail)

        self.center = QFrame(objectName="center")
        cl = QVBoxLayout(self.center)
        cl.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        cl.addWidget(self.stack)
        body.addWidget(self.center, 1)
        self.bar = ControlBar(self, self.center)
        self.center.installEventFilter(self)

        self.right = QFrame(objectName="right")
        self.right.setFixedWidth(294)
        rlay = QVBoxLayout(self.right)
        rlay.setContentsMargins(2, 10, 8, 8)
        card = QFrame(objectName="rightcard")
        rlay.addWidget(card)
        self.right_lay = QVBoxLayout(card)
        self.right_lay.setContentsMargins(0, 0, 0, 14)
        self.right_lay.setSpacing(6)
        body.addWidget(self.right)

    def eventFilter(self, obj, ev):
        if obj is self.center and ev.type() == QEvent.Resize:
            self.bar.move((self.center.width() - self.bar.width()) // 2, self.center.height() - self.bar.height() - 18)
            self.bar.raise_()
        return False

    def _app_menu(self):
        m = make_menu(self)
        m.addAction("Ouvrir le dossier des sons", lambda: os.startfile(SOUNDS_DIR))
        m.addAction("Recharger les sons", self.reload_sounds)
        m.addAction("Raccourcis clavier", self._show_help)
        m.addSeparator()
        m.addAction("Quitter", self.close)
        m.exec(self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height() + 4)))

    def _show_help(self):
        QMessageBox.information(self, "Raccourcis clavier", (
            "Raccourcis globaux (marchent aussi en jeu) :\n\n"
            "Ctrl+Alt+1…9      choisir une voix\n"
            "Ctrl+Alt+V          activer / couper le changeur de voix\n"
            "Ctrl+Alt+M         m'entendre\n"
            "Ctrl+Maj+S         arrêter tous les sons\n\n"
            "Chaque son peut avoir son propre raccourci : clique sur « Ajouter raccourci » "
            "sous le son, ou clic droit → Définir un raccourci."))

    def _build_right_panel(self):
        r = self.right_lay
        self.sel = VoicePanel(lambda: self.go("settings"), self._random_voice)
        r.addWidget(self.sel)
        r.addSpacing(10)
        rows = QVBoxLayout()
        rows.setContentsMargins(16, 0, 16, 0)
        rows.setSpacing(6)
        self.row_vol = ParamRow("Voice Volume", round(self.engine.voice_gain * 100), 0, 200,
                                self._set_voice_volume, G["speaker"], default=100)
        rows.addWidget(self.row_vol)
        for i, name in enumerate(("Bass", "Mid", "Treble")):
            rows.addWidget(ParamRow(name, self.eq[i], 0, 100, lambda v, i=i: self._set_eq(i, v), default=50))
        r.addLayout(rows)
        r.addStretch()

    # -- navigation --------------------------------------------------------
    def go(self, key, push=True):
        if push and self.page and self.page != key:
            self.history.append((self.page, self.board))
            self.history = self.history[-30:]
        self.stack.setCurrentWidget(self.pages[key])
        self.page = key
        for k, b in self.nav.items():
            b.set_selected(k == key or (key == "board" and k == "library"))
        self.sel.b_lab.set_selected(key == "settings")
        for name, b in self.board_icons.items():
            b.set_selected(key == "board" and name == self.board)

    def back(self):
        if self.history:
            page, board = self.history.pop()
            if page == "board":
                self.open_board(board, push=False)
            else:
                self.go(page, push=False)

    def _page(self, key, hero=None):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 10, 14, 0)
        lay.setSpacing(0)
        h = None
        if hero:
            h = Hero(**hero)
            lay.addWidget(h)
            self.heroes[key] = h
        self.stack.addWidget(w)
        self.pages[key] = w
        return w, lay, h

    def _on_search(self):
        self._layout_voices()
        self._layout_sounds()
        self._layout_board()

    def _query(self):
        return self.search.text().lower().strip()

    # -- page Voix ---------------------------------------------------------
    def _build_voices_page(self):
        _, lay, _ = self._page("voices", dict(
            title="Choisis ta voix", subtitle="Clique sur une voix pour l'appliquer en direct · Ctrl+Alt+1…9",
            actions=[("Voix aléatoire", G["shuffle"], self._random_voice)],
            stops=("#7c3aed", "#1e1442", "#0d1830", "#0e4d6b", "#0bd3e3")))
        cats = ["Toutes"] + list(dict.fromkeys(c for _, _, _, c, _ in VOICES))
        self.voice_tabs = Tabs(cats, self._filter_voices)
        lay.addSpacing(20)
        lay.addWidget(self.voice_tabs)
        lay.addSpacing(16)
        self.voice_grid = TileGrid(Avatar.W, Avatar.H)
        lay.addWidget(scroll_area(self.voice_grid), 1)
        self.voice_tiles = {}
        for n, (vid, name, icon, cat, _) in enumerate(VOICES):
            t = Avatar(icon, name, f"Ctrl+Alt+{n + 1}" if n < 9 else cat, CAT_COLORS.get(cat, PURPLE),
                       command=lambda v=vid: self.select_voice(v), parent=self.voice_grid)
            t.category = cat
            self.voice_tiles[vid] = t
        self._cat = "Toutes"
        self._layout_voices()

    def _layout_voices(self):
        if not hasattr(self, "voice_tiles"):
            return
        q = self._query()
        self.voice_grid.set_widgets([t for t in self.voice_tiles.values()
                                     if self._cat in ("Toutes", t.category) and (not q or q in t.title.lower())])

    def _filter_voices(self, cat):
        self._cat = cat
        self.voice_tabs.select(cat)
        self._layout_voices()

    def _random_voice(self):
        self.select_voice(random.choice([v for v, *_ in VOICES if v != self.engine.voice_id]))

    def select_voice(self, vid):
        info = {v: (n, i, c) for v, n, i, c, _ in VOICES}
        if vid not in info:
            vid = "normal"
        self.engine.set_voice(vid)
        for k, t in self.voice_tiles.items():
            t.set_selected(k == vid)
        name, icon, cat = info[vid]
        idx = [v for v, *_ in VOICES].index(vid)
        self.sel.set_info(icon, name, cat, CAT_COLORS.get(cat, MAGENTA),
                          key_label(MOD_CTRL | MOD_ALT, 0x31 + idx) if idx < 9 else "")

    # -- page Sons ---------------------------------------------------------
    def _build_sounds_page(self):
        _, lay, _ = self._page("sounds", dict(
            title="Tes sons, prêts à balancer !",
            subtitle="Clic = jouer · clic droit ou ⋯ = options du son. Ajoute tes propres fichiers et images.",
            actions=[("Charger un son", None, self._add_sounds)], height=178, light=True))
        self.seg = Segmented([ALL, FAVS], self._seg_changed, glyphs=[G["wave"], G["star"]])
        lay.addSpacing(20)
        lay.addWidget(self.seg, 0, Qt.AlignHCenter)
        lay.addSpacing(20)
        self.sound_tabs = Tabs(["Tous"], self._filter_sounds)
        lay.addWidget(self.sound_tabs)
        lay.addSpacing(26)
        self.sound_grid = TileGrid(CELL_W, CELL_H)
        lay.addWidget(scroll_area(self.sound_grid), 1)

    def _seg_changed(self, it):
        self.sounds_favs = it == FAVS
        self._layout_sounds()

    def _filter_sounds(self, b):
        self.sounds_filter = b
        self.sound_tabs.select(b)
        self._layout_sounds()

    def _matches(self, s):
        q = self._query()
        return not q or q in s.name.lower()

    def _layout_sounds(self):
        tiles = self.tiles["sounds"]
        vis = [s for s in self.sounds if s in tiles and self._matches(s)
               and (not self.sounds_favs or s.opts.favorite) and self.sounds_filter in ("Tous", s.board)]
        vis.sort(key=lambda s: not s.opts.favorite)
        self.sound_grid.set_widgets([tiles[s] for s in vis])

    # -- page Mes soundboards ----------------------------------------------
    def _build_library_page(self):
        _, lay, _ = self._page("library")
        lay.addSpacing(16)
        lay.addWidget(label("Mes soundboards", 18, QFont.Black))
        lay.addSpacing(18)
        self.lib_grid = TileGrid(BoardCard.W + 20, BoardCard.H + 30)
        lay.addWidget(scroll_area(self.lib_grid), 1)
        self.lib_cards = []

    def _board_icon(self, b):
        return next((s.opts.icon for s in self.sounds if s.board == b), "🎵")

    def _board_images(self, b):
        return [s.opts.image for s in self.sounds if s.board == b and getattr(s.opts, "image", "")]

    def _build_library(self):
        for c in self.lib_cards:
            c.deleteLater()
        self.lib_cards = [BoardCard(b, self._board_icon(b), sum(s.board == b for s in self.sounds),
                                    lambda b=b: self.open_board(b), images=self._board_images(b),
                                    cover=self.library.board_image(b),
                                    menu=lambda pos, b=b: self._board_menu(b, pos), parent=self.lib_grid)
                          for b in self.library.boards]
        self.lib_cards.append(BoardCard("", "", 0, self._new_board, create=True, parent=self.lib_grid))
        self.lib_grid.set_widgets(self.lib_cards)

    # -- page d'un soundboard ----------------------------------------------
    def _build_board_page(self):
        _, lay, self.board_hero = self._page("board", dict(
            title=ROOT_BOARD, height=210,
            actions=[("Charger un son", G["upload"], self._add_sounds), ("Dossier", G["folder"], self._open_folder),
                     ("", G["more"], self._board_menu)]))
        lay.addSpacing(16)
        self.board_grid = TileGrid(CELL_W, CELL_H)
        lay.addWidget(scroll_area(self.board_grid), 1)
        self.add_tile = AddTile(self._add_sounds, parent=self.board_grid)

    def open_board(self, b, push=True):
        self.board = b
        c = color_for(b)
        n = sum(s.board == b for s in self.sounds)
        self.board_hero.set_title(b, f"{n} son{'s' if n != 1 else ''} · clique sur un son pour le jouer",
                                  stops=(mix(c, "#000000", .2), mix(c, "#000000", .65), "#101016",
                                         mix(c, "#000000", .55), mix(c, "#000000", .15)))
        self.board_hero.set_image(self.library.board_image(b))
        self._layout_board()
        self.go("board", push=push)

    def _layout_board(self):
        tiles = self.tiles["board"]
        vis = [tiles[s] for s in self.sounds if s.board == self.board and s in tiles and self._matches(s)]
        self.board_grid.set_widgets(vis + [self.add_tile])

    def _board_menu(self, board=None, pos=None):
        """Menu d'un soundboard : depuis le bouton ⋯ de la bannière, ou clic droit sur une carte."""
        b = board or self.board
        m = make_menu(self)
        if board:
            m.addAction("Ouvrir", lambda: self.open_board(b))
        m.addAction("Ouvrir le dossier", lambda: os.startfile(self.library.board_dir(b)))
        m.addSeparator()
        m.addAction("Image du soundboard…", lambda: self._pick_board_image(b))
        if self.library.board_image(b):
            m.addAction("Retirer l'image", lambda: self._set_board_image(b, ""))
        if b != ROOT_BOARD:
            m.addSeparator()
            m.addAction("Renommer…", lambda: self._rename_board(b))
            m.addAction("Supprimer le soundboard", lambda: self._delete_board(b))
        if pos is None:
            btn = self.board_hero.buttons[-1]
            pos = btn.mapToGlobal(QPoint(0, btn.height() + 4))
        m.exec(pos)

    def _pick_board_image(self, b):
        f, _ = QFileDialog.getOpenFileName(self, "Image du soundboard", "",
                                           "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        if not f:
            return
        dest_dir = SOUNDS_DIR / "_images"
        dest_dir.mkdir(exist_ok=True)
        src = Path(f)
        dest = dest_dir / f"board_{b}{src.suffix.lower()}"
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        _PIX.pop(str(dest), None)
        self._set_board_image(b, str(dest))

    def _set_board_image(self, b, path):
        self.library.set_board_image(b, path)
        self._build_library()
        if self.page == "board" and self.board == b:
            self.board_hero.set_image(path)

    def _ask_text(self, title, text, value=""):
        v, ok = QInputDialog.getText(self, title, text, QLineEdit.Normal, value)
        return v if ok else None

    def _confirm(self, title, text, parent=None):
        return QMessageBox.question(parent or self, title, text) == QMessageBox.Yes

    def _rename_board(self, old=None):
        old = old or self.board
        new = self._ask_text("Renommer", "Nouveau nom :", old)
        new = "".join(c for c in (new or "") if c not in '\\/:*?"<>|').strip()
        if not new or new == old or new == ROOT_BOARD or (SOUNDS_DIR / new).exists():
            return
        self.library.save()
        cfg = self.library.cfg_path
        data = json.loads(cfg.read_text(encoding="utf-8"))  # garde les réglages des sons
        data["sounds"] = {(new + k[len(old):] if k.startswith(old + "/") else k): v
                          for k, v in data.get("sounds", {}).items()}
        data["boards"] = {(new if k == old else k): v for k, v in data.get("boards", {}).items()}
        (SOUNDS_DIR / old).rename(SOUNDS_DIR / new)
        cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.reload_sounds()
        self.open_board(new, push=False)

    def _delete_board(self, b=None):
        b = b or self.board
        if not self._confirm("Supprimer", f"Supprimer le soundboard « {b} » ?\n"
                                          "(le dossier sera déplacé dans sons/_corbeille)"):
            return
        self.engine.mixer.stop_all()
        trash = SOUNDS_DIR / "_corbeille"
        trash.mkdir(exist_ok=True)
        dest, i = trash / b, 1
        while dest.exists():
            dest, i = trash / f"{b}_{i}", i + 1
        shutil.move(str(SOUNDS_DIR / b), dest)
        self.reload_sounds()
        if self.page == "board":
            self.go("library", push=False)

    def _open_folder(self):
        os.startfile(self.library.board_dir(self.board) if self.page == "board" else SOUNDS_DIR)

    def _new_board(self):
        name = self._ask_text("Nouveau soundboard", "Nom du soundboard :")
        if name:
            name = self.library.new_board(name)
            self.reload_sounds()
            if name in self.library.boards:
                self.open_board(name)

    def _add_sounds(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Charger des sons", "",
                                                "Audio (*.wav *.mp3 *.ogg *.flac *.aiff);;Tous (*.*)")
        if files:
            board = self.board if self.page == "board" else ROOT_BOARD
            self.library.add_files(files, board)
            self.reload_sounds()

    # -- sons --------------------------------------------------------------
    def reload_sounds(self):
        self.engine.mixer.stop_all()
        self.sound_grid.set_widgets([])
        self.board_grid.set_widgets([self.add_tile])
        for ts in self.tiles.values():
            for t in ts.values():
                t.deleteLater()
        self.library.sr = self.engine.sr
        self.library.reload()
        self.sounds = self.library.sounds
        self.tiles = {"sounds": {s: SoundTile(s, self, True, self.sound_grid) for s in self.sounds},
                      "board": {s: SoundTile(s, self, False, self.board_grid) for s in self.sounds}}
        if self.board not in self.library.boards:
            self.board = ROOT_BOARD
        if self.sounds_filter not in ["Tous"] + self.library.boards:
            self.sounds_filter = "Tous"
        if self.bar.last.sound not in self.sounds:
            self.bar.last.set_sound(None)
        self.sound_tabs.set_items(["Tous"] + self.library.boards, self.sounds_filter)
        self._build_rail_boards()
        self._build_library()
        self._layout_sounds()
        self._layout_board()
        if self.page == "board":
            self.open_board(self.board, push=False)
        self._setup_hotkeys()

    def _build_rail_boards(self):
        while self.rail_boards.count():
            it = self.rail_boards.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.board_icons = {}
        for b in self.library.boards[:8]:
            ic = BoardIcon(b, self._board_icon(b), lambda b=b: self.open_board(b))
            ic.set_selected(self.page == "board" and b == self.board)
            self.rail_boards.addWidget(ic, 0, Qt.AlignHCenter)
            self.board_icons[b] = ic
        self.rail_boards.addWidget(RailBtn(G["add"], self._new_board, "Nouveau soundboard"), 0, Qt.AlignHCenter)

    def refresh_sound_labels(self):
        for ts in self.tiles.values():
            for t in ts.values():
                t.update_labels()
        self._layout_sounds()
        self._layout_board()

    def play_sound(self, s):
        self.engine.mixer.trigger(s)
        self.bar.last.set_sound(s)

    def open_sound_settings(self, s, record=False):
        SoundSettings(self, s, record).exec()

    def sound_menu(self, s, pos):
        m = make_menu(self)
        m.addAction("Jouer", lambda: self.play_sound(s))
        m.addAction("Réglages du son…", lambda: self.open_sound_settings(s))
        m.addAction("Définir un raccourci…", lambda: self.open_sound_settings(s, record=True))
        m.addAction("Retirer des favoris" if s.opts.favorite else "Ajouter aux favoris", lambda: self._toggle_fav(s))
        m.addSeparator()
        m.addAction("Supprimer", lambda: self.delete_sound(s))
        m.exec(pos)

    def _toggle_fav(self, s):
        s.opts.favorite = not s.opts.favorite
        self.library.save()
        self.refresh_sound_labels()

    def delete_sound(self, s, parent=None):
        if not self._confirm("Supprimer", f"Supprimer « {s.name} » ?\n(le fichier sera déplacé dans sons/_corbeille)",
                             parent):
            return False
        self.engine.mixer.stop(s)
        self.library.delete(s)
        QTimer.singleShot(0, self.reload_sounds)
        return True

    # -- page Réglages -----------------------------------------------------
    def _build_settings_page(self):
        _, lay, _ = self._page("settings")
        self.set_tabs = UnderTabs([(G["headphone"], "Audio"), (G["keyboard"], "Raccourcis"), (G["help"], "Aide")],
                                  self._settings_tab)
        lay.addWidget(self.set_tabs)
        lay.addSpacing(20)
        self.set_stack = QStackedWidget()
        lay.addWidget(self.set_stack, 1)
        devs = list_devices()
        self.dev_in = [(i, n) for i, n, ni, _ in devs if ni > 0]
        self.dev_out = [(i, n) for i, n, _, no in devs if no > 0]

        # ---- onglet Audio ------------------------------------------------
        audio = QWidget()
        al = QVBoxLayout(audio)
        al.setContentsMargins(0, 0, 10, 120)
        al.setSpacing(18)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.b_basic = Btn("Basic Mode", G["headphone"], "mode", lambda: self._set_mixer_mode(False), h=40, size=10)
        self.b_mixer = Btn("Mixer Mode", G["mixer"], "mode", lambda: self._set_mixer_mode(True), h=40, size=10)
        top.addWidget(self.b_basic)
        top.addWidget(self.b_mixer)
        top.addStretch()
        top.addWidget(Btn("Réinitialiser par défaut", kind="flat", command=self._reset_mixer, h=40, size=10))
        al.addLayout(top)
        self.banner = QLabel(objectName="notice")
        self.banner.setFont(font(9.5))
        self.banner.setWordWrap(True)
        self.banner.hide()
        al.addWidget(self.banner)
        self.b_install = Btn("Installer le micro virtuel", G["mic"], "primary", self._install_cable, h=40, size=10,
                             tip="Télécharge et installe VB-CABLE (gratuit) : Discord et les jeux entendront ta voix "
                                 "modifiée. Windows demande une fois d'accepter le pilote.")
        self.b_install.hide()
        al.addWidget(self.b_install, 0, Qt.AlignLeft)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        al.addLayout(cards)
        self.level_faders = []
        GAP = 30  # écart entre deux faders d'un même canal

        def section(title):
            card = QFrame(objectName="mixcard")
            v = QVBoxLayout(card)
            v.setContentsMargins(14, 10, 14, 14)
            v.setSpacing(12)
            t = label(title.upper(), 9, QFont.Bold, MUTED)
            ft = t.font()
            ft.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            t.setFont(ft)
            t.setAlignment(Qt.AlignCenter)
            v.addWidget(t)
            body = QHBoxLayout()
            body.setSpacing(14)
            v.addLayout(body)
            cards.addWidget(card)
            return card, body

        def vsep(body):
            line = QFrame()
            line.setFixedWidth(1)
            line.setStyleSheet("background: #3a3c3c;")
            body.addWidget(line)

        def channel(body, glyph, title, items=None, none_label=None, glyphs=(), refresh=False):
            col = QVBoxLayout()
            col.setSpacing(12)
            hw = QWidget()
            hw.setFixedHeight(28)
            head = QHBoxLayout(hw)
            head.setContentsMargins(0, 0, 0, 0)
            head.setSpacing(8)
            g = QLabel(glyph)
            g.setFont(ifont(14))
            g.setStyleSheet(f"color: {CYAN};")
            head.addWidget(g)
            head.addWidget(label(title, 9.5, QFont.DemiBold))
            head.addStretch()
            if refresh:
                head.addWidget(Btn(glyph=G["refresh"], kind="round", command=self._apply_devices, h=28, size=10,
                                   tip="Relancer l'audio avec ce périphérique"))
            col.addWidget(hw)
            cb = None
            slot = QHBoxLayout()   # même bande que la liste déroulante : liste, icônes, ou vide
            slot.setSpacing(GAP)
            if items is not None:
                cb = ElideCombo(objectName="mixcombo")
                cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                cb.setMinimumContentsLength(12)
                cb.setFixedHeight(36)
                cb.setMinimumWidth(136)
                cb.setMaximumWidth(176)
                cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                cb.setCursor(Qt.PointingHandCursor)
                cb.addItems(([none_label] if none_label else []) + [n for _, n in items])
                cb.view().setMinimumWidth(460)
                cb.activated.connect(lambda _i: self._apply_devices())
                slot.addWidget(cb)
                slot.addStretch()
            elif glyphs:
                for gl in glyphs:
                    lb = QLabel(gl)
                    lb.setFont(ifont(13))
                    lb.setFixedSize(MixFader.W, 36)
                    lb.setAlignment(Qt.AlignCenter)
                    lb.setStyleSheet(f"color: {MUTED};")
                    slot.addWidget(lb)
            else:
                sp = QWidget()
                sp.setFixedHeight(36)
                sp.setMinimumWidth(136)
                slot.addWidget(sp)
            col.addLayout(slot)
            faders = QHBoxLayout()
            faders.setSpacing(GAP)
            col.addLayout(faders)
            col.addStretch()
            body.addLayout(col)
            return cb, faders

        def centered(f, w):
            f.addStretch()
            f.addWidget(w)
            f.addStretch()

        _, body = section("Input")
        self.cb_mic, f = channel(body, G["mic"], "Microphone", self.dev_in, refresh=True)
        mf = self.gain_fader("mic_gain", 200, YELLOW, meter=True)
        self.level_faders.append(mf)
        centered(f, mf)

        self.mix_card, body = section("Voix et sons")
        _, f = channel(body, G["equalizer"], "Voix", glyphs=(G["headphone"], G["wave"]))
        f.addWidget(self.gain_fader("voice_head", 100, YELLOW))
        f.addWidget(self.gain_fader("voice_out", 100, CYAN))
        vsep(body)
        _, f = channel(body, G["bolt"], "Sons", glyphs=(G["headphone"], G["wave"]))
        f.addWidget(self.gain_fader("sound_head", 100, YELLOW))
        f.addWidget(self.gain_fader("sound_gain", 150, CYAN))

        _, body = section("Output")
        self.cb_head, f = channel(body, G["headphone"], "Casque", self.dev_out, "— aucun —", refresh=True)
        centered(f, self.gain_fader("head_gain", 100, YELLOW))
        vsep(body)
        self.cb_virt, f = channel(body, G["wave"], "Sortie virtuelle", self.dev_out)
        centered(f, self.gain_fader("out_gain", 100, CYAN))
        cards.addStretch()

        al.addSpacing(24)
        self.b_adv = Btn("Paramètres avancés", G["chevron_down"], "adv", self._toggle_advanced, h=44, size=13,
                         after=True)
        al.addWidget(self.b_adv, 0, Qt.AlignLeft)
        self.adv = QFrame(objectName="mixcard")
        av = QGridLayout(self.adv)
        av.setContentsMargins(18, 14, 18, 14)
        av.setHorizontalSpacing(40)
        av.addWidget(self.flag_toggle("voice_on", "Changeur de voix", 250), 0, 0)
        av.addWidget(self.flag_toggle("hear_myself", "M'entendre", 250), 0, 1)
        av.addWidget(self.flag_toggle("sounds_to_me", "Sons dans mon casque", 250), 1, 0)
        self.t_default = Toggle("Micro par défaut Windows (Discord, jeux)", self.cfg.get("auto_default_mic", True),
                                width=300)
        self.t_default.command = self._set_auto_default
        av.addWidget(self.t_default, 1, 1)
        av.addWidget(Btn("Relancer l'audio", G["refresh"], "panel", self._apply_devices, h=34), 2, 0, Qt.AlignLeft)
        av.addWidget(label("Le casque sert seulement de retour : tes amis entendent la sortie virtuelle. "
                           "« Micro par défaut Windows » déclare le micro virtuel comme micro par défaut du PC tant que "
                           "Py Mod tourne : Discord, jeux et navigateurs réglés sur « Default » l'utilisent sans rien "
                           "changer (l'ancien micro est remis à la fermeture). "
                           "Préfère les périphériques [Windows WASAPI] pour une latence plus faible.", 9,
                           color=MUTED, wrap=True), 3, 0, 1, 2)
        self.lbl_cable = label("", 9, color=DIM, wrap=True)
        av.addWidget(self.lbl_cable, 4, 0, 1, 2)
        self.lbl_status = label("", 9, color=DIM)
        av.addWidget(self.lbl_status, 5, 0, 1, 2)
        self.adv.hide()
        al.addWidget(self.adv)
        al.addStretch()
        self.set_stack.addWidget(scroll_area(audio))
        self._set_mixer_mode(self.cfg.get("mixer_mode", True))

        # ---- onglet Raccourcis --------------------------------------------
        self.hk_list = QWidget()
        self.hk_lay = QVBoxLayout(self.hk_list)
        self.hk_lay.setContentsMargins(0, 0, 10, 130)
        self.hk_lay.setSpacing(4)
        self.set_stack.addWidget(scroll_area(self.hk_list))

        # ---- onglet Aide ---------------------------------------------------
        aide = QWidget()
        hl = QVBoxLayout(aide)
        hl.setContentsMargins(0, 0, 10, 130)
        help_card = Card(22, 8)
        help_card.lay.addWidget(label("Utiliser ta voix modifiée dans Discord, OBS ou un jeu", 12, QFont.DemiBold))
        help_card.lay.addWidget(label(
            "Py Mod se branche tout seul : il détecte un micro virtuel (driver Voicemod, VB-CABLE, Voicemeeter), "
            "y envoie ta voix modifiée et le déclare micro par défaut de Windows. Discord, les jeux et les "
            "navigateurs réglés sur « Default » l'utilisent donc sans rien changer.\n\n"
            "Pas de micro virtuel ? Onglet Audio → « Installer le micro virtuel » : VB-CABLE (gratuit) est "
            "téléchargé et installé, Windows demande une seule fois d'accepter le pilote.\n\n"
            "Si une appli a un micro précis de sélectionné, choisis-y « Microphone (Voicemod) » ou "
            "« CABLE Output » (le nom exact est affiché dans Audio → Paramètres avancés).\n\n"
            "Les faders jaunes règlent ce que TU entends dans ton casque, les cyan ce qui part vers "
            "la sortie virtuelle (ce que tes amis entendent).", 10, color=MUTED, wrap=True))
        hl.addWidget(help_card)
        hl.addStretch()
        self.set_stack.addWidget(aide)

    def _settings_tab(self, i):
        if i == 1:
            self._build_hotkey_list()
        self.set_stack.setCurrentIndex(i)

    def _build_hotkey_list(self):
        while self.hk_lay.count():
            it = self.hk_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        def row(text, key, cb=None):
            f = QFrame(objectName="mixcard")
            h = QHBoxLayout(f)
            h.setContentsMargins(16, 8, 10, 8)
            h.addWidget(label(text, 10))
            h.addStretch()
            k = label(key or "—", 10, QFont.DemiBold, CYAN if key else DIM)
            h.addWidget(k)
            if cb:
                h.addSpacing(10)
                h.addWidget(Btn("Modifier", G["edit"], "panel", cb, h=30, size=9))
            self.hk_lay.addWidget(f)

        self.hk_lay.addWidget(label("Raccourcis globaux (marchent aussi en jeu)", 12, QFont.DemiBold))
        for n, (vid, name, *_r) in enumerate(VOICES[:9]):
            row(f"Voix : {name}", key_label(MOD_CTRL | MOD_ALT, 0x31 + n))
        row("Activer / couper le changeur de voix", key_label(MOD_CTRL | MOD_ALT, ord("V")))
        row("M'entendre", key_label(MOD_CTRL | MOD_ALT, ord("M")))
        row("Arrêter tous les sons", key_label(MOD_CTRL | MOD_SHIFT, ord("S")))
        self.hk_lay.addSpacing(16)
        self.hk_lay.addWidget(label("Sons", 12, QFont.DemiBold))
        for s in self.sounds:
            row(f"{s.opts.icon}  {s.name}   ·  {s.board}", key_label(*s.opts.hotkey) if s.opts.hotkey else "",
                lambda s=s: (self.open_sound_settings(s, record=True), self._build_hotkey_list()))
        self.hk_lay.addStretch()

    def _set_mixer_mode(self, on):
        self.cfg["mixer_mode"] = bool(on)
        self.mix_card.setVisible(bool(on))
        self.b_mixer.set_selected(bool(on))
        self.b_basic.set_selected(not on)

    def _toggle_advanced(self):
        vis = not self.adv.isVisible()
        self.adv.setVisible(vis)
        self.b_adv.glyph = G["chevron_up"] if vis else G["chevron_down"]
        self.b_adv.update()

    def _reset_mixer(self):
        for key, v in GAIN_DEFAULTS.items():
            setattr(self.engine, key, v / 100)
            for w in self.gain_widgets.get(key, []):
                w.set(v)
        self._sync_param_rows()

    def _name_for(self, items, dev_id):
        return next((n for i, n in items if i == dev_id), "")

    def _id_for(self, items, name):
        return next((i for i, n in items if n == name), None)

    def _apply_devices(self):
        mic = self._id_for(self.dev_in, self.cb_mic.currentText())
        virt = self._id_for(self.dev_out, self.cb_virt.currentText())
        head = self._id_for(self.dev_out, self.cb_head.currentText())
        self.cfg.update(mic=self.cb_mic.currentText(), virt=self.cb_virt.currentText(),
                        head=self.cb_head.currentText())
        self._start_audio(mic, virt, head)

    # -- audio -------------------------------------------------------------
    def _start_audio(self, mic=None, virt=None, head=None):
        cables = vm.find_cables()
        if mic is None and virt is None:  # premier lancement : config ou détection auto
            mic = self._id_for(self.dev_in, self.cfg.get("mic"))
            virt = self._id_for(self.dev_out, self.cfg.get("virt"))
            head = self._id_for(self.dev_out, self.cfg.get("head"))
            if mic is None:
                mic = sd.default.device[0]
                if vm.is_virtual_mic(self._name_for(self.dev_in, mic)):  # le défaut est un micro virtuel (le nôtre ?)
                    real = [i for i, n in self.dev_in if not vm.is_virtual_mic(n)]
                    mic = real[0] if real else mic
            # la « sortie virtuelle » va vers le câble dès qu'il en existe un
            if cables and not any(c.has_out(virt) for c in cables):
                virt = cables[0].out_for(mic)
                if head is None:
                    head = sd.default.device[1]
            if virt is None:
                virt = sd.default.device[1]
        self.cb_mic.setCurrentText(self._name_for(self.dev_in, mic))
        self.cb_virt.setCurrentText(self._name_for(self.dev_out, virt))
        self.cb_head.setCurrentText(self._name_for(self.dev_out, head) or "— aucun —")

        ok = self.engine.start(mic, virt, head)
        virt_name = self._name_for(self.dev_out, virt).lower()
        self.cable = next((c for c in cables if c.has_out(virt) or c.render_key in virt_name), None)
        msg = ""
        if not ok:
            msg = f"Impossible d'ouvrir l'audio : {self.engine.error}"
        elif self.cable is None and not cables:
            msg = ("Aucun micro virtuel : ta voix sort dans tes haut-parleurs et Discord ne l'entend pas. "
                   "Clique sur « Installer le micro virtuel » (une seule fois, environ une minute).")
        elif self.cable is None:
            msg = (f"La sortie virtuelle n'est pas un micro virtuel : choisis « {cables[0].out_name} » "
                   "pour que Discord entende ta voix.")
        self._update_default_mic()
        self.banner.setText(msg)
        self.banner.setVisible(bool(msg))
        self.b_install.setVisible(ok and not cables and self.installer is None)
        self.warn.setVisible(bool(msg))
        self.warn.setToolTip(msg)
        self._refresh_cable_label()

    # -- micro virtuel ----------------------------------------------------
    def _update_default_mic(self):
        """Déclare (ou non) le micro virtuel comme micro par défaut de Windows."""
        want = (self.cfg.get("auto_default_mic", True) and bool(self.engine.streams)
                and self.cable is not None and self.cable.mic_endpoint)
        if want:
            self.default_mic.apply(self.cable.mic_endpoint)
        else:
            self.default_mic.restore()

    def _set_auto_default(self, v):
        self.cfg["auto_default_mic"] = bool(v)
        self._update_default_mic()
        self._refresh_cable_label()

    def _refresh_cable_label(self):
        c = self.cable
        if c is None:
            t = "Micro virtuel : aucun."
        elif self.default_mic.active == c.mic_endpoint:
            t = (f"Micro virtuel : {c.name} — « {c.mic_name} » est le micro par défaut de Windows, "
                 "rien à régler dans Discord.")
        else:
            t = f"Micro virtuel : {c.name} — dans Discord ou le jeu, choisis « {c.mic_name} » comme micro."
        self.lbl_cable.setText(t)

    def _rescan_devices(self):
        """Relit les périphériques (après installation d'un pilote) et met à jour les listes."""
        self.engine.stop()
        vm.rescan_devices()
        devs = list_devices()
        self.dev_in = [(i, n) for i, n, ni, _ in devs if ni > 0]
        self.dev_out = [(i, n) for i, n, _, no in devs if no > 0]
        for cb, items, none in ((self.cb_mic, self.dev_in, None), (self.cb_head, self.dev_out, "— aucun —"),
                                (self.cb_virt, self.dev_out, None)):
            cur = cb.currentText()
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(([none] if none else []) + [n for _, n in items])
            cb.setCurrentText(cur)
            cb.blockSignals(False)

    def _install_cable(self):
        if self.installer is not None:
            return
        self.installer = CableInstaller()
        self.installer.progress.connect(self._install_progress)
        self.installer.done.connect(self._install_done)
        self.b_install.setEnabled(False)
        self.engine.stop()  # libère les périphériques pendant l'installation
        self.banner.setText("Préparation de l'installation…")
        self.banner.show()
        self.installer.start()

    def _install_progress(self, msg):
        self.banner.setText(msg)
        self.banner.show()

    def _install_done(self, ok, msg):
        self.installer = None
        self.b_install.setEnabled(True)
        self._rescan_devices()
        mic = self._id_for(self.dev_in, self.cb_mic.currentText())
        head = self._id_for(self.dev_out, self.cb_head.currentText())
        cable = vm.find_cable()
        if ok and cable is not None:
            virt = cable.out_for(mic)
            self.cfg["virt"] = self._name_for(self.dev_out, virt)
            self._start_audio(mic, virt, head)
        else:
            self._start_audio(mic, self._id_for(self.dev_out, self.cb_virt.currentText()), head)
            self.banner.setText(msg)
            self.banner.show()
            self.warn.setVisible(True)
            self.warn.setToolTip(msg)

    # -- raccourcis --------------------------------------------------------
    def _setup_hotkeys(self):
        b = {}
        for n, (vid, *_rest) in enumerate(VOICES[:9]):
            b[(MOD_CTRL | MOD_ALT, 0x31 + n)] = ("voice", vid)
        b[(MOD_CTRL | MOD_ALT, ord("V"))] = ("toggle_voice", None)
        b[(MOD_CTRL | MOD_ALT, ord("M"))] = ("toggle_hear", None)
        b[(MOD_CTRL | MOD_SHIFT, ord("S"))] = ("stop", None)
        for s in self.sounds:
            if s.opts.hotkey and tuple(s.opts.hotkey) not in b:
                b[tuple(s.opts.hotkey)] = ("sound", s)
        if self.hk:
            self.hk.close()
        try:
            self.hk = GlobalHotkeys(b)
        except Exception:
            self.hk = None

    def _handle(self, ev):
        kind, arg = ev
        if kind == "voice":
            self.select_voice(arg)
        elif kind == "toggle_voice":
            self.set_flag("voice_on", not self.engine.voice_on)
        elif kind == "toggle_hear":
            self.set_flag("hear_myself", not self.engine.hear_myself)
        elif kind == "sound" and arg in self.sounds:
            self.play_sound(arg)
        elif kind == "stop":
            self.engine.mixer.stop_all()

    # -- boucle UI ---------------------------------------------------------
    def _tick(self):
        if self.hk:
            while not self.hk.events.empty():
                self._handle(self.hk.events.get_nowait())
        on = bool(self.engine.streams)
        lvl = min(1.0, self.engine.level) if on else 0.0
        for m in self.meters + getattr(self, "level_faders", []):
            if m.isVisible():
                (m.set_level if isinstance(m, MixFader) else m.set)(lvl ** .5)
        hero = self.heroes.get(self.page)
        if hero:
            hero.animate(lvl)
        self.engine.level *= 0.9
        for t in self.tiles.get(self.page, {}).values():
            if t.isVisible():
                t.refresh()
        self.bar.set_state("running", on)
        if on != self._running:
            self._running = on
            self.dot.setStyleSheet(f"background: {GREEN if on else RED}; border-radius: 4px;")
        st = f"{'Audio actif' if on else 'Audio arrêté'}  ·  {self.engine.sr} Hz  ·  charge DSP {self.engine.load:.0f} %"
        self.dot.setToolTip(st)
        if self.adv.isVisible():
            self.lbl_status.setText(st)

    def showEvent(self, e):
        super().showEvent(e)
        dark_titlebar(self)

    def closeEvent(self, e):
        self.timer.stop()
        self._save_cfg()
        if self.hk:
            self.hk.close()
        self.engine.stop()
        self.default_mic.restore()  # remet l'ancien micro par défaut de Windows
        e.accept()


def main():
    global ICON
    app = QApplication(sys.argv)
    app.setApplicationName("Py Mod")
    app.setStyle("Fusion")
    if "Segoe Fluent Icons" in QFontDatabase.families():
        ICON = "Segoe Fluent Icons"
    pal = QPalette()
    for role, col in ((QPalette.Window, PANEL), (QPalette.WindowText, TEXT), (QPalette.Base, CARD2),
                      (QPalette.AlternateBase, CARD), (QPalette.Text, TEXT), (QPalette.Button, CARD2),
                      (QPalette.ButtonText, TEXT), (QPalette.Highlight, CYAN), (QPalette.HighlightedText, DARK_TXT),
                      (QPalette.ToolTipBase, "#1b1b20"), (QPalette.ToolTipText, TEXT),
                      (QPalette.PlaceholderText, DIM)):
        pal.setColor(role, QColor(col))
    app.setPalette(pal)
    app.setFont(font(10))
    import tempfile
    arrow = Path(tempfile.gettempdir()) / "pymod_arrow.png"
    glyph_icon(chr(0xE70D), MUTED, 12).pixmap(24, 24).save(str(arrow))
    app.setStyleSheet(QSS.replace("@ARROW", arrow.as_posix()))
    titles = DarkTitles(app)
    app.installEventFilter(titles)
    w = App()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
