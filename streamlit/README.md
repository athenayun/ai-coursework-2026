# Streamlit Applications

A collection of interactive Python web applications developed as part of my AI and Python coursework.

These projects explore web scraping, data processing, exploratory data analysis, and interactive dashboard development using Streamlit.

## Applications

| Project                         | Description                                                                                             | Source Code                                                                                                 | Live Demo                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **E-commerce Price Comparison** | Compare product pricing information across e-commerce platforms through an interactive web interface.   | [View Code](https://github.com/athenayun/ai-coursework-2026/tree/main/streamlit/ecommerce-price-comparison) | [Launch App](https://ai-coursework-2026-ecommerce-price-comparison.streamlit.app/) |
| **Momo Price Analyzer**         | Retrieve and explore product pricing information from Momo, with an interactive interface for analysis. | [View Code](https://github.com/athenayun/ai-coursework-2026/tree/main/streamlit/momo-price-analyzer)        | [Launch App](https://ai-coursework-2026-momo-price-analyzer.streamlit.app/)        |
| **PChome Price Analyzer**       | Explore and analyze product pricing data from PChome through a Streamlit application.                   | [View Code](https://github.com/athenayun/ai-coursework-2026/tree/main/streamlit/pchome-price-analyzer)      | [Launch App](https://ai-coursework-2026-pchome-price-analyzer.streamlit.app/)      |
| **Tainan Parking Dashboard**    | An interactive dashboard for exploring and visualizing parking-related data in Tainan, Taiwan.          | [View Code](https://github.com/athenayun/ai-coursework-2026/tree/main/streamlit/tainan_parking_dashboard)   | [Launch App](https://ai-coursework-2026-tainan-parking-dashboard.streamlit.app/)   |

## Technologies

- **Programming:** Python
- **Web Framework:** Streamlit
- **Data Processing:** Pandas and other project-specific libraries
- **Visualization:** Interactive charts and dashboards
- **Data Sources:** Public datasets and external websites, depending on the application
- **Deployment:** Streamlit Community Cloud

## Running Locally

Each application is organized in its own directory with its source code and dependencies.

### 1. Clone the repository

```bash
git clone https://github.com/athenayun/ai-coursework-2026.git
cd ai-coursework-2026
```

### 2. Install dependencies

For example, to run the PChome Price Analyzer:

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install -r streamlit/pchome-price-analyzer/requirements.txt
```

### 3. Launch the application

From the repository root:

```bash
streamlit run streamlit/pchome-price-analyzer/app.py
```

To run another application, replace the folder path with the corresponding project directory.

## Deployment

All four applications are deployed independently on [Streamlit Community Cloud](https://streamlit.io/cloud), while sharing the same GitHub repository.

Each application has its own entry point and dependency configuration, allowing it to be maintained separately.

## Notes

- These applications were developed for educational and experimental purposes.
- Applications relying on external websites or APIs may require updates if their data sources change.
- Each project is maintained within its own directory for easier organization and future development.

---

**Maintained by [Athie Lee](https://github.com/athenayun)**
