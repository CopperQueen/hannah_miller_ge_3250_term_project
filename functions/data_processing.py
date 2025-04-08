import pandas as pd 

"""
Functions for processing and cleaning earthquake and plate data.
(e.g., converting to GeoDataFrames, filtering, aligning CRS).
"""

# --- Modified Function ---
def get_utm_info_and_reproject(row, source_crs):
    """
    Calculates the UTM zone, EPSG code, and reprojects the geometry
    for a given row. Assumes the geometry is in a geographic CRS.
    Returns a tuple: (utm_zone_str, utm_epsg_str, utm_geometry).
    """
    # Default return values in case of issues
    utm_zone_str = None
    utm_epsg_str = None
    utm_geometry = None

    # Ensure it's a Point geometry and not None
    if not isinstance(row.geometry, Point) or pd.isna(row.geometry):
        return utm_zone_str, utm_epsg_str, utm_geometry # Return None tuple

    # Get longitude and latitude
    lon = row.geometry.x
    lat = row.geometry.y

    # Handle potential invalid coordinates outside typical lat/lon ranges if necessary
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
         logging.warning(f"Coordinates ({lon}, {lat}) outside standard range at index {row.name}. Skipping UTM calculation and projection.")
         return utm_zone_str, utm_epsg_str, utm_geometry # Return None tuple

    try:
        # Calculate UTM zone number
        zone_number = math.floor(((lon + 180) / 6) % 60) + 1

        # Determine hemisphere (North or South)
        hemisphere = 'N' if lat >= 0 else 'S'

        # Construct UTM zone string
        utm_zone_str = f"{int(zone_number)}{hemisphere}" # Ensure zone_number is int

        # Determine EPSG code base (WGS 84 UTM)
        epsg_base = 32600 if lat >= 0 else 32700
        utm_epsg = epsg_base + int(zone_number)
        utm_epsg_str = f'EPSG:{utm_epsg}'

        # --- Reprojection Step ---
        # Create a temporary GeoSeries with the single geometry and original CRS
        temp_gs = gpd.GeoSeries([row.geometry], crs=source_crs)
        # Reproject to the target UTM CRS
        reprojected_gs = temp_gs.to_crs(utm_epsg_str) # Use the calculated EPSG string
        # Get the reprojected Shapely geometry object
        utm_geometry = reprojected_gs.iloc[0]

    except Exception as e:
        # Log error if calculation or reprojection fails
        logging.error(f"Failed UTM calculation or reprojection at index {row.name} for geom {row.geometry} to {utm_epsg_str}. Error: {e}")
        # Return None tuple in case of error
        return None, None, None

    return utm_zone_str, utm_epsg_str, utm_geometry