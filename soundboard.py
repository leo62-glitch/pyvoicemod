"""
Soundboard : bibliothèque de sons, options par son, et mixeur temps réel.

Organisation sur disque :
    sons/                    -> soundboard "Général"
    sons/<nom>/              -> un soundboard par sous-dossier
    sons/soundboard.json     -> réglages de chaque son (volume, mode, raccourci...)

Modes de lecture (comportement quand on rappuie sur le son pendant qu'il joue) :
    overlap    : superposer, une nouvelle copie démarre
    restart    : redémarrer depuis le début
    play_stop  : 2e appui = stop
    play_pause : 2e appui = pause / reprise
    loop       : joue en boucle jusqu'au prochain appui
"""
from __future__ import annotations

import json
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".aiff", ".aif"}
MODES = {
    "overlap": "Superposer",
    "restart": "Redémarrer",
    "play_stop": "Lecture / Stop",
    "play_pause": "Lecture / Pause",
    "loop": "Boucle",
}
ROOT_BOARD = "Général"


@dataclass
class SoundOptions:
    name: str = ""
    icon: str = "🔊"
    volume: float = 1.0          # 0..2
    mode: str = "restart"
    fade_in: float = 0.0         # millisecondes
    fade_out: float = 0.0
    stop_others: bool = False    # arrête les autres sons au lancement
    mute_others: bool = False    # rend muets les autres sons tant que celui-ci joue
    mute_voice: bool = False     # coupe le micro tant que le son joue
    favorite: bool = False
    hotkey: list | None = None   # [modificateurs, code_touche_virtuelle]
    image: str = ""              # image perso (chemin), sinon l'icône emoji


class Sound:
    def __init__(self, path: Path, board: str, opts: SoundOptions):
        self.path, self.board, self.opts = path, board, opts
        self.data: np.ndarray | None = None
        self.duration = 0.0

    def load(self, sr: int):
        data, fsr = sf.read(str(self.path), dtype="float32", always_2d=True)
        data = data.mean(axis=1)
        if fsr != sr:
            g = np.gcd(int(fsr), int(sr))
            data = resample_poly(data, sr // g, int(fsr) // g).astype(np.float32)
        peak = float(np.abs(data).max()) if len(data) else 1.0
        self.data = (data / max(peak, 1.0)).astype(np.float32)
        self.duration = len(data) / sr

    @property
    def name(self):
        return self.opts.name or self.path.stem.replace("_", " ")


# --------------------------------------------------------------------------- #
#  Bibliothèque (fichiers + réglages persistants)
# --------------------------------------------------------------------------- #
class Library:
    def __init__(self, folder: Path, sr: int):
        self.folder, self.sr = folder, sr
        self.cfg_path = folder / "soundboard.json"
        self.sounds: list[Sound] = []
        self.boards: list[str] = [ROOT_BOARD]
        self.board_meta: dict = {}      # {nom du soundboard: {"image": chemin}}

    def _key(self, p: Path):
        return p.relative_to(self.folder).as_posix()

    def reload(self):
        self.folder.mkdir(exist_ok=True)
        try:
            data = json.loads(self.cfg_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        saved = data.get("sounds", {})
        self.board_meta = {k: v for k, v in data.get("boards", {}).items() if isinstance(v, dict)}
        known = set(SoundOptions.__dataclass_fields__)
        self.boards = [ROOT_BOARD] + sorted(d.name for d in self.folder.iterdir()
                                            if d.is_dir() and not d.name.startswith("_"))
        sounds = []
        for board in self.boards:
            d = self.folder if board == ROOT_BOARD else self.folder / board
            for p in sorted(d.iterdir()):
                if p.suffix.lower() not in AUDIO_EXT:
                    continue
                opts = SoundOptions(**{k: v for k, v in saved.get(self._key(p), {}).items() if k in known})
                s = Sound(p, board, opts)
                try:
                    s.load(self.sr)
                    sounds.append(s)
                except Exception as e:
                    print(f"Impossible de charger {p.name} : {e}")
        self.sounds = sounds
        self._auto_hotkeys()
        self.save()

    def _auto_hotkeys(self):
        """Premier lancement : Ctrl+Maj+1…0 sur les 10 premiers sons sans raccourci."""
        used = {tuple(s.opts.hotkey) for s in self.sounds if s.opts.hotkey}
        free = [[0x2 | 0x4, ord(k)] for k in "1234567890" if (0x6, ord(k)) not in used]
        for s in self.sounds:
            if not free:
                break
            if s.opts.hotkey is None:  # [] = raccourci volontairement supprimé
                s.opts.hotkey = free.pop(0)

    def save(self):
        data = {"sounds": {self._key(s.path): asdict(s.opts) for s in self.sounds},
                "boards": {k: v for k, v in self.board_meta.items() if v}}
        self.cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def board_image(self, board):
        return self.board_meta.get(board, {}).get("image", "")

    def set_board_image(self, board, path):
        meta = self.board_meta.setdefault(board, {})
        if path:
            meta["image"] = path
        else:
            meta.pop("image", None)
        self.save()

    # -- gestion ------------------------------------------------------------
    def board_dir(self, board):
        return self.folder if board == ROOT_BOARD else self.folder / board

    def new_board(self, name):
        name = "".join(c for c in name if c not in '\\/:*?"<>|').strip()
        if name and name != ROOT_BOARD:
            (self.folder / name).mkdir(exist_ok=True)
        return name

    def add_files(self, paths, board):
        dest = self.board_dir(board)
        for p in map(Path, paths):
            if p.suffix.lower() in AUDIO_EXT:
                target = dest / p.name
                i = 1
                while target.exists():
                    target = dest / f"{p.stem}_{i}{p.suffix}"
                    i += 1
                shutil.copy2(p, target)

    def delete(self, sound: Sound):
        """Déplace le fichier dans sons/_corbeille (récupérable)."""
        trash = self.folder / "_corbeille"
        trash.mkdir(exist_ok=True)
        shutil.move(str(sound.path), trash / sound.path.name)
        self.sounds.remove(sound)
        self.save()


# --------------------------------------------------------------------------- #
#  Mixeur temps réel
# --------------------------------------------------------------------------- #
@dataclass
class _Instance:
    sound: Sound
    pos: int = 0
    paused: bool = False
    loop: bool = False
    age: int = 0                 # échantillons joués (pour le fondu d'entrée)
    stopping: int = -1           # échantillons restants de fondu de sortie (-1 = non)
    fade_out_len: int = 0


class SoundMixer:
    def __init__(self, sr: int):
        self.sr = sr
        self.lock = threading.Lock()
        self.inst: list[_Instance] = []

    # -- commandes (appelées depuis l'interface / les raccourcis) -----------
    def trigger(self, snd: Sound):
        o = snd.opts
        with self.lock:
            mine = [i for i in self.inst if i.sound is snd and i.stopping < 0]
            if mine and o.mode in ("play_stop", "loop"):
                for i in mine:
                    self._stop(i)
                return
            if mine and o.mode == "play_pause":
                for i in mine:
                    i.paused = not i.paused
                return
            if mine and o.mode == "restart":
                self.inst = [i for i in self.inst if i.sound is not snd]
            if o.stop_others:
                for i in self.inst:
                    if i.sound is not snd:
                        self._stop(i)
            self.inst.append(_Instance(snd, loop=(o.mode == "loop")))

    def stop(self, snd: Sound):
        with self.lock:
            for i in self.inst:
                if i.sound is snd:
                    self._stop(i)

    def stop_all(self):
        with self.lock:
            for i in self.inst:
                self._stop(i)

    def _stop(self, i: _Instance):
        n = int(i.sound.opts.fade_out * self.sr / 1000)
        if n <= 0:
            i.stopping, i.fade_out_len = 0, 1  # supprimé au prochain bloc
        elif i.stopping < 0:
            i.stopping, i.fade_out_len = n, n

    # -- état ---------------------------------------------------------------
    def state(self, snd: Sound):
        """None, 'playing' ou 'paused'."""
        with self.lock:
            for i in self.inst:
                if i.sound is snd and i.stopping < 0:
                    return "paused" if i.paused else "playing"
        return None

    def progress(self, snd: Sound):
        with self.lock:
            for i in self.inst:
                if i.sound is snd and i.sound.data is not None and len(i.sound.data):
                    return i.pos / len(i.sound.data)
        return 0.0

    # -- rendu audio (appelé dans le callback audio) -------------------------
    def mix(self, n):
        """Renvoie (bloc_mixé, couper_la_voix)."""
        out = np.zeros(n, np.float32)
        mute_voice = False
        with self.lock:
            active = [i for i in self.inst if not i.paused and i.stopping != 0]
            solo = [i for i in active if i.sound.opts.mute_others]
            alive = []
            for i in self.inst:
                if i.stopping == 0:
                    continue
                if i.paused:
                    alive.append(i)
                    continue
                d, o = i.sound.data, i.sound.opts
                # lecture (avec bouclage éventuel)
                if i.loop:
                    idx = (i.pos + np.arange(n)) % len(d)
                    chunk = d[idx]
                else:
                    chunk = d[i.pos:i.pos + n]
                m = len(chunk)
                g = np.full(m, o.volume, np.float32)
                fi = int(o.fade_in * self.sr / 1000)
                if fi > 0 and i.age < fi:
                    g *= np.minimum(1.0, (i.age + np.arange(m)) / fi)
                fo = int(o.fade_out * self.sr / 1000)
                if fo > 0 and not i.loop and i.stopping < 0:  # fondu naturel en fin de fichier
                    remaining = len(d) - (i.pos + np.arange(m))
                    g *= np.minimum(1.0, remaining / fo)
                if i.stopping > 0:  # fondu de sortie après un "stop"
                    r = i.stopping - np.arange(m)
                    g *= np.clip(r / i.fade_out_len, 0, 1)
                    i.stopping = max(0, i.stopping - m)
                if solo and i not in solo:
                    g *= 0.0
                out[:m] += chunk * g
                if o.mute_voice:
                    mute_voice = True
                i.pos += n
                i.age += n
                if i.loop:
                    i.pos %= len(d)
                if (i.loop or i.pos < len(d)) and i.stopping != 0:
                    alive.append(i)
            self.inst = alive
        return out, mute_voice
