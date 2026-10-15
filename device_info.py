from device_scanner import query, safe_get
NA = "N/A"  # afficher quand une information n'est pas disponible

# Caches : on lit chaque classe WMI une seule fois (la lecture est lente).
_objects = {}           # classe WMI -> {identifiant en MAJUSCULES: objet WMI}
_drivers = None         # identifiant en MAJUSCULES -> objet pilote
_driver_error = None    # message si la lecture des pilotes a echouer


# Petits outils de mise en forme
def _text(value, unit=""):
    if value is None:
        return NA
    return f"{value} {unit}".strip()

def _gb(size_in_bytes):
    try:
        return round(int(size_in_bytes) / 1024 ** 3, 1)
    except (TypeError, ValueError):
        return None

def _mbps(bits_per_second):
    """bits/s -> Mb/s. WMI renvoie une valeur geante quand la vitesse est inconnue."""
    try:
        value = int(bits_per_second)
    except (TypeError, ValueError):
        return None
    return round(value / 1_000_000) if 0 < value <= 10 ** 12 else None

def _date(wmi_date):
    """Date WMI '20230415000000.000000+000' -> '15/04/2023'. None si invalide."""
    text = str(wmi_date or "")
    if len(text) < 8 or not text[:8].isdigit():
        return None
    return f"{text[6:8]}/{text[4:6]}/{text[:4]}"

#_disk, _network, _video : chacun prend un objet WMI et retourne un dictionnaire de détails prêts à afficher
def _disk(obj):
    serial = safe_get(obj, "SerialNumber")
    return {
        "Taille": _text(_gb(safe_get(obj, "Size")), "Go"),
        "Interface": _text(safe_get(obj, "InterfaceType")),
        "Partitions": _text(safe_get(obj, "Partitions")),
        "Numero de serie": _text(str(serial).strip(" .") if serial else None),
        "Firmware": _text(safe_get(obj, "FirmwareRevision")),
    }

def _network(obj):
    return {
        "Adresse MAC": _text(safe_get(obj, "MACAddress")),
        "Nom de la connexion": _text(safe_get(obj, "NetConnectionID")),
        "Vitesse": _text(_mbps(safe_get(obj, "Speed")), "Mb/s"),
    }

def _video(obj):
    ram = safe_get(obj, "AdapterRAM")
    try:
        ram_mb = round(int(ram) / 1024 ** 2) if ram is not None else None
    except (TypeError, ValueError):
        ram_mb = None
    width = safe_get(obj, "CurrentHorizontalResolution")
    height = safe_get(obj, "CurrentVerticalResolution")
    return {
        "Memoire video": _text(ram_mb, "Mo"),
        "Resolution": NA if width is None or height is None else f"{width}x{height}",
        "Frequence d'affichage": _text(safe_get(obj, "CurrentRefreshRate"), "Hz"),
        "Processeur video": _text(safe_get(obj, "VideoProcessor")),
    }

SPECIFIC = {
    "Disque": ("Win32_DiskDrive", _disk),
    "Reseau": ("Win32_NetworkAdapter", _network),
    "Affichage": ("Win32_VideoController", _video),
}

# Retourne l'objet de cette classe WMI qui a cet identifiant, ou None
def _find(wmi_class, device_id):
    if wmi_class not in _objects:
        _objects[wmi_class] = {
            str(safe_get(obj, "PNPDeviceID", "")).upper(): obj
            for obj in query(wmi_class)
        }
    return _objects[wmi_class].get(device_id.upper())

#Retourne l'objet pilote du périphérique. Tous les pilotes sont lus une fois
def _find_driver(device_id):
    global _drivers, _driver_error
    if _drivers is None:
        try:
            fields = "DeviceID, DriverVersion, DriverDate, DriverProviderName, InfName"
            _drivers = {
                str(safe_get(obj, "DeviceID", "")).upper(): obj
                for obj in query("Win32_PnPSignedDriver", fields)
            }
        except RuntimeError as error:
            _drivers = {}
            _driver_error = str(error)
    return _drivers.get(device_id.upper())

#Remplit device.driver et ajoute les infos du pilote dans device.details
def _fill_driver(device):
    obj = _find_driver(device.device_id)
    if obj is None:
        if _driver_error:
            device.details["Pilote"] = f"Indisponible ({_driver_error})"
        return
    provider = safe_get(obj, "DriverProviderName")
    version = safe_get(obj, "DriverVersion")
    device.driver = f"{provider or ''} {version or ''}".strip() or NA
    date = _date(safe_get(obj, "DriverDate"))
    if date and date != "21/06/2006":   # date générique des pilotes inclus dans Windows
         device.details["Date du pilote"] = date

# Fonction principale
def get_details(device):
    # 1. Caractéristiques spécifiques à la catégorie (disque, réseau, affichage)
    try:
        if device.category in SPECIFIC:
            wmi_class, builder = SPECIFIC[device.category]
            obj = _find(wmi_class, device.device_id)
            if obj is not None:
                device.details.update(builder(obj))
    except Exception as error:
        device.details["Erreur"] = f"Lecture des détails impossible : {error}"

    # 2. Pilote
    try:
        _fill_driver(device)
    except Exception as error:
        device.details["Pilote"] = f"Indisponible ({error})"

    # 2b. Description et identifiant matériel
    if device.description and device.description != device.name:
        device.details["Description"] = device.description
    if device.device_id:
        device.details["Identifiant materiel"] = device.device_id

    # 3. On enlève les valeurs vides
    device.details = {
        label: value for label, value in device.details.items()
        if value != NA
    }
    return device