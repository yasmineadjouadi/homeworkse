from dataclasses import dataclass, field

@dataclass
class Device:
    name: str                                   
    category: str                                
    manufacturer: str = "Inconnu"                # fabricant
    device_id: str = ""                       
    status: str = "Inconnu"                      # "OK", "Erreur" ou "Inconnu"
    description: str = ""  
    driver: str = ""                             # pilote (rempli par device_info.py)
    details: dict = field(default_factory=dict)  # caracteristiques (rempli par device_info.py)