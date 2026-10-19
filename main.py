"""
Utilisation (sous Windows) :
    python main.py                          -> menu principal
    python main.py --details                -> la détection affiche aussi pilote et caractéristiques
    python main.py --category Disque --details
    python main.py --name realtek --details
    python main.py --all                    -> la détection inclut les périphériques techniques
"""
import argparse
import sys
import time
from device_scanner import scan_all, scan_system
from device_info import get_details
from collections import Counter
from itertools import groupby
from keyboard_control import main as menu_controle

# Périphériques techniques masqués par défaut (virtuels, internes à Windows).
NOISE = ("WAN Miniport", "Kernel Debug", "Wi-Fi Direct", "MS Idd",
         "Proxy de service", "Hub USB racine", "USB composite")


def is_noise(device):
    return any(word.lower() in device.name.lower() for word in NOISE)

#Retourne ' - Fabricant' seulement s'il apprend quelque chose
def show_maker(device):
    maker = device.manufacturer
    if maker == "Inconnu" or maker.lower().startswith("microsoft"):
        return ""
    if maker.split()[0].split("(")[0].lower() in device.name.lower():  # déjà dans le nom
        return ""
    return f" - {maker}"

def print_device(device, with_details, count=1):
    line = f"  - {device.name}{show_maker(device)}"
    if count > 1:
        line += f"  x{count}"
    if with_details or device.status != "OK":
        line += f"  [{device.status}]"
    print(line)
    if with_details:
        if device.driver:
            print(f"        Pilote : {device.driver}")
        for label, value in device.details.items():
            print(f"        {label} : {value}")


def detection(args):
    start = time.time()
    try:
        devices = scan_system() + scan_all()
    except RuntimeError as error:
        print(f"Erreur : {error}")
        return
    total = len(devices)
    print(f"{total} périphériques détectés en {time.time() - start:.1f} s")

    if not args.all:
        devices = [d for d in devices if not is_noise(d)]
    if args.category:
        devices = [d for d in devices if d.category.lower() == args.category.lower()]
    if args.name:
        devices = [d for d in devices if args.name.lower() in d.name.lower()]

    if args.details:
        start = time.time()
        for device in devices:
            get_details(device)
        print(f"Détails lus en {time.time() - start:.1f} s")

    for category, group in groupby(devices, key=lambda d: d.category):
        group = list(group)
        print(f"\n[{category}]")
        counts = Counter(d.name for d in group)
        shown = set()
        for device in group:
            if device.name not in shown:
                shown.add(device.name)
                print_device(device, args.details, counts[device.name])


def main():
    parser = argparse.ArgumentParser(description="Détection et contrôle des périphériques")
    parser.add_argument("--details", action="store_true", help="lire aussi les détails et le pilote")
    parser.add_argument("--all", action="store_true", help="inclure les périphériques techniques")
    parser.add_argument("--category", help="filtrer par catégorie (ex. Disque, Reseau)")
    parser.add_argument("--name", help="filtrer par texte contenu dans le nom")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    while True:
        print("\n==============================")
        print("1. Détection des périphériques")
        print("2. Contrôle")
        print("3. Quitter")
        choice = input("\nChoix : ").strip()
        if choice == "1":
            detection(args)
        elif choice == "2":
            menu_controle()
        elif choice == "3":
            break
        else:
            print("Choix invalide.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nArrêt.")