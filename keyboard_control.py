"""
keyboard_control.py

"""

import ctypes
import msvcrt
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from device_scanner import scan_all
from device_info import get_details, clear_cache


LOG_FILE = Path(__file__).with_name("keyboard_test_log.txt")

NORMAL_KEYS = {
    "\r": "Entrée",
    "\t": "Tabulation",
    "\x08": "Retour arrière",
    " ": "Espace",
}

# Deuxième code renvoyé par getwch() après \x00 ou \xe0.
EXTENDED_KEYS = {
    "H": "Flèche haut",
    "P": "Flèche bas",
    "K": "Flèche gauche",
    "M": "Flèche droite",
    "G": "Début",
    "O": "Fin",
    "I": "Page précédente",
    "Q": "Page suivante",
    "R": "Inser",
    "S": "Suppr",
    "\x85": "F11",
    "\x86": "F12",
}
for _number, _code in enumerate(";<=>?@ABCD", start=1):
    EXTENDED_KEYS[_code] = f"F{_number}"

# Touches à vérifier dans le test guidé.
TARGET_KEYS = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + [str(n) for n in range(10)]
    + ["Espace", "Entrée", "Tabulation", "Retour arrière", "Suppr"]
    + ["Flèche haut", "Flèche bas", "Flèche gauche", "Flèche droite"]
    + [f"F{n}" for n in range(1, 13)]
)

STATUS_HELP = {
    "OK": "fonctionne normalement",
    "Desactive": "désactivé dans Windows",
    "Erreur": "Windows signale une erreur (voir le Gestionnaire de périphériques)",
    "Inconnu": "état non fourni par Windows",
}

# pnputil renvoie 3010 quand l'opération a réussi mais qu'un redémarrage est conseillé.
PNPUTIL_OK_CODES = (0, 3010)
PNPUTIL_REBOOT_CODE = 3010

DEFAULT_TEMP_SECONDS = 10
MAX_TEMP_SECONDS = 60


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def setup_console():
    """Force l'UTF-8 pour afficher correctement les accents."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def is_admin():
    """Indique si le programme tourne avec les droits administrateur."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def get_keyboards():
    """Retourne la liste à jour des claviers détectés."""
    clear_cache()
    return [
        device for device in scan_all()
        if device.category == "Clavier"
    ]


def read_key():
    """Lit une touche et retourne son nom lisible."""
    key = msvcrt.getwch()

    if key in ("\x00", "\xe0"):
        code = msvcrt.getwch()
        return EXTENDED_KEYS.get(code, f"Touche spéciale {code!r}")

    if key in NORMAL_KEYS:
        return NORMAL_KEYS[key]

    if key == "\x1b":
        return "Échap"

    if key == "\x03":
        return "Ctrl+C"

    if 1 <= ord(key) <= 26:
        return f"Ctrl+{chr(ord(key) + 64)}"

    if key.isprintable():
        return key.upper() if key.isalpha() else key

    return f"Code {ord(key)}"


# ---------------------------------------------------------------------------
# Détection
# ---------------------------------------------------------------------------

def detect_keyboard():
    """Détecte les claviers et affiche leurs informations."""
    try:
        keyboards = get_keyboards()

        if not keyboards:
            print("Aucun clavier détecté.")
            return

        for keyboard in keyboards:
            get_details(keyboard)

            print("\n--- Clavier détecté ---")
            print("Nom :", keyboard.name)
            print("Fabricant :", keyboard.manufacturer)

            help_text = STATUS_HELP.get(keyboard.status, "")
            suffix = f" ({help_text})" if help_text else ""
            print(f"État : {keyboard.status}{suffix}")

            for label, value in keyboard.details.items():
                print(f"{label} : {value}")

    except (RuntimeError, OSError) as error:
        print("Erreur de détection :", error)


# ---------------------------------------------------------------------------
# Tests des touches
# ---------------------------------------------------------------------------

def _open_log():
    log = LOG_FILE.open("a", encoding="utf-8")
    log.write(f"\n--- Début du test : {datetime.now():%d/%m/%Y %H:%M:%S} ---\n")
    return log


def _write_log(log, text):
    if log:
        log.write(f"{datetime.now():%H:%M:%S}  {text}\n")
        log.flush()


def _close_log(log):
    if log:
        log.write("--- Fin du test ---\n")
        log.close()


def test_keyboard(save_log=False):
    """Teste librement les touches saisies dans le terminal."""
    print("\n=== TEST DU CLAVIER ===")
    print("Tape des touches dans ce terminal.")
    print("Appuie sur Échap pour arrêter le test.")

    log = None
    pressed = set()
    total = 0
    start = time.time()

    try:
        if save_log:
            log = _open_log()

        while True:
            name = read_key()

            if name == "Échap":
                break

            total += 1
            pressed.add(name)
            print("Touche :", name)
            _write_log(log, name)

    except KeyboardInterrupt:
        print("\nTest interrompu.")

    finally:
        _close_log(log)

    print(
        f"\nTest terminé : {total} appuis, "
        f"{len(pressed)} touches différentes, "
        f"{time.time() - start:.1f} s."
    )


def guided_test():
    """Demande d'appuyer sur chaque touche courante et signale celles qui manquent."""
    print("\n=== TEST GUIDÉ DU CLAVIER ===")
    print("Appuie sur toutes les touches : lettres, chiffres,")
    print("espace, entrée, flèches, F1 à F12, etc.")
    print("Appuie sur Échap pour terminer.\n")

    remaining = list(TARGET_KEYS)

    try:
        while remaining:
            name = read_key()

            if name == "Échap":
                break

            if name in remaining:
                remaining.remove(name)
                print(f"OK : {name:<16} (reste {len(remaining)})")
            else:
                print(f"    {name} (déjà testée ou hors liste)")

    except KeyboardInterrupt:
        print("\nTest interrompu.")

    if remaining:
        print(f"\n{len(remaining)} touche(s) non testée(s) :")
        print(", ".join(remaining))
        print("Elles peuvent être défectueuses ou simplement oubliées.")
    else:
        print("\nToutes les touches de la liste ont répondu.")


def keyboard_logger():
    """Enregistre une session de test volontaire."""
    print("\nJournal local :", LOG_FILE)
    print("N'entre aucun mot de passe ni donnée confidentielle.")
    test_keyboard(save_log=True)



# Contrôle : activer / désactiver / redémarrer


def run_pnputil(action, device_id):
    """
    Exécute pnputil /<action>-device sur un périphérique.
    action : "enable", "disable" ou "restart".
    Retourne (succès, message, redémarrage_conseillé).
    """
    try:
        result = subprocess.run(
            ["pnputil", f"/{action}-device", device_id],
            capture_output=True,
            text=True,
            encoding="oem",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError:
        return False, "pnputil introuvable (Windows 10 version 2004 ou plus requis).", False
    except subprocess.TimeoutExpired:
        return False, "Délai dépassé.", False
    except OSError as error:
        return False, str(error), False

    message = (result.stdout or result.stderr or "").strip()
    success = result.returncode in PNPUTIL_OK_CODES
    reboot = result.returncode == PNPUTIL_REBOOT_CODE

    return success, message, reboot


def apply_action(action, device, label):
    """Exécute une action et affiche le résultat."""
    print(f"\n{label} : {device.name}...")
    success, message, reboot = run_pnputil(action, device.device_id)

    if success:
        print("Opération réussie.")
        if reboot:
            print("Un redémarrage de Windows est conseillé pour finaliser.")
    else:
        print("Échec de l'opération.")
        if message:
            print(message)

    return success


def choose_keyboard(keyboards):
    """Fait choisir un clavier dans la liste. Retourne None si annulé."""
    print("\nClaviers disponibles :")

    for number, keyboard in enumerate(keyboards, start=1):
        print(f"  {number}. {keyboard.name}  [{keyboard.status}]")

    answer = input("\nNuméro du clavier (Entrée pour annuler) : ").strip()

    if not answer:
        return None

    if not answer.isdigit() or not 1 <= int(answer) <= len(keyboards):
        print("Numéro invalide.")
        return None

    return keyboards[int(answer) - 1]


def ask_seconds(prompt, default=None):
    """Demande une durée en secondes. Retourne None si la réponse est vide sans défaut."""
    answer = input(prompt).strip()

    if not answer:
        return default

    if not answer.isdigit() or int(answer) <= 0:
        print("Durée invalide.")
        return -1

    return int(answer)


def disable_keyboard(device, keyboards):
    """Désactive un clavier, avec réactivation automatique si besoin."""
    if device.status == "Desactive":
        print("Ce clavier est déjà désactivé.")
        return

    others_active = [
        k for k in keyboards
        if k.status == "OK" and k.device_id != device.device_id
    ]

    if others_active:
        print("\nD'autres claviers actifs sont détectés.")
        seconds = ask_seconds(
            "Durée en secondes (Entrée = jusqu'à réactivation manuelle) : "
        )
    else:
        print("\nATTENTION : c'est ton seul clavier actif.")
        print("Seule la désactivation temporaire est autorisée.")
        seconds = ask_seconds(
            f"Durée en secondes [{DEFAULT_TEMP_SECONDS}] : ",
            default=DEFAULT_TEMP_SECONDS,
        )
        if seconds is not None and seconds > MAX_TEMP_SECONDS:
            print(f"Durée limitée à {MAX_TEMP_SECONDS} s.")
            seconds = MAX_TEMP_SECONDS

    if seconds == -1:
        return

    answer = input(
        f"\nDésactiver « {device.name} » ? Tape OUI pour confirmer : "
    ).strip().upper()

    if answer != "OUI":
        print("Annulé.")
        return

    if not apply_action("disable", device, "Désactivation"):
        return

    if seconds is None:
        print("Pour le réactiver : option « Activer » de ce menu.")
        return

    # Désactivation temporaire : on réactive quoi qu'il arrive.
    try:
        for remaining in range(seconds, 0, -1):
            print(f"\rRéactivation dans {remaining:>2} s...", end="", flush=True)
            time.sleep(1)
        print()
    finally:
        if not apply_action("enable", device, "Réactivation"):
            print("\nIMPORTANT : le clavier n'a pas été réactivé.")
            print("Ouvre le Gestionnaire de périphériques (souris),")
            print("clic droit sur le clavier > Activer, ou redémarre le PC.")


def control_keyboard():
    """Menu d'activation, de désactivation et de redémarrage."""
    if not is_admin():
        print("\nDroits administrateur requis.")
        print("Relance le terminal en « Exécuter en tant qu'administrateur ».")
        return

    try:
        keyboards = get_keyboards()
    except (RuntimeError, OSError) as error:
        print("Erreur de détection :", error)
        return

    if not keyboards:
        print("Aucun clavier détecté.")
        return

    device = choose_keyboard(keyboards)

    if device is None:
        return

    print(f"\nClavier choisi : {device.name}  [{device.status}]")
    print("1. Activer")
    print("2. Désactiver")
    print("3. Redémarrer le pilote")
    print("0. Annuler")

    choice = input("\nChoix : ").strip()

    if choice == "1":
        apply_action("enable", device, "Activation")
    elif choice == "2":
        disable_keyboard(device, keyboards)
    elif choice == "3":
        apply_action("restart", device, "Redémarrage")
    elif choice == "0":
        print("Annulé.")
    else:
        print("Choix invalide.")


def manage_keyboard():
    """Ouvre le Gestionnaire de périphériques Windows."""
    print("\nOuverture du Gestionnaire de périphériques...")
    print("Cherche la catégorie « Claviers ».")
    print("Ne désactive pas ton clavier principal.")

    try:
        subprocess.Popen(["mmc.exe", "devmgmt.msc"])
    except OSError as error:
        print("Impossible d'ouvrir le gestionnaire :", error)


# Menu


def keyboard_menu():
    """Affiche le menu de contrôle du clavier."""
    while True:
        print("\n==============================")
        print("      CONTRÔLE DU CLAVIER")
        print("==============================")
        print("1. Détecter le clavier et son état")
        print("2. Tester les touches (libre)")
        print("3. Test guidé (toutes les touches)")
        print("4. Enregistrer une session de test")
        print("5. Activer / désactiver / redémarrer")
        print("6. Ouvrir le gestionnaire Windows")
        print("0. Retour au programme principal")

        choice = input("\nChoix : ").strip()

        if choice == "1":
            detect_keyboard()
        elif choice == "2":
            test_keyboard()
        elif choice == "3":
            guided_test()
        elif choice == "4":
            keyboard_logger()
        elif choice == "5":
            control_keyboard()
        elif choice == "6":
            manage_keyboard()
        elif choice == "0":
            print("Retour au programme principal.")
            break
        else:
            print("Choix invalide.")

        if choice in ("1", "5", "6"):
            input("\nAppuie sur Entrée pour continuer...")


if __name__ == "__main__":
    setup_console()
    keyboard_menu()