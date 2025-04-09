"""
Functions for creating interactive (Folium/Plotly) and
static (Matplotlib/Cartopy) maps of earthquake and plate data.
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from datetime import date # For type hinting
import logging

# Configure logging (optional, basic configuration)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def plot_earthquake_plate_map(
    earthquake_gdf: gpd.GeoDataFrame | None,
    plate_gdf: gpd.GeoDataFrame | None,
    ne_land_gdf: gpd.GeoDataFrame | None, # Renamed from ne_states_gdf
    ne_lakes_gdf: gpd.GeoDataFrame | None,
    min_magnitude: float = 1.0,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    target_crs_epsg: str = "EPSG:4326"
) -> None:
    """
    Generates a static map showing earthquakes, plate boundaries, and a Natural Earth basemap.

    Args:
        earthquake_gdf: GeoDataFrame with earthquake data (must include 'mag' and geometry).
        plate_gdf: GeoDataFrame with plate boundary data (must include 'boundary_type' and geometry).
        ne_land_gdf: GeoDataFrame for Natural Earth land boundaries (e.g., countries or states).
        ne_lakes_gdf: GeoDataFrame for Natural Earth lakes basemap.
        min_magnitude: Minimum magnitude used for loading data (used in title). Defaults to 1.0.
        start_date: Start date used for loading data (used in title). Defaults to None.
        end_date: End date used for loading data (used in title). Defaults to None.
        target_crs_epsg: The CRS the data is expected to be in (used in title). Defaults to "EPSG:4326".
    """

    # --- Data Availability Check ---
    can_plot_plates_eq = all(gdf is not None for gdf in [plate_gdf, earthquake_gdf])
    can_plot_ne = all(gdf is not None for gdf in [ne_land_gdf, ne_lakes_gdf])

    if not can_plot_plates_eq:
        logging.error("Cannot generate plot as Plate Boundary or Earthquake data is missing.") # Changed to error level
        return

    logging.info("\nGenerating plot...")
    fig, ax = plt.subplots(1, 1, figsize=(20, 15))

    # --- 1. Plot Natural Earth Basemap (if available) ---
    if can_plot_ne:
        logging.info("Plotting Natural Earth layers...")
        # Plot the land boundaries (countries or states, depending on input)
        logging.info("Plotting land boundaries...")
        ne_land_gdf.plot(ax=ax, color='lightgray', edgecolor='white', linewidth=0.5, zorder=1)

        # Filter and plot lakes (top 100 by area)
        if ne_lakes_gdf is not None and not ne_lakes_gdf.empty:
            logging.info("Filtering lakes to top 100 by area (using original CRS area)...")
            # Ensure CRS is set
            if ne_lakes_gdf.crs is None:
                 logging.info(f"Lake GeoDataFrame CRS is not set. Assuming {target_crs_epsg} based on loading parameters.") # Changed to info level
                 ne_lakes_gdf.set_crs(target_crs_epsg, inplace=True, allow_override=True) # Assume input CRS if none

            # Calculate area directly (may be inaccurate depending on CRS)
            # Note: Area units depend on the CRS. If it's geographic (like EPSG:4326),
            # the units are degrees squared, which is not a good measure of actual area.
            # If it's projected, units are typically meters squared.
            try:
                # Check if CRS is projected before calculating area directly
                if ne_lakes_gdf.crs.is_projected:
                    ne_lakes_gdf['area_calc'] = ne_lakes_gdf.geometry.area
                else:
                    # Attempt to reproject to a common projected CRS like Web Mercator for area calculation
                    # This is better than using degree-squared, but still not equal-area.
                    # Explain the area calculation process for geographic CRS
                    logging.info(f"Original lake CRS ({ne_lakes_gdf.crs.name}) is geographic.")
                    logging.info("Direct area calculation (degrees-squared) is unsuitable for size comparison.")
                    logging.info("Attempting temporary reprojection to EPSG:3857 (Web Mercator) for approximate area calculation.")
                    try:
                        ne_lakes_gdf_proj = ne_lakes_gdf.to_crs("EPSG:3857") # Web Mercator
                        ne_lakes_gdf['area_calc'] = ne_lakes_gdf_proj.geometry.area
                        logging.info("Successfully reprojected temporarily to very roughly approximate area for ranking purposes only.")
                    except Exception as proj_err:
                        logging.info(f"Temporary reprojection to EPSG:3857 failed: {proj_err}.") # Changed to info level
                        logging.info("Falling back to potentially inaccurate geographic area (degree-squared) for filtering.")
                        ne_lakes_gdf['area_calc'] = ne_lakes_gdf.geometry.area # Fallback to geographic area
            except Exception as e:
                 logging.info(f"Could not calculate lake areas: {e}. Assigning 0 area; filtering may be skipped or inaccurate.") # Changed to info level
                 ne_lakes_gdf['area_calc'] = 0 # Assign default area if calculation fails

            # Sort by calculated area and take top 100
            lakes_sorted = ne_lakes_gdf.sort_values(by='area_calc', ascending=False)
            lakes_to_plot = lakes_sorted.head(100)
            logging.info(f"Plotting {len(lakes_to_plot)} largest lakes.")

            # Plot the filtered lakes with pastel blue color
            lake_fill_color = '#B0C4DE' # LightSteelBlue (greyish-blue)
            lake_edge_color = 'white'   # Match state edge color
            lakes_to_plot.plot(ax=ax, color=lake_fill_color, edgecolor=lake_edge_color, linewidth=0.125, zorder=2) # Reduced linewidth
        elif ne_lakes_gdf is not None:
             logging.info("Lake GeoDataFrame is empty, skipping lake plotting.")
        # No else needed if ne_lakes_gdf is None, handled by can_plot_ne check
    else:
        logging.info("Skipping Natural Earth layers as they are missing.")
        ax.set_facecolor('gainsboro') # Set background if no basemap

    # --- 2. Plot Plate Boundaries by Type ---
    logging.info("Plotting plate boundaries by type...")
    plate_colors = {
        'ridge': 'red',
        'transform': 'green',
        'trench': 'purple'
    }
    plate_labels = {
        'ridge': 'Spreading Ridges',
        'transform': 'Transform Faults',
        'trench': 'Trenches & Underthrusting'
    }
    boundary_col = 'boundary_t' # Assumes this column exists from loading function
    legend_handles = []

    if boundary_col in plate_gdf.columns:
        plotted_boundary_types = set()
        for boundary_type, data in plate_gdf.groupby(boundary_col):
            type_key = str(boundary_type).lower()
            color = plate_colors.get(type_key, 'black')
            label = plate_labels.get(type_key)
            data.plot(ax=ax, color=color, linewidth=1.5, zorder=3)
            if label and type_key not in plotted_boundary_types:
                 legend_handles.append(Line2D([0], [0], color=color, lw=1.5, label=label))
                 plotted_boundary_types.add(type_key)
            elif not label and type_key not in plotted_boundary_types:
                 legend_handles.append(Line2D([0], [0], color=color, lw=1.5, label=f'Other: {boundary_type}'))
                 plotted_boundary_types.add(type_key)
        logging.info(f"Plotted boundary types found: {plate_gdf[boundary_col].unique()}")
    else:
        logging.warning(f"Boundary type column '{boundary_col}' not found. Plotting all boundaries in default color.") # Changed to warning level
        plate_gdf.plot(ax=ax, color='black', linewidth=1.5, label='Plate Boundaries (Type Unknown)', zorder=3)
        legend_handles.append(Line2D([0], [0], color='black', lw=1.5, label='Plate Boundaries (Type Unknown)'))

    # --- 3. Plot Earthquakes ---
    logging.info("Plotting earthquake data...")
    if 'mag' in earthquake_gdf.columns:
        # Note: Filtering by magnitude/date should ideally happen *before* passing data to this function
        # This function assumes the earthquake_gdf is already filtered as desired.
        earthquake_gdf_sorted = earthquake_gdf.sort_values(by='mag', ascending=True)
        cmap = plt.get_cmap('YlOrRd')
        min_mag_plot = earthquake_gdf_sorted['mag'].min()
        max_mag_plot = earthquake_gdf_sorted['mag'].max()

        # Handle case where all magnitudes are the same
        if min_mag_plot == max_mag_plot:
             norm = mcolors.Normalize(vmin=min_mag_plot - 0.1, vmax=max_mag_plot + 0.1)
        else:
             norm = mcolors.Normalize(vmin=min_mag_plot, vmax=max_mag_plot)

        scatter = earthquake_gdf_sorted.plot(
            ax=ax,
            marker='o',
            column='mag',
            cmap=cmap,
            norm=norm,
            markersize=earthquake_gdf_sorted['mag']**2,
            alpha=0.3,
            legend=False,
            zorder=4
        )
        logging.info(f"Plotting {len(earthquake_gdf_sorted)} earthquakes colored by magnitude ({min_mag_plot:.1f}-{max_mag_plot:.1f}), sized by magnitude, alpha=0.3.")
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm._A = []
        cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', shrink=0.6, pad=0.05)
        cbar.set_label('Earthquake Magnitude')
    else:
        logging.warning("Warning: 'mag' column not found. Plotting with default settings.") # Changed to warning level
        earthquake_gdf.plot(ax=ax, marker='o', color='blue', markersize=5, alpha=0.3, label='Earthquakes (Magnitude Unknown)', zorder=4)
        legend_handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=5, linestyle='None', label='Earthquakes (Magnitude Unknown)'))

    # --- 4. Customize Plot ---
    # Construct title
    # Use actual min magnitude from the plotted data if available
    actual_min_mag_str = f"{min_mag_plot:.1f}" if 'min_mag_plot' in locals() else f"{min_magnitude} (input)"
    title = f'Global Earthquakes (M ≥ {actual_min_mag_str})'
    if start_date and end_date:
        title += f' from {start_date} to {end_date}'
    elif start_date:
         title += f' from {start_date}'
    elif end_date:
         title += f' until {end_date}'
    title += f', Plate Boundaries, and Basemap (CRS: {target_crs_epsg})'

    ax.set_title(title)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True, linestyle='--', alpha=0.5, zorder=0)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)

    if legend_handles:
        ax.legend(handles=legend_handles, title="Legend", loc='lower left', fontsize='small')
    else:
        logging.info("No legend items to display.")

    plt.tight_layout()

    # Add note about lake filtering and plotting
    lake_note = ("Note: Only the 100 largest lakes (filtered by approximate area calculated using "
                 "EPSG:3857 projection) are shown for clarity.\n"
                 "Lakes are plotted using their original WGS 84 (EPSG:4326) coordinates.")
    # Place text slightly above the bottom edge, centered horizontally
    fig.text(0.5, 0.01, lake_note, ha='center', va='bottom', fontsize='x-small', style='italic', color='dimgray', wrap=True)

    # Add data source citations with links
    citation_text = (
        "Data Sources:\n"
        "Earthquakes: USGS FDSNWS (earthquake.usgs.gov/fdsnws/event/1/)\n"
        "Boundaries: Natural Earth (naturalearthdata.com)\n"
        "Plates: HDX (data.humdata.org/dataset/tectonic-plates-boundaries)" # Simplified link for brevity
    )
    fig.text(0.98, 0.01, citation_text, ha='right', va='bottom', fontsize='xx-small', style='italic', color='dimgray', wrap=True)


    plt.show()
    logging.info("Plot displayed.")
# Add function definitions later