"""
Geospatial Utilities & Distance Calculations
Provides Haversine great-circle distance, bounding box calculation, and coordinate fuzzing for privacy.
"""
import math
from typing import Tuple

EARTH_RADIUS_KM = 6371.0088

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in kilometers.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 2)

def compute_bounding_box(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    Computes a bounding box (min_lat, max_lat, min_lon, max_lon) around a center point.
    """
    delta_lat = radius_km / 111.0
    delta_lon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return (
        round(lat - delta_lat, 6),
        round(lat + delta_lat, 6),
        round(lon - delta_lon, 6),
        round(lon + delta_lon, 6),
    )

def fuzz_coordinates(lat: float, lon: float, precision_decimals: int = 2) -> Tuple[float, float]:
    """
    Fuzzes GPS coordinates by truncating to ~1km precision to safeguard tenant/owner privacy.
    """
    return (round(lat, precision_decimals), round(lon, precision_decimals))
