# 🌍 Project Learnings

## 🧰 Development Environment

- Set up **Visual Studio Code** for the first time.
- Discovered helpful **VS Code extensions**:
  - **Markdown Preview**: lets me view markdown documents in a split screen.
  - **RooCode**: an agentic AI plugin that helps me:
    - Navigate and understand my codebase.
    - Generate clean, well-commented, and easy-to-debug code.
    - Plan and update my project as it evolves.
- Learned how to **create a Google Cloud Platform (GCP) billing account** and:
  - Associate an **API key** with it for use in the RooCode extension.
  - This was critical, as RooCode requires a connected API.
  - Used **Google’s Gemini 2.5 Pro model**, which currently offers some of the best coding capabilities.
    - While not used 100% of the time, Gemini 2.5 Pro powered a large portion of the agentic coding work done through RooCode.

## 🔀 Version Control & Documentation

- Learned how to use **GitHub** for the first time:
  - Created an account and uploaded the entire project repository.
  - Created **feature branches** and merged them back into the main branch over time.
  - Used **commit messages** to track progress:
    - Early commit messages were written manually.
    - Later commits were assisted by **RooCode**, which generated more detailed and informative comments.
  - Still working on checking in more frequently, but the commit history includes:
    - Lots of check-ins.
    - Plenty of descriptive comments.
- Gained experience with **Markdown**:
  - First real experience writing and using Markdown syntax.
  - Used Markdown to format documentation in GitHub.
  - Benefited from GitHub's automatic rendering of Markdown files to clearly present my work in a readable format.

## 🐼 Data Analysis & Libraries

- Deepened knowledge of **pandas** and **geopandas**:
  - Learned to use the `.apply()` function to efficiently run custom functions on each row.
- Learned how to **download and assemble data** from various sources:
  - APIs
  - Direct file downloads
- Worked extensively with **geospatial data**:
  - In class, I only learned how to project entire GeoDataFrames.
  - I figured out how to project **individual points** into **UTM coordinates**.
  - Used UTM to calculate **distances from earthquake points to the nearest linestring (plate boundaries)**.

## 🧠 RooCode-Specific Skills

- Used RooCode to:
  - Generate **clear, highly commented code**.
  - **Design and maintain a detailed project plan**, with:
    - Milestones and deliverables.
    - Checkboxes for completed tasks.
    - Iterative updates based on project changes.

## 🔄 Project Planning & Pivots

- Original plan:
  - Use **station data** alongside earthquakes to understand seismic activity.
  - Wrote code to download and process station data.
- Challenges:
  - Station data volume was too large for local compute resources.
  - Realized the original plan was **too ambitious** for the timeframe and hardware.
- Pivoted plan:
  - Focused solely on **earthquake** and **plate ridge** data.
  - Calculated **distances from earthquake points to nearest plate ridges**.
  - Performed **analysis by ridge type** and **ridge identity**.
