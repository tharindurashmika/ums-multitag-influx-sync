# UMS Multi-Tag & Influx Repopulation Studio — Operational Guide

A complete operational guide for configuring, testing, and running the UMS Multi-Tagging and InfluxDB historical repopulation engine.

---

## 1. Overview & Architecture

The **UMS Tagging & Influx Repopulation Studio** automates the end-to-end process of:
1. Validating and creating tag trees in UMS (`POST /api/v1/tags`).
2. Mapping CSV meter identifiers to real UMS utility meters (`GET /api/v1/utilitymeters`).
3. Merging new tags with existing meter tags without overwriting previous associations.
4. Patching meters with updated tag sets (`PATCH /api/v1/utilitymeters/{id}`).
5. Automatically triggering InfluxDB time-series repopulation (`isChange=1&start=...&stop=...`).

```
┌─────────────────────────┐
│   CSV Tag Mapping File  │
└────────────┬────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────┐
│     UMS Multi-Tag & Influx Repopulation Studio (UI)     │
│   (Dry Run Validation & Tag Tree Deduplication Engine) │
└────────────┬────────────────────────────┬──────────────┘
             │                            │
             ▼                            ▼
┌─────────────────────────┐  ┌───────────────────────────┐
│     UMS REST API        │  │     InfluxDB Backfill     │
│ (Tags & Meter Updates)  │  │ (Historical Data Series)  │
└─────────────────────────┘  └───────────────────────────┘
```

---

## 2. Quick Start & Setup

### Cloning & Running from GitHub
```bash
# Clone the repository
git clone https://github.com/your-org/ums-tagging-repopulation-studio.git
cd ums-tagging-repopulation-studio

# Start the server (Windows)
.\run_ui.bat

# Or run directly via Python (Cross-platform)
python ui_server.py
```

Once started, open your web browser at:
👉 **`http://127.0.0.1:8080`**

---

## 3. CSV File Requirements

The application expects a CSV file containing 3 required columns:

| Column Header | Description | Example |
| :--- | :--- | :--- |
| **`MeterName`** | The Meter Display Name or unique GUID in UMS | `EM-1121 MCHW-FWU-22-01104` |
| **`MainTag`** | The root tag category / namespace | `test-tag-version-1` |
| **`taghierachy`** | The full hierarchical path under MainTag | `test-tag-version-1/test-tag-5` |

### Sample CSV Structure (`meter_tags_sample.csv`):
```csv
MeterName,MainTag,taghierachy
EM-1121 MCHW-FWU-22-01104,test-tag-version-1,test-tag-version-1/test-tag-5
EM-1121 MCHW-FWU-22-01104,testing,testing/testtag-4
EM-1074 TX-E-01002,test-tag-version-1,test-tag-version-1/test-tag-6
```
> **Multi-Tag Support:** If the same meter appears on multiple rows with different tags, the engine automatically groups them together into a single merged tag payload.

---

## 4. UI Step-by-Step Workflow

### Step 1: Connection Settings
1. **Base URL:** Enter the UMS API endpoint (e.g., `https://api-ums.iviva.com`).
2. **Iviva Account:** Enter your Iviva account identifier.
3. **API Token:** Provide the bearer token or API key for authentication.
4. Click **Test Connection** to ensure credentials and connectivity are valid.

### Step 2: Upload & Preview CSV
1. Click **Choose File** or drag-and-drop your CSV file.
2. Click **Preview CSV** to view grouped meters, total count, and assigned tags.

### Step 3: Configure InfluxDB Repopulation Settings
* **Trigger Influx Repopulate (`isChange=1`):** Enabled by default to trigger historical data backfill.
* **Repopulate Start Time (UTC):** ISO 8601 start timestamp (e.g. `2026-05-31T18:30:00.000Z`).
* **Repopulate Stop Time (UTC):** ISO 8601 stop timestamp (e.g. Current UTC time).

### Step 4: Dry Run vs Live Execution
* **Start Dry Run (Recommended First):**
  - Verifies tag hierarchies and matches all CSV meter names against UMS.
  - Zero modifications are made to the live system.
* **Start Live Execution:**
  - Creates any missing tag nodes in UMS.
  - Merges new tags with existing meter tags.
  - Sends PATCH requests and triggers InfluxDB repopulation.

---

## 5. REST Endpoints Summary

| Action | Method | Endpoint | Query / Payload Parameters |
| :--- | :--- | :--- | :--- |
| **Get Tags** | `GET` | `/api/v1/tags` | Retrieves the current UMS tag hierarchy |
| **Create Tag** | `POST` | `/api/v1/tags` | `{"name": "...", "parentTag": "..."}` |
| **Fetch Meters** | `GET` | `/api/v1/utilitymeters` | `?limit=1000&account=...` |
| **Patch & Backfill** | `PATCH` | `/api/v1/utilitymeters/{id}` | `?isChange=1&start=...&stop=...`<br/>`{"tags": [...]}` |

---

## 6. Safety & Best Practices
1. **Always run a Dry Run first** to confirm 100% meter matching and catch typo errors in meter names.
2. **Non-Destructive Tag Merging:** The engine reads existing tags from each meter and appends new tags without removing pre-existing tags (such as `energy/cooling`, `location`, `ghg`).
3. **Log History:** Real-time console logs can be copied to your clipboard using the **Copy Logs** button at any time.
