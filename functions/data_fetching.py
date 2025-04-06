import os
import requests
import geopandas as gpd
import json
import pandas as pd # Need pandas for concatenation
from datetime import datetime, timedelta, date # Import date
import time # To add delays between requests

# Define the path for storing earthquake data
DATA_DIR = os.path.join("resources", "earthquake_data")

# Base URL for USGS FDSNWS Event query
USGS_BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

def fetch_and_load_earthquake_data(
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    min_magnitude: float = 2.5,
    force_download: bool = False,
    request_delay_seconds: float = 0.5 # Delay between API calls
) -> gpd.GeoDataFrame | None:
    """
    Fetches earthquake data from USGS day-by-day for the specified period,
    saves each day locally as earthquakes-YYYY-MM-DD.geojson if it doesn't exist
    or if force_download is True. Loads all relevant daily files and concatenates
    them into a single GeoDataFrame.

    Args:
        start_date: Start date (inclusive). Accepts YYYY-MM-DD string or date object.
                    Defaults to 2 years before end_date.
        end_date: End date (inclusive). Accepts YYYY-MM-DD string or date object.
                  Defaults to yesterday (to ensure full days).
        min_magnitude: Minimum earthquake magnitude. Defaults to 2.5.
        force_download: If True, always download fresh data for each day in the range,
                        overwriting corresponding local files.
        request_delay_seconds: Time in seconds to wait between daily API requests.

    Returns:
        A GeoDataFrame containing the earthquake data for the entire period,
        or None if fetching/loading fails or no data is found.
    """
    # --- Parameter Handling and Date Conversion ---
    if end_date is None:
        # Default to yesterday to ensure we query full days
        end_dt = date.today() - timedelta(days=1)
    elif isinstance(end_date, str):
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    else: # Assume it's a date object
        end_dt = end_date

    if start_date is None:
        # Default to 2 years prior to the end date
        start_dt = end_dt - timedelta(days=365 * 2)
    elif isinstance(start_date, str):
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
    else: # Assume it's a date object
        start_dt = start_date

    if start_dt > end_dt:
        print(f"Error: Start date ({start_dt}) cannot be after end date ({end_dt}).")
        return None

    print(f"Processing earthquake data from {start_dt} to {end_dt} (inclusive)...")

    # Ensure the main data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    all_daily_files = []
    current_date = start_dt
    total_days = (end_dt - start_dt).days + 1
    processed_days = 0

    # --- Loop Through Each Day ---
    while current_date <= end_dt:
        processed_days += 1
        day_str = current_date.strftime('%Y-%m-%d')
        print(f"\rProcessing day {processed_days}/{total_days}: {day_str}...", end="")

        filename = f"earthquakes-{day_str}.geojson"
        file_path = os.path.join(DATA_DIR, filename)
        all_daily_files.append(file_path) # Add to list for later loading

        # Check if the daily file exists or if forced download is requested
        if not os.path.exists(file_path) or force_download:
            # Define start and end times for the API query (full day)
            day_start_time_str = f"{day_str}T00:00:00"
            # End time is exclusive in API, so use start of *next* day
            next_day = current_date + timedelta(days=1)
            day_end_time_str = f"{next_day.strftime('%Y-%m-%d')}T00:00:00"

            query_params = {
                'format': 'geojson',
                'starttime': day_start_time_str,
                'endtime': day_end_time_str,
                'minmagnitude': min_magnitude,
                'eventtype': 'earthquake',
                'orderby': 'time'
            }

            try:
                # Add a delay to avoid overwhelming the API
                time.sleep(request_delay_seconds)

                response = requests.get(USGS_BASE_URL, params=query_params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Save the downloaded data only if features exist
                if data.get('features'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2) # Smaller indent
                    # print(f" Data saved to {file_path}") # Optional: print confirmation
                else:
                    # Create an empty file or a file with empty features
                    # to signify no data for this day, preventing re-download
                    with open(file_path, 'w', encoding='utf-8') as f:
                         json.dump({"type": "FeatureCollection", "features": []}, f)
                    # print(" No features found for this day.") # Optional

            except requests.exceptions.RequestException as e:
                print(f"\nError downloading data for {day_str}: {e}")
                # Don't stop processing other days, just skip this one's download
                # If an old file exists, it will be loaded later.
            except json.JSONDecodeError as e:
                 print(f"\nError decoding JSON data for {day_str}: {e}")
            except IOError as e:
                print(f"\nError saving data to {file_path}: {e}")

        current_date += timedelta(days=1)
    print("\nFinished checking/downloading daily files.")

    # --- Load and Concatenate Daily Files ---
    daily_gdfs = []
    print("Loading daily GeoJSON files...")
    loaded_files = 0
    for file_path in all_daily_files:
        if os.path.exists(file_path):
            try:
                # Check file size to avoid error on empty files
                if os.path.getsize(file_path) > 0:
                    gdf_day = gpd.read_file(file_path)
                    # Ensure it's not empty after loading
                    if not gdf_day.empty:
                        daily_gdfs.append(gdf_day)
                        loaded_files += 1
                    # else: # Optional: report empty files
                    #     print(f"  - Skipped empty file: {os.path.basename(file_path)}")
                # else: # Optional: report zero-byte files
                #     print(f"  - Skipped zero-byte file: {os.path.basename(file_path)}")

            except Exception as e:
                print(f"Error loading GeoDataFrame from {file_path}: {e}")
                # Optionally remove corrupted file?
                # try: os.remove(file_path) except OSError: pass
        # else: # Optional: report missing files (shouldn't happen if download logic is correct)
            # print(f"  - File not found (skipped): {os.path.basename(file_path)}")


    if not daily_gdfs:
        print("No earthquake data loaded for the specified period.")
        return None

    print(f"Concatenating data from {loaded_files} daily files...")
    try:
        # Concatenate all loaded daily GeoDataFrames
        combined_gdf = pd.concat(daily_gdfs, ignore_index=True)

        # Ensure the result is still a GeoDataFrame with a valid CRS
        # (concat might return DataFrame if input list is empty or types are mixed)
        if not isinstance(combined_gdf, gpd.GeoDataFrame):
             print("Error: Concatenation did not result in a GeoDataFrame.")
             return None

        # Attempt to set CRS from the first loaded GDF if needed
        if combined_gdf.crs is None and daily_gdfs:
             combined_gdf.crs = daily_gdfs[0].crs

        print(f"Successfully loaded and combined {len(combined_gdf)} total earthquakes.")
        return combined_gdf
    except Exception as e:
        print(f"Error during concatenation: {e}")
        return None

# Example usage
if __name__ == "__main__":
    print("\n--- Testing with a small date range (last 3 days, M >= 1.0) ---")
    # Use a smaller magnitude to likely get some data even for short periods
    end_test = date.today() - timedelta(days=1)
    start_test = end_test - timedelta(days=365*1) # 3 days total (inclusive)

    earthquake_gdf_small_range = fetch_and_load_earthquake_data(
        start_date=start_test, # Pass date objects directly
        end_date=end_test,
        min_magnitude=1.0,
        force_download=False # Set to True to force redownload for testing
    )

    if earthquake_gdf_small_range is not None:
        print(f"\nLoaded {len(earthquake_gdf_small_range)} earthquakes ({start_test} to {end_test}, M >= 1.0).")
        # print(earthquake_gdf_small_range.head())
        # print(earthquake_gdf_small_range.crs) # Check CRS
    else:
        print("\nFailed to load earthquake data for the small range test.")

    # --- Optional: Test with default (last 2 years) - This might take a while! ---
    # print("\n--- Testing with default parameters (last 2 years, M >= 2.5) ---")
    # print("NOTE: This may take a significant amount of time due to daily downloads.")
    # earthquake_gdf_default = fetch_and_load_earthquake_data(min_magnitude=2.5)
    # if earthquake_gdf_default is not None:
    #     print(f"\nLoaded {len(earthquake_gdf_default)} earthquakes (Default Params).")
    # else:
    #     print("\nFailed to load earthquake data (Default Params).")