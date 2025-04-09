# Pseudocode for functions/spatial_analysis.py

# --- Imports ---
import geopandas as gpd
import pandas as pd
import numpy as np
import swifter # < TDD: Ensure swifter is installed and imported
import warnings
import traceback
import logging # Added for logging
import concurrent.futures # Added for parallel processing of zones
import os # Added to potentially get CPU count
from shapely.geometry import Point, LineString, MultiLineString, box # Added box for extent filtering

# --- Constants ---
# Define default CRS if needed (e.g., for input checks if CRS is missing)
DEFAULT_CRS = "EPSG:4326"
# Define required columns for clarity
REQ_EQ_COLS = ['utm_geometry', 'utm_epsg']
REQ_PLATE_COLS = ['geometry', 'strnum', 'platecode', 'geogdesc', 'boundary_t']
# Define output columns
OUTPUT_COLS = ['distance_to_plate', 'nearest_plate_strnum', 'nearest_plate_platecode', 'nearest_plate_geogdesc', 'nearest_plate_boundary_t']

# --- Logger Setup ---
# Get a logger for this module
logger = logging.getLogger(__name__)
# Basic configuration if no handlers are set (optional, depends on application structure)
# if not logger.hasHandlers():
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Helper Function (for swifter.apply) ---
# Define the helper function that will be applied to each earthquake row within a UTM zone
def find_nearest_plate_info(earthquake_utm_geom, plate_gdf_proj, logger): # Added logger parameter
    """
    Finds the nearest plate boundary and its attributes for a single earthquake point.
    (Called by swifter within _process_zone)

    Args:
        earthquake_utm_geom (shapely.geometry.Point): The UTM geometry of a single earthquake.
        plate_gdf_proj (gpd.GeoDataFrame): The plate boundaries projected to the *same* UTM zone
                                           as the earthquake point.
        logger (logging.Logger): The logger instance to use for messages.

    Returns:
        pandas.Series: Contains distance and attributes of the nearest plate, or NaNs if error/no plates.
                       Index: ['distance_to_plate', 'nearest_plate_strnum', 'nearest_plate_platecode', 'nearest_plate_geogdesc', 'nearest_plate_boundary_t']
    """
    # Initialize result Series with NaNs using the final output column names
    result_data = {
        'distance_to_plate': np.nan,
        'nearest_plate_strnum': pd.NA,
        'nearest_plate_platecode': pd.NA,
        'nearest_plate_geogdesc': pd.NA,
        'nearest_plate_boundary_t': pd.NA
    }
    result_series = pd.Series(result_data, index=OUTPUT_COLS) # Ensure index matches OUTPUT_COLS

    # Check if input geometry is valid and plate GDF is not empty
    if earthquake_utm_geom is None or not earthquake_utm_geom.is_valid or plate_gdf_proj.empty:
        return result_series

    # Add more detailed logging within the helper
    # Note: logger passed from _process_zone will have the correct level set
    logger.debug(f"      Helper: Processing point {earthquake_utm_geom.wkt}") # DEBUG level
    logger.debug(f"      Helper: Comparing against {len(plate_gdf_proj)} filtered plates.") # DEBUG level
    try:
        # Calculate distances from the earthquake point to all plate geometries
        distances = plate_gdf_proj.geometry.distance(earthquake_utm_geom)
        logger.debug(f"      Helper: Distances calculated (sample): {distances.head().tolist()}") # DEBUG level

        # Check if any valid distances were computed
        if distances.empty:
             logger.warning(f"      Helper: No distances calculated for point {earthquake_utm_geom.wkt}.")
             return result_series
        if distances.isna().all():
             logger.warning(f"      Helper: All calculated distances are NaN for point {earthquake_utm_geom.wkt}.")
             logger.debug(f"      Helper DEBUG: Plate geoms being compared:\n{plate_gdf_proj.geometry.head()}") # DEBUG level
             return result_series

        # Find the index (label) of the minimum distance
        nearest_plate_idx_label = distances.idxmin(skipna=True)

        # Check if idxmin returned NaN
        if pd.isna(nearest_plate_idx_label):
             logger.warning(f"      Helper: Could not find minimum distance (idxmin returned NaN) for point {earthquake_utm_geom.wkt}.")
             return result_series

        # Get the minimum distance value
        min_distance = distances.loc[nearest_plate_idx_label]

        # Check if the minimum distance itself is NaN
        if pd.isna(min_distance):
             logger.warning(f"      Helper: Minimum distance value is NaN for point {earthquake_utm_geom.wkt} (Index: {nearest_plate_idx_label}).")
             return result_series

        # Retrieve the required attributes from the nearest plate
        nearest_plate_attributes = plate_gdf_proj.loc[nearest_plate_idx_label, ['strnum', 'platecode', 'geogdesc', 'boundary_t']]

        # Update the result Series
        result_series['distance_to_plate'] = min_distance
        result_series['nearest_plate_strnum'] = nearest_plate_attributes['strnum']
        result_series['nearest_plate_platecode'] = nearest_plate_attributes['platecode']
        result_series['nearest_plate_geogdesc'] = nearest_plate_attributes['geogdesc']
        result_series['nearest_plate_boundary_t'] = nearest_plate_attributes['boundary_t']

        return result_series

    except Exception as e:
        # Log the error for the specific point
        logger.error(f"      Helper: Error finding nearest plate for point {earthquake_utm_geom.wkt}. Type: {type(e).__name__}, Error: {e}", exc_info=False)
        return result_series

# --- Worker Function (for parallel processing of zones) ---
def _process_zone(utm_epsg, eq_subset_gdf, plate_gdf_copy, logger, log_level_str):
    """
    Processes all earthquakes within a single UTM zone.
    (Called by ProcessPoolExecutor in calculate_distance_to_plate)

    Args:
        utm_epsg: The UTM EPSG code (e.g., 32610) for the current zone.
        eq_subset_gdf (gpd.GeoDataFrame): Subset of earthquake data for this zone.
        plate_gdf_copy (gpd.GeoDataFrame): A copy of the plate boundary data.
        logger (logging.Logger): The logger instance.
        log_level_str (str): The string representation of the log level ('INFO', 'DEBUG', etc.).

    Returns:
        gpd.GeoDataFrame: The input eq_subset_gdf with distance/attribute columns added/updated.
                          Returns the original subset if processing fails for this zone.
    """
    # --- Per-Zone Setup ---
    current_epsg_str = None
    current_epsg_int = None
    try:
        # Validate and format the EPSG code
        if pd.isna(utm_epsg):
             logger.warning(f"  Skipping zone with null EPSG value.")
             return eq_subset_gdf # Return unprocessed subset

        # Handle string format like 'EPSG:32605' or just integer 32605
        if isinstance(utm_epsg, str):
            if utm_epsg.upper().startswith('EPSG:'):
                epsg_num_str = utm_epsg.split(':')[-1]
                current_epsg_int = int(epsg_num_str)
            else:
                current_epsg_int = int(utm_epsg)
        elif isinstance(utm_epsg, (int, float)):
             current_epsg_int = int(utm_epsg)
        else:
             raise ValueError(f"Unsupported EPSG format: {type(utm_epsg)}")

        if current_epsg_int is None:
             raise ValueError("Could not parse EPSG code.")

        current_epsg_str = f"EPSG:{current_epsg_int}"
        logger.info(f"\nProcessing zone: {current_epsg_str} (Parsed from: {utm_epsg})")

        # Validate the target CRS itself before projecting
        try:
             _ = gpd.GeoDataFrame(geometry=[]).set_crs(current_epsg_str).crs
        except Exception as crs_e:
             logger.warning(f"  Invalid target CRS '{current_epsg_str}'. Skipping this zone. Reason: {crs_e}")
             return eq_subset_gdf # Return unprocessed subset

    except (ValueError, TypeError, IndexError) as e:
        logger.warning(f"  Skipping invalid or unparseable EPSG value '{utm_epsg}'. Reason: {e}")
        return eq_subset_gdf # Return unprocessed subset

    # If no earthquakes in this zone (shouldn't happen if called from grouped data, but check)
    if eq_subset_gdf.empty:
        logger.info(f"  No earthquakes found for {current_epsg_str}. Skipping.")
        return eq_subset_gdf

    logger.info(f"  Found {len(eq_subset_gdf)} earthquakes for {current_epsg_str}.")

    # --- Project Plates to Current Zone ---
    plate_gdf_proj = None
    plate_gdf_to_use = None
    try:
        logger.info(f"  Projecting {len(plate_gdf_copy)} plate boundaries to {current_epsg_str}...")
        # Check if plates are already in the target CRS
        if plate_gdf_copy.crs and plate_gdf_copy.crs.equals(current_epsg_str):
            plate_gdf_proj = plate_gdf_copy.copy() # Still copy to be safe
            logger.debug("    Plates already in target CRS.")
        else:
            plate_gdf_proj = plate_gdf_copy.to_crs(current_epsg_str)
            logger.debug(f"    Plates reprojected. New CRS: {plate_gdf_proj.crs}")

        # --- Filter and Validate Projected Plates ---
        # 1. Drop invalid geometries created during projection
        initial_plate_count = len(plate_gdf_proj)
        plate_gdf_proj = plate_gdf_proj[plate_gdf_proj.is_valid]
        valid_plate_count = len(plate_gdf_proj)
        if valid_plate_count < initial_plate_count:
            logger.debug(f"    Dropped {initial_plate_count - valid_plate_count} invalid geometries after projection.")

        # If all plates became invalid, skip this zone
        if plate_gdf_proj.empty:
            logger.warning(f"    No valid plate geometries remain after projection for {current_epsg_str}. Skipping.")
            return eq_subset_gdf # Return unprocessed subset

        # 2. Filter plates by buffered extent of earthquakes in this zone
        logger.info(f"    Filtering {valid_plate_count} valid plates by earthquake extent...")
        eq_bounds = eq_subset_gdf.total_bounds
        buffer_dist = 1_000_000
        buffered_bounds_poly = box(
            eq_bounds[0] - buffer_dist, eq_bounds[1] - buffer_dist,
            eq_bounds[2] + buffer_dist, eq_bounds[3] + buffer_dist
        )
        plates_sindex = plate_gdf_proj.sindex
        possible_matches_index = list(plates_sindex.intersection(buffered_bounds_poly.bounds))
        plate_gdf_filtered = plate_gdf_proj.iloc[possible_matches_index]
        logger.info(f"    Filtered to {len(plate_gdf_filtered)} plates within buffered extent.")

        # If filtering results in no plates, skip calculations for this zone
        if plate_gdf_filtered.empty:
             logger.warning(f"    No plates found within the buffered extent for {current_epsg_str}. Skipping calculations.")
             return eq_subset_gdf # Return unprocessed subset

        # Use the filtered plates for distance calculation
        plate_gdf_to_use = plate_gdf_filtered
    except Exception as e:
        logger.error(f"  Error projecting/filtering plates for {current_epsg_str}: {e}", exc_info=True)
        logger.warning(f"  Skipping calculations for earthquakes in {current_epsg_str}.")
        return eq_subset_gdf # Return unprocessed subset

    # Check if the *filtered* plate GDF is empty
    if plate_gdf_to_use is None or plate_gdf_to_use.empty:
        logger.warning(f"  Skipping calculations for {current_epsg_str} due to empty/invalid filtered plates.")
        return eq_subset_gdf # Return unprocessed subset

    # --- Apply Helper Function using Swifter ---
    logger.info(f"  Calculating distances and attributes for {len(eq_subset_gdf)} earthquakes...")
    try:
        # Determine whether to show the swifter progress bar based on log level
        show_progress_bar = log_level_str.upper() != 'NONE'
        logger.debug(f"  Swifter progress bar enabled: {show_progress_bar}")

        nearest_info_series = eq_subset_gdf['utm_geometry'].swifter.progress_bar(show_progress_bar).apply(
            find_nearest_plate_info,
            args=(plate_gdf_to_use, logger) # Pass FILTERED plates and logger
        )

        # --- Combine Results ---
        logger.info(f"  Combining results for {current_epsg_str}...")
        if isinstance(nearest_info_series, pd.DataFrame):
            nearest_info_df = nearest_info_series
            nearest_info_df = nearest_info_df.reindex(eq_subset_gdf.index)
        elif isinstance(nearest_info_series, pd.Series):
             try:
                 nearest_info_df = pd.DataFrame(nearest_info_series.tolist(), index=nearest_info_series.index)
             except AttributeError as e:
                  logger.error(f"  Error converting Series results to DataFrame for {current_epsg_str}: {e}")
                  logger.warning(f"  Skipping result combination for this zone.")
                  return eq_subset_gdf # Return unprocessed subset
        else:
             logger.error(f"  Unexpected type returned by swifter.apply for {current_epsg_str}: {type(nearest_info_series)}")
             logger.warning(f"  Skipping result combination for this zone.")
             return eq_subset_gdf # Return unprocessed subset

        # Ensure the resulting DataFrame has the expected columns
        for col in OUTPUT_COLS:
            if col not in nearest_info_df.columns:
                logger.warning(f"  Column '{col}' missing in swifter results for {current_epsg_str}. Filling with NA.")
                fill_val = np.nan if col == 'distance_to_plate' else pd.NA
                nearest_info_df[col] = fill_val

        # Assign the new columns to the earthquake subset DataFrame
        # Create a copy to avoid modifying the original slice from the groupby object
        processed_subset_gdf = eq_subset_gdf.copy()
        for col in OUTPUT_COLS:
             if col in nearest_info_df.columns:
                 processed_subset_gdf.loc[nearest_info_df.index, col] = nearest_info_df[col]
             else:
                 logger.warning(f"  Column '{col}' not found in helper function results for {current_epsg_str}.")
                 fill_val = np.nan if col == 'distance_to_plate' else pd.NA
                 processed_subset_gdf.loc[nearest_info_df.index, col] = fill_val

        updated_count = processed_subset_gdf[OUTPUT_COLS[0]].notna().sum()
        logger.info(f"  Successfully processed {updated_count} earthquakes for {current_epsg_str}.")
        return processed_subset_gdf # Return the processed subset

    except Exception as apply_e:
         logger.error(f"  Error during swifter.apply or result combination for {current_epsg_str}: {apply_e}", exc_info=True)
         logger.warning(f"  Skipping calculations for earthquakes associated with {current_epsg_str}.")
         return eq_subset_gdf # Return unprocessed subset


# --- Main Function ---
def calculate_distance_to_plate(earthquake_gdf, plate_gdf, log_level='INFO', max_workers=None): # Added log_level and max_workers
    """
    Calculates the distance from each earthquake point (using pre-defined UTM geometry)
    to the nearest tectonic plate boundary and retrieves specific plate attributes.
    Uses the specified UTM zone for each earthquake for accurate calculations.
    Processes different UTM zones in parallel using ProcessPoolExecutor.

    Args:
        earthquake_gdf (gpd.GeoDataFrame): GeoDataFrame with earthquake data.
            Must include columns: 'utm_geometry' (Point geometry in UTM),
            'utm_epsg' (Integer EPSG code for the UTM zone). Original columns are preserved.
        plate_gdf (gpd.GeoDataFrame): GeoDataFrame with tectonic plate boundaries.
            Must include columns: 'geometry' (LineString/MultiLineString),
            'strnum', 'platecode', 'geogdesc', 'boundary_t'.
        log_level (str, optional): Controls the logging verbosity.
            Options: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'NONE'. Defaults to 'INFO'.
        max_workers (int, optional): Maximum number of worker processes for parallel zone processing.
            Defaults to os.cpu_count().

    Returns:
        gpd.GeoDataFrame: The input earthquake_gdf with new columns added:
                          'distance_to_plate', 'nearest_plate_strnum',
                          'nearest_plate_platecode', 'nearest_plate_geogdesc',
                          'nearest_plate_boundary_t'.
                          Returns the original DataFrame with NaN/NA in new columns
                          if inputs are invalid or processing fails.
    """
    # --- Function Setup ---
    # --- Logger Level Setup ---
    log_level_map = {
        'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING,
        'ERROR': logging.ERROR, 'NONE': logging.CRITICAL + 1
    }
    requested_level = log_level_map.get(str(log_level).upper(), logging.INFO)
    original_level = logger.level
    logger.setLevel(requested_level)

    # Define final_gdf in the outer scope
    final_gdf = None
    results_list = [] # Initialize results list here

    try:
        func_name = "calculate_distance_to_plate"
        logger.info(f"--- Starting {func_name} (Log Level: {log_level.upper()}) ---")

        # --- Input Validation ---
        if not isinstance(earthquake_gdf, gpd.GeoDataFrame):
            logger.error("Input validation failed: earthquake_gdf is not a GeoDataFrame.")
            return earthquake_gdf
        if not isinstance(plate_gdf, gpd.GeoDataFrame):
            logger.error("Input validation failed: plate_gdf is not a GeoDataFrame.")
            return earthquake_gdf
        missing_eq_cols = [col for col in REQ_EQ_COLS if col not in earthquake_gdf.columns]
        if missing_eq_cols:
            logger.error(f"Input validation failed: earthquake_gdf missing required columns: {missing_eq_cols}.")
            return earthquake_gdf
        missing_plate_cols = [col for col in REQ_PLATE_COLS if col not in plate_gdf.columns]
        if missing_plate_cols:
            logger.error(f"Input validation failed: plate_gdf missing required columns: {missing_plate_cols}.")
            return earthquake_gdf

        # Create copies
        eq_gdf_processed = earthquake_gdf.copy()
        plate_gdf_copy = plate_gdf.copy()

        # Initialize output columns
        for col in OUTPUT_COLS:
            if col == 'distance_to_plate': eq_gdf_processed[col] = np.nan
            else: eq_gdf_processed[col] = pd.NA

        # Handle empty inputs
        if earthquake_gdf.empty:
            logger.warning("Input earthquake_gdf is empty. Returning with NA columns.")
            return eq_gdf_processed
        if plate_gdf.empty:
            logger.warning("Input plate_gdf is empty. Returning with NA columns.")
            return eq_gdf_processed

        # --- Geometry Validation (Optional - can be done within worker) ---
        # Basic checks can remain here, more detailed checks can move to worker if needed
        # ... (geometry validation checks as before, using logger) ...
        logger.debug("Performing initial geometry validation checks...")
        # (Include the geometry validation blocks from the previous version here if desired)
        logger.debug("Initial geometry validation checks complete.")


        # --- CRS Handling (Plates) ---
        if plate_gdf_copy.crs is None:
            logger.warning(f"plate_gdf has no CRS. Assuming {DEFAULT_CRS}.")
            try:
                plate_gdf_copy = plate_gdf_copy.set_crs(DEFAULT_CRS, allow_override=True)
            except Exception as e:
                logger.error(f"Failed to set CRS '{DEFAULT_CRS}' on plate_gdf. {e}")
                return eq_gdf_processed
        else:
            logger.info(f"Input plate CRS: {plate_gdf_copy.crs}")

        # --- Group Earthquakes by UTM Zone ---
        # Drop rows where utm_epsg is NaN before grouping
        eq_gdf_processed_valid_epsg = eq_gdf_processed.dropna(subset=['utm_epsg'])
        if len(eq_gdf_processed_valid_epsg) < len(eq_gdf_processed):
             logger.warning(f"Dropped {len(eq_gdf_processed) - len(eq_gdf_processed_valid_epsg)} earthquakes with missing 'utm_epsg'.")

        grouped_eq = eq_gdf_processed_valid_epsg.groupby('utm_epsg')
        num_zones = len(grouped_eq)
        logger.info(f"Found {num_zones} unique UTM EPSG zones with valid data to process.")

        if num_zones == 0:
            logger.warning("No valid UTM EPSG zones found in earthquake_gdf. Returning original data.")
            return eq_gdf_processed # Return original with NAs initialized

        # --- Parallel Processing by UTM Zone ---
        # Determine number of workers
        if max_workers is None:
            max_workers = os.cpu_count()
            logger.info(f"Using default max_workers: {max_workers}")
        else:
            logger.info(f"Using specified max_workers: {max_workers}")

        futures = []
        # Use ProcessPoolExecutor for CPU-bound tasks
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            for utm_epsg, eq_subset_gdf in grouped_eq:
                # Submit each zone's processing task
                # Pass necessary data (subset, plate copy, logger, log level string)
                future = executor.submit(
                    _process_zone,
                    utm_epsg,
                    eq_subset_gdf, # Pass the actual subset GeoDataFrame
                    plate_gdf_copy, # Pass the plate copy
                    logger, # Pass the logger instance
                    log_level.upper() # Pass log level string for swifter control
                )
                futures.append(future)

            logger.info(f"Submitted {len(futures)} zone processing tasks to executor.")

            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    processed_subset = future.result()
                    if processed_subset is not None and not processed_subset.empty:
                        results_list.append(processed_subset)
                    else:
                         logger.warning(f"A zone processing task returned None or empty result.")
                except Exception as e:
                    # Log errors from worker processes
                    logger.error(f"Error processing a UTM zone: {e}", exc_info=True)
                    # Optionally: could try to identify which zone failed if needed

        logger.info(f"Collected results from {len(results_list)} successfully processed zones.")

        # --- Final Concatenation ---
        if not results_list:
            logger.warning("No UTM zones were processed successfully. Returning original data with NA columns.")
            final_gdf = eq_gdf_processed # Assign initial copy
        else:
            try:
                logger.info("Concatenating results...")
                # Concatenate results, ensuring index is preserved if possible,
                # but reset if there are duplicates (which shouldn't happen if grouped correctly)
                final_gdf = pd.concat(results_list, ignore_index=False)

                # --- Reintegrate with original DataFrame ---
                # Update the original eq_gdf_processed with results from final_gdf
                # This ensures rows that failed processing or had no EPSG are kept
                logger.info("Updating original DataFrame with processed results...")
                # Use update, aligning on index. Overwrite=True ensures calculated values replace NAs.
                eq_gdf_processed.update(final_gdf[OUTPUT_COLS], overwrite=True)
                final_gdf = eq_gdf_processed # Assign the updated original back to final_gdf

                # Ensure geometry column and CRS are set correctly on the final combined DataFrame
                if 'utm_geometry' in final_gdf.columns:
                     output_crs = None
                     if results_list: # Try to get CRS from a processed subset
                         first_subset = results_list[0]
                         if isinstance(first_subset, gpd.GeoDataFrame) and first_subset.crs:
                             output_crs = first_subset.crs
                     if output_crs is None and earthquake_gdf.crs: # Fallback
                         output_crs = earthquake_gdf.crs
                     final_gdf = gpd.GeoDataFrame(final_gdf, geometry='utm_geometry', crs=output_crs)
                     logger.debug(f"Final GeoDataFrame geometry set to 'utm_geometry', CRS: {final_gdf.crs}")
                elif 'geometry' in final_gdf.columns and earthquake_gdf.crs:
                     final_gdf = gpd.GeoDataFrame(final_gdf, geometry='geometry', crs=earthquake_gdf.crs)
                     logger.debug(f"Final GeoDataFrame geometry set to 'geometry', CRS: {final_gdf.crs}")
                else:
                     logger.warning("Could not determine geometry column or CRS for the final output. Returning DataFrame.")
                     # Ensure index matches original if returning pandas DataFrame
                     final_gdf = final_gdf.reindex(earthquake_gdf.index)

            except Exception as concat_e:
                logger.error(f"Error during final concatenation or GDF creation: {concat_e}", exc_info=True)
                logger.warning("Returning original data with potentially partial updates or NAs.")
                final_gdf = eq_gdf_processed # Fallback to original with NAs

    # --- Main Exception Handling ---
    except Exception as main_e:
        logger.error(f"An unexpected error occurred in main function: {main_e}", exc_info=True)
        # Assign the initial copy if a major error occurred before final_gdf was potentially set
        if final_gdf is None:
             final_gdf = earthquake_gdf.copy() # Use original GDF copy
             # Ensure NA columns exist if error happened early
             for col in OUTPUT_COLS:
                 if col not in final_gdf.columns:
                     if col == 'distance_to_plate': final_gdf[col] = np.nan
                     else: final_gdf[col] = pd.NA

    # --- Restore Logger Level and Return ---
    finally:
        logger.setLevel(original_level)
        logger.debug(f"Restored logger level to {original_level}")

    # --- Final Return ---
    if final_gdf is None:
        logger.error("Critical error: final_gdf is None after processing. Returning original data.")
        # Create a fresh copy with NAs if somehow final_gdf is still None
        final_gdf = earthquake_gdf.copy()
        for col in OUTPUT_COLS:
            if col == 'distance_to_plate': final_gdf[col] = np.nan
            else: final_gdf[col] = pd.NA

    logger.info(f"--- Finished {func_name} ---")
    return final_gdf

# --- Example Usage Placeholder ---
# if __name__ == '__main__':
#     # Configure logging for testing
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')
#     logger.info("Starting example usage...")
#     # Placeholder for loading data
#     # print("Example usage placeholder...")
#     # earthquake_gdf = ... # Load earthquake_gdf (ensure 'utm_geometry', 'utm_epsg')
#     # plate_gdf = ... # Load plate_gdf (ensure 'geometry', 'strnum', 'platecode', 'geogdesc', 'boundary_t')
#     # print("Data loaded (placeholder).")
#     # print(f"Earthquake GDF info:\n{earthquake_gdf.info()}")
#     # print(f"Plate GDF info:\n{plate_gdf.info()}")
#
#     # Call the function with parallel processing
#     # eq_with_distances = calculate_distance_to_plate(earthquake_gdf, plate_gdf, log_level='INFO', max_workers=4)
#
#     # print("Processing complete.")
#     # print(eq_with_distances.head())
#     # print(f"Total earthquakes processed: {len(eq_with_distances)}")
#     # print(f"Earthquakes with distance calculated: {eq_with_distances['distance_to_plate'].notna().sum()}")
