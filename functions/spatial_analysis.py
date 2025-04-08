import geopandas as gpd
import modin.pandas as pd
from shapely.geometry import Point, base, LineString # Added LineString
from tqdm import tqdm
import logging
import numpy as np
# Set up basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s') # Changed level to DEBUG

def calculate_distance_to_nearest_line(points_gdf, lines_gdf, target_crs="EPSG:4087"):
    """
    Calculates the distance from each point in points_gdf to the nearest line
    in lines_gdf.

    Args:
        points_gdf (gpd.GeoDataFrame): GeoDataFrame containing Point geometries.
        lines_gdf (gpd.GeoDataFrame): GeoDataFrame containing LineString geometries.
        target_crs (str, optional): The CRS to project data to for accurate
                                     distance calculation. Defaults to "EPSG:4087".

    Returns:
        gpd.GeoDataFrame: The input points_gdf with two new columns:
                          'nearest_line_id': Index of the nearest line in the
                                             (filtered and re-indexed) lines_gdf.
                          'distance_to_line': Distance to the nearest line in meters
                                              (based on target_crs).
                          Returns the original DataFrame with NA columns if errors occur.
    """
    if points_gdf.empty or lines_gdf.empty:
        logging.warning("Input GeoDataFrame(s) are empty. Returning original points GDF.")
        points_gdf['nearest_line_id'] = pd.NA
        points_gdf['distance_to_line'] = pd.NA
        return points_gdf

    # --- Preprocessing ---
    logging.info(f"Original points CRS: {points_gdf.crs}, Original lines CRS: {lines_gdf.crs}")
    if points_gdf.crs != target_crs:
        logging.info(f"Projecting points data to {target_crs}...")
        points_gdf = points_gdf.to_crs(target_crs)
    if lines_gdf.crs != target_crs:
        logging.info(f"Projecting lines data to {target_crs}...")
        lines_gdf = lines_gdf.to_crs(target_crs)
    logging.info("Projection complete (if needed).")

    # Filter invalid/null geometries
    logging.info("Filtering invalid/null geometries...")
    initial_points = len(points_gdf)
    initial_lines = len(lines_gdf)

    points_gdf_filtered = points_gdf[points_gdf.geometry.notnull() & points_gdf.is_valid].copy()
    lines_gdf_filtered = lines_gdf[lines_gdf.geometry.notnull() & lines_gdf.is_valid].copy()

    logging.info(f"Filtered points: {initial_points} -> {len(points_gdf_filtered)}")
    logging.info(f"Filtered lines: {initial_lines} -> {len(lines_gdf_filtered)}")

    if points_gdf_filtered.empty or lines_gdf_filtered.empty:
        logging.error("One or both GeoDataFrames are empty after filtering. Cannot proceed.")
        points_gdf['nearest_line_id'] = pd.NA
        points_gdf['distance_to_line'] = pd.NA
        return points_gdf # Return original with NA columns

    # IMPORTANT: Reset lines index after filtering
    # Store original index if needed later, though the function returns the reset index
    # lines_gdf_filtered['original_index'] = lines_gdf_filtered.index
    lines_gdf_filtered = lines_gdf_filtered.reset_index(drop=True)
    logging.info("Lines GeoDataFrame index reset.")

    # Build spatial index
    logging.info("Building spatial index for lines...")
    lines_sindex = lines_gdf_filtered.sindex
    logging.info("Spatial index built.")
    if len(lines_gdf_filtered) > 0: # Add check to prevent index error if empty
        logging.debug(f"Geometry at index 0 of filtered/reset lines: {lines_gdf_filtered.geometry.iloc[0].wkt}") # DEBUG LOG ADDED
    else:
        logging.debug("Filtered lines GeoDataFrame is empty after reset.")

    # --- Define Inner Function ---
    def find_nearest(point_geom, lines_data, sindex):
        if not isinstance(point_geom, Point):
            return None, None
        try:
            # Get candidate indices from spatial index (limit check to e.g., 10)
            # Note: sindex.nearest with return_all=True might still be limited by implementation
            # Consider sindex.query(point_geom.buffer(some_distance)) if this fails.
            candidate_indices = list(sindex.nearest(point_geom, return_distance=False, return_all=True))

            if not candidate_indices:
                logging.warning(f"No candidate geometries found via sindex for point: {point_geom.wkt}")
                return None, None

            min_dist = float('inf')
            best_match_idx = -1 # Use -1 to indicate no valid match found yet

            # Limit the number of candidates to check for performance
            candidates_to_check = candidate_indices[:10] # Check up to the first 10 candidates
            logging.debug(f"Point: {point_geom.wkt}, Checking candidates: {candidates_to_check}")

            for idx in candidates_to_check:
                # Ensure index is a valid integer
                try:
                    candidate_idx = int(idx)
                except (ValueError, TypeError):
                    logging.warning(f"Skipping invalid candidate index {idx} for point {point_geom.wkt}")
                    continue

                # Check bounds
                if candidate_idx < 0 or candidate_idx >= len(lines_data):
                    logging.warning(f"Skipping out-of-bounds candidate index {candidate_idx} for point {point_geom.wkt}")
                    continue

                # Get candidate geometry robustly (handling potential Series return)
                try:
                    geom_iloc_result = lines_data.geometry.iloc[candidate_idx]
                    candidate_geom = None
                    if isinstance(geom_iloc_result, gpd.GeoSeries):
                        if len(geom_iloc_result) > 0:
                            candidate_geom = geom_iloc_result.iloc[0]
                    elif isinstance(geom_iloc_result, base.BaseGeometry):
                        candidate_geom = geom_iloc_result

                    if not isinstance(candidate_geom, base.BaseGeometry):
                        logging.warning(f"Skipping invalid geometry type {type(candidate_geom)} at index {candidate_idx} for point {point_geom.wkt}")
                        continue

                    # Calculate exact distance
                    dist = point_geom.distance(candidate_geom)

                    # Update minimum distance and best match index
                    if dist < min_dist:
                        min_dist = dist
                        best_match_idx = candidate_idx

                except Exception as inner_e:
                    logging.error(f"Error processing candidate index {candidate_idx} for point {point_geom.wkt}: {inner_e}", exc_info=False)
                    continue # Skip this candidate

            # Return the best match found
            if best_match_idx != -1:
                strnum = lines_data.iloc[best_match_idx]['strnum'] if 'strnum' in lines_data.columns else None
                logging.debug(f"Point: {point_geom.wkt}, Best match index: {best_match_idx}, Min distance: {min_dist}, strnum: {strnum}")
                return best_match_idx, min_dist, strnum
            else:
                logging.warning(f"Could not find a valid nearest line among candidates for point: {point_geom.wkt}")
                return None, None, None

        except Exception as e:
            logging.error(f"Error processing point {point_geom.wkt}: {e}", exc_info=False) # Keep top-level error catch
            return None, None, None

    # --- Apply Function ---
    logging.info("Applying distance calculation function...")
    # Apply to the filtered points, using the filtered+reset lines GDF and its sindex
    results = points_gdf_filtered.geometry.apply(
        lambda geom: find_nearest(geom, lines_gdf_filtered, lines_sindex)
    )
    logging.info("Distance calculation complete.")

    # --- Process Results ---
    logging.info("Processing results...")
    # Create temporary DataFrame from results with the index of the filtered points
    results_df = pd.DataFrame(results.tolist(), index=points_gdf_filtered.index, columns=['nearest_line_id', 'distance_to_line', 'strnum'])

    # Join results back to the *original* points_gdf based on index
    # This handles cases where some points were filtered out
    output_gdf = points_gdf.join(results_df)

    # Fill NaN for points that were filtered out or had errors
    output_gdf['nearest_line_id'] = output_gdf['nearest_line_id'].astype(pd.Int64Dtype())  # Allow NA for integer ID
    output_gdf['distance_to_line'] = output_gdf['distance_to_line'].astype(float)  # Ensure float type
    output_gdf['strnum'] = output_gdf['strnum'].astype(str)  # Ensure string type

    logging.info("Results successfully merged back to the original points GeoDataFrame.")

    return output_gdf

# Example Usage (can be commented out or removed)
if __name__ == '__main__':
    # Create dummy data for testing
    points = gpd.GeoDataFrame({
        'id': [1, 2, 3, 4],
        'geometry': [Point(1, 1), Point(3, 3), Point(5, 1), Point(-1,-1)] # Added an invalid point case implicitly if CRS is geographic
    }, crs="EPSG:4326")

    lines = gpd.GeoDataFrame({
        'line_id': ['A', 'B', 'C'],
        'geometry': [LineString([(0, 0), (2, 2)]), LineString([(4, 0), (4, 2)]), None] # Added a None geometry
    }, crs="EPSG:4326")

    # Add an invalid geometry explicitly
    # from shapely.geometry import Polygon
    # invalid_point = gpd.GeoDataFrame({'id': [5], 'geometry': [Polygon([(0,0),(1,1),(1,0)])]}, crs="EPSG:4326") # Polygon instead of Point
    # points = pd.concat([points, invalid_point], ignore_index=True)


    logging.info("--- Running Example Usage ---")
    points_with_distance = calculate_distance_to_nearest_line(points.copy(), lines.copy(), target_crs="EPSG:3857") # Use common projected CRS for example

    print("\n--- Results ---")
    print(points_with_distance)
    logging.info("--- Example Usage Finished ---")
