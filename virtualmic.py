"""
Micro virtuel « intégré » — ce que Voicemod fait avec son driver voicemodvad.sys
et son outil AudioEndPointTool.exe, refait en Python.

Comment fait Voicemod (analysé sur l'installation locale) :
  * un driver noyau (dérivé de l'exemple Microsoft « sysvad ») crée une paire de
    périphériques : une sortie « Dummy Output (Voicemod) » reliée en boucle à un
    micro « Microphone (Voicemod) » ; l'application joue simplement sa voix
    traitée dans la sortie, et Discord lit le micro ;
  * la sortie est marquée « jamais périphérique par défaut » (INF) pour que le
    son Windows n'y aille pas ;
  * AudioEndPointTool.exe rend le micro virtuel « micro par défaut » de Windows
    via l'interface COM non documentée IPolicyConfig(Vista)::SetDefaultEndpoint,
    donc Discord (réglé sur « Default ») l'utilise sans rien toucher.

On ne peut pas livrer un driver noyau signé depuis Python, alors :
  1. on réutilise un câble déjà installé (driver Voicemod, VB-CABLE, Voicemeeter) ;
  2. sinon on télécharge et installe VB-CABLE (gratuit, donationware) — Windows
     affiche une seule fenêtre pour accepter le pilote, impossible à éviter ;
  3. on rend le micro virtuel « micro par défaut » (comme AudioEndPointTool) et on
     remet l'ancien à la fermeture.
"""
from __future__ import annotations

import ctypes
import platform
import shutil
import sys
import tempfile
import threading
import urllib.request
import zipfile
from ctypes import POINTER, Structure, byref, c_int, c_longlong, c_ushort, c_void_p
from ctypes.wintypes import DWORD, LPCWSTR, LPWSTR, UINT
from dataclasses import dataclass, field
from pathlib import Path

import sounddevice as sd

try:
    import comtypes
    import comtypes.client
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown
except ImportError:  # pragma: no cover
    comtypes = None

VB_CABLE_URL = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack46.zip"

E_RENDER, E_CAPTURE = 0, 1
ROLE_CONSOLE, ROLE_MULTIMEDIA, ROLE_COMMUNICATIONS = 0, 1, 2
ALL_ROLES = (ROLE_CONSOLE, ROLE_MULTIMEDIA, ROLE_COMMUNICATIONS)
DEVICE_STATE_ACTIVE = 1


# --------------------------------------------------------------------------- #
#  Câbles connus : (nom, morceau du nom de la sortie, morceau du nom du micro)
# --------------------------------------------------------------------------- #
@dataclass
class Cable:
    name: str
    render_key: str
    capture_key: str
    out_device: int | None = None        # index sounddevice de la sortie
    out_name: str = ""
    mic_endpoint: str | None = None      # id d'endpoint Windows du micro
    mic_name: str = ""
    outs: dict = field(default_factory=dict)   # API hôte -> (index sounddevice, nom)

    def __str__(self):
        return f"{self.name} ({self.mic_name or self.capture_key})"

    def has_out(self, device_index) -> bool:
        return any(i == device_index for i, _ in self.outs.values())

    def out_for(self, mic_index) -> int | None:
        """Sortie du câble sur la même API hôte que le micro (PortAudio exige la même API en duplex)."""
        try:
            mi = mic_index if mic_index is not None else sd.default.device[0]
            api = sd.query_hostapis(sd.query_devices(mi)["hostapi"])["name"]
            return self.outs.get(api, (self.out_device, ""))[0]
        except Exception:
            return self.out_device


KNOWN_CABLES = [
    Cable("Driver Voicemod", "dummy output", "microphone (voicemod)"),
    Cable("VB-CABLE", "cable input", "cable output"),
    Cable("Voicemeeter", "voicemeeter input", "voicemeeter output"),
    Cable("Voicemeeter AUX", "voicemeeter aux input", "voicemeeter aux output"),
]
# mots qui désignent un micro virtuel (à ne jamais prendre comme vrai micro)
VIRTUAL_MIC_WORDS = ("voicemod", "cable", "voicemeeter", "mappeur", "mapper", "steam streaming", "droidcam",
                     "wo mic", "nvidia broadcast", "virtual")


def is_virtual_mic(name: str) -> bool:
    return any(w in name.lower() for w in VIRTUAL_MIC_WORDS)


# --------------------------------------------------------------------------- #
#  COM : IMMDeviceEnumerator (lecture) et IPolicyConfig (micro par défaut)
# --------------------------------------------------------------------------- #
if comtypes is not None:
    class PROPERTYKEY(Structure):
        _fields_ = [("fmtid", GUID), ("pid", DWORD)]

    class PROPVARIANT(Structure):
        _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                    ("pwszVal", LPWSTR), ("pad", c_longlong)]

    class IPropertyStore(IUnknown):
        _iid_ = GUID("{886d8eeb-8cf2-4446-8d02-cdba1dbdcf99}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(DWORD), "c")),
            COMMETHOD([], HRESULT, "GetAt", (["in"], DWORD, "i"), (["out"], POINTER(PROPERTYKEY), "k")),
            COMMETHOD([], HRESULT, "GetValue", (["in"], POINTER(PROPERTYKEY), "k"),
                      (["out"], POINTER(PROPVARIANT), "v")),
            COMMETHOD([], HRESULT, "SetValue", (["in"], POINTER(PROPERTYKEY), "k"),
                      (["in"], POINTER(PROPVARIANT), "v")),
            COMMETHOD([], HRESULT, "Commit"),
        ]

    class IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Activate", (["in"], POINTER(GUID), "iid"), (["in"], DWORD, "ctx"),
                      (["in"], c_void_p, "p"), (["out"], POINTER(c_void_p), "iface")),
            COMMETHOD([], HRESULT, "OpenPropertyStore", (["in"], DWORD, "access"),
                      (["out"], POINTER(POINTER(IPropertyStore)), "ps")),
            COMMETHOD([], HRESULT, "GetId", (["out"], POINTER(LPWSTR), "id")),
            COMMETHOD([], HRESULT, "GetState", (["out"], POINTER(DWORD), "st")),
        ]

    class IMMDeviceCollection(IUnknown):
        _iid_ = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT), "c")),
            COMMETHOD([], HRESULT, "Item", (["in"], UINT, "i"), (["out"], POINTER(POINTER(IMMDevice)), "d")),
        ]

    class IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumAudioEndpoints", (["in"], c_int, "flow"), (["in"], DWORD, "mask"),
                      (["out"], POINTER(POINTER(IMMDeviceCollection)), "c")),
            COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint", (["in"], c_int, "flow"), (["in"], c_int, "role"),
                      (["out"], POINTER(POINTER(IMMDevice)), "d")),
            COMMETHOD([], HRESULT, "GetDevice", (["in"], LPCWSTR, "id"),
                      (["out"], POINTER(POINTER(IMMDevice)), "d")),
        ]

    # Interface non documentée utilisée par Voicemod (AudioEndPointTool.exe),
    # SoundSwitch, NirCmd... Deux variantes selon la version de Windows.
    _POLICY_HEAD = [
        COMMETHOD([], HRESULT, "GetMixFormat", (["in"], LPCWSTR, "id"), (["out"], POINTER(c_void_p), "f")),
        COMMETHOD([], HRESULT, "GetDeviceFormat", (["in"], LPCWSTR, "id"), (["in"], c_int, "d"),
                  (["out"], POINTER(c_void_p), "f")),
    ]
    _POLICY_TAIL = [
        COMMETHOD([], HRESULT, "SetDeviceFormat", (["in"], LPCWSTR, "id"), (["in"], c_void_p, "a"),
                  (["in"], c_void_p, "b")),
        COMMETHOD([], HRESULT, "GetProcessingPeriod", (["in"], LPCWSTR, "id"), (["in"], c_int, "d"),
                  (["out"], POINTER(c_longlong), "a"), (["out"], POINTER(c_longlong), "b")),
        COMMETHOD([], HRESULT, "SetProcessingPeriod", (["in"], LPCWSTR, "id"), (["in"], POINTER(c_longlong), "p")),
        COMMETHOD([], HRESULT, "GetShareMode", (["in"], LPCWSTR, "id"), (["out"], POINTER(c_void_p), "m")),
        COMMETHOD([], HRESULT, "SetShareMode", (["in"], LPCWSTR, "id"), (["in"], c_void_p, "m")),
        COMMETHOD([], HRESULT, "GetPropertyValue", (["in"], LPCWSTR, "id"), (["in"], POINTER(PROPERTYKEY), "k"),
                  (["out"], POINTER(PROPVARIANT), "v")),
        COMMETHOD([], HRESULT, "SetPropertyValue", (["in"], LPCWSTR, "id"), (["in"], POINTER(PROPERTYKEY), "k"),
                  (["in"], POINTER(PROPVARIANT), "v")),
        COMMETHOD([], HRESULT, "SetDefaultEndpoint", (["in"], LPCWSTR, "id"), (["in"], c_int, "role")),
        COMMETHOD([], HRESULT, "SetEndpointVisibility", (["in"], LPCWSTR, "id"), (["in"], c_int, "visible")),
    ]

    class IPolicyConfigVista(IUnknown):
        _iid_ = GUID("{568b9108-44bf-40b4-9006-86afe5b5a620}")
        _methods_ = _POLICY_HEAD + _POLICY_TAIL

    class IPolicyConfig(IUnknown):
        _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
        _methods_ = _POLICY_HEAD + [
            COMMETHOD([], HRESULT, "ResetDeviceFormat", (["in"], LPCWSTR, "id")),
        ] + _POLICY_TAIL

    CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    CLSID_PolicyConfigVista = GUID("{294935CE-F637-4E7C-A41B-AB255460B862}")
    CLSID_PolicyConfig = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")
    PKEY_Device_FriendlyName = PROPERTYKEY(GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}"), 14)


def _com():
    """Initialise COM pour le thread courant (sans erreur si déjà fait)."""
    if comtypes is None:
        raise RuntimeError("Le module « comtypes » est requis :  pip install comtypes")
    try:
        comtypes.CoInitialize()
    except OSError:
        pass


def _enumerator():
    _com()
    return comtypes.client.CreateObject(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)


def list_endpoints(flow=E_CAPTURE, active_only=True) -> list[tuple[str, str]]:
    """[(id_endpoint, nom convivial)] des périphériques Windows (flow : 0 sortie, 1 micro)."""
    out = []
    try:
        col = _enumerator().EnumAudioEndpoints(flow, DEVICE_STATE_ACTIVE if active_only else 0xF)
        for i in range(col.GetCount()):
            d = col.Item(i)
            try:
                name = d.OpenPropertyStore(0).GetValue(byref(PKEY_Device_FriendlyName)).pwszVal or ""
            except Exception:
                name = ""
            out.append((d.GetId(), name))
    except Exception:
        pass
    return out


def default_endpoint(flow=E_CAPTURE, role=ROLE_COMMUNICATIONS) -> str | None:
    try:
        return _enumerator().GetDefaultAudioEndpoint(flow, role).GetId()
    except Exception:
        return None


def set_default_endpoint(endpoint_id: str, roles=ALL_ROLES) -> bool:
    """Rend `endpoint_id` périphérique par défaut pour les rôles donnés (comme AudioEndPointTool)."""
    _com()
    last = None
    for clsid, iface in ((CLSID_PolicyConfigVista, IPolicyConfigVista), (CLSID_PolicyConfig, IPolicyConfig)):
        try:
            pc = comtypes.client.CreateObject(clsid, interface=iface)
            for r in roles:
                pc.SetDefaultEndpoint(endpoint_id, r)
            return True
        except Exception as e:  # pragma: no cover
            last = e
    print(f"[virtualmic] SetDefaultEndpoint impossible : {last}", file=sys.stderr)
    return False


# --------------------------------------------------------------------------- #
#  Détection du câble
# --------------------------------------------------------------------------- #
def _sd_outputs():
    apis = [a["name"] for a in sd.query_hostapis()]
    return [(i, d["name"], apis[d["hostapi"]]) for i, d in enumerate(sd.query_devices()) if d["max_output_channels"]]


def find_cables() -> list[Cable]:
    """Câbles présents, le meilleur en premier (sortie trouvée par sounddevice, micro par Windows)."""
    outs = _sd_outputs()
    mics = list_endpoints(E_CAPTURE)
    found = []
    for proto in KNOWN_CABLES:
        c = Cable(proto.name, proto.render_key, proto.capture_key)
        cands = [(i, n, api) for i, n, api in outs if proto.render_key in n.lower()]
        if not cands:
            continue
        # WASAPI = nom complet et latence basse ; sinon MME/DirectSound
        cands.sort(key=lambda t: ("WASAPI" not in t[2], "DirectSound" not in t[2]))
        c.out_device, c.out_name = cands[0][0], cands[0][1]
        for i, n, api in cands:
            c.outs.setdefault(api, (i, n))
        for eid, name in mics:
            if proto.capture_key in name.lower():
                c.mic_endpoint, c.mic_name = eid, name
                break
        found.append(c)
    return found


def find_cable() -> Cable | None:
    cables = find_cables()
    return cables[0] if cables else None


def rescan_devices():
    """Relit la liste des périphériques PortAudio (après installation d'un driver)."""
    try:
        sd._terminate()
        sd._initialize()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
#  Micro par défaut Windows (et restauration)
# --------------------------------------------------------------------------- #
class DefaultMic:
    """Met le micro virtuel par défaut pour Discord & co, puis remet l'ancien."""

    def __init__(self):
        self.previous: dict[int, str] = {}
        self.active: str | None = None

    def apply(self, endpoint_id: str) -> bool:
        if not endpoint_id or endpoint_id == self.active:
            return True
        prev = {r: default_endpoint(E_CAPTURE, r) for r in ALL_ROLES}
        if all(v == endpoint_id for v in prev.values()):
            self.active = endpoint_id
            return True
        if not self.previous:  # ne garder que le tout premier état
            self.previous = {r: v for r, v in prev.items() if v and v != endpoint_id}
        ok = set_default_endpoint(endpoint_id)
        if ok:
            self.active = endpoint_id
        return ok

    def restore(self):
        if not self.previous:
            self.active = None
            return
        for r, eid in self.previous.items():
            try:
                set_default_endpoint(eid, (r,))
            except Exception:
                pass
        self.previous, self.active = {}, None


# --------------------------------------------------------------------------- #
#  Installation de VB-CABLE
# --------------------------------------------------------------------------- #
class SHELLEXECUTEINFOW(Structure):
    _fields_ = [("cbSize", DWORD), ("fMask", ctypes.c_ulong), ("hwnd", c_void_p), ("lpVerb", LPCWSTR),
                ("lpFile", LPCWSTR), ("lpParameters", LPCWSTR), ("lpDirectory", LPCWSTR), ("nShow", c_int),
                ("hInstApp", c_void_p), ("lpIDList", c_void_p), ("lpClass", LPCWSTR), ("hkeyClass", c_void_p),
                ("dwHotKey", DWORD), ("hIcon", c_void_p), ("hProcess", c_void_p)]


def run_elevated(exe: str, args: str = "", cwd: str | None = None, timeout_s: int = 600) -> int | None:
    """Lance `exe` en administrateur (UAC) et attend la fin. Retourne le code de sortie, None si refusé."""
    SEE_MASK_NOCLOSEPROCESS = 0x40
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb, info.lpFile, info.lpParameters, info.lpDirectory = "runas", exe, args, cwd
    info.nShow = 1
    if not ctypes.windll.shell32.ShellExecuteExW(byref(info)):
        return None  # UAC refusé
    k32 = ctypes.windll.kernel32
    k32.WaitForSingleObject(info.hProcess, timeout_s * 1000)
    code = DWORD()
    k32.GetExitCodeProcess(info.hProcess, byref(code))
    k32.CloseHandle(info.hProcess)
    return code.value


def install_vb_cable(progress=lambda msg: None) -> tuple[bool, str]:
    """Télécharge VB-CABLE et lance son installateur (silencieux, hors fenêtre Windows « pilote »).

    Retourne (succès, message). Les sorties/entrées par défaut de Windows sont
    préservées (VB-CABLE a tendance à devenir la sortie par défaut après installation).
    """
    before = {(f, r): default_endpoint(f, r) for f in (E_RENDER, E_CAPTURE) for r in ALL_ROLES}
    tmp = Path(tempfile.mkdtemp(prefix="pyvoicemod_vbcable_"))
    try:
        progress("Téléchargement de VB-CABLE…")
        zpath = tmp / "vbcable.zip"
        req = urllib.request.Request(VB_CABLE_URL, headers={"User-Agent": "PyVoiceMod"})
        with urllib.request.urlopen(req, timeout=60) as r, open(zpath, "wb") as f:
            shutil.copyfileobj(r, f)
        if not zipfile.is_zipfile(zpath):
            return False, "Le fichier téléchargé n'est pas une archive valide."
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp)
        exes = [p for p in tmp.rglob("*.exe") if "setup" in p.name.lower()]
        arch = platform.machine().lower()
        want = "arm64" if "arm" in arch else ("x64" if sys.maxsize > 2**32 else "")
        exes.sort(key=lambda p: (want not in p.name.lower(), "x64" in p.name.lower() and want != "x64"))
        if not exes:
            return False, "Installateur introuvable dans l'archive VB-CABLE."
        setup = exes[0]
        progress("Installation du pilote… accepte la fenêtre Windows « Installer ce pilote »")
        code = run_elevated(str(setup), "-i -h", str(setup.parent))
        if code is None:
            return False, "Installation annulée (droits administrateur refusés)."
        progress("Pilote installé, recherche du nouveau micro…")
        rescan_devices()
        # Windows peut avoir basculé la sortie par défaut vers « CABLE Input » : on remet l'ancienne.
        for (flow, role), eid in before.items():
            if eid and default_endpoint(flow, role) != eid:
                set_default_endpoint(eid, (role,))
        if find_cable() is None:
            return False, "VB-CABLE installé mais pas encore visible : redémarre le PC puis relance Py Mod."
        return True, "Micro virtuel installé."
    except Exception as e:
        return False, f"Échec de l'installation : {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_vb_cable_async(done, progress=lambda msg: None):
    """Lance install_vb_cable dans un thread ; `done(ok, msg)` est appelé à la fin (depuis le thread)."""
    def work():
        _com()
        done(*install_vb_cable(progress))
    t = threading.Thread(target=work, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print("Câbles détectés :")
    for c in find_cables():
        print(f"  - {c.name}: sortie #{c.out_device} « {c.out_name} » → micro « {c.mic_name} » ({c.mic_endpoint})")
    for r, lab in zip(ALL_ROLES, ("console", "multimédia", "communications")):
        print(f"micro par défaut ({lab}) : {default_endpoint(E_CAPTURE, r)}")
