# Make functions available directly from the data_fetching package
from .earthquake_data import fetch_and_load_earthquake_data
from .plate_data import load_plate_boundaries
from .seismic_data import fetch_seismic_data
__all__ = [
    'fetch_and_load_earthquake_data',
    'load_plate_boundaries',
    'fetch_seismic_data'
]