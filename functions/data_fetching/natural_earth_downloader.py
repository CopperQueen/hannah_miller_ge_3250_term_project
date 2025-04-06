import os
import logging
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_natural_earth_boundaries(output_dir='resources/natural_earth_boundaries'):
    """
    Downloads specific Natural Earth boundary datasets (10m Admin 1, 10m Lakes, 50m Countries)
    and saves them as zipped shapefiles to the specified directory.

    Args:
        output_dir (str): The directory where the downloaded zip files will be saved.
                          Defaults to 'resources/natural_earth_boundaries'.
    """
    datasets = {
        '10m_admin_1': {
            'url_template': 'https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip',
            'filename': 'ne_10m_admin_1_states_provinces.zip'
        },
        '10m_lakes': {
            'url_template': 'https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip',
            'filename': 'ne_10m_lakes.zip'
        },
        '50m_countries': {
            'url_template': 'https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip',
            'filename': 'ne_50m_admin_0_countries.zip'
        }
    }

    if not os.path.exists(output_dir):
        logging.info(f"Creating directory: {output_dir}")
        os.makedirs(output_dir)

    for key, info in datasets.items():
        url = info['url_template']
        filename = info['filename']
        local_zip_path = os.path.join(output_dir, filename)

        if os.path.exists(local_zip_path):
            logging.info(f"Dataset '{key}' ({filename}) already exists at {local_zip_path}. Skipping download.")
            continue

        logging.info(f"Downloading '{key}' data from {url} to {local_zip_path}")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            with open(local_zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Successfully downloaded {filename}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading {filename} from {url}: {e}")
            # Optionally remove partially downloaded file
            if os.path.exists(local_zip_path):
                try:
                    os.remove(local_zip_path)
                    logging.info(f"Removed partially downloaded file: {local_zip_path}")
                except OSError as remove_err:
                    logging.error(f"Error removing partially downloaded file {local_zip_path}: {remove_err}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during download of {filename}: {e}", exc_info=True)
            # Handle potential partial file here too if needed


import geopandas as gpd

def load_natural_earth_data(data_dir='resources/natural_earth_boundaries', target_crs="EPSG:4326"):
    """
    Loads the 50m Natural Earth countries and 10m lakes shapefiles from zip files,
    reprojects them to the target CRS if necessary, and returns them as GeoDataFrames.

    Args:
        data_dir (str): Directory containing the Natural Earth zip files.
                        Defaults to 'resources/natural_earth_boundaries'.
        target_crs (str): The target Coordinate Reference System (e.g., "EPSG:4326").
                          Defaults to "EPSG:4326".

    Returns:
        dict: A dictionary containing the loaded GeoDataFrames, like:
              {'countries': countries_gdf, 'lakes': lakes_gdf}.
              Values will be None if loading or reprojection fails for a dataset.
    """
    datasets = {
        'countries': { # Changed from 'states'
            'zip_filename': 'ne_50m_admin_0_countries.zip', # Changed filename
            'layer_name': 'ne_50m_admin_0_countries' # Changed layer name
        },
        'lakes': {
            'zip_filename': 'ne_10m_lakes.zip',
            'layer_name': 'ne_10m_lakes' # Common layer name inside zip
        }
    }
    loaded_data = {'countries': None, 'lakes': None} # Changed key from 'states'

    for key, info in datasets.items():
        zip_path = os.path.join(data_dir, info['zip_filename'])
        layer_name = info['layer_name']
        gdf = None

        if not os.path.exists(zip_path):
            logging.warning(f"Natural Earth zip file not found for '{key}': {zip_path}. Skipping load.")
            continue

        logging.info(f"Loading Natural Earth '{key}' data from {zip_path}...")
        try:
            # Directly read the zip file path - geopandas/pyogrio usually finds the shapefile inside
            zip_uri = f"zip://{zip_path}"
            gdf = gpd.read_file(zip_uri)
            logging.info(f"Successfully loaded {len(gdf)} features for '{key}'. Original CRS: {gdf.crs}")

            # Reproject if necessary
            if gdf.crs != target_crs:
                logging.info(f"Reprojecting '{key}' data from {gdf.crs} to {target_crs}...")
                gdf = gdf.to_crs(target_crs)
                logging.info(f"Reprojection successful for '{key}'. New CRS: {gdf.crs}")
            else:
                logging.info(f"'{key}' data is already in target CRS ({target_crs}).")

            loaded_data[key] = gdf

        except Exception as e:
             logging.error(f"Error loading or processing Natural Earth '{key}' data from {zip_path}: {e}", exc_info=True)
             loaded_data[key] = None # Ensure it's None if loading fails

    return loaded_data


if __name__ == '__main__':
    logging.info("Natural Earth Downloader Module")
    logging.info("This script provides the function 'download_natural_earth_boundaries'.")
    logging.info("Run this script directly to download the default datasets to 'resources/natural_earth_boundaries'.")
    logging.info("\nExample usage in another script:")
    logging.info("from natural_earth_downloader import download_natural_earth_boundaries")
    logging.info("# download_natural_earth_boundaries()") # Downloads to default folder
    logging.info("# download_natural_earth_boundaries(output_dir='my_custom_data_folder')")

    # Execute the download when run as a script
    logging.info("\nAttempting to download Natural Earth boundaries...")
    try:
        download_natural_earth_boundaries()
        logging.info("\nDownload function executed. Check logs and the 'resources/natural_earth_boundaries' folder.")
    except Exception as e:
        logging.error(f"\nError executing download function: {e}")