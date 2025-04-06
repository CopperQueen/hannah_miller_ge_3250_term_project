# Project Plan: Interactive Earthquake and Tectonic Plate Visualization

This document outlines the steps to create an interactive visualization project combining earthquake data and tectonic plate boundaries using Python, primarily within an iPython Notebook environment.

## Project Goal

To fetch, process, analyze, and visualize earthquake data in relation to tectonic plate boundaries, creating both interactive and static maps to demonstrate the correlation between seismicity and plate tectonics.

## Directory Structure

```
hannah_miller_term_project/
│
├── project_plan.md             # This file
├── earthquake_plate_notebook.ipynb # The main iPython notebook
│
├── functions/                  # Directory for Python helper functions
│   ├── __init__.py
│   ├── data_fetching.py        # Functions to get earthquake & plate data
│   ├── data_processing.py      # Functions for cleaning and merging data
│   ├── spatial_analysis.py     # Functions for proximity analysis, etc.
│   ├── plotting.py             # Functions for creating maps (interactive/static)
│   └── utils.py                # General utility functions (optional)
│
└── resources/                  # Directory for downloaded/saved data & maps
    ├── plate_boundaries/       # Downloaded plate boundary data (e.g., shapefiles)
    └── earthquake_data/        # Downloaded earthquake catalogs (optional, if not using API directly)
    └── static_maps/            # Saved static map images
```

## Overall Workflow


## Detailed Steps

- [x] **1. Project Setup:**
    - [x] Create the main project directory (`hannah_miller_term_project`).
    - [x] Create subdirectories: `functions/`, `resources/`, `resources/plate_boundaries/`, `resources/earthquake_data/`, `resources/static_maps/`.
    - [x] Create `functions/__init__.py`.
    - [x] Set up Python environment (e.g., using Conda or venv).
    - [x] Install necessary libraries: `notebook`, `pandas`, `geopandas`, `requests`, `folium`, `plotly`, `matplotlib`, `shapely`, `rasterio` (if needed for advanced base maps), `cartopy` (for static maps).
        ```bash
        # Example using conda
        conda create -n geo_env python=3
        conda activate geo_env
        conda install -c conda-forge notebook pandas geopandas requests folium plotly matplotlib shapely cartopy rasterio
        ```
    - [x] Initialize the main iPython Notebook (`earthquake_plate_notebook.ipynb`).

- [ ] **2. Data Acquisition (`functions/data_fetching.py`):**
    - [x] **Function:** `fetch_and_load_earthquake_data(start_date, end_date, min_magnitude, force_download=False, max_workers=10)`.
        - Downloads earthquake data from USGS API day-by-day using parallel requests (`concurrent.futures`).
        - Saves each day's data locally in `resources/earthquake_data/minmagnitude={mag}/earthquakes-YYYY-MM-DD.geojson`.
        - Skips download if daily file exists (unless `force_download=True`).
        - Loads all relevant daily GeoJSON files and concatenates them into a single GeoDataFrame.
        - Handles request errors and manages local file storage.
    - [ ] **Function:** `load_plate_boundaries(filepath)`.
        - Use `geopandas` to read plate boundary data (e.g., from a Shapefile downloaded from sources like Peter Bird's dataset or GPlates). Ensure the file is placed in `resources/plate_boundaries/`.
        - Return a GeoDataFrame.

- [ ] **3. Data Processing (`functions/data_processing.py`):**
    - [ ] **Function:** `process_earthquake_data(df)`.
        - Convert the earthquake DataFrame into a GeoDataFrame using latitude/longitude.
        - Set the Coordinate Reference System (CRS), likely WGS84 (`EPSG:4326`).
        - Filter data if necessary (e.g., remove entries with missing coordinates).
        - Convert timestamp columns to datetime objects.
        - Return the processed GeoDataFrame.
    - [ ] **Function:** `process_plate_data(gdf)`.
        - Ensure the plate boundary GeoDataFrame has the correct CRS. If not, reproject it to match the earthquake data (e.g., `EPSG:4326`).
        - Select relevant columns if necessary.
        - Return the processed GeoDataFrame.

- [ ] **4. Spatial Analysis (`functions/spatial_analysis.py`):**
    - [ ] **Function:** `calculate_distance_to_boundary(quake_gdf, plate_gdf)`.
        - Calculate the minimum distance from each earthquake point to the nearest plate boundary line/polygon. *Note: This can be computationally intensive for many points/complex boundaries. Consider optimizations or simplifying geometries if needed.*
        - Add the distance as a new column to the earthquake GeoDataFrame.
        - Return the updated GeoDataFrame.
    - [ ] **Function:** `categorize_earthquakes(quake_gdf, buffer_distance)`.
        - Categorize earthquakes based on their proximity to boundaries (e.g., 'Near Boundary', 'Far Field').
        - *Optional Advanced:* Determine the type of the nearest boundary segment (convergent, divergent, transform) if the plate data includes this information.
        - Return the updated GeoDataFrame with categories.

- [ ] **5. Visualization (`functions/plotting.py`):**
    - [ ] **Function:** `plot_map(quake_gdf, plate_gdf, interactive=True, output_path=None, ...)`.
        - **Core Logic:** Takes processed GeoDataFrames and a boolean `interactive` flag.
        - **If `interactive=True`:**
            - Use `folium` or `plotly.graph_objects.Scattergeo` / `plotly.express.scatter_geo`.
            - Create a base map.
            - Add plate boundaries (lines/polygons).
            - Add earthquake points (customize markers by magnitude/depth, add tooltips).
            - Return the Folium map object or Plotly figure object.
        - **If `interactive=False`:**
            - Use `matplotlib` with `geopandas.plot()` and potentially `cartopy` for better map projections and features (coastlines, borders).
            - Create axes with a map projection.
            - Plot plate boundaries.
            - Plot earthquake points.
            - Customize appearance (colors, sizes, legend, title).
            - If `output_path` is provided (e.g., `resources/static_maps/map.png`), save the figure using `plt.savefig()`.
            - Return the Matplotlib axes object.

- [ ] **6. iPython Notebook Assembly (`earthquake_plate_notebook.ipynb`):**
    - [ ] **Structure:** Use Markdown cells extensively to explain each step: introduction, setup, data loading, processing, analysis methods, visualization choices, and conclusions.
    - [ ] **Import Functions:** Import the necessary functions from your `functions/` modules.
    - [ ] **Workflow:**
        - Call data fetching functions.
        - Call data processing functions.
        - Display snippets of processed data (e.g., `gdf.head()`, `gdf.info()`, `gdf.crs`).
        - Call spatial analysis functions.
        - Display analysis results (e.g., statistics, counts per category).
        - Call the `plot_map` function:
            - Once with `interactive=True` to display the interactive map directly in the notebook.
            - Once with `interactive=False` and an `output_path` to generate and save a static map image. Display the static image in the notebook using Markdown `![Static Map](resources/static_maps/map.png)`.
    - [ ] **Interpretation:** Include Markdown cells discussing the results, the visual correlation observed, limitations, and potential future work.

## Key Libraries & Concepts

*   **Pandas:** Data manipulation and analysis (DataFrames).
*   **GeoPandas:** Geospatial data manipulation (GeoDataFrames), spatial operations, plotting.
*   **Shapely:** Underlying library for geometric objects used by GeoPandas.
*   **Requests:** Fetching data from web APIs.
*   **Folium / Plotly:** Creating interactive maps.
*   **Matplotlib / Cartopy:** Creating static maps with proper geographic projections.
*   **iPython Notebook:** Interactive development and presentation environment.
*   **Coordinate Reference Systems (CRS):** Ensuring spatial data aligns correctly.
*   **Spatial Joins / Overlays / Proximity Analysis:** Core geospatial analysis techniques.

This plan provides a structured approach to building your project. Remember to commit your code regularly and test functions as you build them.