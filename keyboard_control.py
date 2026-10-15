
"""
keyboard_control.py
Détection et test du clavier sous Windows.
Le journal enregistre uniquement les touches saisies
volontairement dans le terminal pendant le test.
"""

import msvcrt
import subprocess
from datetime import datetime
from pathlib import Path

from device_scanner import scan_all
from device_info import get_details, clear_cache


LOG_FILE = Path(__file__).with_name("keyboard_test_log.txt")


def detect_keyboard():
    """Détecte les claviers et affiche leurs informations."""
    try:
        devices = scan_all()

        keyboards = [
            device for device in devices
            if device.category == "Clavier"
        ]

        if not keyboards:
            print("Aucun clavier détecté.")
            return

        clear_cache()

        for keyboard in keyboards:
            get_details(keyboard)

            print("\n--- Clavier détecté ---")
            print("Nom :", keyboard.name)
            print("Fabricant :", keyboard.manufacturer)
            print("État :", keyboard.status)

            for label, value in keyboard.details.items():
                print(f"{label} : {value}")

    except (RuntimeError, OSError) as error:
        print("Erreur de détection :", error)


def test_keyboard(save_log=False):
    """Teste les touches saisies dans le terminal Windows."""
    print("\n=== TEST DU CLAVIER ===")
    print("Tape des caractères dans ce terminal.")
    print("Appuie sur Échap pour arrêter le test.")

    log = None

    try:
        if save_log:
            log = LOG_FILE.open("a", encoding="utf-8")
            log.write(
                f"\n--- Début du test : {datetime.now()} ---\n"
            )

        while True:
            key = msvcrt.getwch()

            if key == "\x1b":
                print("\nTest terminé.")
                break

            if key == "\r":
                description = "[ENTRÉE]"
            elif key == "\t":
                description = "[TABULATION]"
            elif key == "\x08":
                description = "[RETOUR ARRIÈRE]"
            elif key in ("\x00", "\xe0"):
                special = msvcrt.getwch()
                description = f"[TOUCHE SPÉCIALE : {special!r}]"
            elif key.isprintable():
                description = repr(key)
            else:
                description = f"[CODE : {ord(key)}]"

            print("Touche :", description)

            if log:
                log.write(description + "\n")
                log.flush()

    except KeyboardInterrupt:
        print("\nTest interrompu.")

    finally:
        if log:
            log.write("--- Fin du test ---\n")
            log.close()


def keyboard_logger():
    """Enregistre une session de test volontaire."""
    print("\nJournal local :", LOG_FILE)
    print("N'entre aucun mot de passe ni donnée confidentielle.")
    test_keyboard(save_log=True)


def manage_keyboard():
    """Ouvre le Gestionnaire de périphériques Windows."""
    print("\nOuverture du Gestionnaire de périphériques...")
    print("Cherche la catégorie « Claviers ».")
    print("Ne désactive pas ton clavier principal.")

    try:
        subprocess.Popen(["mmc.exe", "devmgmt.msc"])
    except OSError as error:
        print("Impossible d'ouvrir le gestionnaire :", error)


def keyboard_menu():
    """Affiche le menu de contrôle du clavier."""
    while True:
        print("\n==============================")
        print("      CONTRÔLE DU CLAVIER")
        print("==============================")
        print("1. Détecter le clavier et son état")
        print("2. Tester les touches")
        print("3. Enregistrer une session de test")
        print("4. Ouvrir le gestionnaire Windows")
        print("0. Retour au programme principal")

        choice = input("\nChoix : ").strip()

        if choice == "1":
            detect_keyboard()
        elif choice == "2":
            test_keyboard()
        elif choice == "3":
            keyboard_logger()
        elif choice == "4":
            manage_keyboard()
        elif choice == "0":
            print("Retour au programme principal.")
            break
        else:
            print("Choix invalide.")

        if choice in ("1", "4"):
            input("\nAppuie sur Entrée pour continuer...")


if __name__ == "__main__":
    keyboard_menu()
