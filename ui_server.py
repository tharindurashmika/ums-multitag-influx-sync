"""
==============================================================================
UMS Tagging & Influx Repopulation Web Server
Lightweight, zero-dependency local server powering the Interactive Web UI.
==============================================================================
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
import json
import csv
import re
import os
import sys
import threading
import time
import datetime

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

# Global Log Buffer for real-time log streaming
_log_queue = []
_log_lock = threading.Lock()
_active_task_running = False

def add_log(level, message, details=None):
    """Adds a log entry with timestamp and level."""
    entry = {
        "id": int(time.time() * 1000),
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "level": level.upper(),  # INFO, SUCCESS, WARN, ERROR, PROGRESS
        "message": message,
        "details": details
    }
    with _log_lock:
        _log_queue.append(entry)
        if len(_log_queue) > 2000:
            _log_queue.pop(0)
    print(f"[{entry['time']}] [{entry['level']}] {message}")


def clear_logs():
    with _log_lock:
        _log_queue.clear()


# ==============================================================================
# UMS API CLIENT
# ==============================================================================
class UmsClient:
    def __init__(self, base_url, account, api_token):
        self.base_url = base_url.rstrip('/')
        self.account = account.strip() if account else ""
        self.api_token = api_token.strip() if api_token else ""

    def request(self, endpoint, method="GET", payload=None, query=None, timeout=30):
        ep = "/" + endpoint.lstrip("/")
        url = self.base_url + ep
        if query:
            clean_q = {k: str(v) for k, v in query.items() if v is not None}
            query_str = urllib.parse.urlencode(clean_q)
            url += ("?" if "?" not in url else "&") + query_str

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.account:
            headers["X-IVIVA-ACCOUNT"] = self.account
        if self.api_token:
            if self.api_token.startswith("SC:"):
                headers["Authorization"] = self.api_token
                headers["apiKey"] = self.api_token
            else:
                headers["Authorization"] = "Bearer " + self.api_token

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise Exception(f"HTTP {e.code} {e.reason}: {err_body}")
        except Exception as e:
            raise e


# ==============================================================================
# TAGGING & REPOPULATION LOGIC
# ==============================================================================
def normalize_identifier(val):
    if not val:
        return ""
    s = str(val).strip()
    s = s.replace('\xa0', ' ').replace('\u2013', '-').replace('\u2014', '-')
    return " ".join(s.split()).lower()

def normalize_alphanumeric(val):
    if not val:
        return ""
    norm = normalize_identifier(val)
    return re.sub(r'[^a-z0-9]', '', norm)

def parse_csv_content(csv_text):
    lines = [line.strip() for line in csv_text.splitlines() if line.strip()]
    if not lines:
        return []

    reader = list(csv.reader(lines))
    if not reader:
        return []

    header = [h.strip().lower() for h in reader[0]]
    meter_col = -1
    main_tag_col = -1
    hierarchy_col = -1

    for idx, col in enumerate(header):
        if col in ['metername', 'meter_name', 'meter', 'meterid', 'displayname']:
            meter_col = idx
        elif col in ['maintag', 'main_tag', 'tagtype', 'type', 'category']:
            main_tag_col = idx
        elif col in ['taghierachy', 'taghierarchy', 'tag_hierarchy', 'hierarchy', 'tagpath', 'tag']:
            hierarchy_col = idx

    if meter_col == -1: meter_col = 0
    if main_tag_col == -1: main_tag_col = 1
    if hierarchy_col == -1: hierarchy_col = 2

    grouped_meters = {}
    total_rows = 0

    for row_idx, row in enumerate(reader[1:], start=2):
        if not row or len(row) <= max(meter_col, main_tag_col, hierarchy_col):
            continue
        
        meter_name = row[meter_col].strip()
        main_tag = row[main_tag_col].strip()
        hierarchy = row[hierarchy_col].strip()

        if not meter_name or not main_tag or not hierarchy:
            continue

        # Format canonical path
        path_clean = hierarchy.replace('\\', '/')
        if not path_clean.lower().startswith(main_tag.lower() + '/') and path_clean.lower() != main_tag.lower():
            canonical_path = main_tag + '/' + path_clean
        else:
            canonical_path = path_clean

        key = meter_name.lower()
        if key not in grouped_meters:
            grouped_meters[key] = {
                'displayName': meter_name,
                'tags': {}
            }
        grouped_meters[key]['tags'][main_tag] = canonical_path
        total_rows += 1

    return grouped_meters


def execute_tagging_process(config, is_dry_run=False):
    global _active_task_running
    _active_task_running = True
    try:
        add_log("INFO", f"=== Starting {'DRY RUN' if is_dry_run else 'LIVE EXECUTION'} ===")
        add_log("INFO", f"Target UMS Base URL: {config['baseUrl']}")
        add_log("INFO", f"Iviva Account: {config.get('account', 'N/A')}")
        
        client = UmsClient(config["baseUrl"], config.get("account", ""), config.get("apiToken", ""))
        
        # Step 1: Pre-load existing tags
        add_log("PROGRESS", "Step 1/4: Fetching existing UMS tags...", {"progress": 10})
        tag_cache = {}
        try:
            tags = client.request("/api/v1/tags") or []
            for t in tags:
                t_type = str(t.get('type', '')).lower()
                t_path = str(t.get('path', '')).lower()
                t_id = str(t.get('id', ''))
                if t_type and t_path:
                    tag_cache[(t_type, t_path)] = t_id
            add_log("SUCCESS", f"Loaded {len(tag_cache)} existing tag(s) from UMS.")
        except Exception as e:
            add_log("WARN", f"Notice loading existing tags: {str(e)}")

        # Step 2: Parse CSV
        add_log("PROGRESS", "Step 2/4: Reading and grouping meter tags...", {"progress": 25})
        csv_data = config.get("csvData", "")
        if not csv_data and config.get("csvPath"):
            try:
                with open(config["csvPath"], "r", encoding="utf-8", errors="ignore") as f:
                    csv_data = f.read()
            except Exception as e:
                add_log("ERROR", f"Failed to read CSV from path {config['csvPath']}: {str(e)}")
                return

        grouped_meters = parse_csv_content(csv_data)
        if not grouped_meters:
            add_log("ERROR", "No valid meter records found in CSV. Aborting.")
            return

        add_log("SUCCESS", f"Identified {len(grouped_meters)} unique meter configuration(s) from CSV.")

        # Ensure all tag hierarchies exist in UMS (unless dry run)
        if not is_dry_run:
            add_log("INFO", "Registering any missing hierarchical tag nodes in UMS...")
            for meter_key, item in grouped_meters.items():
                for main_tag, hierarchy_path in item['tags'].items():
                    segments = [s.strip() for s in hierarchy_path.split('/') if s.strip()]
                    current_path = ""
                    parent_id = None
                    for i, seg in enumerate(segments):
                        current_path = seg if i == 0 else current_path + '/' + seg
                        cache_key = (main_tag.lower(), current_path.lower())
                        if cache_key in tag_cache:
                            parent_id = tag_cache[cache_key]
                            continue

                        # Create tag
                        tag_payload = {
                            "name": seg,
                            "type": main_tag,
                            "path": current_path,
                            "parentTagId": parent_id,
                            "baselines": {},
                            "baselineConfigs": {}
                        }
                        try:
                            res = client.request("/api/v1/tags", method="POST", payload=tag_payload)
                            created_id = res.get("id") if isinstance(res, dict) else None
                            add_log("SUCCESS", f"Created Tag: '{seg}' (Type: {main_tag}, Path: {current_path})")
                            tag_cache[cache_key] = created_id
                            parent_id = created_id
                        except Exception as e:
                            if "already exists" in str(e).lower():
                                pass
                            else:
                                add_log("WARN", f"Notice on tag creation '{current_path}': {str(e)}")

        # Step 3: Fetch all UMS Meters with pagination
        add_log("PROGRESS", "Step 3/4: Fetching registered meters from UMS...", {"progress": 45})
        all_ums_meters = []
        limit = 500
        offset = 0
        while True:
            try:
                batch = client.request("/api/v1/utilitymeters", query={"limit": limit, "offset": offset})
                if not batch or not isinstance(batch, list):
                    break
                all_ums_meters.extend(batch)
                if len(batch) < limit:
                    break
                offset += limit
            except Exception as e:
                add_log("ERROR", f"Error fetching meters batch at offset {offset}: {str(e)}")
                break

        add_log("SUCCESS", f"Retrieved {len(all_ums_meters)} total meter(s) from UMS platform.")

        # Build multi-attribute lookup index
        lookup = {}
        for m in all_ums_meters:
            can_id = str(m.get('meterId') or m.get('id') or '')
            if not can_id:
                continue
            m['_canonical_id'] = can_id
            candidates = [
                m.get('meterId'), m.get('umsServiceId'), m.get('id'), m.get('_id'),
                m.get('name'), m.get('displayName'), m.get('externalId'),
                m.get('assetKey'), m.get('meterKey'), m.get('code')
            ]
            for c in candidates:
                if c:
                    norm = normalize_identifier(c)
                    if norm: lookup[norm] = m
                    alpha = normalize_alphanumeric(c)
                    if alpha: lookup[alpha] = m

        # Match and apply tags
        add_log("PROGRESS", "Matching meters and updating tags...", {"progress": 65})
        matched_count = 0
        unmatched = []

        for idx, (raw_key, item) in enumerate(grouped_meters.items(), start=1):
            norm_k = normalize_identifier(raw_key)
            alpha_k = normalize_alphanumeric(raw_key)
            meter_obj = lookup.get(norm_k) or lookup.get(alpha_k)

            # Direct fallback query if not in local cache
            if not meter_obj:
                try:
                    direct_res = client.request("/api/v1/utilitymeters", query={"query": item['displayName'], "limit": 5})
                    if direct_res and isinstance(direct_res, list) and len(direct_res) > 0:
                        meter_obj = direct_res[0]
                        meter_obj['_canonical_id'] = str(meter_obj.get('meterId') or meter_obj.get('id') or '')
                except Exception:
                    pass

            if meter_obj and meter_obj.get('_canonical_id'):
                real_id = meter_obj['_canonical_id']
                m_display = str(meter_obj.get('displayName') or meter_obj.get('name') or real_id)
                new_tags = item['tags']

                existing_tags = meter_obj.get('tags') or {}
                merged_tags = dict(existing_tags)
                merged_tags.update(new_tags)

                tags_summary = ", ".join([f"{k}: '{v}'" for k, v in merged_tags.items()])
                add_log("INFO", f"[{idx}/{len(grouped_meters)}] Matched '{m_display}' (ID: {real_id}) -> Tags: [{tags_summary}]")

                if not is_dry_run:
                    patch_payload = {'tags': merged_tags}
                    if meter_obj.get('description'):
                        patch_payload['description'] = meter_obj['description']
                    elif m_display:
                        patch_payload['description'] = m_display
                    if meter_obj.get('meterType'):
                        patch_payload['meterType'] = meter_obj['meterType']

                    patch_query = None
                    if config.get("triggerInfluxRepopulate", True):
                        start_ts = config.get("repopulateStart") or "2026-05-31T18:30:00.000Z"
                        stop_ts = config.get("repopulateStop") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                        patch_query = {
                            "isChange": str(config.get("repopulateIsChange", 1)),
                            "start": start_ts,
                            "stop": stop_ts
                        }

                    try:
                        client.request(f"/api/v1/utilitymeters/{real_id}", method="PATCH", payload=patch_payload, query=patch_query)
                        add_log("SUCCESS", f"  -> Patched & Influx repopulate triggered for '{m_display}'")
                    except Exception as e:
                        add_log("ERROR", f"  -> Failed to patch meter {real_id}: {str(e)}")

                matched_count += 1
            else:
                unmatched.append(item['displayName'])
                add_log("WARN", f"[{idx}/{len(grouped_meters)}] Meter '{item['displayName']}' in CSV was NOT found in UMS.")

        add_log("INFO", f"Summary: Successfully matched {matched_count} of {len(grouped_meters)} meter(s).")
        if unmatched:
            add_log("WARN", f"Unmatched meters ({len(unmatched)}): {', '.join(unmatched[:10])}{' ...' if len(unmatched) > 10 else ''}")

        # Step 4: Repopulate / Recalculate Rollups
        if not is_dry_run:
            add_log("PROGRESS", "Step 4/4: Triggering UMS analytics rollups...", {"progress": 90})
            if config.get("clearCache", True):
                try:
                    client.request("/api/v1/locations/cache")
                    add_log("SUCCESS", "Cleared UMS location & meter caches.")
                except Exception as e:
                    add_log("WARN", f"Cache clear notice: {str(e)}")

            if config.get("triggerAnalyticsRollup", True):
                try:
                    client.request("/api/v1/analytics/trigger/24h")
                    add_log("SUCCESS", "Triggered 24h analytics rollup job.")
                    client.request("/api/v1/analytics/trigger/30d")
                    add_log("SUCCESS", "Triggered 30d analytics rollup job.")
                except Exception as e:
                    add_log("WARN", f"Analytics trigger notice: {str(e)}")

        add_log("PROGRESS", "Completed!", {"progress": 100})
        add_log("SUCCESS", f"=== {'DRY RUN COMPLETED' if is_dry_run else 'ALL OPERATIONS COMPLETED SUCCESSFULLY!'} ===")

    except Exception as e:
        add_log("ERROR", f"Fatal execution error: {str(e)}")
    finally:
        _active_task_running = False


# ==============================================================================
# HTTP REQUEST HANDLER
# ==============================================================================
class WebUIRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        url_parsed = urllib.parse.urlparse(self.path)
        if url_parsed.path == "/api/status":
            self.send_json_response({
                "status": "online",
                "running": _active_task_running,
                "serverTime": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
            return
        elif url_parsed.path == "/api/stream-logs":
            with _log_lock:
                logs_snapshot = list(_log_queue)
            self.send_json_response({
                "logs": logs_snapshot,
                "running": _active_task_running
            })
            return
        elif url_parsed.path == "/api/clear-logs":
            clear_logs()
            self.send_json_response({"success": True})
            return

        # Serve static web files
        return super().do_GET()

    def do_POST(self):
        url_parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if url_parsed.path == "/api/test-connection":
            base_url = data.get("baseUrl", "")
            account = data.get("account", "")
            api_token = data.get("apiToken", "")
            if not base_url:
                self.send_json_response({"success": False, "error": "Base URL is required."}, status=400)
                return
            try:
                client = UmsClient(base_url, account, api_token)
                res = client.request("/api/v1/utilitymeters", query={"limit": 1})
                self.send_json_response({
                    "success": True,
                    "message": "Connection to UMS successful! API responded correctly."
                })
            except Exception as e:
                self.send_json_response({
                    "success": False,
                    "error": str(e)
                }, status=200)
            return

        elif url_parsed.path == "/api/preview-csv":
            csv_content = data.get("csvData", "")
            csv_path = data.get("csvPath", "")
            if not csv_content and csv_path:
                try:
                    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                        csv_content = f.read()
                except Exception as e:
                    self.send_json_response({"success": False, "error": f"Failed to read file from path: {str(e)}"}, status=400)
                    return

            if not csv_content:
                self.send_json_response({"success": False, "error": "No CSV content provided."}, status=400)
                return

            grouped = parse_csv_content(csv_content)
            rows = []
            for k, v in grouped.items():
                rows.append({
                    "meter": v["displayName"],
                    "tags": v["tags"]
                })

            self.send_json_response({
                "success": True,
                "totalMeters": len(rows),
                "data": rows
            })
            return

        elif url_parsed.path == "/api/run":
            global _active_task_running
            if _active_task_running:
                self.send_json_response({"success": False, "error": "A task is already running in background."}, status=400)
                return

            clear_logs()
            is_dry_run = bool(data.get("isDryRun", False))
            threading.Thread(target=execute_tagging_process, args=(data, is_dry_run), daemon=True).start()
            self.send_json_response({
                "success": True,
                "message": f"{'Dry Run' if is_dry_run else 'Repopulation'} process started successfully."
            })
            return

        self.send_json_response({"error": "Endpoint not found"}, status=404)

    def send_json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def run_server():
    os.makedirs(WEB_DIR, exist_ok=True)
    with socketserver.TCPServer(("", PORT), WebUIRequestHandler) as httpd:
        print("==================================================================")
        print(f"  UMS TAGGING & REPOPULATION UI SERVER STARTED")
        print(f"  Open in Browser: http://127.0.0.1:{PORT}")
        print("==================================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer shutting down gracefully.")


if __name__ == "__main__":
    run_server()
