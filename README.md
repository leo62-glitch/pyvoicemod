# Py Mod (PyVoiceMod)

Un voice changer + soundboard **100 % Python**, avec une interface **Qt (PySide6)**.
Le micro passe par une chaîne d'effets temps réel (numpy / scipy), est mixé avec
une soundboard, puis envoyé vers un micro virtuel que Discord, les jeux ou OBS
voient comme un micro normal.

## Fonctionnalités

- **Voix** : catalogue de presets (robot, monstre, chipmunk, écho, vocodeur,
  auto-tune, wah-wah…) construits comme des graphes de nœuds DSP écrits from scratch
  (`dsp.py`, `presets.py`).
- **Soundboard** : bibliothèque de sons, soundboards par dossier, modes de lecture
  (superposer, redémarrer, stopper, boucle…), fondu, favoris, images, **raccourcis
  clavier globaux** Win32 qui marchent même quand un jeu a le focus (`hotkeys.py`).
- **Labo de voix** : égaliseur 3 bandes et réglages fins.
- **Réglages audio** : choix du micro, de la sortie virtuelle et du casque
  (« m'entendre »), gains séparés voix / sons, mode mixeur.
- **Micro virtuel** : détection et installation assistée d'un câble audio virtuel
  (`virtualmic.py`), le rôle que joue le driver noyau dans Voicemod.
- Moteur PortAudio (sounddevice) à faible latence, avec repli automatique sur deux
  flux reliés par un tampon quand micro et sortie ne sont pas sur la même API
  Windows (`engine.py`).

## Installation

```powershell
git clone https://github.com/leo62-glitch/pyvoicemod.git
cd pyvoicemod
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe gui_qt.py
```

Pour servir de micro dans une autre application, installe un câble audio virtuel
(par exemple VB-Audio Virtual Cable), choisis « CABLE Input » comme sortie
virtuelle dans *Réglages audio*, et « CABLE Output » comme micro dans Discord.
L'onglet Réglages propose cette installation.

Au premier lancement sans son, l'interface peut générer quelques sons de démo
synthétisés (`demo_sounds.py`). Les réglages sont enregistrés dans `config.json`
à côté du script (non versionné).

## Structure

| Fichier | Rôle |
|---|---|
| `gui_qt.py` | Interface Qt : pages Voix, Sons, Mes soundboards, Labo de voix, Réglages |
| `engine.py` | Moteur audio temps réel micro → voix → (+ soundboard) → sortie virtuelle / casque |
| `dsp.py` | Nœuds DSP bloc par bloc (filtres, pitch shift, FFT, réverb, distorsion…) |
| `presets.py` | Catalogue des voix = chaînes de nœuds |
| `soundboard.py` | Bibliothèque de sons, options par son, mixeur |
| `hotkeys.py` | Raccourcis clavier globaux (RegisterHotKey) |
| `virtualmic.py` | Détection / installation d'un micro virtuel |
| `demo_sounds.py` | Génération de sons de démo |
| `sons/` | Sons de la soundboard « Général » et leurs réglages (`soundboard.json`) |

Windows uniquement (raccourcis globaux et micro virtuel reposent sur l'API Win32).
