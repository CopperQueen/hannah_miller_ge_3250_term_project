import os
import requests
import geopandas as gpd
import json

# Define the path for storing earthquake data
DATA_DIR = os.path.join("resources", "earthquake_data")
DEFAULT_FILE_NAME = "earthquakes_m2.5_30day.geojson"
DEFAULT_DATA_PATH = os.path.join(DATA_DIR, DEFAULT_FILE_NAME)

# USGS GeoJSON feed URL (Magnitude 2.5+ for the past 30 days)
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_month.geojson"

def fetch_and_load_earthquake_data(
    file_path: str = DEFAULT_DATA_PATH,
    url: str = USGS_URL,
    force_download: bool = False
) -> gpd.GeoDataFrame | None:
    """
    Fetches earthquake data from USGS, saves it locally if it doesn't exist
    or if force_download is True, and loads it into a GeoDataFrame.

    Args:
        file_path: The local path to save/load the GeoJSON file.
        url: The URL to download the GeoJSON data from.
        force_download: If True, always download fresh data, overwriting the local file.

    Returns:
        A GeoDataFrame containing the earthquake data, or None if fetching/loading fails.
    """
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Check if the file exists or if forced download is requested
    if not os.path.exists(file_path) or force_download:
        print(f"Local data not found or force_download=True. Downloading from {url}...")
        try:
            response = requests.get(url, timeout=30) # Added timeout
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

            # Save the downloaded data
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(response.json(), f, ensure_ascii=False, indent=4) # Save as formatted JSON
            print(f"Data successfully downloaded and saved to {file_path}")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading data: {e}")
            # If download fails but an old file exists, try loading that
            if os.path.exists(file_path):
                 print(f"Attempting to load existing local file: {file_path}")
            else:
                return None # No local file and download failed
        except json.JSONDecodeError as e:
             print(f"Error decoding JSON data from {url}: {e}")
             return None
        except IOError as e:
            print(f"Error saving data to {file_path}: {e}")
            return None # Cannot proceed if saving failed

    # Load the data from the local file
    try:
        print(f"Loading earthquake data from {file_path}...")
        gdf = gpd.read_file(file_path)
        print("Data loaded successfully.")
        # Basic validation: check if 'geometry' column exists
        if 'geometry' not in gdf.columns:
             print("Error: Loaded data does not contain a 'geometry' column.")
             # Optionally, delete the invalid file?
             # os.remove(file_path)
             return None
        return gdf
    except Exception as e: # Catch potential GeoPandas read errors or other issues
        print(f"Error loading GeoDataFrame from {file_path}: {e}")
        # Optionally, attempt to delete the corrupted file if loading fails
        # try:
        #     os.remove(file_path)
        #     print(f"Removed potentially corrupted file: {file_path}")
        # except OSError as remove_err:
        #     print(f"Error removing file {file_path}: {remove_err}")
        return None

# Example usage (optional, can be removed or commented out)
# if __name__ == "__main__":
#     earthquake_gdf = fetch_and_load_earthquake_data()
#     if earthquake_gdf is not None:
#         print("\nEarthquake GeoDataFrame Info:")
#         earthquake_gdf.info()
#         print("\nFirst 5 rows:")
#         print(earthquake_gdf.head())
#     else:
#         print("\nFailed to load earthquake data.")