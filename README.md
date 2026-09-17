# UMS Multi-Tag & Influx Repopulation Studio ⚡

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero-Dependencies](https://img.shields.io/badge/dependencies-zero%20external-brightgreen.svg)]()

> A lightweight, zero-dependency local web studio to automate hierarchical tag provisioning and trigger historical InfluxDB repopulation on **Iviva UMS (Utility Management System)**.

---

## 🌟 Key Features

- **🚀 Zero-Dependency Architecture:** Built purely on Python's built-in standard library (`http.server`, `urllib`, `socketserver`) — no `pip install` required!
- **🏷️ Automated Tag Provisioning:** Parses CSV tag hierarchies and recursively builds missing tag trees in UMS (`POST /api/v1/tags`).
- **🔗 Non-Destructive Tag Merging:** Safely merges new tags into existing meter configurations without overwriting pre-existing meter tags (e.g. `energy/cooling`, `location`, `ghg`).
- **⏳ InfluxDB Historical Repopulation:** Automatically appends `isChange=1&start=...&stop=...` query parameters to trigger backfilling of time-series series data in InfluxDB.
- **🛡️ Safe Dry Run Mode:** Simulates CSV meter matching and tag resolution with zero risk to production data.
- **📊 Real-time Web Terminal:** Interactive dashboard with real-time log streaming, progress tracking, and CSV previews.

---

## 📁 Repository Structure

```
ums-tagging-repopulation-studio/
├── web/                           # Modern Glassmorphic Web UI
│   ├── index.html                 # UI layout and interactive panels
│   ├── style.css                  # Dark-themed responsive design system
│   └── app.js                     # Frontend API client and log poller
├── ui_server.py                   # Lightweight backend server & UMS client
├── meter_tags_sample.csv          # Sample CSV template for meter mapping
├── run_ui.bat                     # Windows batch launcher (double-click to start)
├── GUIDE.md                       # Comprehensive operational guide
├── UMS_Quick_Guide.pdf            # Printable PDF operations manual
└── .gitignore                     # Git ignore rules
```

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/ums-tagging-repopulation-studio.git
cd ums-tagging-repopulation-studio
```

### 2. Launch the Application

#### On Windows:
Double-click `run_ui.bat` or run:
```powershell
python ui_server.py
```

#### On Linux / macOS:
```bash
python3 ui_server.py
```

### 3. Open in Browser
Navigate to **`http://127.0.0.1:8080`** in any modern web browser.

---

## 📋 CSV Format Specification

Prepare your CSV file following this structure:

```csv
MeterName,MainTag,taghierachy
EM-1121 MCHW-FWU-22-01104,test-tag-version-1,test-tag-version-1/test-tag-5
EM-1121 MCHW-FWU-22-01104,testing,testing/testtag-4
EM-1074 TX-E-01002,test-tag-version-1,test-tag-version-1/test-tag-6
```

- **`MeterName`**: The display name or unique meter GUID in UMS.
- **`MainTag`**: The root tag category / namespace.
- **`taghierachy`**: The full path under the main category (delimited by `/`).

> **Multi-Tagging:** Multiple rows for the same `MeterName` are automatically aggregated into a single combined patch operation.

---

## 🔄 Execution Workflow

```mermaid
flowchart LR
    A[1. Set Credentials & Test Connection] --> B[2. Upload / Preview CSV]
    B --> C[3. Run Dry Run Validation]
    C --> D[4. Execute Live Tagging & Influx Backfill]
```

1. **Test Connection:** Input your UMS Base URL, Account Key, and API Token and click *Test Connection*.
2. **Preview CSV:** Load your mapping file to inspect grouped meter assignments.
3. **Dry Run (Recommended):** Run a simulation to ensure 100% meter resolution without writing any changes.
4. **Live Execution:** Automatically provisions missing tags, applies non-destructive patches, and initiates InfluxDB repopulation.

---

## 🔌 API Endpoints Reference

| Action | Method | Endpoint | Query / Payload |
| :--- | :--- | :--- | :--- |
| **Fetch Tags** | `GET` | `/api/v1/tags` | Loads current UMS tag hierarchy |
| **Create Tag** | `POST` | `/api/v1/tags` | `{"name": "...", "parentTag": "..."}` |
| **List Meters** | `GET` | `/api/v1/utilitymeters` | `?limit=1000&account=...` |
| **Patch & Repopulate** | `PATCH` | `/api/v1/utilitymeters/{id}` | `?isChange=1&start=...&stop=...`<br/>`{"tags": [...]}` |

---

## 📄 Documentation

For full details, please refer to:
- 📖 [GUIDE.md](GUIDE.md) — Comprehensive operations and troubleshooting guide.
- 📕 [UMS_Quick_Guide.pdf](UMS_Quick_Guide.pdf) — Printable PDF quick-reference.

---

## 🛡️ License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
