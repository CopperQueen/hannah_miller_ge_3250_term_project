# Data Sources and Citations

This document lists the URLs and services used to download data for this project.

## Earthquake Data

-   **Source:** USGS FDSNWS (Federation of Digital Seismograph Networks Web Services) Event Query
-   **Base URL:** [`https://earthquake.usgs.gov/fdsnws/event/1/query`](https://earthquake.usgs.gov/fdsnws/event/1/query)
-   **Description:** Used to query and download earthquake event data based on parameters like time range and magnitude.
-   **File:** `functions/data_fetching/earthquake_data.py`

## Natural Earth Boundaries

-   **Source:** Natural Earth Data hosted on AWS S3
-   **URLs:**
    -   10m Admin 1 States/Provinces: [`https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip`](https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip)
    -   10m Lakes: [`https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip`](https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip)
    -   50m Countries: [`https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip`](https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip)
-   **Description:** Used to download administrative and physical boundaries as zipped shapefiles.
-   **File:** `functions/data_fetching/natural_earth_downloader.py`

## Tectonic Plate Boundaries

-   **Source:** Humanitarian Data Exchange (HDX) - Tectonic Plates and Boundaries
-   **URL:** [`https://data.humdata.org/dataset/f2ea5d82-1b04-4d36-8e94-a73a2eed099d/resource/1bd63193-68da-4c86-a217-c0c8b2c3b2a6/download/plates_plateboundary_arcgis.zip`](https://data.humdata.org/dataset/f2ea5d82-1b04-4d36-8e94-a73a2eed099d/resource/1bd63193-68da-4c86-a217-c0c8b2c3b2a6/download/plates_plateboundary_arcgis.zip)
-   **Description:** Used to download tectonic plate boundary data as a zipped shapefile.
-   **File:** `functions/data_fetching/plate_data.py`

## Seismic Waveform Data 
***(Not Used Currently except downloading, had big plans to use initially, keeping download for potential future use.)***

-   **Source:** FDSN Data Centers (e.g., IRIS - Incorporated Research Institutions for Seismology) via ObsPy
-   **Access Method:** The `obspy.clients.fdsn.Client` class is used to connect to specified data centers (defaulting to "IRIS"). Direct URLs are not specified in the script; ObsPy handles the communication with the FDSN web services.
-   **Description:** Used to download seismic waveform data (MiniSEED format) for specified stations and time ranges.
-   **File:** `functions/data_fetching/seismic_data.py`