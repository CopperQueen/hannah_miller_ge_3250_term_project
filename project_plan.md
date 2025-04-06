# Project Plan: Interactive Earthquake and Tectonic Plate Visualization

[Back to Main README](./README.md)

This document outlines the steps to create an interactive visualization project combining earthquake data and tectonic plate boundaries using Python, primarily within an iPython Notebook environment. 

## Project Goal

The primary goal is to build a foundational system for visualizing and analyzing seismic activity to advance earthquake prediction efforts. This involves:

1.  **Visualization:** Develop maps displaying tectonic plates, historical earthquakes, and dynamically added seismic events from feature tables.
2.  **Machine Learning for Prediction:** Train ML models using features derived from seismic station activity (paired with ground truth earthquake data, e.g., from USGS) to predict earthquake location and depth.
3.  **Robust Evaluation:** Evaluate model performance using temporal validation strategies like Leave-One-Year-Out (LOYO) cross-validation to assess generalizability.
4.  **Scenario Analysis:** Enable experimentation with varying numbers and combinations of seismic stations to understand model robustness under different data availability conditions.
5.  **Project North Star Goal and Foundation for Forecasting:** Establish the groundwork (data pipelines, feature engineering, modeling framework) for the long-term "North Star" goal of developing a reliable predictive system capable of identifying precursors to large earthquakes.

Clear, informative visualizations will support all project phases, aiding in pattern discovery, model interpretation, and communication of results.

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
│   │   └── natural_earth_downloader.py # Function to download Natural Earth boundaries
│   ├── data_processing.py      # Functions for cleaning, merging, feature extraction & file creation
│   ├── spatial_analysis.py     # Functions for proximity analysis, feature linking etc.
│   ├── stream_station_timeseries.py # Functions for seismic time series processing
│   ├── machine_learning.py     # Functions for ML model training, validation, inference
│   ├── plotting.py             # Functions for creating static maps
│   └── utils.py                # General utility functions (optional)
│
└── resources/                  # Directory for downloaded/saved data & maps
    ├── plate_boundaries/       # Processed plate boundary data (e.g., combined_plate_boundaries.shp)
    ├── natural_earth_boundaries/ # Downloaded Natural Earth boundary zip files
    ├── earthquake_data/minmagnitude={mag}/ # Downloaded earthquake catalogs by minmagnitude
    ├── seismic_data/           # Raw downloaded seismic waveform data
    ├── feature_files/          # Compressed feature files for ML
    ├── trained_models/         # Saved trained ML models
    └── static_maps/            # Saved static map images
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
    - [x] **Module:** `functions/data_fetching/seismic_data.py` (Initial implementation complete)
        - **Function:** `fetch_seismic_data(stations, start_time, end_time, data_dir='resources/seismic_data/')`.
            - Use `obspy` client (e.g., `FDSN client`) to download waveform data for specified stations and time range.
            - Save raw data locally (e.g., in MiniSEED format) in `data_dir`.
            - Handle potential download errors and data gaps.
            - Return paths to downloaded files or confirmation.


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
        - Return the processed GeoDataFrame.
    - [ ] **Function:** `process_seismic_waveforms(file_paths_or_stream)`.
        - Read raw seismic data (e.g., using `obspy.read()`).
        - Apply necessary preprocessing: detrending, filtering, resampling, instrument correction.
        - Extract relevant features (e.g., spectral properties, amplitudes, STA/LTA, polarization attributes) over defined time windows.
        - Return a structured format (e.g., Pandas DataFrame) containing features, timestamps, and station info.
    - [ ] **Function:** `create_feature_file(features_df, output_path)`.
        - Takes the DataFrame of extracted seismic features.
        - Saves the features to a compressed, efficient format (e.g., HDF5 using `h5py` or Parquet using `pyarrow`).
        - Structure the file for easy loading during ML training/inference (e.g., datasets for features and labels if applicable).
        - Ensure metadata (station info, feature descriptions, processing steps) is included.
        - Example path: `resources/feature_files/seismic_features_YYYYMMDD.h5`


- [ ] **4. Spatial Analysis (`functions/spatial_analysis.py`):**
    - [ ] **Function:** `calculate_distance_to_boundary(quake_gdf, plate_gdf)`.
        - Calculate the minimum distance from each earthquake point to the nearest plate boundary line/polygon. *Note: This can be computationally intensive for many points/complex boundaries. Consider optimizations or simplifying geometries if needed.*
        - Add the distance as a new column to the earthquake GeoDataFrame.
        - Return the updated GeoDataFrame.
    - [ ] **Function:** `categorize_earthquakes(quake_gdf, buffer_distance)`.
        - Categorize earthquakes based on their proximity to boundaries (e.g., 'Near Boundary', 'Far Field').
        - *Optional Advanced:* Determine the type of the nearest boundary segment (convergent, divergent, transform) if the plate data includes this information.
        - Return the updated GeoDataFrame with categories.
        - Return the updated GeoDataFrame with categories.
    - [ ] **Function:** `analyze_seismic_features_spatially(seismic_features_df, quake_gdf, plate_gdf)`.
        - Link seismic features (from specific stations/times) to nearby earthquakes or plate boundary segments.
        - This might involve temporal and spatial proximity calculations.
        - Could add flags/labels to features based on proximity to significant events/structures.
        - Return the enriched seismic features DataFrame or related analysis results.

- [ ] **5. Machine Learning (`functions/machine_learning.py`):**
    - [ ] **Goal:** Train models using features derived from seismic station activity to predict earthquake location (latitude, longitude) and depth, evaluating performance rigorously.
    - [ ] **Data Preparation:**
        - Load compressed feature file(s) (`resources/feature_files/`).
        - Align seismic features temporally with ground truth earthquake data (location, depth from USGS catalog).
        - Define features (input) and target variables (output: lat, lon, depth).
        - Split data into training, validation, and test sets using temporal criteria (e.g., train on earlier years, validate/test on later years) to prevent data leakage.
    - [ ] **Model Training:**
        - Select appropriate ML model(s) (e.g., RandomForest, LSTM, CNN depending on features/task).
        - Train model(s) on the training dataset.
        - Tune hyperparameters.
    - [ ] **Model Validation:**
        - Evaluate model performance on the validation set using appropriate metrics for regression (e.g., Mean Absolute Error, RMSE for location/depth) and potentially classification if predicting occurrence.
        - **Primary Strategy: Leave-One-Year-Out (LOYO) Cross-Validation:** Systematically train on all years except one and test on the held-out year to assess temporal generalizability. Repeat for multiple held-out years.
        - Analyze performance variations across different time periods.
    - [ ] **Station Robustness Analysis:**
        - Re-train/evaluate models using different subsets of seismic stations (e.g., reducing station count, using specific geographic combinations).
        - Analyze the impact of station availability/loss on prediction accuracy.
    - [ ] **Inference:**
    - [ ] **Inference & Feature Importance:**
        - Use the final trained model to make predictions on the held-out test set.
        - Analyze feature importance (e.g., using SHAP or model-specific methods) to understand which seismic features are most predictive. This informs the long-term goal of identifying potential precursors.
    - [ ] **Model Saving:**
        - Save the best performing model(s), associated data scalers, and validation results (including LOYO performance) to `resources/trained_models/`.

- [x] **6. Visualization (`functions/plotting.py`):** (Static map implemented)
    - [x] **Function:** `plot_earthquake_plate_map(earthquake_gdf, plate_gdf, ne_land_gdf, ne_lakes_gdf, ...)` (Implemented)
        - **Core Logic:** Generates static map using Matplotlib/GeoPandas showing earthquakes (sized/colored by magnitude), plate boundaries (colored by type), and Natural Earth basemap (land, filtered lakes).
        - Includes legend, colorbar, title, and robust CRS/area handling for lakes.
        - Create axes with a map projection.
        - Plot plate boundaries.
        - Plot earthquake points (customize markers by magnitude/depth).
        - *Future Enhancements:* Plot seismic station locations, ML results, allow Cartopy projections.
        - If `output_path` is provided (e.g., `resources/static_maps/map.png`), save the figure using `plt.savefig()`.
        - Return the Matplotlib axes object.

- [/] **7. iPython Notebook Assembly (`earthquake_plate_notebook.ipynb`):** (Partially complete)
    - [ ] **Structure:** Use Markdown cells extensively to explain each step: introduction, setup, data loading, processing, analysis methods, visualization choices, and conclusions.
    - [ ] **Import Functions:** Import the necessary functions from your `functions` package (e.g., `from functions.data_fetching import load_plate_boundaries`).
    - [ ] **Workflow:**
        - [x] **Setup & Imports:** Refactored imports, added logging.
        - [x] **Data Acquisition:** Calls implemented for earthquake, plate, and Natural Earth data.
        - **Data Processing:**
            - Process earthquake and plate data.
            - Process seismic waveforms and extract features.
            - Create the compressed feature file.
            - Display snippets of processed data.
        - **Spatial Analysis:**
            - Analyze earthquake proximity to boundaries.
            - Analyze seismic features spatially (linking to events/locations).
            - Display analysis results.
        - **Machine Learning:**
            - Load feature file.
            - Prepare data for predicting earthquake location/depth from station features.
            - Train selected model(s).
            - Perform and document Leave-One-Year-Out (LOYO) cross-validation results.
            - Conduct station robustness experiments and report findings.
            - Run inference on the test set and analyze feature importance.
        - [x] **Visualization:**
            - Call `plot_earthquake_plate_map` showing historical quakes, plates, basemap.
            - Create static maps visualizing key ML results (e.g., prediction accuracy, feature importance).
            - Display all maps/plots within the notebook.
    - [ ] **Interpretation:** Include Markdown cells discussing the results, the visual correlation observed, limitations, and potential future work.

        - **Interpretation:** Include Markdown cells discussing:
            - Visual correlations observed.
            - ML model performance (LOYO results, location/depth accuracy).
            - Impact of station robustness tests.
            - Key predictive features identified and their potential link to the forecasting goal.
            - Overall limitations and directions for future work (e.g., refining features for precursor identification).

## Key Libraries & Concepts

*   **Pandas:** Data manipulation (DataFrames).
*   **GeoPandas:** Geospatial data manipulation (GeoDataFrames), spatial operations.
*   **Shapely:** Geometric objects.
*   **Requests:** Fetching web API data (USGS).
*   **ObsPy:** Fetching and processing seismic waveform data (FDSN).
*   **H5py / PyArrow:** Reading/writing compressed data formats (HDF5/Parquet).
*   **Scikit-learn:** Machine learning algorithms, preprocessing, validation.
*   **(Optional) TensorFlow / PyTorch:** Deep learning frameworks.
*   **Matplotlib / Cartopy:** Static maps with geographic projections.
*   **iPython Notebook:** Interactive development environment.
*   **CRS:** Coordinate Reference Systems.
*   **Spatial Analysis:** Proximity, joins, overlays.
*   **Time Series Analysis:** Handling temporal data, feature extraction from waveforms.
*   **Machine Learning Validation:** Temporal Cross-validation (Leave-One-Year-Out), Regression Metrics (MAE, RMSE), Feature Importance Analysis.

This plan provides a structured approach to building your project. Remember to commit your code regularly and test functions as you build them.