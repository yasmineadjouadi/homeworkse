import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from device_scanner import scan_all

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

KEYUP = 0x0002                      
INJECTED = 0x10                     
KEY_UP_MESSAGES = (0x0101, 0x0105)  
PNPUTIL_OK = (0, 3010)               
MAX_SECONDS = 60

VK_CAPS = 0x14
LEDS = {"Verr. Maj": VK_CAPS, "Verr. Num": 0x90, "Arrêt défil.": 0x91}
MODIFIERS = {1: 0x10, 2: 0x11, 4: 0x12}  

# Types nécessaires au hook clavier
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.VkKeyScanW.restype = ctypes.c_short
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


# ---------- Outils ----------

def is_admin():
    return bool(ctypes.windll.shell32.IsUserAnAdmin())

def key(vk, up=False):
    """Simule l'appui (ou le relâchement) d'une touche."""
    user32.keybd_event(vk, 0, KEYUP if up else 0, 0)

def press(vk):
    key(vk)
    key(vk, up=True)

def ask_seconds(default):
    answer = input(f"Durée en secondes (1 à {MAX_SECONDS}) [{default}] : ").strip()
    if not answer:
        return default
    if answer.isdigit() and 1 <= int(answer) <= MAX_SECONDS:
        return int(answer)
    print("Durée invalide.")
    return None

def ask_letter(prompt):
    """Demande une lettre A-Z et retourne le code de la touche (le code d'une lettre = son code ASCII)."""
    answer = input(prompt).strip()
    if len(answer) == 1 and answer.isascii() and answer.isalpha():
        return ord(answer.upper())
    print("Entre une seule lettre (A à Z).")
    return None

def run_hook(callback, seconds):
    """Installe un hook clavier, le garde `seconds` secondes, puis le retire."""
    proc = HOOKPROC(callback)   # garder une référence, sinon Python la détruit
    hook = user32.SetWindowsHookExW(13, proc, kernel32.GetModuleHandleW(None), 0)   # 13 = WH_KEYBOARD_LL
    if not hook:
        print("Impossible d'installer le hook clavier.")
        return False
    msg = wintypes.MSG()
    end = time.time() + seconds
    try:
        while time.time() < end:   # la boucle de messages est obligatoire pour que le hook fonctionne
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.01)
    finally:
        user32.UnhookWindowsHookEx(hook)   # le clavier redevient normal
    return True


# ---------- État du clavier (partie 1) ----------

def get_keyboards():
    return [d for d in scan_all() if d.category == "Clavier" and d.device_id]

def show_state():
    try:
        keyboards = get_keyboards()
    except RuntimeError as error:
        print(f"Erreur : {error}")
        return []
    print("État du clavier :")
    if not keyboards:
        print("  Aucun clavier détecté.")
    for kb in keyboards:
        print(f"  - {kb.name}  [{kb.status}]")
    return keyboards


# ---------- 1. Désactiver temporairement ----------

def run_pnputil(action, device_id):
    """action : "enable" ou "disable". Retourne True si Windows a accepté."""
    try:
        result = subprocess.run(["pnputil", f"/{action}-device", device_id],
                                capture_output=True, text=True, encoding="oem", errors="replace")
    except OSError as error:
        print(f"pnputil impossible à lancer : {error}")
        return False
    if result.returncode not in PNPUTIL_OK:
        print((result.stdout or result.stderr).strip())
        return False
    return True

def choose_keyboard(keyboards):
    if len(keyboards) == 1:
        return keyboards[0]
    for number, kb in enumerate(keyboards, start=1):
        print(f"  {number}. {kb.name}")
    answer = input("Numéro du clavier : ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(keyboards):
        return keyboards[int(answer) - 1]
    print("Numéro invalide.")
    return None

def block_keys(seconds):
    """Avale toutes les touches pendant `seconds` secondes."""
    def callback(code, wparam, lparam):
        if code == 0:
            return 1   # la touche est jetée
        return user32.CallNextHookEx(None, code, wparam, lparam)

    print(f"Touches bloquées pendant {seconds} s...")
    if run_hook(callback, seconds):
        print("Touches débloquées.")

def disable_keyboard(keyboards):
    if not is_admin():
        print("Droits administrateur requis : relance le terminal en « Exécuter en tant qu'administrateur ».")
        return
    if not keyboards:
        print("Aucun clavier détecté.")
        return
    device = choose_keyboard(keyboards)
    if device is None:
        return
    seconds = ask_seconds(5)
    if seconds is None:
        return

    # Sécurité 1 : un processus séparé réactive le clavier même si ce programme plante.
    subprocess.Popen(
        f'ping -n {seconds + 3} 127.0.0.1 >nul & pnputil /enable-device "{device.device_id}"',
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=0x08000000)   # 0x08000000 = pas de fenêtre noire

    if run_pnputil("disable", device.device_id):
        print(f"Clavier désactivé : {device.name}")
        try:
            for left in range(seconds, 0, -1):
                print(f"\rRéactivation dans {left:>2} s...", end="", flush=True)
                time.sleep(1)
            print()
        finally:
            # Sécurité 2 : réactivation dans tous les cas (fin normale, Ctrl+C, erreur).
            if run_pnputil("enable", device.device_id):
                print("Clavier réactivé.")
            else:
                print("IMPORTANT : réactivation impossible, le processus de secours réessaiera.")
    else:
        # Le clavier PS/2 d'une VM est un périphérique système critique : Windows refuse.
        print("\nWindows a refusé de désactiver ce clavier (voir le message ci-dessus).")
        print("On bloque donc ses touches à la place.")
        block_keys(seconds)


# ---------- 2. Changer le rôle d'une touche ----------

def change_key():
    source = ask_letter("Touche à remplacer (une lettre) : ")
    if source is None:
        return
    target = ask_letter("Lettre écrite à la place : ")
    if target is None:
        return
    seconds = ask_seconds(15)
    if seconds is None:
        return

    def callback(code, wparam, lparam):
        if code == 0:
            info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            # On ignore les touches simulées (les nôtres), sinon le programme se rappellerait lui-même.
            if info.vkCode == source and not (info.flags & INJECTED):
                key(target, up=wparam in KEY_UP_MESSAGES)
                return 1   # la touche d'origine est bloquée
        return user32.CallNextHookEx(None, code, wparam, lparam)

    print(f"Pendant {seconds} s : {chr(source)} écrit {chr(target)}. Teste dans le Bloc-notes.")
    if run_hook(callback, seconds):
        print("Touche remise à la normale.")


# ---------- 3. Voyants ----------

def leds_state():
    return "  ".join(f"{name} {'ON' if user32.GetKeyState(vk) & 1 else 'OFF'}"
                     for name, vk in LEDS.items())

def blink_leds():
    saved = {vk: user32.GetKeyState(vk) & 1 for vk in LEDS.values()}
    print("Départ :", leds_state())
    print("Clignotement en cours, ne tape rien...")
    try:
        for turn in range(1, 7):
            for vk in LEDS.values():
                press(vk)   # chaque appui inverse l'état de la touche
            time.sleep(0.4)
            print(f"  tour {turn} : {leds_state()}")
    finally:
        for vk, state in saved.items():   # remet chaque voyant comme au départ
            if (user32.GetKeyState(vk) & 1) != state:
                press(vk)
    time.sleep(0.2)
    print("Retour :", leds_state())


# ---------- 4. Écrire un texte ----------

def type_text():
    text = input("Texte à écrire : ")
    if not text:
        return
    print("Clique dans le Bloc-notes : écriture dans 3 s...")
    time.sleep(3)

    caps_was_on = user32.GetKeyState(VK_CAPS) & 1
    if caps_was_on:
        press(VK_CAPS)   # Verr. Maj inverserait les majuscules
        time.sleep(0.1)
    skipped = ""
    try:
        for char in text:
            code = user32.VkKeyScanW(ord(char))   # touche + modificateurs pour ce caractère
            if code == -1:
                skipped += char   # caractère absent du clavier
                continue
            vk, state = code & 0xFF, code >> 8
            modifiers = [m for bit, m in MODIFIERS.items() if state & bit]
            for m in modifiers:
                key(m)
            press(vk)
            for m in reversed(modifiers):
                key(m, up=True)
            time.sleep(0.05)
    finally:
        if caps_was_on:
            press(VK_CAPS)
    print(f"Caractères absents du clavier, ignorés : {skipped}" if skipped else "Terminé.")


# ---------- Menu ----------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    while True:
        print("\n==============================")
        keyboards = show_state()
        print("\n1. Désactiver temporairement le clavier")
        print("2. Changer le rôle d'une touche (temporaire)")
        print("3. Voyants (Maj / Verr. Num / Arrêt défil.)")
        print("4. Écrire un texte automatiquement")
        print("5. Quitter")
        choice = input("\nChoix : ").strip()
        if choice == "1":
            disable_keyboard(keyboards)
        elif choice == "2":
            change_key()
        elif choice == "3":
            blink_leds()
        elif choice == "4":
            type_text()
        elif choice == "5":
            break
        else:
            print("Choix invalide.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nArrêt.")