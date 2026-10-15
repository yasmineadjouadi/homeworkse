
"""
Utilisation sous Windows :

    python main.py
        -> Affiche les périphériques détectés.

    python main.py --details
        -> Affiche aussi les détails et les pilotes.

    python main.py --category Disque --details
        -> Filtre par catégorie.

    python main.py --name realtek --details
        -> Recherche par nom.

    python main.py --all
        -> Inclut les périphériques techniques.

    python main.py --keyboard
        -> Ouvre le menu de contrôle du clavier.
"""

import argparse
import sys
import time
from collections import Counter, defaultdict

from device_scanner import scan_all
from device_info import get_details, clear_cache
from keyboard_control import keyboard_menu


# Périphériques techniques masqués par défaut.
NOISE = (
    "WAN Miniport",
    "Kernel Debug",
    "Wi-Fi Direct",
    "MS Idd",
    "Proxy de service",
    "Hub USB racine",
    "USB composite",
)


def is_noise(device):
    """Indique si un périphérique est technique."""
    return any(
        word.casefold() in device.name.casefold()
        for word in NOISE
    )


def show_maker(device):
    """Affiche le fabricant uniquement s'il est utile."""
    maker = device.manufacturer or ""

    if not maker or maker == "Inconnu":
        return ""

    if maker.casefold().startswith("microsoft"):
        return ""

    first_word = maker.split()[0].split("(")[0]

    if first_word.casefold() in device.name.casefold():
        return ""

    return f" - {maker}"


def print_device(device, with_details, count=1):
    """Affiche un périphérique et, si demandé, ses détails."""
    line = f"  - {device.name}{show_maker(device)}"

    if count > 1:
        line += f"  x{count}"

    if with_details or device.status != "OK":
        line += f"  [{device.status}]"

    print(line)

    if with_details:
        if device.driver and device.driver != "N/A":
            print(f"        Pilote : {device.driver}")

        for label, value in device.details.items():
            print(f"        {label} : {value}")


def build_parser():
    """Configure les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Scanner et contrôler les périphériques Windows"
    )

    parser.add_argument(
        "--details",
        action="store_true",
        help="afficher les détails et les informations des pilotes",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="inclure les périphériques techniques",
    )

    parser.add_argument(
        "--category",
        help="filtrer par catégorie, par exemple Clavier ou Disque",
    )

    parser.add_argument(
        "--name",
        help="filtrer par texte contenu dans le nom",
    )

    parser.add_argument(
        "--keyboard",
        action="store_true",
        help="ouvrir le menu de contrôle du clavier",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Menu de contrôle du clavier.
    if args.keyboard:
        keyboard_menu()
        return

    # Scanner les périphériques.
    start = time.time()

    try:
        devices = scan_all()
    except (RuntimeError, OSError) as error:
        print(f"Erreur de détection : {error}")
        return

    print(
        f"{len(devices)} périphériques détectés en "
        f"{time.time() - start:.1f} s"
    )

    # Masquer les périphériques techniques par défaut.
    if not args.all:
        devices = [
            device for device in devices
            if not is_noise(device)
        ]

    # Filtrer par catégorie.
    if args.category:
        devices = [
            device for device in devices
            if device.category.casefold()
            == args.category.casefold()
        ]

    # Filtrer par nom.
    if args.name:
        devices = [
            device for device in devices
            if args.name.casefold() in device.name.casefold()
        ]

    if not devices:
        print("Aucun périphérique correspondant aux critères.")
        return

    # Charger les détails uniquement si demandé.
    if args.details:
        start = time.time()
        clear_cache()

        for device in devices:
            get_details(device)

        print(
            f"Détails lus en {time.time() - start:.1f} s"
        )

    # Regrouper les périphériques par catégorie.
    grouped = defaultdict(list)

    for device in devices:
        grouped[device.category].append(device)

    for category in sorted(grouped, key=str.casefold):
        group = grouped[category]

        print(f"\n[{category}]")

        counts = Counter(device.name for device in group)
        shown = set()

        for device in group:
            if device.name in shown:
                continue

            shown.add(device.name)

            print_device(
                device,
                args.details,
                counts[device.name],
            )


if __name__ == "__main__":
    main()
