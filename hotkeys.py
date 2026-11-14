"""Raccourcis clavier globaux Windows (fonctionnent même quand un jeu a le focus),
via l'API Win32 RegisterHotKey, sans dépendance externe."""
import ctypes
import queue
import threading
from ctypes import wintypes

MOD_ALT, MOD_CTRL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012


class GlobalHotkeys:
    """bindings : {(modificateurs, code_touche_virtuelle): action}
    Les actions déclenchées sont déposées dans self.events (thread-safe) ;
    l'interface les récupère périodiquement."""

    def __init__(self, bindings):
        self.bindings = list(bindings.items())
        self.events: queue.Queue = queue.Queue()
        self.failed: list = []
        self._tid = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(2)

    def _run(self):
        user32 = ctypes.windll.user32
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        for i, ((mods, vk), _) in enumerate(self.bindings):
            if not user32.RegisterHotKey(None, i + 1, mods | MOD_NOREPEAT, vk):
                self.failed.append((mods, vk))  # déjà pris par une autre appli
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and 1 <= msg.wParam <= len(self.bindings):
                self.events.put(self.bindings[msg.wParam - 1][1])
        for i in range(len(self.bindings)):
            user32.UnregisterHotKey(None, i + 1)

    def close(self):
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            self._thread.join(1.0)  # libère les raccourcis avant d'en ré-enregistrer


def key_label(mods, vk):
    parts = []
    if mods & MOD_CTRL: parts.append("Ctrl")
    if mods & MOD_ALT: parts.append("Alt")
    if mods & MOD_SHIFT: parts.append("Maj")
    if 0x30 <= vk <= 0x5A:
        name = chr(vk)
    elif 0x70 <= vk <= 0x87:
        name = f"F{vk - 0x6F}"
    elif 0x60 <= vk <= 0x69:
        name = f"Num{vk - 0x60}"
    else:  # nom fourni par Windows pour les autres touches
        buf = ctypes.create_unicode_buffer(32)
        scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        ctypes.windll.user32.GetKeyNameTextW(scan << 16, buf, 32)
        name = buf.value or hex(vk)
    parts.append(name)
    return "+".join(parts)
