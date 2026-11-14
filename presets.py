"""Catalogue de voix = chaînes de noeuds DSP (réglages originaux).

Chaque voix : (id, nom affiché, icône, catégorie, fabrique(sr) -> Node)
"""
from dsp import (Chain, Parallel, Gain, NoiseGate, Limiter, Filter, RingMod, Tremolo,
                 Distortion, Bitcrusher, Echo, Comb, Chorus, Reverb, PitchShift,
                 PitchShiftFFT, RobotFFT, Whisper, VocoderFFT, AutoTune, WahWah)


def _wrap(sr, *nodes):
    return Chain(sr, [NoiseGate(sr), *nodes, Limiter(sr)])


VOICES = [
    # --- Basiques -----------------------------------------------------------
    ("normal",     "Clean",        "🎙️", "Basiques",  lambda sr: _wrap(sr)),
    ("femme",      "Voix aiguë",   "🌸", "Basiques",  lambda sr: _wrap(sr, PitchShiftFFT(sr, +5, formant=1.18))),
    ("homme",      "Voix grave",   "🧔", "Basiques",  lambda sr: _wrap(sr, PitchShiftFFT(sr, -5, formant=0.86))),
    ("enfant",     "Enfant",       "🧒", "Basiques",  lambda sr: _wrap(sr, PitchShiftFFT(sr, +8, formant=1.3))),
    ("geant",      "Géant",        "🗿", "Basiques",  lambda sr: _wrap(sr, PitchShiftFFT(sr, -10, formant=0.72),
                                                                       Reverb(sr, 0.8, 0.2))),
    ("chipmunk",   "Écureuil",     "🐿️", "Basiques",  lambda sr: _wrap(sr, PitchShiftFFT(sr, +12, keep_formants=False))),
    # --- Créatures ----------------------------------------------------------
    ("monstre",    "Monstre",      "👹", "Créatures", lambda sr: _wrap(sr, PitchShiftFFT(sr, -9, formant=0.7), Distortion(sr, 3),
                                                                       Filter(sr, "lowpass", 2500), Reverb(sr, 0.7, 0.2), Gain(sr, 3))),
    ("demon",      "Démon",        "😈", "Créatures", lambda sr: _wrap(sr, Parallel(sr, [(PitchShiftFFT(sr, -12, formant=0.65), 0.7),
                                                                                         (PitchShiftFFT(sr, -5, formant=0.8), 0.4)]),
                                                                       Distortion(sr, 2.5), Reverb(sr, 0.85, 0.35))),
    ("fantome",    "Fantôme",      "👻", "Créatures", lambda sr: _wrap(sr, Whisper(sr), Reverb(sr, 0.92, 0.6), Tremolo(sr, 3, 0.4), Gain(sr, 4))),
    ("alien",      "Alien",        "👽", "Créatures", lambda sr: _wrap(sr, PitchShiftFFT(sr, +3, formant=1.4), Chorus(sr, 3, 2.5, 4.0, 0.6),
                                                                       Tremolo(sr, 9, 0.5), Reverb(sr, 0.6, 0.25), Gain(sr, 8))),
    ("gobelin",    "Gobelin",      "🧌", "Créatures", lambda sr: _wrap(sr, PitchShiftFFT(sr, +6, formant=0.8), Distortion(sr, 2))),
    # --- Machines -----------------------------------------------------------
    ("robot",      "Robot",        "🤖", "Machines",  lambda sr: _wrap(sr, RobotFFT(sr, 120), Comb(sr, 4.0, 0.5), Gain(sr, 3))),
    ("dalek",      "Ring-mod",     "🛸", "Machines",  lambda sr: _wrap(sr, RingMod(sr, 30), Distortion(sr, 2), Gain(sr, 4))),
    ("vocoder",    "Vocoder",      "🎹", "Machines",  lambda sr: _wrap(sr, VocoderFFT(sr, (110, 138.6, 164.8)), Chorus(sr), Gain(sr, 7))),
    ("8bit",       "8-bit",        "👾", "Machines",  lambda sr: _wrap(sr, PitchShiftFFT(sr, +4), Bitcrusher(sr, 5, 8))),
    ("autotune",   "Autotune",     "🎶", "Machines",  lambda sr: _wrap(sr, AutoTune(sr, speed=1.0), Reverb(sr, 0.6, 0.15))),
    # --- Ambiances ----------------------------------------------------------
    ("radio",      "Radio",        "📻", "Ambiances", lambda sr: _wrap(sr, Filter(sr, "bandpass", (400, 3000), 4), Distortion(sr, 4), Gain(sr, 2))),
    ("telephone",  "Téléphone",    "☎️", "Ambiances", lambda sr: _wrap(sr, Filter(sr, "bandpass", (300, 3400), 6), Bitcrusher(sr, 8, 3), Gain(sr, 4))),
    ("chuchote",   "Chuchotement", "🤫", "Ambiances", lambda sr: _wrap(sr, Whisper(sr), Gain(sr, 6))),
    ("cathedrale", "Cathédrale",   "⛪", "Ambiances", lambda sr: _wrap(sr, Reverb(sr, 0.92, 0.55))),
    ("echo",       "Canyon",       "🏜️", "Ambiances", lambda sr: _wrap(sr, Echo(sr, 280, 0.5, 0.5))),
    ("chorale",    "Chorale",      "👥", "Ambiances", lambda sr: _wrap(sr, Parallel(sr, [(Gain(sr), 0.5), (PitchShiftFFT(sr, -12), 0.35),
                                                                                         (PitchShiftFFT(sr, +7), 0.25)]),
                                                                       Chorus(sr), Reverb(sr, 0.8, 0.3), Gain(sr, 7))),
    ("wahwah",     "Wah-wah",      "🎸", "Ambiances", lambda sr: _wrap(sr, WahWah(sr), Gain(sr, 5))),
    ("flanger",    "Jet",          "✈️", "Ambiances", lambda sr: _wrap(sr, Chorus(sr, 2.5, 2.0, 0.25, 0.5), Gain(sr, 3))),
]


def custom_voice(sr, pitch=0.0, formant=1.0, robot=False, distortion=0.0, echo=0.0, reverb=0.0):
    """Voix personnalisée construite depuis les curseurs de l'interface."""
    nodes = []
    if robot:
        nodes.append(RobotFFT(sr, 120))
    if abs(pitch) > 0.05 or abs(formant - 1) > 0.01:
        nodes.append(PitchShiftFFT(sr, pitch, formant=formant))
    if distortion > 0.01:
        nodes.append(Distortion(sr, 1 + distortion * 10))
    if echo > 0.01:
        nodes.append(Echo(sr, 260, 0.45, echo))
    if reverb > 0.01:
        nodes.append(Reverb(sr, 0.88, reverb))
    return _wrap(sr, *nodes)


PRESETS = {vid: fn for vid, _, _, _, fn in VOICES}
