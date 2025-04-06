import os
import requests
import geopandas as gpd
import json
import pandas as pd # Need pandas for concatenation
from datetime import datetime, timedelta, date # Import date
import time
import concurrent.futures # Added for threading

# Define the path for storing earthquake data
DATA_DIR = os.path.join("resources", "earthquake_data")

# Base URL for USGS FDSNWS Event query
USGS_BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# --- Helper Function for Single Day Download ---
def _download_single_day(
    current_date: date,
    min_magnitude: float,
    request_delay_seconds: float = 0.1 # Shorter delay within threads
) -> tuple[str, str]:
    """
    Downloads and saves earthquake data for a single specified day.

    Args:
        current_date: The date to download data for.
        min_magnitude: Minimum earthquake magnitude.
        request_delay_seconds: Delay before making the API request.

    Returns:
        A tuple containing the file path and a status message ("success", "no_features", or "error: ...").
    """
    day_str = current_date.strftime('%Y-%m-%d')
    filename = f"earthquakes-{day_str}.geojson"
    file_path = os.path.join(DATA_DIR, filename)

    # Define start and end times for the API query (full day)
    day_start_time_str = f"{day_str}T00:00:00"
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
        # Add a small delay before each request even in parallel
        time.sleep(request_delay_seconds)

        response = requests.get(USGS_BASE_URL, params=query_params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Save the downloaded data only if features exist
        if data.get('features'):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return file_path, "success"
        else:
            # Create an empty file to signify no data, preventing re-download
            with open(file_path, 'w', encoding='utf-8') as f:
                 json.dump({"type": "FeatureCollection", "features": []}, f)
            return file_path, "no_features"

    except requests.exceptions.RequestException as e:
        return file_path, f"error: Request failed - {e}"
    except json.JSONDecodeError as e:
         return file_path, f"error: JSON decode failed - {e}"
    except IOError as e:
        return file_path, f"error: File save failed - {e}"
    except Exception as e: # Catch any other unexpected errors
        return file_path, f"error: Unexpected error - {e}"


# --- Main Function ---
def fetch_and_load_earthquake_data(
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    min_magnitude: float = 1.0,
    force_download: bool = False,
    max_workers: int = 10 # Max parallel downloads
) -> gpd.GeoDataFrame | None:
    """
    Fetches earthquake data from USGS day-by-day for the specified period using
    parallel downloads. Saves each day locally as earthquakes-YYYY-MM-DD.geojson
    if it doesn't exist or if force_download is True. Loads all relevant daily
    files and concatenates them into a single GeoDataFrame.

    Args:
        start_date: Start date (inclusive). Accepts YYYY-MM-DD string or date object.
                    Defaults to 1 year before end_date.
        end_date: End date (inclusive). Accepts YYYY-MM-DD string or date object.
                  Defaults to yesterday (to ensure full days).
        min_magnitude: Minimum earthquake magnitude. Defaults to 1.0.
        force_download: If True, always download fresh data for each day in the range,
                        overwriting corresponding local files.
        max_workers: Maximum number of parallel download threads.

    Returns:
        A GeoDataFrame containing the earthquake data for the entire period,
        or None if fetching/loading fails or no data is found.
    """
    # --- Parameter Handling and Date Conversion ---
    # (Same as before)
    if end_date is None:
        end_dt = date.today() - timedelta(days=1)
    elif isinstance(end_date, str):
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_dt = end_date

    if start_date is None:
        start_dt = end_dt - timedelta(days=365 * 1) # Default start date changed to 1 year before end_dt
    elif isinstance(start_date, str):
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_dt = start_date

    if start_dt > end_dt:
        print(f"Error: Start date ({start_dt}) cannot be after end date ({end_dt}).")
        return None

    print(f"Processing earthquake data from {start_dt} to {end_dt} (inclusive)...")
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- Identify Dates to Download ---
    all_dates_in_range = [start_dt + timedelta(days=i) for i in range((end_dt - start_dt).days + 1)]
    dates_to_download = []
    all_expected_files = [] # Keep track of all files for the range

    for current_date in all_dates_in_range:
        day_str = current_date.strftime('%Y-%m-%d')
        filename = f"earthquakes-{day_str}.geojson"
        file_path = os.path.join(DATA_DIR, filename)
        all_expected_files.append(file_path)

        if not os.path.exists(file_path) or force_download:
            dates_to_download.append(current_date)

    # --- Parallel Download ---
    if dates_to_download:
        print(f"Need to download data for {len(dates_to_download)} days (using up to {max_workers} workers)...")
        download_results = {}
        # Using ThreadPoolExecutor for I/O-bound tasks
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit download tasks
            future_to_date = {
                executor.submit(_download_single_day, dt, min_magnitude): dt
                for dt in dates_to_download
            }
            processed_count = 0
            total_to_process = len(dates_to_download)
            for future in concurrent.futures.as_completed(future_to_date):
                current_dt = future_to_date[future]
                processed_count += 1
                try:
                    file_path, status = future.result()
                    download_results[current_dt] = (file_path, status)
                    if "error" in status:
                         print(f"\nError downloading for {current_dt}: {status}")
                    # Update progress (optional)
                    print(f"\rDownloaded {processed_count}/{total_to_process} days...", end="")

                except Exception as exc:
                    print(f'\n{current_dt} generated an exception: {exc}')
                    download_results[current_dt] = (None, f"error: Exception in thread - {exc}")
        print("\nFinished parallel download process.")
    else:
        print("All daily files already exist locally.")

    # --- Load and Concatenate Daily Files ---
    # (Same logic as before, but uses all_expected_files list)
    daily_gdfs = []
    print("Loading daily GeoJSON files...")
    loaded_files = 0
    for file_path in all_expected_files: # Load all files expected for the range
        if os.path.exists(file_path):
            try:
                if os.path.getsize(file_path) > 0:
                    gdf_day = gpd.read_file(file_path)
                    if not gdf_day.empty:
                        # Add a 'source_date' column for potential debugging/verification
                        file_date_str = os.path.basename(file_path).replace('earthquakes-','').replace('.geojson','')
                        try:
                            gdf_day['source_date'] = datetime.strptime(file_date_str, '%Y-%m-%d').date()
                        except ValueError:
                             gdf_day['source_date'] = None # Handle potential parsing errors
                        daily_gdfs.append(gdf_day)
                        loaded_files += 1
            except Exception as e:
                print(f"Error loading GeoDataFrame from {file_path}: {e}")
        # else: # File might be missing if download failed and it didn't exist before
            # print(f"  - File not found (skipped): {os.path.basename(file_path)}")


    if not daily_gdfs:
        print("No earthquake data loaded for the specified period.")
        return None

    print(f"Concatenating data from {loaded_files} daily files...")
    try:
        combined_gdf = pd.concat(daily_gdfs, ignore_index=True)
        if not isinstance(combined_gdf, gpd.GeoDataFrame):
             print("Error: Concatenation did not result in a GeoDataFrame.")
             return None
        if combined_gdf.crs is None and daily_gdfs:
             combined_gdf.crs = daily_gdfs[0].crs

        print(f"Successfully loaded and combined {len(combined_gdf)} total earthquakes.")
        # Optional: Filter results strictly within the requested date range
        # combined_gdf = combined_gdf[(combined_gdf['source_date'] >= start_dt) & (combined_gdf['source_date'] <= end_dt)]
        # print(f"Filtered to {len(combined_gdf)} earthquakes within the exact date range.")
        return combined_gdf
    except Exception as e:
        print(f"Error during concatenation: {e}")
        return None

# Example usage
if __name__ == "__main__":
    end_test = date.today() - timedelta(days=1)
    start_test = end_test - timedelta(days=365 * 1) # Default load the last 1 years
    start_run_time = time.time()
    earthquake_gdf_small_range = fetch_and_load_earthquake_data(
        start_date=start_test,
        end_date=end_test,
        min_magnitude=1.0,
        force_download=False # Set to True to force redownload for testing
    )
    end_run_time = time.time()
    print(f"Time taken: {end_run_time - start_run_time:.2f} seconds")

    if earthquake_gdf_small_range is not None:
        print(f"\nLoaded {len(earthquake_gdf_small_range)} earthquakes ({start_test} to {end_test}, M >= 1.0).")
    else:
        print("\nFailed to load earthquake data for the small range test.")
