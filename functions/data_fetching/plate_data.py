import os
import requests
import geopandas as gpd
import pandas as pd # Added for pd.concat
import zipfile
import io
import time    # For testing block
import logging # For logging messages
import glob    # For finding files to delete
import pandas as pd # Added for pd.concat

# --- Constants ---
# Define the path for storing plate boundary data relative to the project root
PLATE_DATA_DIR = os.path.join("resources", "plate_boundaries")
# Source: https://data.humdata.org/dataset/tectonic-plate
# Paper: https://www-udc.ig.utexas.edu/external/plates/data/plate_boundaries/204_plate_pb.pdf
# Assuming the shapefile name inside the zip, might need adjustment after inspection/testing
# Define the base names of the shapefiles expected within the zip
PLATE_FILENAMES = ["ridge", "transform", "trench"]
PLATE_DATA_URL = "https://data.humdata.org/dataset/f2ea5d82-1b04-4d36-8e94-a73a2eed099d/resource/1bd63193-68da-4c86-a217-c0c8b2c3b2a6/download/plates_plateboundary_arcgis.zip" # New HDX URL
COMBINED_PLATE_FILENAME = "combined_plate_boundaries.shp"

# --- Plate Boundary Function ---
def load_plate_boundaries(target_crs: str = "EPSG:4326") -> gpd.GeoDataFrame | None:
    """
    Loads tectonic plate boundary data from a shapefile.

    Checks if the required shapefiles (ridge.shp, transform.shp, trench.shp) exist in
    `resources/plate_boundaries/`. If not, downloads and extracts the zip file
    from the Humanitarian Data Exchange (HDX). Then loads the shapefile into a GeoDataFrame.

    Data Source: https://data.humdata.org/dataset/tectonic-plate

    Args:
        target_crs (str): The target Coordinate Reference System for the output GeoDataFrame.
                          Defaults to "EPSG:4326".

    Returns:
        A GeoDataFrame containing the plate boundary data projected to the target_crs,
        or None if fetching/loading fails.
    """
    os.makedirs(PLATE_DATA_DIR, exist_ok=True) # Ensure directory exists
    combined_shp_path = os.path.join(PLATE_DATA_DIR, COMBINED_PLATE_FILENAME)

    # --- Check 1: Does the combined file already exist? ---
    if os.path.exists(combined_shp_path):
        logging.info(f"Found existing combined plate boundary file: {combined_shp_path}")
        try:
            combined_gdf = gpd.read_file(combined_shp_path)
            logging.info(f"Successfully loaded {len(combined_gdf)} features from combined file. CRS: {combined_gdf.crs}")

            # --- Reproject to Final Target CRS (if needed) ---
            if combined_gdf.crs is None:
                 logging.warning("Combined plate boundary GeoDataFrame has no CRS defined. Cannot reproject.")
            elif combined_gdf.crs != target_crs:
                logging.info(f"Reprojecting combined plate boundary data from {combined_gdf.crs} to {target_crs}...")
                try:
                    combined_gdf = combined_gdf.to_crs(target_crs)
                    logging.info(f"Reprojection successful. Final CRS: {combined_gdf.crs}")
                except Exception as e:
                    logging.error(f"Error during final reprojection to {target_crs}: {e}")
                    return None # Fail if final projection fails
            else:
                 logging.info(f"Combined plate boundary data is already in target CRS ({target_crs}).")

            return combined_gdf # Return the loaded and potentially reprojected data

        except Exception as e:
            logging.error(f"Error loading existing combined shapefile {combined_shp_path}: {e}. Proceeding to download/recreate.")
            # If loading the existing combined file fails, proceed as if it wasn't there

    # --- Check 2: Do the individual source files exist? ---
    # Define paths for all target shapefiles first
    target_shp_paths = {name: os.path.join(PLATE_DATA_DIR, f"{name}.shp") for name in PLATE_FILENAMES}
    # Check if all target shapefiles exist
    all_files_exist = all(os.path.exists(p) for p in target_shp_paths.values())

    if not all_files_exist:
        # Determine which files are missing for a more informative message
        missing_files = [os.path.basename(p) for name, p in target_shp_paths.items() if not os.path.exists(p)]
        logging.info(f"One or more plate boundary shapefiles not found: {', '.join(missing_files)}")
        logging.info(f"Downloading from {PLATE_DATA_URL}...")
        try:
            # Add standard User-Agent and Referer headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
                'Referer': 'https://data.humdata.org/dataset/tectonic-plate' # Updated Referer for HDX
            }
            response = requests.get(PLATE_DATA_URL, stream=True, timeout=60, headers=headers)
            response.raise_for_status() # Check for download errors

            # Use BytesIO to handle the zip file in memory
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                logging.info(f"Extracting contents to {PLATE_DATA_DIR}...")
                required_extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg'] # Common shapefile components
                extracted_count = 0
                files_extracted_this_run = []

                # Iterate through desired base names and extract their components
                for base_name in PLATE_FILENAMES:
                    logging.info(f"  Looking for components of {base_name}.shp...")
                    found_shp_for_base = False
                    for member in z.namelist():
                        if member.endswith('/'): continue # Skip directories

                        member_filename = os.path.basename(member)
                        member_base, member_ext = os.path.splitext(member_filename)

                        if member_base.lower() == base_name.lower() and member_ext.lower() in required_extensions:
                            target_file_path = os.path.join(PLATE_DATA_DIR, member_filename)
                            # Avoid re-extracting if already done (e.g., if zip contains duplicates)
                            if target_file_path not in files_extracted_this_run:
                                try:
                                    with z.open(member) as source, open(target_file_path, "wb") as target:
                                        target.write(source.read())
                                    logging.debug(f"    - Extracted {member_filename}") # Use debug for individual file extraction
                                    files_extracted_this_run.append(target_file_path)
                                    extracted_count += 1
                                    if member_ext.lower() == '.shp':
                                        found_shp_for_base = True
                                except Exception as extract_err:
                                     logging.error(f"    - Error extracting {member}: {extract_err}")

                    if not found_shp_for_base:
                         logging.warning(f"  Warning: Could not find or extract required .shp file for '{base_name}'.")


            # Verify again if all target .shp files exist after extraction
            all_files_exist = all(os.path.exists(p) for p in target_shp_paths.values())
            if not all_files_exist:
                 missing_files = [os.path.basename(p) for name, p in target_shp_paths.items() if not os.path.exists(p)]
                 logging.error(f"Extraction incomplete. Missing files: {', '.join(missing_files)}")
                 # Optionally list extracted files: print(os.listdir(PLATE_DATA_DIR))
                 return None
            logging.info("Download and extraction successful.")

        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading plate boundary data: {e}")
            return None
        except zipfile.BadZipFile:
            logging.error("Downloaded file is not a valid zip archive.")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during download/extraction: {e}")
            return None
    else:
        # Use the already defined target_shp_paths here
        logging.info(f"Found existing plate boundary shapefiles: {', '.join(os.path.basename(p) for p in target_shp_paths.values())}")

    # Load the individual shapefiles and concatenate
    all_gdfs = []
    logging.info("Loading individual shapefiles...")
    initial_crs = None # Store the CRS of the first loaded file to check consistency
    for name, shp_path in target_shp_paths.items():
        try:
            logging.info(f"  Loading {os.path.basename(shp_path)}...")
            gdf = gpd.read_file(shp_path)
            logging.info(f"    - Loaded {len(gdf)} features. CRS: {gdf.crs}")

            # Store CRS of the first file, check consistency or reproject later ones
            if initial_crs is None:
                initial_crs = gdf.crs
            elif gdf.crs != initial_crs:
                logging.warning(f"    - CRS mismatch ({gdf.crs} != {initial_crs}). Reprojecting to {initial_crs} for concatenation...")
                try:
                    gdf = gdf.to_crs(initial_crs)
                    logging.info(f"    - Reprojected to {initial_crs}")
                except Exception as reproj_err:
                    logging.error(f"    - Error reprojecting {os.path.basename(shp_path)}: {reproj_err}. Skipping this file.")
                    continue # Skip this file if reprojection fails

            # Add a column indicating the boundary type (optional but useful)
            gdf['boundary_type'] = name
            all_gdfs.append(gdf)

        except Exception as e:
            logging.error(f"  Error loading shapefile {os.path.basename(shp_path)}: {e}")
            # Decide if loading should fail entirely if one file fails, or just continue
            # For now, we'll print the error and continue

    if not all_gdfs:
        logging.error("No plate boundary shapefiles could be loaded successfully.")
        return None

    # Concatenate the GeoDataFrames
    try:
        logging.info("Concatenating loaded GeoDataFrames...")
        combined_gdf = pd.concat(all_gdfs, ignore_index=True)
        # Ensure the result is still a GeoDataFrame with the correct CRS
        if not isinstance(combined_gdf, gpd.GeoDataFrame):
             combined_gdf = gpd.GeoDataFrame(combined_gdf, geometry=gpd.GeoSeries(combined_gdf['geometry']), crs=initial_crs)

        logging.info(f"Successfully loaded and combined {len(combined_gdf)} total boundary features.")

        # --- Save combined GeoDataFrame ---
        # combined_shp_path is already defined earlier
        try:
            logging.info(f"Saving combined shapefile to {combined_shp_path}...")
            combined_gdf.to_file(combined_shp_path, driver='ESRI Shapefile')
            logging.info("Combined shapefile saved successfully.")

            # --- Cleanup individual files ---
            logging.info("Cleaning up individual extracted files...")
            files_to_delete = []
            for base_name in PLATE_FILENAMES:
                # Use glob to find all components (e.g., ridge.shp, ridge.shx, ridge.dbf, etc.)
                pattern = os.path.join(PLATE_DATA_DIR, f"{base_name}.*")
                files_to_delete.extend(glob.glob(pattern))

            deleted_count = 0
            for f_path in files_to_delete:
                # Avoid deleting the combined file if it somehow matches the pattern
                if os.path.basename(f_path) != COMBINED_PLATE_FILENAME:
                    try:
                        os.remove(f_path)
                        logging.debug(f"  - Deleted {os.path.basename(f_path)}")
                        deleted_count += 1
                    except OSError as del_err:
                        logging.warning(f"  - Could not delete file {os.path.basename(f_path)}: {del_err}")
            logging.info(f"Cleanup complete. Deleted {deleted_count} individual files.")

        except Exception as save_err:
            logging.error(f"Error saving combined shapefile to {combined_shp_path}: {save_err}")
            # Decide if we should still return the in-memory gdf even if saving failed
            # return None # Option 1: Fail if save fails
            # Option 2: Log error and return gdf anyway (chosen here)

        # --- Reproject to Final Target CRS ---
        if combined_gdf.crs is None:
             logging.warning("Combined plate boundary GeoDataFrame has no CRS defined. Cannot reproject.")
        elif combined_gdf.crs != target_crs:
            logging.info(f"Reprojecting combined plate boundary data from {combined_gdf.crs} to {target_crs}...")
            try:
                combined_gdf = combined_gdf.to_crs(target_crs)
                logging.info(f"Reprojection successful. Final CRS: {combined_gdf.crs}")
            except Exception as e:
                logging.error(f"Error during final reprojection to {target_crs}: {e}")
                # Decide if we should return None or the unprojected data
                return None # Fail if final projection fails
        else:
             logging.info(f"Combined plate boundary data is already in target CRS ({target_crs}).")


        return combined_gdf # Return the newly created, combined, and potentially reprojected dataframe

    except Exception as e:
        logging.error(f"Error during concatenation: {e}")
        return None

# Example usage (optional)
if __name__ == "__main__":
    # Configure logging for basic console output when run as script
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("\n--- Testing Plate Boundary Loading ---")
    start_plate_time = time.time()
    plate_boundaries_gdf = load_plate_boundaries()
    end_plate_time = time.time()
    logging.info(f"Plate loading time: {end_plate_time - start_plate_time:.2f} seconds")

    if plate_boundaries_gdf is not None:
        logging.info(f"Successfully loaded plate boundaries. CRS: {plate_boundaries_gdf.crs}")
        # Log the first few rows of the dataframe for inspection
        logging.info("First 4 rows of the combined GeoDataFrame (selected columns):")
        try:
            # Select columns and get string representation
            df_head_str = plate_boundaries_gdf[['boundary_type', 'platecode', 'geogdesc', 'geometry']].head(4).to_string()
            # Log each line of the string representation
            for line in df_head_str.splitlines():
                logging.info(line)
        except KeyError as e:
             logging.warning(f"Could not log selected columns due to KeyError: {e}. Logging all columns:")
             df_head_str = plate_boundaries_gdf.head(4).to_string()
             # Log each line of the string representation
             for line in df_head_str.splitlines():
                 logging.info(line)
    else:
        logging.error("Failed to load plate boundaries.")