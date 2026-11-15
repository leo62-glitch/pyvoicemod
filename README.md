# Py Mod (PyVoiceMod)

A voice changer + soundboard written in **100% Python**, with a **Qt (PySide6)**
interface. The microphone goes through a real-time effects chain (numpy / scipy),
is mixed with a soundboard, then sent to a virtual microphone that Discord, games
or OBS see as a regular mic.

## Features

- **Voices**: a catalogue of presets (robot, monster, chipmunk, echo, vocoder,
  auto-tune, wah-wah…) built as graphs of DSP nodes written from scratch
  (`dsp.py`, `presets.py`).
- **Soundboard**: sound library, per-folder soundboards, playback modes
  (overlap, restart, stop, loop…), fades, favourites, images, **global Win32
  hotkeys** that keep working while a game has focus (`hotkeys.py`).
- **Voice lab**: 3-band equalizer and fine-tuning controls.
- **Audio settings**: choice of microphone, virtual output and headphones
  ("hear myself"), separate voice / sound gains, mixer mode.
- **Virtual microphone**: automatic detection and installation of VB-CABLE
  (`virtualmic.py`), then switching of the Windows default microphone. No
  Voicemod file or driver is used.
- **Advanced settings** (like Voicemod): background noise reduction (RNNoise,
  with a built-in numpy fallback), noise gate with adjustable level, and
  "bypass system audio processing" (WASAPI RAW mode on the microphone).
- Low-latency PortAudio engine (sounddevice), with an automatic fallback to two
  buffer-linked streams when the microphone and the output are not on the same
  Windows host API (`engine.py`).

## Installation

```powershell
git clone https://github.com/leo62-glitch/pyvoicemod.git
cd pyvoicemod
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install pyrnnoise --no-deps   # optional: better noise reduction
.\.venv\Scripts\python.exe gui_qt.py
```

To act as a microphone in another application, Py Mod uses VB-CABLE
(VB-Audio Virtual Cable, free). If it is not installed, Py Mod downloads and
installs it automatically and silently on launch (only the Windows UAC prompt
appears), after which "CABLE Output" becomes the Windows default microphone. If an application has a
specific microphone selected, pick "CABLE Output" there.

On the first launch without any sounds, the interface can generate a few
synthesized demo sounds (`demo_sounds.py`). Settings are saved in `config.json`
next to the script (not versioned).

## Layout

| File | Role |
|---|---|
| `gui_qt.py` | Qt interface: Voices, Sounds, My soundboards, Voice lab, Settings pages |
| `engine.py` | Real-time audio engine: mic → voice → (+ soundboard) → virtual output / headphones |
| `dsp.py` | Block-based DSP nodes (filters, pitch shift, FFT, reverb, distortion…) |
| `presets.py` | Voice catalogue = node chains |
| `soundboard.py` | Sound library, per-sound options, mixer |
| `hotkeys.py` | Global hotkeys (RegisterHotKey) |
| `virtualmic.py` | Virtual microphone detection / installation |
| `demo_sounds.py` | Demo sound generation |
| `sons/` | Sounds of the "General" soundboard and their settings (`soundboard.json`) |

Windows only (global hotkeys and the virtual microphone rely on the Win32 API).
