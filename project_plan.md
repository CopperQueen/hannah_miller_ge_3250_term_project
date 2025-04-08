# Project Goal

***Question to answer:***
"Is there a quantifiable correlation between earthquake magnitude and the distance from the nearest fault line, and does this relationship vary by fault type? Specifically, can earthquake magnitude be used to predict proximity to a fault line, or vice versa?"

----

# Project Plan: Interactive Earthquake and Tectonic Plate Visualization

[Back to Main README](./README.md)

This document outlines the steps to create an interactive visualization project combining earthquake data and tectonic plate boundaries using Python, primarily within an iPython Notebook environment. 



The primary goal is to analyze the spatial relationship between historical earthquake occurrences and tectonic plate boundaries. This involves:

1.  **Data Integration:** Combining USGS earthquake catalog data with tectonic plate boundary data (ridges, transforms, trenches).
2.  **Accurate Distance Calculation:** Calculating the precise distance (in meters) from each earthquake epicenter to the nearest tectonic plate boundary segment. This will involve projecting data to appropriate UTM zones for accuracy.
3.  **Data Enrichment:** Labeling each earthquake record with the calculated distance and the name/type of the nearest plate boundary segment.
4.  **Exploratory Data Analysis (EDA):** Investigating potential correlations and patterns between:
    *   Earthquake magnitude and distance to the nearest fault.
    *   Fault type/name and the proximity of associated earthquakes.
    *   Fault type/name and the frequency of associated earthquakes.
    *   Earthquake magnitude and its relationship to fault types/names and earthquake frequency/proximity.
5.  **Visualization:** Creating maps and plots to visually represent the data, distances, and analysis findings.

Clear, informative visualizations and documented analysis will support pattern discovery and communication of results. The project also aims to document learnings and data sources used.

## Directory Structure

```
hannah_miller_term_project/
│
├── project_plan.md             # This file
├── earthquake_plate_notebook.ipynb # The main iPython notebook
│
├── functions/                  # Directory for Python helper functions
│   ├── __init__.py             # Makes 'functions' a package
│   ├── data_fetching/          # Sub-package for data acquisition functions
│   │   ├── [x] __init__.py         # Makes 'data_fetching' a package
│   │   ├── earthquake_data.py  # Function to fetch USGS earthquake data
│   │   ├── plate_data.py       # Function to fetch and process plate boundary data
│   │   ├── natural_earth_downloader.py # Function to download Natural Earth boundaries
│   │   └── seismic_data.py     # Function to fetch seismic data (NOTE: Data fetched but not used in current analysis plan)
│   ├── data_processing.py      # Functions for cleaning, merging, projecting data
│   ├── spatial_analysis.py     # Functions for distance calculation and spatial joining
│   ├── plotting.py             # Functions for creating static maps and analysis plots
│   └── utils.py                # General utility functions (e.g., UTM zone calculation)
│
└── resources/                  # Directory for downloaded/saved data & maps
    ├── plate_boundaries/       # Processed plate boundary data (e.g., combined_plate_boundaries.shp)
    ├── natural_earth_boundaries/ # Downloaded Natural Earth boundary zip files
    ├── earthquake_data/minmagnitude={mag}/ # Downloaded earthquake catalogs by minmagnitude
    ├── seismic_data/           # Raw downloaded seismic waveform data (NOTE: Retained as work was done, but not used in current analysis due to complexity/scope change)
    └── static_maps/            # Saved static map images and analysis plots
```

## Overall Workflow


## Detailed Steps

- [x] **1. Project Setup:**
    - [x] Create the main project directory (`hannah_miller_term_project`).
    - [x] Create subdirectories: `functions/`, `resources/`, `resources/plate_boundaries/`, `resources/earthquake_data/`, `resources/static_maps/`.
    - [x] Create `functions/__init__.py`.
    - [x] Set up Python environment (e.g., using Conda or venv).
    - [x] Install necessary libraries: `notebook`, `pandas`, `geopandas`, `requests`, `matplotlib`, `shapely`, `rasterio`, `cartopy`, `obspy` (for seismic data), `scikit-learn`, `h5py`/`pyarrow` (for feature files), potentially `tensorflow` or `pytorch`.
        ```bash
        # Example using conda
        conda create -n geo_env python=3.9 # Or later
        conda activate geo_env
        # Install core geo/plotting libs
        conda install -c conda-forge notebook pandas geopandas requests matplotlib shapely cartopy rasterio
        # Install seismic lib
        conda install -c conda-forge obspy
        # Install ML libs
        conda install -c conda-forge scikit-learn h5py pyarrow # Add tensorflow/pytorch if needed
        ```
    - [x] Initialize the main iPython Notebook (`earthquake_plate_notebook.ipynb`).

- [ ] **2. Data Acquisition (`functions/data_fetching/` package):**
    - [x] **Module:** `functions/data_fetching/earthquake_data.py`
        - **Function:** `fetch_and_load_earthquake_data(start_date, end_date, min_magnitude, force_download=False, max_workers=10)`.
            - Downloads earthquake data from USGS API day-by-day using parallel requests (`concurrent.futures`).
            - Saves each day's data locally in `resources/earthquake_data/minmagnitude={mag}/earthquakes-YYYY-MM-DD.geojson`.
            - Skips download if daily file exists (unless `force_download=True`).
            - Loads all relevant daily GeoJSON files and concatenates them into a single GeoDataFrame.
            - Handles request errors and manages local file storage. Uses `logging`.
    - [x] **Module:** `functions/data_fetching/plate_data.py` (Refactored with caching & improved CRS handling)
        - **Function:** `load_plate_boundaries()`.
            - Checks for `ridge.shp`, `transform.shp`, `trench.shp` in `resources/plate_boundaries/`.
            - If any are missing, downloads plate boundary zip archive from Humanitarian Data Exchange (HDX).
            - Extracts required components for the three shapefiles (`ridge.*`, `transform.*`, `trench.*`).
            - Loads the three individual shapefiles into GeoDataFrames.
            - Concatenates the three GeoDataFrames.
            - Saves the combined data to `resources/plate_boundaries/combined_plate_boundaries.shp`.
            - Cleans up (deletes) the individual extracted shapefile components.
            - Returns the combined GeoDataFrame. Uses `logging`.
    - [x] **Module:** `functions/data_fetching/natural_earth_downloader.py`
        - **Function:** `download_natural_earth_boundaries(output_dir='resources/natural_earth_boundaries')`.
            - Downloads specified Natural Earth boundary datasets (10m Admin 1, 10m Lakes, 50m Countries) as zip files.
            - Creates the output directory if it doesn't exist.
            - Saves files to `resources/natural_earth_boundaries/`.
            - Skips download if files already exist. Uses `logging`.
    - [x] **Module:** `functions/data_fetching/seismic_data.py` (Fetching implemented, data unused in current plan)
        - **Function:** `fetch_seismic_data(stations, start_time, end_time, data_dir='resources/seismic_data/')`.
            - Uses `obspy` client (e.g., `FDSN client`) to download waveform data for specified stations and time range.
            - Saves raw data locally (e.g., in MiniSEED format) in `data_dir`.
            - Handles potential download errors and data gaps.
            - Returns paths to downloaded files or confirmation.
            - **Note:** While the data fetching was completed, this seismic data is **not used** in the current analysis plan due to a scope change. The data was found to be large and complex to integrate effectively within the project timeframe and available compute resources. It is retained here as completed work. Future work with more resources could potentially integrate this data.


- [ ] **3. Data Processing (`functions/data_processing.py`):**
    - [ ] **Function:** `process_earthquake_data(df)`.
        - Convert the earthquake DataFrame into a GeoDataFrame using latitude/longitude.
        - Set the initial Coordinate Reference System (CRS), likely WGS84 (`EPSG:4326`).
        - Filter data if necessary (e.g., remove entries with missing coordinates).
        - Convert timestamp columns to datetime objects.
        - **Note:** Further projection (e.g., to appropriate UTM zones) might occur within the spatial analysis step or a dedicated function for accurate distance calculation.
        - Return the processed GeoDataFrame.
    - [ ] **Function:** `process_plate_data(gdf)`.
        - Ensure the plate boundary GeoDataFrame has the correct CRS (likely WGS84, `EPSG:4326`). If not, reproject it.
        - Select relevant columns (e.g., boundary name/type).
        - **Note:** Similar to earthquake data, further projection might occur later for distance calculations.
        - Return the processed GeoDataFrame.


- [ ] **4. Spatial Analysis (`functions/spatial_analysis.py`):**
    - [ ] **Function:** `calculate_distance_to_nearest_boundary(quake_gdf, plate_gdf)`.
        - **Core Logic:** For each earthquake point:
            - Determine the appropriate UTM zone.
            - Project the earthquake point and the plate boundary data to that UTM zone.
            - Calculate the minimum distance (in meters) from the projected point to the nearest projected plate boundary line segment.
            - Identify the name and/or type of that nearest boundary segment from the plate data.
        - Add new columns to the earthquake GeoDataFrame:
            - `distance_m`: The calculated minimum distance in meters.
            - `nearest_boundary_name`: The name of the closest boundary.
            - `nearest_boundary_type`: The type of the closest boundary (if available).
        - **Optimization:** Consider spatial indexing (`rtree`) for efficiency. Handle points that might span UTM zone boundaries carefully (e.g., analyze within multiple relevant zones if necessary).
        - Return the updated earthquake GeoDataFrame (likely still in its original CRS like WGS84, but with the calculated distances).
    - [ ] **(Optional) Function:** `find_utm_zone(longitude, latitude)` (Could be in `utils.py`).
        - Helper function to determine the correct UTM zone based on coordinates.

- [ ] **5. Exploratory Data Analysis (EDA):** (To be performed in the notebook)
    - Analyze the enriched earthquake GeoDataFrame (with distances and nearest boundary info).
    - Investigate relationships using statistical summaries and plots:
        - Distribution of distances to nearest boundaries.
        - Distance vs. Earthquake Magnitude.
        - Earthquake frequency per boundary type/name.
        - Proximity of earthquakes for different boundary types/names.
        - Relationship between magnitude and boundary type/proximity.
    - Document findings in the notebook.

- [ ] **6. Visualization (`functions/plotting.py`):**
    - [x] **Function:** `plot_earthquake_plate_map(earthquake_gdf, plate_gdf, ne_land_gdf, ne_lakes_gdf, ...)` (Base map implemented)
        - Generates static map using Matplotlib/GeoPandas showing earthquakes (sized/colored by magnitude), plate boundaries (colored by type), and Natural Earth basemap.
        - Includes legend, colorbar, title.
        - Saves the figure if `output_path` is provided.
        - Returns the Matplotlib axes object.
    - [ ] **Additional Plots (To be developed/added in notebook or `plotting.py`):**
        - Maps visualizing earthquake proximity to boundaries (e.g., color points by distance).
        - Histograms/scatter plots for EDA:
            - Distribution of distances.
            - Distance vs. Magnitude.
            - Earthquake counts per boundary type/name.
        - Save plots to `resources/static_maps/`.

- [ ] **7. iPython Notebook Assembly (`earthquake_plate_notebook.ipynb`):**
    - [ ] **Structure:** Use Markdown cells extensively to explain each step: introduction, setup, data loading, processing, spatial analysis (distance calculation), exploratory data analysis (EDA), visualization choices, and conclusions/learnings.
    - [ ] **Import Functions:** Import necessary functions from the `functions` package.
    - [ ] **Workflow:**
        - [x] **Setup & Imports:** Standard library imports, package imports, logging setup.
        - [x] **Data Acquisition:** Call functions to load/fetch earthquake, plate, and Natural Earth data. Add note about unused seismic data.
        - [ ] **Data Processing:**
            - Call functions to process earthquake and plate GeoDataFrames (initial CRS setting, cleaning).
            - Display snippets of processed data.
        - [ ] **Spatial Analysis:**
            - Call `calculate_distance_to_nearest_boundary` to compute distances (using UTM projections internally) and label earthquakes with nearest boundary info.
            - Display head of the enriched earthquake GeoDataFrame.
        - [ ] **Exploratory Data Analysis (EDA):**
            - Perform analysis on the enriched data (distributions, correlations between magnitude, distance, boundary type).
            - Use pandas/geopandas for statistical summaries.
            - Generate plots (histograms, scatter plots) to visualize findings (calls to `functions/plotting.py` or inline plotting).
        - [ ] **Visualization:**
            - Call `plot_earthquake_plate_map` to show the base map of earthquakes and plates.
            - Display EDA plots generated above.
        - [ ] **Conclusions & Learnings:**
            - Summarize key findings from the EDA regarding earthquake proximity to different fault types/locations.
            - Discuss limitations (e.g., accuracy of plate boundaries, projection effects).
            - Document project learnings (challenges, discoveries) in this notebook or link to `project_learnings.md`.
            - List data sources with URLs for citation (or link to `data_sources.md`).

## Key Libraries & Concepts

*   **Pandas:** Data manipulation (DataFrames).
*   **GeoPandas:** Geospatial data manipulation (GeoDataFrames), spatial operations, reprojection.
*   **Shapely:** Geometric objects and operations.
*   **Requests:** Fetching web API data (USGS).
*   **Matplotlib / Cartopy:** Static maps and plots with geographic projections.
*   **iPython Notebook:** Interactive development environment.
*   **CRS:** Coordinate Reference Systems (e.g., WGS84 - EPSG:4326).
*   **UTM Projection:** Universal Transverse Mercator projection for accurate distance calculations in local zones.
*   **Spatial Analysis:** Proximity calculation (distance), spatial joins.
*   **Exploratory Data Analysis (EDA):** Statistical summaries, correlation analysis, visualization for pattern discovery.

This plan provides a structured approach to building your project. Remember to commit your code regularly and test functions as you build them.