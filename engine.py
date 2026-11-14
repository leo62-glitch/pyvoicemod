"""
Moteur audio : micro -> voix -> (+ soundboard) -> sortie virtuelle
                                               +-> casque (retour "m'entendre")

Flux PortAudio (via sounddevice) :
  * un flux duplex micro -> sortie virtuelle ("Dummy Output" du driver Voicemod,
    "CABLE Input" de VB-Cable...) dont le micro associé est lu par Discord ;
    si micro et sortie ne sont pas sur la même API Windows (MME / WASAPI...),
    PortAudio refuse le duplex : on ouvre alors deux flux reliés par un tampon,
  * un flux de sortie casque alimenté par un tampon circulaire.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from dsp import EQ3
from presets import PRESETS
from soundboard import SoundMixer

BLOCK = 512


# --------------------------------------------------------------------------- #
#  Tampon pour le flux casque (les deux cartes son n'ont pas la même horloge)
# --------------------------------------------------------------------------- #
class Fifo:
    def __init__(self, max_len):
        self.buf = np.zeros(0, np.float32)
        self.max = max_len
        self.lock = threading.Lock()

    def push(self, x):
        with self.lock:
            self.buf = np.concatenate([self.buf, x])[-self.max:]

    def pull(self, n):
        with self.lock:
            out, self.buf = self.buf[:n], self.buf[n:]
        if len(out) < n:
            out = np.concatenate([out, np.zeros(n - len(out), np.float32)])
        return out


# --------------------------------------------------------------------------- #
#  Moteur
# --------------------------------------------------------------------------- #
def list_devices():
    """[(id, libellé, nb_entrées, nb_sorties)] — libellé = nom [API]."""
    apis = [a["name"] for a in sd.query_hostapis()]
    return [(i, f"{d['name']}  [{apis[d['hostapi']]}]", d["max_input_channels"], d["max_output_channels"])
            for i, d in enumerate(sd.query_devices())]


def find_virtual_cable():
    """Sortie du câble virtuel (driver Voicemod, VB-Cable, Voicemeeter...) ou None.

    La détection complète (micro associé, micro par défaut Windows) est dans virtualmic.py.
    """
    try:
        from virtualmic import find_cable
        c = find_cable()
        if c is not None:
            return c.out_device
    except Exception:
        pass
    for i, name, _, nout in list_devices():
        low = name.lower()
        if nout and ("cable input" in low or "voicemeeter input" in low or "dummy output" in low):
            return i
    return None


class Engine:
    def __init__(self, sr=48000):
        self.sr = sr
        self.lock = threading.Lock()
        self.voice_id = "normal"
        self.chain = PRESETS["normal"](sr)
        self.voice_on = True
        self.hear_myself = False
        self.sounds_to_me = True     # entendre le soundboard dans le casque
        self.mic_gain = 1.0
        self.sound_gain = 0.8        # sons -> sortie virtuelle
        # table de mixage (1.0 = 100 %)
        self.voice_gain = 1.0        # volume de la voix (après effet)
        self.voice_out = 1.0         # voix -> sortie virtuelle
        self.voice_head = 1.0        # voix -> casque (si "m'entendre")
        self.sound_head = 0.8        # sons -> casque
        self.out_gain = 1.0          # volume général sortie virtuelle
        self.head_gain = 1.0         # volume général casque
        self.eq = EQ3(sr)
        self.eq_db = (0.0, 0.0, 0.0)
        self.mixer = SoundMixer(sr)
        self.fifo = Fifo(BLOCK * 8)
        self.out_fifo = Fifo(BLOCK * 8)   # mode « deux flux » (API différentes)
        self.monitor = False              # flux casque ouvert ?
        self.level = 0.0             # niveau micro (pour le VU-mètre)
        self.load = 0.0              # charge CPU du DSP (%)
        self.streams: list = []
        self.error: str | None = None
        self.devices = (None, None, None)  # micro, sortie virtuelle, casque

    # -- voix --------------------------------------------------------------
    def set_voice(self, voice_id, factory=None):
        chain = (factory or PRESETS[voice_id])(self.sr)
        with self.lock:
            self.chain, self.voice_id = chain, voice_id

    def set_eq(self, bass, mid, treble):
        """Gains en dB (-12..+12) des graves, médiums, aigus de la voix."""
        self.eq_db = (bass, mid, treble)
        eq = EQ3(self.sr, bass, mid, treble)
        eq.zi = self.eq.zi
        self.eq = eq

    # -- audio -------------------------------------------------------------
    def _process(self, indata, frames):
        """Micro -> voix traitée + sons ; alimente aussi le retour casque. Renvoie le bloc de sortie."""
        t0 = time.perf_counter()
        x = indata[:, 0] * self.mic_gain
        self.level = max(float(np.abs(x).max()), self.level * 0.85)
        s, mute_voice = self.mixer.mix(frames)
        with self.lock:
            v = self.chain.process(x) if self.voice_on else x
        v = self.eq.process(v) * self.voice_gain
        if mute_voice:  # option "couper ma voix pendant le son"
            v = v * 0
        out = (v * self.voice_out + s * self.sound_gain) * self.out_gain
        if self.monitor:
            mon = ((v * self.voice_head if self.hear_myself else 0 * v)
                   + (s * self.sound_head if self.sounds_to_me else 0 * s))
            self.fifo.push(mon * self.head_gain)
        self.load = 0.9 * self.load + 0.1 * (time.perf_counter() - t0) / (frames / self.sr) * 100
        return out

    def _main_cb(self, indata, outdata, frames, t, status):
        outdata[:] = self._process(indata, frames)[:, None]

    def _in_cb(self, indata, frames, t, status):
        self.out_fifo.push(self._process(indata, frames))

    def _out_cb(self, outdata, frames, t, status):
        outdata[:] = self.out_fifo.pull(frames)[:, None]

    def _monitor_cb(self, outdata, frames, t, status):
        outdata[:] = self.fifo.pull(frames)[:, None]

    def start(self, mic=None, virtual_out=None, headphones=None):
        self.stop()
        self.error = None
        self.devices = (mic, virtual_out, headphones)
        same_api = self._same_hostapi(mic, virtual_out)
        for sr in (self.sr, 48000, 44100):
            try:
                if sr != self.sr:
                    self.sr = sr
                    self.mixer.sr = sr
                    self.set_voice(self.voice_id)
                    self.set_eq(*self.eq_db)
                    self.eq.zi[:] = 0
                kw = dict(samplerate=sr, blocksize=BLOCK, dtype="float32", latency="low", channels=1)
                if same_api:
                    self.streams = [sd.Stream(device=(mic, virtual_out), callback=self._main_cb, **kw)]
                else:  # ex. micro [MME] et câble [WASAPI] : deux flux reliés par un tampon
                    self.out_fifo = Fifo(BLOCK * 8)
                    self.out_fifo.push(np.zeros(BLOCK * 2, np.float32))
                    self.streams = [sd.InputStream(device=mic, callback=self._in_cb, **kw),
                                    sd.OutputStream(device=virtual_out, callback=self._out_cb, **kw)]
                self.monitor = headphones is not None and headphones != virtual_out
                if self.monitor:
                    mon = sd.OutputStream(samplerate=sr, blocksize=BLOCK, dtype="float32", latency="low",
                                          device=headphones, channels=1, callback=self._monitor_cb)
                    self.streams.append(mon)
                for s in self.streams:
                    s.start()
                return True
            except Exception as e:  # mauvais taux d'échantillonnage, périphérique occupé...
                self.error = str(e)
                self.stop()
        return False

    @staticmethod
    def _same_hostapi(a, b):
        try:
            devs = sd.query_devices()
            ia = a if a is not None else sd.default.device[0]
            ib = b if b is not None else sd.default.device[1]
            return devs[ia]["hostapi"] == devs[ib]["hostapi"]
        except Exception:
            return True

    def stop(self):
        self.monitor = False
        for s in self.streams:
            try:
                s.stop(); s.close()
            except Exception:
                pass
        self.streams = []
