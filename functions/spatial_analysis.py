import geopandas as gpd
import pandas as pd
import numpy as np # Import numpy
import re # Import regex module
import warnings # To suppress warnings if needed, or manage them
import traceback # For detailed error printing

# Note: shapely.ops.nearest_points is not explicitly needed if using sjoin_nearest

DEFAULT_CRS = "EPSG:4326" # WGS84, common for lat/lon data

def calculate_distance_to_plate(earthquake_gdf, plates_gdf):
    """
    Calculates the distance from each earthquake point to the nearest tectonic plate boundary
    using appropriate UTM projections for accurate measurements. Assumes input CRS is EPSG:4326 if not set.

    Args:
        earthquake_gdf (gpd.GeoDataFrame): GeoDataFrame containing earthquake data with points.
                                           Must include a 'geometry' column and a 'utm_epsg'
                                           column indicating the EPSG code (e.g., "EPSG:32610" or 32610)
                                           for the correct UTM zone of each point.
        plates_gdf (gpd.GeoDataFrame): GeoDataFrame containing tectonic plate boundaries
                                       as LineStrings. Must include a 'geometry' column
                                       and a 'strnum' column identifying each plate
                                       boundary segment.

    Returns:
        gpd.GeoDataFrame: The input earthquake_gdf with two new columns added:
                          'distance_to_plate' (distance in meters to the nearest plate) and
                          'closest_plate_strnum' (the 'strnum' of that nearest plate).
                          Returns the original DataFrame with NA values in the new columns
                          if inputs are invalid or processing fails for all zones.
    """
    func_name = "calculate_distance_to_plate"
    print(f"--- Starting {func_name} ---")

    # --- Input Validation ---
    if not isinstance(earthquake_gdf, gpd.GeoDataFrame):
        print(f"[{func_name}] Error: earthquake_gdf must be a GeoDataFrame.")
        return earthquake_gdf
    if not isinstance(plates_gdf, gpd.GeoDataFrame):
        print(f"[{func_name}] Error: plates_gdf must be a GeoDataFrame.")
        return earthquake_gdf

    required_eq_cols = ['geometry', 'utm_epsg']
    required_plate_cols = ['geometry', 'strnum']

    if not all(col in earthquake_gdf.columns for col in required_eq_cols):
        print(f"[{func_name}] Error: earthquake_gdf must contain columns: {required_eq_cols}")
        return earthquake_gdf
    if not all(col in plates_gdf.columns for col in required_plate_cols):
        print(f"[{func_name}] Error: plates_gdf must contain columns: {required_plate_cols}")
        return earthquake_gdf

    if earthquake_gdf.empty:
        print(f"[{func_name}] Warning: earthquake_gdf is empty. Returning.")
        earthquake_gdf['distance_to_plate'] = np.nan
        earthquake_gdf['closest_plate_strnum'] = pd.NA
        return earthquake_gdf

    if plates_gdf.empty:
        print(f"[{func_name}] Warning: plates_gdf is empty. Cannot calculate distances. Returning.")
        earthquake_gdf['distance_to_plate'] = np.nan
        earthquake_gdf['closest_plate_strnum'] = pd.NA
        return earthquake_gdf

    # Check geometry types more robustly
    if not earthquake_gdf.geometry.geom_type.isin(['Point']).all():
         print(f"[{func_name}] Warning: Not all geometries in earthquake_gdf are Points.")
    # Check for invalid geometries early
    invalid_eq_geoms = earthquake_gdf[~earthquake_gdf.geometry.is_valid]
    if not invalid_eq_geoms.empty:
        print(f"[{func_name}] Warning: Found {len(invalid_eq_geoms)} invalid geometries in input earthquake_gdf.")

    if not plates_gdf.geometry.geom_type.str.contains('LineString').all():
         print(f"[{func_name}] Warning: Not all geometries in plates_gdf are LineStrings.")
    invalid_plate_geoms = plates_gdf[~plates_gdf.geometry.is_valid]
    if not invalid_plate_geoms.empty:
        print(f"[{func_name}] Warning: Found {len(invalid_plate_geoms)} invalid geometries in input plates_gdf.")


    # --- Initialization & CRS Handling ---
    eq_gdf = earthquake_gdf.copy()
    pl_gdf = plates_gdf.copy()

    # Check and set CRS if missing, assuming WGS84 (EPSG:4326)
    if eq_gdf.crs is None:
        print(f"[{func_name}] Warning: earthquake_gdf has no CRS set. Assuming {DEFAULT_CRS}.")
        try:
            eq_gdf = eq_gdf.set_crs(DEFAULT_CRS, allow_override=True) # Use set_crs correctly
        except Exception as e:
            print(f"[{func_name}] Error setting default CRS for earthquakes: {e}. Aborting.")
            return earthquake_gdf # Return original if CRS setting fails
    else:
        print(f"[{func_name}] Input earthquake CRS: {eq_gdf.crs}")

    if pl_gdf.crs is None:
        print(f"[{func_name}] Warning: plates_gdf has no CRS set. Assuming {DEFAULT_CRS}.")
        try:
            pl_gdf = pl_gdf.set_crs(DEFAULT_CRS, allow_override=True)
        except Exception as e:
            print(f"[{func_name}] Error setting default CRS for plates: {e}. Aborting.")
            # Still return eq_gdf, but without distances
            eq_gdf['distance_to_plate'] = np.nan
            eq_gdf['closest_plate_strnum'] = pd.NA
            return eq_gdf
    else:
        print(f"[{func_name}] Input plates CRS: {pl_gdf.crs}")


    # Initialize new columns
    eq_gdf['distance_to_plate'] = np.nan
    eq_gdf['closest_plate_strnum'] = pd.NA
    eq_gdf['closest_plate_strnum'] = eq_gdf['closest_plate_strnum'].astype('object')


    # --- Processing by UTM Zone ---
    unique_epsgs_raw = eq_gdf['utm_epsg'].dropna().unique()
    print(f"\n[{func_name}] Found {len(unique_epsgs_raw)} unique raw UTM EPSG values to process.")

    if len(unique_epsgs_raw) == 0:
        print(f"[{func_name}] Warning: No valid 'utm_epsg' values found in earthquake_gdf. Cannot calculate distances.")
        return eq_gdf

    processed_epsg_ints = set()

    for epsg_code_raw in unique_epsgs_raw:
        epsg_int = None
        target_crs_obj = None
        target_crs_str = None
        try:
            # Attempt to extract the integer part of the EPSG code
            if isinstance(epsg_code_raw, str):
                match = re.search(r'\d+$', epsg_code_raw)
                if match: epsg_int = int(match.group())
                else:
                    try: epsg_int = int(epsg_code_raw)
                    except ValueError: raise ValueError(f"Could not extract number from string: {epsg_code_raw}")
            elif isinstance(epsg_code_raw, (int, float)) and np.isfinite(epsg_code_raw):
                 if float(epsg_code_raw).is_integer(): epsg_int = int(epsg_code_raw)
                 else: raise ValueError(f"Non-integer numeric EPSG code: {epsg_code_raw}")
            else:
                 if pd.isna(epsg_code_raw): print(f"\n[{func_name}] Skipping NA EPSG code."); continue
                 else: raise TypeError(f"Unsupported EPSG code type: {type(epsg_code_raw)} for value {epsg_code_raw}")

            if epsg_int is None: raise ValueError("EPSG integer code could not be determined.")

            if epsg_int in processed_epsg_ints: continue

            # Validate the target CRS before proceeding
            try:
                # Use pyproj or geopandas internal mechanism to validate CRS
                target_crs_str = f"EPSG:{epsg_int}"
                target_crs_obj = gpd.GeoDataFrame(geometry=[]).set_crs(target_crs_str, allow_override=True).crs
                print(f"\n[{func_name}] Processing zone with {target_crs_str} (from raw value: '{epsg_code_raw}')...")
            except Exception as crs_e:
                print(f"\n[{func_name}] Skipping invalid target CRS: {target_crs_str} (from raw value '{epsg_code_raw}'). Reason: {crs_e}")
                continue

        except (ValueError, TypeError) as e:
            print(f"\n[{func_name}] Skipping invalid EPSG value: '{epsg_code_raw}'. Reason: {e}")
            continue

        # --- Filter, Reproject, Calculate for this specific EPSG integer ---
        zone_mask = eq_gdf['utm_epsg'] == epsg_code_raw
        eq_subset = eq_gdf.loc[zone_mask].copy()

        if eq_subset.empty: print(f"  [{func_name}] No earthquakes found for raw value '{epsg_code_raw}'. Skipping."); continue

        print(f"  [{func_name}] Found {len(eq_subset)} earthquakes for raw value '{epsg_code_raw}' ({target_crs_str}).")

        try:
            # --- Reprojection ---
            print(f"  [{func_name}] Reprojecting {len(eq_subset)} earthquakes from {eq_subset.crs} to {target_crs_str}...")
            if not eq_subset.crs.equals(target_crs_obj): # Use equals for robust comparison
                 eq_subset_proj = eq_subset.to_crs(target_crs_obj)
                 print(f"    Earthquake subset reprojected. New CRS: {eq_subset_proj.crs}")
            else:
                 eq_subset_proj = eq_subset # Already in correct CRS
                 print(f"    Earthquake subset already in target CRS ({eq_subset_proj.crs}).")

            print(f"  [{func_name}] Reprojecting {len(pl_gdf)} plate boundaries from {pl_gdf.crs} to {target_crs_str}...")
            if not pl_gdf.crs.equals(target_crs_obj):
                plates_proj = pl_gdf.to_crs(target_crs_obj)
                print(f"    Plate boundaries reprojected. New CRS: {plates_proj.crs}")
            else:
                plates_proj = pl_gdf.copy() # Still copy if already in correct CRS
                print(f"    Plate boundaries already in target CRS ({plates_proj.crs}).")

            # --- Geometry Validity Check Post-Reprojection ---
            invalid_eq_subset = eq_subset_proj[~eq_subset_proj.geometry.is_valid]
            if not invalid_eq_subset.empty:
                print(f"  [{func_name}] Warning: Found {len(invalid_eq_subset)} invalid geometries in projected earthquake subset for {target_crs_str}.")
                # Optionally filter them out: eq_subset_proj = eq_subset_proj[eq_subset_proj.geometry.is_valid]

            invalid_plates_proj = plates_proj[~plates_proj.geometry.is_valid]
            if not invalid_plates_proj.empty:
                print(f"  [{func_name}] Warning: Found {len(invalid_plates_proj)} invalid geometries in projected plates for {target_crs_str}.")
                # Optionally filter them out: plates_proj = plates_proj[plates_proj.geometry.is_valid]

            if eq_subset_proj.empty or plates_proj.empty:
                 print(f"  [{func_name}] Skipping join for {target_crs_str} due to empty or invalid projected geometries.")
                 continue


            # --- Distance Calculation using sjoin_nearest ---
            print(f"  [{func_name}] Calculating nearest plates using sjoin_nearest for {len(eq_subset_proj)} earthquakes and {len(plates_proj)} plates...")
            if eq_subset_proj.index.name is None: eq_subset_proj.index.name = 'original_eq_index'
            if plates_proj.index.name is None: plates_proj.index.name = 'original_plate_index'

            # Suppress potential UserWarning about CRS mismatch if confident they are the same
            with warnings.catch_warnings():
                 warnings.filterwarnings(
                     "ignore",
                     message="CRS mismatch between the CRS of left geometries and the CRS of right geometries.",
                     category=UserWarning
                 )
                 joined_gdf = gpd.sjoin_nearest(
                     eq_subset_proj,
                     plates_proj,
                     how='left',
                     distance_col="distance_temp",
                     max_distance=None
                 )

            print(f"    sjoin_nearest completed. Result has {len(joined_gdf)} rows.")
            valid_distances = joined_gdf['distance_temp'].dropna()
            print(f"    Found {len(valid_distances)} non-NA distances.")
            if not valid_distances.empty:
                 print(f"    Distance range: {valid_distances.min():.2f} to {valid_distances.max():.2f} meters.")
            else:
                 print(f"    No valid distances calculated by sjoin_nearest.")


            # --- Post-processing Join Results ---
            joined_gdf = joined_gdf.sort_values(by="distance_temp")
            joined_gdf = joined_gdf[~joined_gdf.index.duplicated(keep='first')]
            print(f"    Dropped duplicates, {len(joined_gdf)} rows remaining.")

            # --- Update the main DataFrame ---
            update_indices = joined_gdf.index
            distances = joined_gdf['distance_temp']

            valid_join_mask = joined_gdf['index_right'].notna()
            nearest_plate_indices_float = joined_gdf.loc[valid_join_mask, 'index_right']
            closest_strnums = pd.Series(index=update_indices, dtype='object') # Initialize with NAs

            print(f"    Attempting to update {len(update_indices)} rows in original DataFrame.")
            print(f"    Indices to update: {update_indices.tolist()[:10]}...") # Show sample indices
            print(f"    Number of valid joins (found nearest plate): {valid_join_mask.sum()}")


            if not nearest_plate_indices_float.empty:
                nearest_plate_indices_int = nearest_plate_indices_float.astype(int)
                # Check if indices exist in plates_proj before accessing
                valid_plate_indices = plates_proj.index.intersection(nearest_plate_indices_int)
                print(f"    Nearest plate indices found in join: {nearest_plate_indices_int.tolist()[:10]}...")
                print(f"    Valid plate indices present in projected plates: {valid_plate_indices.tolist()[:10]}...")

                if not valid_plate_indices.empty:
                     strnums_subset = plates_proj.loc[valid_plate_indices, 'strnum']
                     # Map nearest_plate_indices_int back to the update_indices where the join was valid
                     # Create a mapping from the plate index (in plates_proj) to the earthquake index (in eq_subset_proj/joined_gdf)
                     index_map = pd.Series(joined_gdf.loc[valid_join_mask].index, index=nearest_plate_indices_int)
                     # Use this map to find the correct earthquake indices corresponding to the valid plate indices
                     aligned_indices = valid_plate_indices.map(index_map)
                     # Filter out any NAs that might result from the map if indices don't align perfectly (shouldn't happen here)
                     aligned_indices = aligned_indices.dropna()

                     print(f"    Indices in original eq_gdf to update strnum for: {aligned_indices.tolist()[:10]}...")
                     print(f"    Corresponding strnums: {strnums_subset.tolist()[:10]}...")

                     # Assign strnums using the aligned earthquake indices
                     closest_strnums.loc[aligned_indices] = strnums_subset.values


            # Assign values back to the main eq_gdf using the correct indices
            eq_gdf.loc[update_indices, 'distance_to_plate'] = distances
            eq_gdf.loc[update_indices, 'closest_plate_strnum'] = closest_strnums

            # Verify update
            updated_count = eq_gdf.loc[update_indices, 'distance_to_plate'].notna().sum()
            print(f"  [{func_name}] Successfully updated distance for {updated_count} earthquakes for {target_crs_str}.")
            processed_epsg_ints.add(epsg_int) # Mark this integer code as processed

        except Exception as e:
            print(f"  [{func_name}] Error processing {target_crs_str} (from raw value '{epsg_code_raw}'): {e}")
            print(traceback.format_exc())
            print(f"  [{func_name}] Skipping distance calculation for earthquakes associated with raw value '{epsg_code_raw}'.")
            # Earthquakes in this zone will retain NA values

    print(f"\n--- Finished {func_name} ---")
    return eq_gdf

# Example Usage (requires having earthquake_gdf and plates_gdf loaded)
# if __name__ == '__main__':
#     # Load your data here, e.g., from files
#     # earthquake_gdf = gpd.read_file(...) # Ensure it has geometry and utm_epsg
#     # plates_gdf = gpd.read_file(...)   # Ensure it has geometry and strnum
#
#     # Optional: Explicitly set CRS if you know it and it might be missing
#     # if earthquake_gdf.crs is None: earthquake_gdf = earthquake_gdf.set_crs("EPSG:4326")
#     # if plates_gdf.crs is None: plates_gdf = plates_gdf.set_crs("EPSG:4326")
#
#     # Call the function
#     # eq_with_distances = calculate_distance_to_plate(earthquake_gdf, plates_gdf)
#
#     # print(eq_with_distances[['geometry', 'utm_epsg', 'distance_to_plate', 'closest_plate_strnum']].head())
#     # print(f"Number of earthquakes with calculated distance: {eq_with_distances['distance_to_plate'].notna().sum()}")
