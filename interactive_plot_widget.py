import ipywidgets as widgets
from IPython.display import display, clear_output
import pandas as pd
import geopandas as gpd
from datetime import date, datetime
import logging

# Assuming functions.plotting.plot_earthquake_plate_map exists
# and has the signature seen previously.
# Make sure the 'functions' module is importable from your notebook.
try:
    from functions import plotting
except ImportError:
    logging.error("Could not import functions.plotting. Make sure 'functions' is in the Python path.")
    # Define a dummy function if import fails, so the rest of the widget code doesn't crash immediately
    class plotting:
        @staticmethod
        def plot_earthquake_plate_map(*args, **kwargs):
            print("Error: functions.plotting could not be imported. Plotting is disabled.")
            pass

def create_interactive_plot(
    earthquake_gdf: gpd.GeoDataFrame,
    plate_gdf: gpd.GeoDataFrame,
    ne_land_gdf: gpd.GeoDataFrame,
    ne_lakes_gdf: gpd.GeoDataFrame,
    target_crs_epsg: str = "EPSG:4326"
):
    """
    Creates interactive widgets (date pickers, magnitude slider)
    to filter and display the earthquake map.

    Args:
        earthquake_gdf: The *unfiltered* GeoDataFrame with earthquake data
                        (must include 'time' and 'mag' columns).
        plate_gdf: GeoDataFrame with plate boundary data.
        ne_land_gdf: GeoDataFrame for Natural Earth land boundaries.
        ne_lakes_gdf: GeoDataFrame for Natural Earth lakes basemap.
        target_crs_epsg: The target CRS for the plot title.
    """
    if earthquake_gdf is None or earthquake_gdf.empty:
        print("Earthquake data is empty or None. Cannot create interactive plot.")
        return

    # --- Ensure correct data types ---
    # Convert 'time' column to datetime objects if not already
    if 'time' not in earthquake_gdf.columns:
         print("Error: 'time' column not found in earthquake_gdf.")
         return
    if not pd.api.types.is_datetime64_any_dtype(earthquake_gdf['time']):
        try:
            earthquake_gdf['time'] = pd.to_datetime(earthquake_gdf['time'])
        except Exception as e:
            print(f"Error converting 'time' column to datetime: {e}")
            return

    # Convert 'mag' column to numeric if not already
    if 'mag' not in earthquake_gdf.columns:
         print("Error: 'mag' column not found in earthquake_gdf.")
         return
    if not pd.api.types.is_numeric_dtype(earthquake_gdf['mag']):
        try:
            earthquake_gdf['mag'] = pd.to_numeric(earthquake_gdf['mag'])
        except Exception as e:
            print(f"Error converting 'mag' column to numeric: {e}")
            return

    # --- Get Data Limits for Widgets ---
    min_date_data = earthquake_gdf['time'].min().date()
    max_date_data = earthquake_gdf['time'].max().date()
    min_mag_data = earthquake_gdf['mag'].min()
    max_mag_data = earthquake_gdf['mag'].max()

    # Handle potential NaT or NaN values if data is empty after conversion errors
    min_date_data = min_date_data if pd.notna(min_date_data) else date.today()
    max_date_data = max_date_data if pd.notna(max_date_data) else date.today()
    min_mag_data = min_mag_data if pd.notna(min_mag_data) else 0.0
    max_mag_data = max_mag_data if pd.notna(max_mag_data) else 10.0
    # Ensure min isn't greater than max if data is weird
    if min_mag_data > max_mag_data:
        min_mag_data = max_mag_data

    # --- Create Widgets ---
    start_date_picker = widgets.DatePicker(
        description='Start Date:',
        value=min_date_data,
        disabled=False
    )

    end_date_picker = widgets.DatePicker(
        description='End Date:',
        value=max_date_data,
        disabled=False
    )

    magnitude_slider = widgets.FloatRangeSlider(
        value=[min_mag_data, max_mag_data],
        min=min_mag_data,
        max=max_mag_data,
        step=0.1,
        description='Magnitude Range:',
        disabled=False,
        continuous_update=False, # Only update on release
        orientation='horizontal',
        readout=True,
        readout_format='.1f',
        layout=widgets.Layout(width='500px') # Adjust width if needed
    )

    # Output widget to hold the plot
    plot_output = widgets.Output()

    # --- Define Update Function ---
    def update_plot(change):
        """Callback function to filter data and regenerate the plot."""
        with plot_output:
            clear_output(wait=True) # Clear previous plot

            # Get current widget values
            start_dt = datetime.combine(start_date_picker.value, datetime.min.time()) if start_date_picker.value else None
            end_dt = datetime.combine(end_date_picker.value, datetime.max.time()) if end_date_picker.value else None # Use end of day
            min_mag_filter, max_mag_filter = magnitude_slider.value

            # Filter the earthquake GeoDataFrame
            filtered_eq_gdf = earthquake_gdf.copy() # Work on a copy

            # Apply date filtering
            if start_dt:
                filtered_eq_gdf = filtered_eq_gdf[filtered_eq_gdf['time'] >= start_dt]
            if end_dt:
                filtered_eq_gdf = filtered_eq_gdf[filtered_eq_gdf['time'] <= end_dt]

            # Apply magnitude filtering
            filtered_eq_gdf = filtered_eq_gdf[
                (filtered_eq_gdf['mag'] >= min_mag_filter) &
                (filtered_eq_gdf['mag'] <= max_mag_filter)
            ]

            print(f"Filtering complete. Plotting {len(filtered_eq_gdf)} earthquakes...")

            if filtered_eq_gdf.empty:
                print("No earthquakes match the current filter criteria.")
                # Optionally display an empty plot or just the message
                # For now, we just print the message and don't call the plot function.
                return # Exit if no data to plot

            # Call the original plotting function with FILTERED earthquake data
            # Note: We pass the FILTERED gdf, but the original min_magnitude, start/end dates
            # used for LOADING the data might still be needed if the plot function's
            # title relies on them. Here, we assume the title should reflect the FILTERED range.
            # If the title needs the original load parameters, pass them explicitly.
            # For simplicity now, we let the plot function determine title from filtered data if possible,
            # or we could construct a title here. Let's pass the filtered range info.
            try:
                plotting.plot_earthquake_plate_map(
                    earthquake_gdf=filtered_eq_gdf, # Pass the filtered data
                    plate_gdf=plate_gdf,
                    ne_land_gdf=ne_land_gdf,
                    ne_lakes_gdf=ne_lakes_gdf,
                    # Pass filter values for potential use in title/logging by plot func
                    min_magnitude=min_mag_filter,
                    start_date=start_date_picker.value,
                    end_date=end_date_picker.value,
                    target_crs_epsg=target_crs_epsg
                )
            except Exception as e:
                 print(f"Error during plotting: {e}")
                 logging.exception("Plotting function failed.") # Log traceback


    # --- Link Widgets to Update Function ---
    start_date_picker.observe(update_plot, names='value')
    end_date_picker.observe(update_plot, names='value')
    magnitude_slider.observe(update_plot, names='value')

    # --- Display Widgets and Initial Plot ---
    # Arrange widgets (e.g., in a VBox)
    controls = widgets.VBox([
        widgets.HBox([start_date_picker, end_date_picker]),
        magnitude_slider
    ])

    display(controls, plot_output)

    # Trigger initial plot generation
    update_plot(None)

# Example usage (commented out, use in notebook):
# Assuming you have loaded: earthquake_gdf, plate_gdf, ne_countries_gdf, ne_lakes_gdf
# import importlib
# import interactive_plot_widget
# importlib.reload(interactive_plot_widget) # Reload if you make changes
#
# create_interactive_plot(
#     earthquake_gdf=earthquake_gdf_loaded, # Your fully loaded, unfiltered EQ data
#     plate_gdf=plate_gdf_loaded,
#     ne_land_gdf=ne_countries_gdf_loaded,
#     ne_lakes_gdf=ne_lakes_gdf_loaded,
#     target_crs_epsg="EPSG:4326" # Or your target CRS
# )