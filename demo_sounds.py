"""Génère quelques sons de démo synthétisés (aucun fichier externe)."""
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000


def _env(n, a=0.01, r=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def _tone(f, dur, wave="sine"):
    t = np.arange(int(SR * dur)) / SR
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(f, t.shape)) / SR
    return np.sin(ph) if wave == "sine" else np.sign(np.sin(ph)) * 0.5


def make_demo_sounds(folder: Path):
    folder.mkdir(exist_ok=True)
    s = {}
    s["bip"] = _tone(1000, 0.25) * _env(int(SR * 0.25), 0.005, 1)
    t = np.arange(int(SR * 1.6)) / SR
    s["sirene"] = _tone(700 + 300 * np.sin(2 * np.pi * 1.2 * t), 1.6, "square") * 0.6
    s["tada"] = np.concatenate([_tone(f, d) * _env(int(SR * d), 0.005, d / 2)
                                for f, d in ((523, 0.12), (659, 0.12), (784, 0.12), (1047, 0.6))])
    t = np.arange(int(SR * 0.7)) / SR
    s["boing"] = _tone(120 + 400 * np.exp(-t * 6) * (1 + 0.3 * np.sin(2 * np.pi * 14 * t)), 0.7) * _env(len(t), 0.003, 0.3)
    t = np.arange(int(SR * 0.4)) / SR
    s["laser"] = _tone(3000 * np.exp(-t * 8) + 200, 0.4, "square") * _env(len(t), 0.002, 0.15)
    rng = np.random.default_rng(1)
    clap = lambda: rng.standard_normal(int(SR * 0.05)) * _env(int(SR * 0.05), 0.001, 0.01)
    applause = np.zeros(int(SR * 2.5))
    for _ in range(400):
        p = rng.integers(0, len(applause) - 2400)
        applause[p:p + 2400] += clap() * rng.uniform(0.1, 0.3)
    s["applaudissements"] = applause * np.minimum(1, (len(applause) - np.arange(len(applause))) / SR)
    for name, x in s.items():
        x = 0.8 * x / np.abs(x).max()
        sf.write(folder / f"{name}.wav", x.astype(np.float32), SR)


if __name__ == "__main__":
    make_demo_sounds(Path(__file__).parent / "sons")
