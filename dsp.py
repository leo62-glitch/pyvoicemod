"""
Noeuds DSP temps réel (bloc par bloc), en numpy pur.

Architecture inspirée de ce qu'on observe dans Voicemod (un graphe de "AudioNode"
chaînés, chacun avec une méthode process(bloc)), mais tout le code ici est écrit
from scratch avec des algorithmes classiques de traitement du signal.

Convention : chaque noeud reçoit un bloc mono float32 (shape [N]) et renvoie
un bloc de même taille. Les noeuds gardent leur état entre deux blocs
(phase d'oscillateur, lignes à retard, état des filtres...).
"""
from __future__ import annotations

import numpy as np
from scipy import signal


# --------------------------------------------------------------------------- #
#  Base
# --------------------------------------------------------------------------- #
class Node:
    def __init__(self, sr: int):
        self.sr = sr

    def process(self, x: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError


class Chain(Node):
    """Exécute des noeuds en série (l'équivalent d'un preset de voix)."""

    def __init__(self, sr: int, nodes: list[Node]):
        super().__init__(sr)
        self.nodes = nodes

    def process(self, x):
        for n in self.nodes:
            x = n.process(x)
        return x


class Mix(Node):
    """Mélange sec / traité : out = (1-wet)*x + wet*child(x)."""

    def __init__(self, sr, child: Node, wet: float = 0.5):
        super().__init__(sr)
        self.child, self.wet = child, wet

    def process(self, x):
        return (1 - self.wet) * x + self.wet * self.child.process(x)


class Parallel(Node):
    """Plusieurs branches sur le même signal, sommées avec des gains."""

    def __init__(self, sr, branches: list[tuple[Node, float]]):
        super().__init__(sr)
        self.branches = branches

    def process(self, x):
        return sum(g * n.process(x) for n, g in self.branches)


# --------------------------------------------------------------------------- #
#  Briques de base : lignes à retard
# --------------------------------------------------------------------------- #
class _RingReader:
    """Tampon circulaire d'entrée + lecture à retard fractionnaire (interp. linéaire).

    On écrit d'abord tout le bloc, puis on lit chaque échantillon n à
    (position_écriture_de_n - retard[n]). Tout est vectorisé.
    """

    def __init__(self, size: int):
        self.size = 1 << int(np.ceil(np.log2(size)))
        self.mask = self.size - 1
        self.buf = np.zeros(self.size, np.float32)
        self.w = 0

    def write(self, x):
        idx = (self.w + np.arange(len(x))) & self.mask
        self.buf[idx] = x
        base = self.w + np.arange(len(x))
        self.w = (self.w + len(x)) & self.mask
        return base  # position absolue de chaque échantillon écrit

    def read(self, base, delay):
        pos = base - delay
        i0 = np.floor(pos).astype(np.int64)
        frac = (pos - i0).astype(np.float32)
        a = self.buf[i0 & self.mask]
        b = self.buf[(i0 + 1) & self.mask]
        return a + frac * (b - a)


class _FeedbackLine:
    """v[n] = x[n] + g * v[n-D]. Traité par sous-blocs de taille <= D
    pour pouvoir vectoriser malgré la récursion."""

    def __init__(self, delay: int, g: float):
        self.D, self.g = max(1, int(delay)), g
        self.buf = np.zeros(self.D, np.float32)
        self.i = 0

    def run(self, x):
        """Renvoie (v, v_retardé) pour tout le bloc."""
        v_all = np.empty_like(x)
        old_all = np.empty_like(x)
        pos = 0
        while pos < len(x):
            L = min(self.D - self.i, len(x) - pos)
            old = self.buf[self.i:self.i + L].copy()
            v = x[pos:pos + L] + self.g * old
            self.buf[self.i:self.i + L] = v
            v_all[pos:pos + L], old_all[pos:pos + L] = v, old
            self.i = (self.i + L) % self.D
            pos += L
        return v_all, old_all


# --------------------------------------------------------------------------- #
#  Dynamique / utilitaires
# --------------------------------------------------------------------------- #
class Gain(Node):
    def __init__(self, sr, db: float = 0.0):
        super().__init__(sr)
        self.g = 10 ** (db / 20)

    def process(self, x):
        return x * self.g


class NoiseGate(Node):
    """Coupe le son sous un seuil (RMS par bloc, gain lissé pour éviter les clics)."""

    def __init__(self, sr, threshold_db=-45.0, attack=0.6, release=0.15):
        super().__init__(sr)
        self.th = 10 ** (threshold_db / 20)
        self.attack, self.release = attack, release
        self.g = 0.0

    def process(self, x):
        rms = float(np.sqrt(np.mean(x * x) + 1e-12))
        target = 1.0 if rms > self.th else 0.0
        k = self.attack if target > self.g else self.release
        g_new = self.g + k * (target - self.g)
        ramp = np.linspace(self.g, g_new, len(x), dtype=np.float32)
        self.g = g_new
        return x * ramp


class Limiter(Node):
    """Soft clip final pour ne jamais saturer la sortie."""

    def process(self, x):
        return 0.98 * np.tanh(x)  # quasi linéaire à bas niveau, borné à ±0.98


# --------------------------------------------------------------------------- #
#  Filtres
# --------------------------------------------------------------------------- #
class Filter(Node):
    """Butterworth (lowpass / highpass / bandpass) avec état conservé entre blocs."""

    def __init__(self, sr, kind="lowpass", freq=1000.0, order=2):
        super().__init__(sr)
        self.sos = signal.butter(order, freq, btype=kind, fs=sr, output="sos")
        self.zi = np.zeros((self.sos.shape[0], 2))

    def process(self, x):
        y, self.zi = signal.sosfilt(self.sos, x, zi=self.zi)
        return y.astype(np.float32)


# --------------------------------------------------------------------------- #
#  Effets de modulation / couleur
# --------------------------------------------------------------------------- #
class RingMod(Node):
    """Multiplie la voix par une sinusoïde → son métallique / robot / dalek."""

    def __init__(self, sr, freq=50.0):
        super().__init__(sr)
        self.freq, self.ph = freq, 0.0

    def process(self, x):
        inc = 2 * np.pi * self.freq / self.sr
        ph = self.ph + inc * np.arange(len(x))
        self.ph = (self.ph + inc * len(x)) % (2 * np.pi)
        return x * np.sin(ph).astype(np.float32)


class Tremolo(Node):
    def __init__(self, sr, rate=6.0, depth=0.7):
        super().__init__(sr)
        self.lfo = RingMod(sr, rate)
        self.depth = depth

    def process(self, x):
        m = self.lfo.process(np.ones_like(x))  # sinus pur
        return x * (1 - self.depth * (0.5 + 0.5 * m))


class Distortion(Node):
    """Saturation tanh + gain de compensation."""

    def __init__(self, sr, drive=8.0):
        super().__init__(sr)
        self.drive = drive

    def process(self, x):
        return np.tanh(self.drive * x) / np.tanh(self.drive)


class Bitcrusher(Node):
    """Réduit la résolution (bits) et la fréquence d'échantillonnage → voix 8-bit."""

    def __init__(self, sr, bits=6, downsample=6):
        super().__init__(sr)
        self.q = 2 ** (bits - 1)
        self.ds = downsample

    def process(self, x):
        y = np.round(x * self.q) / self.q
        y = np.repeat(y[:: self.ds], self.ds)[: len(x)]
        return y.astype(np.float32)


# --------------------------------------------------------------------------- #
#  Effets à retard
# --------------------------------------------------------------------------- #
class Echo(Node):
    def __init__(self, sr, ms=300.0, feedback=0.45, wet=0.5):
        super().__init__(sr)
        self.line = _FeedbackLine(sr * ms / 1000, feedback)
        self.wet = wet

    def process(self, x):
        _, old = self.line.run(x)
        return x + self.wet * old


class Comb(Node):
    """Résonateur court (quelques ms) : timbre métallique / tube."""

    def __init__(self, sr, ms=5.0, feedback=0.7):
        super().__init__(sr)
        self.line = _FeedbackLine(sr * ms / 1000, feedback)

    def process(self, x):
        v, _ = self.line.run(x)
        return v * (1 - self.line.g)


class Chorus(Node):
    """Retard modulé par un LFO (chorus si ~20 ms, flanger si ~2 ms)."""

    def __init__(self, sr, base_ms=20.0, depth_ms=6.0, rate=0.8, wet=0.5):
        super().__init__(sr)
        self.ring = _RingReader(int(sr * (base_ms + depth_ms) / 1000) + 4096)
        self.base, self.depth = sr * base_ms / 1000, sr * depth_ms / 1000
        self.rate, self.ph, self.wet = rate, 0.0, wet

    def process(self, x):
        base = self.ring.write(x)
        inc = 2 * np.pi * self.rate / self.sr
        ph = self.ph + inc * np.arange(len(x))
        self.ph = (self.ph + inc * len(x)) % (2 * np.pi)
        d = self.base + self.depth * np.sin(ph)
        return (1 - self.wet) * x + self.wet * self.ring.read(base, d)


class Reverb(Node):
    """Réverbération de Schroeder : 4 combs parallèles + 2 allpass en série."""

    COMBS_MS = (29.7, 37.1, 41.1, 43.7)
    ALLPASS_MS = (5.0, 1.7)

    def __init__(self, sr, room=0.84, wet=0.35):
        super().__init__(sr)
        self.combs = [_FeedbackLine(sr * ms / 1000, room) for ms in self.COMBS_MS]
        self.aps = [_FeedbackLine(sr * ms / 1000, 0.7) for ms in self.ALLPASS_MS]
        self.wet = wet

    def process(self, x):
        acc = np.zeros_like(x)
        for c in self.combs:
            _, old = c.run(x)
            acc += old
        y = acc * 0.25
        for ap in self.aps:  # allpass : y = -g*v + v[n-D]
            v, old = ap.run(y)
            y = -ap.g * v + old
        return (1 - self.wet) * x + self.wet * y


# --------------------------------------------------------------------------- #
#  Pitch shifting (le coeur d'un voice changer)
# --------------------------------------------------------------------------- #
class PitchShift(Node):
    """Pitch shifter temporel à deux têtes de lecture ("delay-line / Doppler").

    Principe : on lit le signal dans une ligne à retard dont le retard varie
    linéairement. Un retard qui diminue = on lit plus vite = son plus aigu.
    Comme le retard ne peut pas diminuer indéfiniment, on utilise deux têtes
    décalées d'une demi-fenêtre et on fond-enchaîne entre elles.

    Latence ≈ window_ms. Simple, robuste, utilisable en temps réel.
    (Les vrais produits utilisent plutôt des méthodes FFT/phase vocoder ou PSOLA,
    qui gèrent mieux les formants — c'est un bon exercice pour la suite.)
    """

    def __init__(self, sr, semitones=0.0, window_ms=40.0):
        super().__init__(sr)
        self.W = sr * window_ms / 1000
        self.ring = _RingReader(int(self.W) + 8192)
        self.ph = 0.0
        self.set_semitones(semitones)

    def set_semitones(self, st):
        self.ratio = 2 ** (st / 12)

    def process(self, x):
        base = self.ring.write(x)
        step = (1 - self.ratio) / self.W  # variation de phase par échantillon
        ph1 = (self.ph + step * np.arange(len(x))) % 1.0
        self.ph = (self.ph + step * len(x)) % 1.0
        ph2 = (ph1 + 0.5) % 1.0
        y1 = self.ring.read(base, 1 + ph1 * self.W)
        y2 = self.ring.read(base, 1 + ph2 * self.W)
        g1 = np.sin(np.pi * ph1) ** 2  # fenêtres complémentaires (somme = 1)
        g2 = np.sin(np.pi * ph2) ** 2
        return (g1 * y1 + g2 * y2).astype(np.float32)


# =========================================================================== #
#  Effets spectraux (STFT) : pitch FFT avec formants, robot, chuchotement,
#  vocoder, autotune. Algorithmes classiques (phase vocoder, enveloppe
#  spectrale par cepstre), implémentés ici from scratch.
# =========================================================================== #
def spectral_envelope(mag, lifter=60):
    """Enveloppe spectrale lissée (= les formants) via le cepstre :
    log|X| -> cepstre -> on garde les basses quéfrences -> retour en spectre."""
    c = np.fft.irfft(np.log(mag + 1e-9))
    c[lifter:-lifter] = 0.0
    return np.exp(np.fft.rfft(c).real)


class Stft(Node):
    """Base générique analyse/synthèse STFT en streaming (overlap-add).

    Les sous-classes surchargent spectral(X) -> Y (spectre d'une trame).
    Latence ajoutée ≈ n échantillons (~21 ms à 48 kHz pour n=1024).
    """

    def __init__(self, sr, n=1024, hop=256):
        super().__init__(sr)
        self.n, self.h = n, hop
        self.win = np.sqrt(0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)
        self.scale = hop / (n / 2)
        self.frame = np.zeros(n, np.float32)
        self.acc = np.zeros(n, np.float32)
        self.inbuf = np.zeros(0, np.float32)
        self.outbuf = np.zeros(0, np.float32)
        self.k = np.arange(n // 2 + 1)

    def spectral(self, X):  # pragma: no cover
        return X

    def process(self, x):
        self.inbuf = np.concatenate([self.inbuf, x])
        outs = [self.outbuf]
        h = self.h
        while len(self.inbuf) >= h:
            hop, self.inbuf = self.inbuf[:h], self.inbuf[h:]
            self.frame = np.concatenate([self.frame[h:], hop])
            Y = self.spectral(np.fft.rfft(self.frame * self.win))
            self.acc += np.fft.irfft(Y, self.n).astype(np.float32) * self.win * self.scale
            outs.append(self.acc[:h].copy())
            self.acc = np.concatenate([self.acc[h:], np.zeros(h, np.float32)])
        out = np.concatenate(outs)
        if len(out) < len(x):  # démarrage : pas encore assez d'échantillons
            out = np.concatenate([np.zeros(len(x) - len(out), np.float32), out])
        self.outbuf = out[len(x):]
        return out[:len(x)]


class PitchShiftFFT(Stft):
    """Pitch shift par phase vocoder, avec préservation / déplacement des formants.

    - semitones : hauteur de la voix
    - formant   : facteur d'échelle des formants (1 = inchangé, >1 = voix plus
                  "petite"/féminine/enfant, <1 = voix plus "grande"/masculine)
    Garder les formants évite l'effet "Chipmunk" : on change la note sans
    changer la taille apparente du conduit vocal.
    """

    def __init__(self, sr, semitones=0.0, formant=1.0, keep_formants=True, n=1024, hop=256):
        super().__init__(sr, n, hop)
        nb = n // 2 + 1
        self.last_phase = np.zeros(nb)
        self.sum_phase = np.zeros(nb)
        self.expected = 2 * np.pi * hop * self.k / n
        self.keep_formants, self.formant = keep_formants, formant
        self.lifter = max(20, int(sr * 0.0013))
        self.ratio = 2 ** (semitones / 12)

    def set_semitones(self, st):
        self.ratio = 2 ** (st / 12)

    def spectral(self, X):
        mag, ph = np.abs(X), np.angle(X)
        d = ph - self.last_phase - self.expected
        self.last_phase = ph
        d = (d + np.pi) % (2 * np.pi) - np.pi
        true_bin = self.k + d * self.n / (2 * np.pi * self.h)  # fréquence instantanée (en bins)

        if self.keep_formants:
            env = spectral_envelope(mag, self.lifter)
            src = mag / env  # "excitation" sans formants
        else:
            src = mag

        nb = len(mag)
        tgt = np.round(self.k * self.ratio).astype(np.int64)
        ok = (tgt >= 0) & (tgt < nb)
        mag_s = np.zeros(nb)
        np.add.at(mag_s, tgt[ok], src[ok])
        bin_s = np.zeros(nb)
        bin_s[tgt[ok]] = true_bin[ok] * self.ratio

        if self.keep_formants:  # on ré-applique l'enveloppe (éventuellement étirée)
            mag_s *= np.interp(self.k / self.formant, self.k, env, right=env[-1] * 1e-3)

        self.sum_phase = (self.sum_phase + 2 * np.pi * self.h * bin_s / self.n) % (2 * np.pi)
        return mag_s * np.exp(1j * self.sum_phase)


class RobotFFT(Stft):
    """Robotisation : on met toutes les phases à zéro à chaque trame.
    Chaque trame devient une impulsion -> la voix "bourdonne" à sr/hop Hz."""

    def __init__(self, sr, freq=150.0, n=1024):
        super().__init__(sr, n, hop=max(64, int(round(sr / freq))))
        self.shift = (-1.0) ** self.k  # centre l'impulsion dans la trame

    def spectral(self, X):
        return np.abs(X) * self.shift


class Whisper(Stft):
    """Chuchotement : on garde les amplitudes, phases aléatoires -> plus de hauteur tonale."""

    def __init__(self, sr):
        super().__init__(sr, n=512, hop=128)
        self.rng = np.random.default_rng()

    def spectral(self, X):
        return np.abs(X) * np.exp(2j * np.pi * self.rng.random(len(X)))


class VocoderFFT(Stft):
    """Vocoder : l'enveloppe spectrale de la voix sculpte un synthé (dents de scie).
    notes : fréquences de la porteuse (une note = robot, plusieurs = accord)."""

    def __init__(self, sr, notes=(110.0, 165.0, 220.0), lifter=40):
        super().__init__(sr, n=1024, hop=256)
        self.notes = np.array(notes)
        self.ph = np.zeros(len(notes))
        self.cframe = np.zeros(self.n, np.float32)
        self.lifter = lifter

    def _carrier(self, n):
        t = np.arange(1, n + 1)[:, None]
        ph = (self.ph + t * self.notes / self.sr) % 1.0
        self.ph = ph[-1]
        return (2 * ph - 1).mean(axis=1).astype(np.float32)

    def spectral(self, X):
        self.cframe = np.concatenate([self.cframe[self.h:], self._carrier(self.h)])
        C = np.fft.rfft(self.cframe * self.win)
        env_c = spectral_envelope(np.abs(C), self.lifter)
        env_v = spectral_envelope(np.abs(X), self.lifter)
        return C / env_c * env_v * 0.5


class AutoTune(Node):
    """Autotune : détection de f0 (autocorrélation), arrondi à la note de la gamme
    la plus proche, puis correction par PitchShiftFFT (formants préservés).

    speed : 1.0 = correction instantanée (effet robotique), 0.1 = naturel.
    scale : classes de hauteur autorisées (0 = Do). Par défaut Do majeur.
    """

    MAJOR = (0, 2, 4, 5, 7, 9, 11)

    def __init__(self, sr, speed=0.9, scale=MAJOR, key=0, fmin=70.0, fmax=800.0):
        super().__init__(sr)
        self.shifter = PitchShiftFFT(sr, 0.0, keep_formants=True)
        self.hist = np.zeros(2048, np.float32)
        self.speed, self.key = speed, key
        self.allowed = np.array(sorted({(p + key) % 12 for p in scale}))
        self.lag_min, self.lag_max = int(sr / fmax), int(sr / fmin)
        self.ratio = 1.0

    def detect(self, x):
        self.hist = np.concatenate([self.hist[len(x):], x])
        h = self.hist - self.hist.mean()
        if np.sqrt(np.mean(h * h)) < 0.01:
            return None
        F = np.fft.rfft(h, 2 * len(h))
        ac = np.fft.irfft(F * np.conj(F))[: self.lag_max + 2]
        lag = int(np.argmax(ac[self.lag_min:self.lag_max])) + self.lag_min
        if ac[lag] / (ac[0] + 1e-9) < 0.45:  # pas assez périodique = non voisé
            return None
        a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]  # interpolation parabolique
        lag = lag + 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
        return self.sr / lag

    def process(self, x):
        f0 = self.detect(x)
        target = 1.0
        if f0:
            midi = 69 + 12 * np.log2(f0 / 440)
            octave = int(midi // 12)
            cands = np.array([o * 12 + p for o in (octave - 1, octave, octave + 1) for p in self.allowed])
            snap = cands[np.argmin(np.abs(cands - midi))]
            target = 2 ** ((snap - midi) / 12)
        self.ratio += self.speed * (target - self.ratio)
        self.shifter.ratio = self.ratio
        return self.shifter.process(x)


class WahWah(Node):
    """Filtre passe-bande dont la fréquence centrale est balayée par un LFO."""

    def __init__(self, sr, rate=1.5, fmin=350.0, fmax=2200.0, q=4.0, sub=64):
        super().__init__(sr)
        self.rate, self.fmin, self.fmax, self.q, self.sub = rate, fmin, fmax, q, sub
        self.ph, self.zi = 0.0, np.zeros(2)

    def process(self, x):
        out = np.empty_like(x)
        for i in range(0, len(x), self.sub):
            seg = x[i:i + self.sub]
            fc = self.fmin * (self.fmax / self.fmin) ** (0.5 + 0.5 * np.sin(self.ph))
            self.ph = (self.ph + 2 * np.pi * self.rate * len(seg) / self.sr) % (2 * np.pi)
            w0 = 2 * np.pi * fc / self.sr  # biquad passe-bande (formules RBJ)
            al = np.sin(w0) / (2 * self.q)
            b = np.array([al, 0, -al]) / (1 + al)
            a = np.array([1, -2 * np.cos(w0) / (1 + al), (1 - al) / (1 + al)])
            out[i:i + self.sub], self.zi = signal.lfilter(b, a, seg, zi=self.zi)
        return out * 2.5


# --------------------------------------------------------------------------- #
#  Égaliseur 3 bandes (graves / médiums / aigus) réglable en direct
# --------------------------------------------------------------------------- #
class EQ3(Node):
    """Low-shelf 200 Hz, cloche 1 kHz, high-shelf 4 kHz (biquads RBJ). Gains en dB."""

    def __init__(self, sr, bass=0.0, mid=0.0, treble=0.0):
        super().__init__(sr)
        self.zi = np.zeros((3, 2))
        self.set_gains(bass, mid, treble)

    @staticmethod
    def _biquad(sr, kind, f0, db, q=0.8):
        a = 10 ** (db / 40)
        w = 2 * np.pi * f0 / sr
        cw, sw = np.cos(w), np.sin(w)
        if kind == "peak":
            al = sw / (2 * q)
            b = [1 + al * a, -2 * cw, 1 - al * a]
            d = [1 + al / a, -2 * cw, 1 - al / a]
        else:
            al = sw / 2 * np.sqrt(2)
            sa = 2 * np.sqrt(a) * al
            if kind == "low":
                b = [a * ((a + 1) - (a - 1) * cw + sa), 2 * a * ((a - 1) - (a + 1) * cw), a * ((a + 1) - (a - 1) * cw - sa)]
                d = [(a + 1) + (a - 1) * cw + sa, -2 * ((a - 1) + (a + 1) * cw), (a + 1) + (a - 1) * cw - sa]
            else:
                b = [a * ((a + 1) + (a - 1) * cw + sa), -2 * a * ((a - 1) + (a + 1) * cw), a * ((a + 1) + (a - 1) * cw - sa)]
                d = [(a + 1) - (a - 1) * cw + sa, 2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - sa]
        return np.array(b + d) / d[0]

    def set_gains(self, bass, mid, treble):
        self.gains = (bass, mid, treble)
        self.active = any(abs(g) > 0.05 for g in self.gains)
        self.sos = np.stack([self._biquad(self.sr, "low", 200, bass), self._biquad(self.sr, "peak", 1000, mid),
                             self._biquad(self.sr, "high", 4000, treble)])

    def process(self, x):
        if not self.active:
            return x
        y, self.zi = signal.sosfilt(self.sos, x, zi=self.zi)
        return y.astype(np.float32)


# --------------------------------------------------------------------------- #
#  Nettoyage du micro (Paramètres avancés) : réduction de bruit + noise gate
# --------------------------------------------------------------------------- #
def _find_rnnoise():
    """Chemin de rnnoise.dll (paquet « pyrnnoise » ou à côté de Py Mod), ou None."""
    import importlib.util
    from pathlib import Path
    cands = [Path(__file__).with_name("rnnoise.dll")]
    try:
        spec = importlib.util.find_spec("pyrnnoise")  # ne l'importe pas (ses dépendances sont lourdes)
        for d in (spec.submodule_search_locations or []) if spec else []:
            cands.append(Path(d) / "rnnoise.dll")
    except Exception:
        pass
    return next((p for p in cands if p.is_file()), None)


class RNNoise(Node):
    """Réseau de neurones RNNoise (Xiph) — le même que Voicemod (« VAudioNodeRnnoise »).

    Ne marche qu'à 48 kHz, par trames de 480 échantillons (10 ms de latence en plus).
    """
    FRAME = 480
    _lib = None

    @classmethod
    def load(cls):
        if cls._lib is None:
            import ctypes
            path = _find_rnnoise()
            if path is None:
                raise OSError("rnnoise.dll introuvable")
            lib = ctypes.CDLL(str(path))
            lib.rnnoise_create.argtypes = [ctypes.c_void_p]
            lib.rnnoise_create.restype = ctypes.c_void_p
            lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
            fp = ctypes.POINTER(ctypes.c_float)
            lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, fp, fp]
            lib.rnnoise_process_frame.restype = ctypes.c_float
            cls._lib = lib
        return cls._lib

    def __init__(self, sr):
        super().__init__(sr)
        if sr != 48000:
            raise ValueError("RNNoise exige 48 kHz")
        import ctypes
        self._ct = ctypes
        self.lib = self.load()
        self.st = self.lib.rnnoise_create(None)
        self.inbuf = np.zeros(0, np.float32)
        self.outbuf = np.zeros(self.FRAME, np.float32)  # une trame de retard
        self.frame_out = np.zeros(self.FRAME, np.float32)

    def __del__(self):
        try:
            self.lib.rnnoise_destroy(self.st)
        except Exception:
            pass

    def process(self, x):
        self.inbuf = np.concatenate([self.inbuf, x])
        outs = [self.outbuf]
        fp = self._ct.POINTER(self._ct.c_float)
        F = self.FRAME
        while len(self.inbuf) >= F:
            fr = np.ascontiguousarray(self.inbuf[:F] * 32768.0, dtype=np.float32)
            self.inbuf = self.inbuf[F:]
            self.lib.rnnoise_process_frame(self.st, self.frame_out.ctypes.data_as(fp), fr.ctypes.data_as(fp))
            outs.append(self.frame_out / 32768.0)
        out = np.concatenate(outs)
        self.outbuf = out[len(x):]
        return out[:len(x)].astype(np.float32)


class SpectralDenoise(Stft):
    """Réduction de bruit de secours (si RNNoise est absent) : bruit estimé par
    « minimum statistics » (minimum de la puissance lissée sur ~0,7 s) + gain de Wiener."""

    def __init__(self, sr, n=1024, hop=256, bias=2.0, floor=0.1):
        super().__init__(sr, n, hop)
        nb = n // 2 + 1
        self.bias, self.floor = bias, floor
        self.prev_a2 = np.zeros(nb)
        self.S = None                         # puissance lissée
        self.cur_min = np.full(nb, np.inf)    # minimum de la fenêtre en cours
        self.prev_min = np.full(nb, np.inf)   # minimum de la fenêtre précédente
        self.D = max(8, int(0.35 * sr / hop)) # ~0,35 s par fenêtre (2 fenêtres ≈ 0,7 s)
        self.count = 0
        self.gain = np.ones(nb)

    def spectral(self, X):
        p = np.abs(X) ** 2
        self.S = p.copy() if self.S is None else 0.8 * self.S + 0.2 * p
        self.cur_min = np.minimum(self.cur_min, self.S)
        noise = np.minimum(self.cur_min, self.prev_min)
        self.count += 1
        if self.count >= self.D:
            self.prev_min, self.cur_min, self.count = self.cur_min, np.full_like(self.cur_min, np.inf), 0
        noise = np.where(np.isfinite(noise), noise, self.S) * self.bias
        # gain de Wiener « decision-directed » (Ephraim-Malah) : peu de bruit musical
        post = p / (noise + 1e-12)
        xi = 0.98 * self.prev_a2 / (noise + 1e-12) + 0.02 * np.maximum(post - 1, 0)
        g = np.maximum(xi / (1 + xi), self.floor)
        self.prev_a2 = (g * g) * p
        self.gain = g
        return X * self.gain


def has_rnnoise():
    return _find_rnnoise() is not None


def make_denoiser(sr):
    """RNNoise si disponible (48 kHz), sinon le débruiteur spectral."""
    try:
        return RNNoise(sr)
    except Exception:
        return SpectralDenoise(sr)


class GateDB(Node):
    """Noise gate réglable en dB (comme « Niveau de la porte de bruit » de Voicemod).

    Hystérésis de 6 dB + maintien 120 ms pour ne pas hacher la fin des mots.
    """

    def __init__(self, sr, threshold_db=-30.0):
        super().__init__(sr)
        self.set_threshold(threshold_db)
        self.g = 0.0
        self.env = 0.0
        self.hold = 0

    def set_threshold(self, db):
        self.db = float(db)
        self.open_th = 10 ** (self.db / 20)
        self.close_th = 10 ** ((self.db - 6) / 20)

    def process(self, x):
        n = len(x)
        peak = float(np.abs(x).max()) if n else 0.0
        self.env = max(peak, self.env * 0.6)
        if self.env > self.open_th:
            self.hold = int(0.12 * self.sr)
        elif self.env > self.close_th and self.g > 0.5:
            self.hold = max(self.hold, n)
        else:
            self.hold = max(0, self.hold - n)
        target = 1.0 if self.hold > 0 else 0.0
        k = 0.8 if target > self.g else 0.25   # ouverture rapide, fermeture douce
        g_new = self.g + k * (target - self.g)
        ramp = np.linspace(self.g, g_new, n, dtype=np.float32)
        self.g = g_new
        return x * ramp
