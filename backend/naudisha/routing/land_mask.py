"""
High-precision Land Mask and Maritime Corridor Geometry for the Indian Ocean Basin.
Identifies landmasses (Indian Subcontinent, Sri Lanka, Arabian Peninsula, Southeast Asia,
Horn of Africa) and ensures nautical routing exclusively traverses navigable ocean waters.
"""

from __future__ import annotations

from typing import List, Tuple, Sequence, Union
import numpy as np
from matplotlib.path import Path


# ---------------------------------------------------------------------------
# 1. High-Resolution Coastal Land Polygons [Latitude, Longitude]
# ---------------------------------------------------------------------------

# Mainland India & Northern Subcontinent
_INDIA_MAINLAND_COAST = [
    # Gujarat & Gulf of Kutch / Khambhat
    [24.50, 68.10],   # Kutch NW border
    [23.70, 68.70],   # Kori Creek / Lakhpat
    [23.00, 69.10],   # Mandvi / Gulf of Kutch North
    [23.10, 70.30],   # Kandla / Little Rann
    [22.80, 70.80],   # Maliya
    [22.50, 70.10],   # Jamnagar / Gulf of Kutch South
    [22.40, 69.00],   # Dwarka / Okha
    [21.60, 69.60],   # Porbandar
    [20.75, 70.90],   # Diu / Veraval
    [20.90, 71.70],   # Jafrabad
    [21.60, 72.20],   # Bhavnagar / Gulf of Khambhat West
    [22.20, 72.60],   # Khambhat inner apex
    [21.70, 72.80],   # Dahej / Narmada mouth
    [21.15, 72.75],   # Surat / Tapi mouth
    [20.40, 72.85],   # Daman / Valsad
    
    # Maharashtra / Konkan Coast
    [19.90, 72.75],   # Dahanu
    [19.30, 72.78],   # Vasai
    [18.95, 72.82],   # Mumbai (Colaba)
    [18.60, 72.87],   # Alibag / Revdanda
    [18.20, 72.95],   # Murud-Janjira
    [17.90, 73.05],   # Harihareshwar
    [17.00, 73.28],   # Ratnagiri / Mirya Bay
    [16.50, 73.33],   # Vijaydurg
    [15.85, 73.60],   # Malvan / Vengurla
    
    # Goa & Karnataka Coast
    [15.55, 73.75],   # Calangute / Panaji
    [15.40, 73.80],   # Mormugao / Vasco
    [15.00, 74.00],   # Canacona
    [14.80, 74.12],   # Karwar
    [14.40, 74.35],   # Kumta / Gokarna
    [14.00, 74.50],   # Honnavar / Bhatkal
    [13.35, 74.70],   # Malpe / Udupi
    [12.87, 74.83],   # Mangalore / Panambur
    
    # Kerala / Malabar Coast
    [12.50, 74.98],   # Kasaragod
    [11.90, 75.35],   # Kannur / Azhikkal
    [11.25, 75.77],   # Kozhikode / Calicut
    [10.80, 75.92],   # Ponnani
    [10.20, 76.15],   # Kodungallur
    [9.96,  76.24],   # Kochi / Willingdon Island
    [9.50,  76.32],   # Alappuzha (Alleppey)
    [9.18,  76.50],   # Kayamkulam / Karunagappalli
    [8.88,  76.60],   # Kollam / Neendakara
    [8.70,  76.72],   # Varkala / Attingal
    [8.48,  76.94],   # Thiruvananthapuram / Vizhinjam
    [8.08,  77.55],   # Kanyakumari / Cape Comorin (Southernmost tip)

    # Tamil Nadu / Coromandel Coast
    [8.40,  77.80],   # Koodankulam
    [8.75,  78.18],   # Tuticorin / VO Chidambaranar
    [9.10,  78.60],   # Valinokkam
    [9.28,  79.15],   # Mandapam / Rameswaram base
    [9.80,  79.00],   # Tondi / Palk Bay West
    [10.30, 79.25],   # Manamelkudi
    [10.35, 79.85],   # Point Calimere (Kodikkarai)
    [10.76, 79.84],   # Nagapattinam / Karaikal
    [11.50, 79.77],   # Cuddalore
    [11.93, 79.83],   # Puducherry
    [12.50, 80.15],   # Mahabalipuram
    [13.08, 80.30],   # Chennai Port / Ennore
    [13.40, 80.25],   # Pulicat Lake mouth
    
    # Andhra Pradesh Coast
    [14.00, 80.12],   # Sriharikota / Dugarajapatnam
    [14.25, 80.15],   # Krishnapatnam Port
    [15.80, 80.40],   # Nizampatnam
    [16.15, 81.18],   # Machilipatnam / Krishna delta
    [16.90, 82.25],   # Kakinada Deepwater Port
    [17.68, 83.25],   # Visakhapatnam / Gangavaram Port
    [18.30, 83.90],   # Kalingapatnam
    [18.90, 84.60],   # Bhavanapadu / Sompeta
    
    # Odisha Coast
    [19.30, 85.00],   # Gopalpur Port
    [19.75, 85.80],   # Chilika / Puri
    [20.26, 86.70],   # Paradip Port
    [20.80, 86.95],   # Dhamra Port
    [21.50, 87.10],   # Chandipur / Balasore
    
    # West Bengal & Bangladesh / Sundarbans
    [21.65, 87.55],   # Digha / Subarnarekha
    [21.80, 88.00],   # Sagar Island / Haldia
    [22.20, 88.10],   # Diamond Harbour / Hooghly
    [22.50, 88.35],   # Kolkata / Howrah
    [22.00, 89.00],   # Sundarbans / Bangladesh border
    [22.30, 91.80],   # Chittagong / Bay of Bengal East
    [21.40, 92.00],   # Cox's Bazar
    [20.15, 92.90],   # Sittwe / Myanmar
    
    # Northern Inland Envelope (Closing the Subcontinent Polygon)
    [28.00, 96.00],   # Northeast Assam / Arunachal
    [32.00, 90.00],   # Tibet / Himalayas
    [36.00, 75.00],   # Kashmir / Karakoram
    [30.00, 68.00],   # Baluchistan / Indus North
    [25.00, 67.00],   # Karachi / Sindh
    [24.50, 68.10],   # Close back at Kutch NW
]

# Sri Lanka Landmass
_SRI_LANKA_COAST = [
    [9.82,  80.24],   # Point Pedro (North tip)
    [9.66,  80.01],   # Jaffna
    [9.15,  79.80],   # Mannar Island
    [8.58,  79.77],   # Kalpitiya
    [8.00,  79.70],   # Puttalam
    [7.20,  79.84],   # Negombo
    [6.94,  79.85],   # Colombo Port
    [6.50,  79.97],   # Beruwala
    [6.03,  80.22],   # Galle Port
    [5.92,  80.55],   # Dondra Head (Southernmost tip of Sri Lanka)
    [6.12,  81.12],   # Hambantota Port
    [6.35,  81.52],   # Kirinda / Yala
    [6.85,  81.85],   # Arugam Bay
    [7.72,  81.70],   # Batticaloa
    [8.58,  81.23],   # Trincomalee Harbor
    [9.28,  80.80],   # Mullaittivu
    [9.82,  80.24],   # Close Point Pedro
]

# Arabian Peninsula & Persian Gulf Landmass
_ARABIAN_PENINSULA = [
    [12.60, 43.40],   # Bab-el-Mandeb / Yemen
    [12.80, 45.00],   # Aden
    [14.50, 49.10],   # Mukalla
    [16.60, 53.20],   # Salalah / Oman border
    [18.20, 56.50],   # Ras Madrakah
    [20.60, 58.90],   # Masirah Island coast
    [22.55, 59.80],   # Ras al Hadd (Easternmost Oman)
    [23.60, 58.55],   # Muscat / Mutrah
    [24.40, 56.70],   # Sohar
    [24.75, 56.45],   # Shinas
    [25.15, 56.36],   # Fujairah
    [25.35, 56.36],   # Khor Fakkan
    [25.62, 56.32],   # Dibba
    [25.98, 56.45],   # Lima Headland
    [26.18, 56.55],   # Ras Qabr Hindi
    [26.38, 56.53],   # Jazirat Musandam
    [26.45, 56.50],   # Ras Al Bab / Kumzar North (Southern boundary of Strait of Hormuz TSS)
    [26.38, 56.38],   # Kumzar Fjord
    [26.35, 56.30],   # Ghanam Island / North Khasab
    [26.26, 56.22],   # Ras Sheikh Masud (Northwestern Musandam Promontory)
    [26.15, 56.12],   # Bukha
    [26.02, 56.08],   # Sha'am (Oman/UAE border)
    [25.82, 55.95],   # Ras Al Khaimah
    [25.70, 55.78],   # Jazirat Al Hamra
    [25.58, 55.58],   # Umm Al Quwain
    [25.38, 55.38],   # Sharjah / Ajman
    [25.25, 55.30],   # Dubai Creek / Port Rashid Coast
    [24.98, 55.04],   # Jebel Ali Port Basin
    [24.94, 54.98],   # Jebel Ali Freezone South
    [24.75, 54.65],   # Al Taweelah / UAE Coast
    [24.52, 54.38],   # Abu Dhabi (Mina Zayed)
    [24.20, 51.50],   # Qatar South
    [25.30, 51.55],   # Doha
    [26.40, 50.10],   # Dammam / Bahrain
    [29.35, 47.95],   # Kuwait Port
    [30.00, 48.00],   # Shatt al-Arab
    [32.00, 40.00],   # Northern Arabia inland
    [28.00, 35.00],   # Gulf of Aqaba / Red Sea North
    [21.50, 39.15],   # Jeddah
    [16.90, 42.55],   # Jizan
    [14.80, 42.95],   # Al Hudaydah
    [12.60, 43.40],   # Close Bab-el-Mandeb
]

# Iran, Pakistan Makran Coast, and Persian Gulf North
_IRAN_MAKRAN_COAST = [
    # Pakistan Makran Coast (High-Precision Headlands & Tombolos)
    [24.83, 66.65],   # Karachi West / Cape Monze
    [25.10, 66.70],   # Sonmiani Bay East / Gadani
    [25.38, 66.55],   # Sonmiani Bay Apex
    [25.35, 65.50],   # Hingol National Park Coast
    [25.30, 65.20],   # Ras Malan Promontory
    [25.23, 64.72],   # Ormara Bay East approach
    [25.20, 64.65],   # Ormara East Bay (Demijarr)
    [25.17, 64.64],   # Ras Ormara East Cliff
    [25.12, 64.58],   # Ras Ormara Hammerhead South Tip (Key Land Obstruction)
    [25.15, 64.52],   # Ras Ormara West Corner
    [25.22, 64.48],   # Ormara West Bay (Paddi Zirr)
    [25.40, 64.08],   # Kalmat Khor Inner Estuary
    [25.30, 63.85],   # Ras Basol Coast
    [25.26, 63.60],   # Pasni Bay East Approach
    [25.18, 63.52],   # Ras Jaddi East Promontory
    [25.16, 63.47],   # Ras Jaddi South Promontory (Key Headland Obstruction)
    [25.20, 63.42],   # Pasni Town / Port Basin
    [25.23, 63.35],   # Pasni West Headland
    [25.20, 63.05],   # Ras Shamal Bandar
    [25.16, 62.38],   # Gwadar East Bay (Demi Zirr)
    [25.12, 62.35],   # Koh-e-Batil East Cliff
    [25.08, 62.32],   # Gwadar Koh-e-Batil / Ras Nuh South Tip
    [25.11, 62.28],   # Koh-e-Batil West Cliff
    [25.16, 62.25],   # Gwadar West Bay (Paddi Zirr)
    [25.18, 62.05],   # Pishukan Headland
    [25.08, 61.85],   # Ganz Promontory
    [25.02, 61.75],   # Ras Jiwani South Tip (Pakistan-Iran Border)
    
    # Iran Makran Coast & Gulf of Oman North
    [25.12, 61.50],   # Gwatar Bay / Baho River mouth
    [25.28, 60.65],   # Chabahar Bay East
    [25.24, 60.58],   # Chabahar Ras Tis Promontory / Port
    [25.35, 60.40],   # Konarak Navy Basin
    [25.36, 60.20],   # Pozm Bay Apex
    [25.30, 60.15],   # Ras Pozm Headland
    [25.33, 59.88],   # Ras Tang Promontory
    [25.40, 59.35],   # Galag Coast
    [25.55, 58.50],   # Sadij
    [25.62, 57.75],   # Cape Jask South Promontory (Gulf of Oman entrance)
    [25.85, 57.30],   # Kohmobarak
    [26.50, 57.08],   # Sirik
    [27.00, 56.90],   # Minab / Hormozgan
    
    # Strait of Hormuz North & Persian Gulf North (Iran)
    [27.15, 56.28],   # Bandar Abbas Port
    [27.00, 55.60],   # Bandar Khamir / Clarence Strait
    [26.55, 54.88],   # Bandar Lengeh
    [26.70, 54.28],   # Bandar-e Charak
    [26.70, 53.75],   # Chiru Point
    [27.10, 53.20],   # Bandar-e Moqam / Lavan Coast
    [27.48, 52.60],   # Asaluyeh / Pars Special Zone
    [27.85, 51.90],   # Kangan / Dayyer
    [28.95, 50.83],   # Bushehr Port
    [29.58, 50.50],   # Bandar Ganaveh
    [30.05, 50.15],   # Bandar Deylam
    [30.45, 49.10],   # Bandar Imam Khomeini / Khuzestan
    [30.00, 48.50],   # Abadan / Shatt al-Arab
    
    # Northern Inland Closure (Highland Envelope)
    [34.00, 48.00],   # Zagros Mountains / Lorestan
    [37.00, 53.00],   # Northern Iran / Alborz
    [37.00, 60.00],   # Mashhad / Turkmenistan Border
    [34.00, 62.00],   # Afghanistan / Herat
    [30.00, 64.00],   # Baluchistan North
    [26.00, 66.50],   # Lasbela
    [24.83, 66.65],   # Close back at Karachi West
]

# Indochina & Malay Peninsula (blocking Bay of Bengal to Pacific)
_MALAY_INDOCHINA = [
    [20.00, 92.90],   # Myanmar / Arakan
    [16.00, 94.20],   # Cape Negrais / Irrawaddy Delta
    [16.80, 96.20],   # Yangon
    [15.00, 97.80],   # Dawei
    [12.00, 98.60],   # Myeik / Tenasserim
    [8.00,  98.30],   # Phuket
    [6.30,  99.80],   # Langkawi
    [5.40,  100.30],  # Penang
    [3.00,  101.35],  # Port Klang
    [2.20,  102.25],  # Melaka
    [1.30,  103.80],  # Singapore / Tanjung Piai
    [1.40,  104.40],  # East Johor
    [4.00,  103.40],  # Kuantan
    [6.00,  102.30],  # Kota Bharu
    [10.00, 99.20],   # Gulf of Thailand West
    [13.50, 100.50],  # Bangkok
    [12.00, 102.50],  # Cambodia coast
    [22.00, 108.00],  # China South
    [26.00, 95.00],   # Myanmar North
    [20.00, 92.90],   # Close
]


# Shallow / Non-Navigable Adams Bridge Reef Barrier (Palk Strait)
_PALK_STRAIT_SHALLOWS = [
    [9.00, 79.10],
    [9.55, 79.10],
    [9.55, 79.90],
    [9.00, 79.90],
    [9.00, 79.10],
]

# Compile spatial paths
_POLYGONS = [
    Path(np.array(_INDIA_MAINLAND_COAST)),
    Path(np.array(_SRI_LANKA_COAST)),
    Path(np.array(_ARABIAN_PENINSULA)),
    Path(np.array(_IRAN_MAKRAN_COAST)),
    Path(np.array(_MALAY_INDOCHINA)),
    Path(np.array(_PALK_STRAIT_SHALLOWS)),
]


def are_points_on_land(pts: np.ndarray) -> np.ndarray:
    """
    Vectorized batch check for an (N, 2) array of [lat, lon] coordinates.
    Returns a boolean 1D numpy array of length N (True if on land, False if in water).
    """
    if len(pts) == 0:
        return np.empty(0, dtype=bool)
    res = np.zeros(len(pts), dtype=bool)
    for poly_path in _POLYGONS:
        res |= poly_path.contains_points(pts)
    return res


def is_point_on_land(lat: float, lon: float) -> bool:
    """
    Checks if a geographic coordinate (lat, lon) falls on land within the Indian Ocean basin.

    Args:
        lat: Latitude in degrees [-90.0, 90.0].
        lon: Longitude in degrees [-180.0, 180.0].

    Returns:
        True if the point is on land, False if in open ocean / navigable water.
    """
    point = np.array([[lat, lon]])
    for poly_path in _POLYGONS:
        if poly_path.contains_points(point)[0]:
            return True
    return False


def is_segment_crossing_land(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    sample_spacing_nm: float = 5.0,
    samples: Optional[int] = None,
) -> bool:
    """
    Checks if a line segment between two coordinates intersects any landmass.
    Uses distance-adaptive sample spacing (default ~5 NM) to guarantee no capes,
    islands, or headlands are skipped even on long intercontinental legs.

    Args:
        lat1, lon1: Start coordinate.
        lat2, lon2: End coordinate.
        sample_spacing_nm: Maximum geographic spacing between sampled points in NM (default: 5.0).
        samples: Optional explicit sample count override.

    Returns:
        True if any sampled point is on land, False otherwise.
    """
    # Check endpoints
    if is_point_on_land(lat1, lon1) or is_point_on_land(lat2, lon2):
        return True

    if samples is None:
        # Approximate spherical distance in NM
        d_lat = (lat2 - lat1) * 60.0
        d_lon = (lon2 - lon1) * 60.0 * np.cos(np.radians((lat1 + lat2) / 2.0))
        dist_nm = float(np.sqrt(d_lat * d_lat + d_lon * d_lon))
        num_samples = max(10, int(dist_nm / max(sample_spacing_nm, 1.0)))
    else:
        num_samples = max(5, samples)

    lats = np.linspace(lat1, lat2, num_samples + 2)[1:-1]
    lons = np.linspace(lon1, lon2, num_samples + 2)[1:-1]
    pts = np.column_stack((lats, lons))

    for poly_path in _POLYGONS:
        if np.any(poly_path.contains_points(pts)):
            return True

    return False


def is_cross_peninsular_voyage(start_lat: float, start_lon: float, dest_lat: float, dest_lon: float) -> bool:
    """
    Detects if a voyage is between the Western quadrant (Arabian Sea, West Coast of India)
    and the Eastern quadrant (Gulf of Mannar, Bay of Bengal, East Coast of India/Sri Lanka),
    where nautical navigation must round Cape Comorin (8.08°N) and/or Sri Lanka.
    """
    def is_west_side(lat: float, lon: float) -> bool:
        # Arabian Sea / Indian west coast (Gujarat to Trivandrum)
        if lat >= 8.0 and lon <= 77.55:
            return True
        # Sri Lanka west coast (Colombo, Negombo, Kalpitiya)
        if 5.5 <= lat <= 10.0 and lon <= 79.90:
            return True
        return False

    def is_east_side(lat: float, lon: float) -> bool:
        # Gulf of Mannar / Coromandel / Bay of Bengal (Tuticorin, Chennai, Vizag, Kolkata)
        if lat >= 8.40 and lon >= 77.80:
            return True
        # Sri Lanka east coast (Trincomalee, Batticaloa, Hambantota East)
        if 6.0 <= lat <= 10.0 and lon >= 81.00:
            return True
        return False

    cross_1 = is_west_side(start_lat, start_lon) and is_east_side(dest_lat, dest_lon)
    cross_2 = is_east_side(start_lat, start_lon) and is_west_side(dest_lat, dest_lon)

    return bool(cross_1 or cross_2)
