import os
import logging
import concurrent.futures
import time
import calendar # Added for month range calculation
from datetime import datetime, timedelta, date
from obspy.clients.fdsn import Client
from obspy import UTCDateTime
from obspy.clients.fdsn.header import FDSNNoDataException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEFAULT_DATA_DIR = 'resources/seismic_data/'

# Define default stations if none are provided
DEFAULT_STATION_REQUESTS = [
    # North America
    ('IU', 'ANMO', '00', 'BHZ'), # Albuquerque, USA
    ('II', 'PFO', '00', 'BHZ'),  # Pinyon Flat, USA
    ('IU', 'COR', '00', 'BHZ'),  # Corvallis, USA
    ('IU', 'TUC', '00', 'BHZ'),  # Tucson, USA
    ('IC', 'RES', '', 'BHZ'),   # Resolute, Canada (Canadian National Seismograph Network)
    ('IU', 'CCM', '00', 'BHZ'),  # Cathedral Caves, Missouri, USA
    ('IU', 'SFJD', '', 'BHZ'),  # Sondre Stromfjord, Greenland
    ('II', 'KDAK', '10', 'BHZ'), # Kodiak Island, USA (IRIS/IDA Network)
    # South America
    ('II', 'NNA', '00', 'BHZ'),  # Nana, Peru
    ('IU', 'TRQA', '10', 'BHZ'), # Tarija, Bolivia
    ('II', 'LCO', '00', 'BHZ'),  # La Cilla, Chile
    ('IU', 'RCBR', '00', 'BHZ'), # Riachuelo, Brazil
    # Europe / Africa
    ('II', 'KONO', '00', 'BHZ'), # Kongsberg, Norway
    ('IU', 'ESK', '', 'BHZ'),   # Eskdalemuir, UK
    # ('GE', 'KEV', '', 'BHZ'), # Kevo, Finland (GEOFON - May have latency at IRIS)
    ('II', 'MBO', '00', 'BHZ'),  # Mbour, Senegal
    # ('GE', 'TAM', '', 'BHZ'), # Tamanrasset, Algeria (GEOFON - May have latency at IRIS)
    ('IU', 'WUS', '', 'BHZ'),   # Wushi, China (Often good availability)
    # Asia / Oceania
    ('IU', 'MAJO', '00', 'BHZ'), # Matsushiro, Japan
    ('IU', 'CHTO', '00', 'BHZ'), # Chiang Mai, Thailand
    ('IU', 'SNZO', '10', 'BHZ'), # South Karori, NZ
    ('AU', 'NWAO', '', 'BHZ'),  # Narrogin, Australia (Australian Network)
    ('IU', 'PET', '00', 'BHZ'),  # Petropavlovsk, Russia
    ('IU', 'TATO', '00', 'BHZ'), # Taipei, Taiwan
    ('AU', 'CTAO', '', 'BHZ'), # Charters Towers, Australia
    ('II', 'WRAB', '00', 'BHZ'), # Warramunga, Australia
    # Antarctica
    ('II', 'SPA', '00', 'BHZ'),  # South Pole, Antarctica
    ('IU', 'VNDA', '00', 'BHZ'), # Vanda, Antarctica
    # Islands
    ('IU', 'KIP', '00', 'BHZ'),  # Kipapa, Hawaii, USA
    ('IU', 'POHA', '00', 'BHZ'), # Pohakuloa, Hawaii, USA
    # ('G', 'PPT', '', 'BHZ'),    # Papeete, Tahiti (GEONET - May have latency at IRIS)
    ('IU', 'XMAS', '00', 'BHZ'), # Kiritimati (Christmas Island)
    ('IU', 'RAO', '', 'BHZ'),   # Raoul Island, Kermadec Islands
] # Total: 29 stations

# --- Helper Function for Month Iteration ---
def month_year_iter(start_month, start_year, end_month, end_year):
    """ Generator for iterating through months (inclusive). """
    ym_start= 12*start_year + start_month - 1
    ym_end= 12*end_year + end_month - 1
    for ym in range(ym_start, ym_end + 1):
        y, m = divmod(ym, 12)
        yield y, m + 1

# --- Helper Function for Single Station-Month Download ---
def _download_single_station_month(
    client: Client,
    request_tuple: tuple,
    target_year: int,
    target_month: int,
    data_dir: str,
    station_inventory: dict, # Pre-fetched inventory { (net, sta): (lon, lat), ... }
    request_delay_seconds: float = 0.1
) -> tuple[str | None, str]:
    """
    Downloads and saves seismic data for a single station for a full month.

    Args:
        client: Initialized obspy FDSN client.
        request_tuple: (network, station, location, channel) for the request.
        target_year: The year to download data for.
        target_month: The month to download data for.
        data_dir: Base directory for saving seismic data.
        station_inventory: Dictionary containing station coordinates.
        request_delay_seconds: Small delay before making the API request.

    Returns:
        A tuple containing the file path (if successful) or None, and a status message.
    """
    network, station, location, channel = request_tuple
    request_id = f"{network}.{station}.{location}.{channel}" # For logging
    # Calculate start and end of the month
    month_start_dt = datetime(target_year, target_month, 1)
    _, last_day = calendar.monthrange(target_year, target_month)
    month_end_dt = datetime(target_year, target_month, last_day, 23, 59, 59, 999999)
    month_start = UTCDateTime(month_start_dt)
    month_end = UTCDateTime(month_end_dt)
    month_str = f"{target_year:04d}-{target_month:02d}"

    # Define station-specific directory
    station_dir = os.path.join(data_dir, network, station)
    os.makedirs(station_dir, exist_ok=True)

    # Get coordinates from inventory
    coords = station_inventory.get((network, station))
    if coords:
        lon, lat = coords
        # Format coordinates, handling potential negative signs for filenames
        lon_str = f"{abs(lon):.2f}{'W' if lon < 0 else 'E'}"
        lat_str = f"{abs(lat):.2f}{'S' if lat < 0 else 'N'}"
        coord_str = f"_lon{lon_str}_lat{lat_str}"
    else:
        coord_str = "_lonNA_latNA" # Fallback if coords not found
        # Warning logged in main function if inventory fetch fails

    # Define filename for the month including coordinates
    loc_fn = location if location else "__" # Use '__' if location code is empty
    chan_fn = channel if channel else "__" # Use '__' if channel code is empty
    filename = f"{network}.{station}{coord_str}.{loc_fn}.{chan_fn}__{month_str}.mseed"
    filepath = os.path.join(station_dir, filename)

    # --- Check if file exists (add force_download logic later if needed) ---
    # This check is now done in the main function before submitting tasks

    logging.debug(f"Requesting data for {request_id} for {month_str}")
    try:
        # Add a small delay before each request
        time.sleep(request_delay_seconds)

        st = client.get_waveforms(network=network, station=station, location=location, channel=channel,
                                  starttime=month_start, endtime=month_end)

        if not st: # Check if the stream is empty
            logging.warning(f"No data returned for {request_id} for {month_str}.")
            return None, "no_data"

        # Save the stream to the monthly file
        logging.debug(f"Saving data to {filepath}")
        st.write(filepath, format="MSEED")
        return filepath, "success"

    except FDSNNoDataException:
        logging.warning(f"No data found via FDSN for {request_id} for {month_str}.")
        return None, "no_data_fdsn"
    except Exception as e:
        # Log only the error message for cleaner concurrent output
        logging.error(f"Failed download/process for {request_id} on {month_str}: {e}")
        return None, f"error: {e}"


# --- Main Fetch Function ---
def fetch_seismic_data(
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    station_requests: list[tuple] = DEFAULT_STATION_REQUESTS,
    client_name: str = "IRIS",
    data_dir: str = DEFAULT_DATA_DIR,
    max_workers: int = 5, # Limit concurrent downloads
    force_download: bool = False # Add option to force re-download
    ) -> list[str]:
    """
    Fetches seismic waveform data from an FDSN client month-by-month for multiple stations
    using parallel downloads. Saves data locally in MiniSEED format, organized by
    network and station, with coordinates in the filename (YYYY-MM format).

    Args:
        start_date: Start date (inclusive). Accepts YYYY-MM-DD string or date object.
                    Defaults to 7 days before end_date.
        end_date: End date (inclusive). Accepts YYYY-MM-DD string or date object.
                    Defaults to yesterday.
        station_requests (list): List of tuples: (network, station, location, channel).
                                 Defaults to DEFAULT_STATION_REQUESTS.
        client_name (str): FDSN data center identifier (e.g., "IRIS"). Defaults to "IRIS".
        data_dir (str): Base directory to save the downloaded MiniSEED files.
                        Defaults to 'resources/seismic_data/'.
        max_workers (int): Maximum number of parallel download threads. Defaults to 5.
        force_download (bool): If True, re-download data even if the file exists. Defaults to False.

    Returns:
        list: A list of file paths to the successfully downloaded/verified MiniSEED files.
    """
    # --- Parameter Handling and Date Conversion ---
    if end_date is None:
        end_dt = date.today() - timedelta(days=1)
    elif isinstance(end_date, str):
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            logging.error(f"Invalid end_date format: {end_date}. Use YYYY-MM-DD.")
            return []
    else:
        end_dt = end_date # Assume it's a date object

    if start_date is None:
        start_dt = end_dt - timedelta(days=7) # Default to last 7 days
    elif isinstance(start_date, str):
         try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
         except ValueError:
            logging.error(f"Invalid start_date format: {start_date}. Use YYYY-MM-DD.")
            return []
    else:
        start_dt = start_date # Assume it's a date object

    if start_dt > end_dt:
        logging.error(f"Start date ({start_dt}) cannot be after end date ({end_dt}).")
        return []

    logging.info(f"Processing seismic data from {start_dt} to {end_dt} (inclusive)...")
    station_codes_log = [f"{req[0]}.{req[1]}.{req[2] if req[2] else '*'}.{req[3] if req[3] else '*'}" for req in station_requests]
    logging.info(f"Requested stations/channels: {station_codes_log}")
    os.makedirs(data_dir, exist_ok=True) # Ensure base data directory exists

    # --- Initialize FDSN Client ---
    logging.info(f"Initializing FDSN client for {client_name}")
    try:
        client = Client(client_name)
    except Exception as e:
        logging.error(f"Failed to initialize FDSN client '{client_name}': {e}")
        return []

    # --- Fetch Station Inventory for Coordinates ---
    logging.info("Fetching station inventory for coordinates...")
    station_inventory = {}
    unique_stations = list(set([(req[0], req[1]) for req in station_requests])) # Get unique net/sta pairs
    try:
        # Build inventory query parameters - handle wildcards if necessary, though specific stations are better
        # Use '*' for network/station if only one unique value exists to avoid issues with comma separation
        net_query = ",".join(s[0] for s in unique_stations) if len(set(s[0] for s in unique_stations)) > 1 else unique_stations[0][0]
        sta_query = ",".join(s[1] for s in unique_stations) if len(set(s[1] for s in unique_stations)) > 1 else unique_stations[0][1]

        inv = client.get_stations(network=net_query,
                                  station=sta_query,
                                  level="station")
        for net in inv:
            for sta in net:
                station_inventory[(net.code, sta.code)] = (sta.longitude, sta.latitude)
        logging.info(f"Successfully fetched coordinates for {len(station_inventory)} stations.")
    except Exception as e:
        logging.error(f"Failed to fetch station inventory: {e}. Coordinates will be missing in filenames.")
        # Continue without coordinates if inventory fails

    # --- Prepare Download Tasks ---
    tasks_to_run = []
    expected_files = [] # Keep track of all files we expect/process
    # Generate month/year combinations in the range
    all_months_in_range = list(month_year_iter(start_dt.month, start_dt.year, end_dt.month, end_dt.year))

    for target_year, target_month in all_months_in_range:
        for request_tuple in station_requests:
            # Calculate expected filepath for checking existence or adding to final list
            network, station, location, channel = request_tuple
            station_dir = os.path.join(data_dir, network, station)
            coords = station_inventory.get((network, station))
            if coords:
                lon, lat = coords
                lon_str = f"{abs(lon):.2f}{'W' if lon < 0 else 'E'}"
                lat_str = f"{abs(lat):.2f}{'S' if lat < 0 else 'N'}"
                coord_str = f"_lon{lon_str}_lat{lat_str}"
            else:
                coord_str = "_lonNA_latNA"
            loc_fn = location if location else "*"
            chan_fn = channel if channel else "*"
            month_str = f"{target_year:04d}-{target_month:02d}"
            filename = f"{network}.{station}{coord_str}.{loc_fn}.{chan_fn}__{month_str}.mseed"
            filepath = os.path.join(station_dir, filename)
            expected_files.append(filepath)

            # Decide if download is needed
            if force_download or not os.path.exists(filepath):
                 tasks_to_run.append((request_tuple, target_year, target_month, filepath)) # Pass filepath to task
            # else:
            #     logging.debug(f"File exists, skipping task creation: {filepath}")

    # --- Parallel Download Execution ---
    successful_downloads = [] # Store paths of successfully created/verified files
    if tasks_to_run:
        logging.info(f"Need to download/check data for {len(tasks_to_run)} station-month combinations (using up to {max_workers} workers)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Pass client, request_tuple, target_year, target_month, data_dir, station_inventory to helper
            future_to_task = {
                executor.submit(
                    _download_single_station_month,
                    client, task[0], task[1], task[2], data_dir, station_inventory # task[0]=req, task[1]=year, task[2]=month
                ): task # task is (request_tuple, target_year, target_month, filepath)
                for task in tasks_to_run
            }
            processed_count = 0
            total_to_process = len(tasks_to_run)
            for future in concurrent.futures.as_completed(future_to_task):
                task_info = future_to_task[future] # (request_tuple, target_year, target_month, filepath)
                original_filepath = task_info[3] # Get the expected filepath
                processed_count += 1
                try:
                    filepath_result, status = future.result()
                    # Use the result filepath if success, otherwise check original expected path
                    if status == "success" and filepath_result:
                        successful_downloads.append(filepath_result)
                    elif "error" in status:
                         # Error already logged in helper
                         pass
                    # Log progress periodically
                    if processed_count % 20 == 0 or processed_count == total_to_process: # Log more frequently
                         logging.info(f"Processed {processed_count}/{total_to_process} download tasks...")

                except Exception as exc:
                    req_tuple_log = task_info[0]
                    year_log = task_info[1]
                    month_log = task_info[2]
                    logging.error(f'Task ({req_tuple_log}, {year_log}-{month_log:02d}) generated an exception: {exc}')
        logging.info("Finished parallel download process.")
    else:
        logging.info("All required monthly files already exist locally (and force_download=False).")

    # --- Final File List ---
    # Combine newly downloaded files with existing files that were skipped but should be included
    final_file_list = list(set(successful_downloads + [fp for fp in expected_files if os.path.exists(fp)]))
    logging.info(f"Total relevant files found/downloaded: {len(final_file_list)}")

    return final_file_list

if __name__ == '__main__':
    # Example usage: Fetch data for default stations for the last week
    logging.info("Running example: Fetching seismic data for default stations for the last year (monthly)...")

    end_run_date = date.today() - timedelta(days=1) # Yesterday
    start_run_date = end_run_date - timedelta(days=365*1) # One year before end date

    start_time_exec = time.time()
    try:
        # Using default stations and calculated dates
        downloaded_files = fetch_seismic_data(
            start_date=start_run_date,
            end_date=end_run_date,
            # station_requests=DEFAULT_STATION_REQUESTS, # Implicitly uses default
            max_workers=5, # Adjust as needed
            force_download=False # Set to False to avoid re-downloading existing files
            # force_download=True # Uncomment to force re-download for testing
        )

        if downloaded_files:
            logging.info(f"\nExample run successful. {len(downloaded_files)} files found/downloaded.")
            # Log first few files for verification
            logging.info("Example files (up to 5):")
            for f in downloaded_files[:5]:
                logging.info(f" - {f}")
        else:
            logging.info("\nExample run completed, but no files were found or downloaded.")

    except Exception as e:
        logging.error(f"An error occurred during the example run: {e}", exc_info=True)
    finally:
        end_time_exec = time.time()
        logging.info(f"Example run finished in {end_time_exec - start_time_exec:.2f} seconds.")