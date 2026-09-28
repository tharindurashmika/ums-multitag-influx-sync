/**
 * UMS Multi-Tag & Influx Repopulation Studio
 * Frontend Application Logic
 */

let csvRawContent = "";
let isTaskRunning = false;
let logPollInterval = null;
let lastLogCount = 0;

// On Page Load
document.addEventListener("DOMContentLoaded", () => {
    checkServerStatus();
    setupDropzone();
    // Pre-load default CSV if available
    loadCsvFromPath();
    // Start periodic log polling
    startLogPolling();
});

// Server Status Check
async function checkServerStatus() {
    const badge = document.getElementById("serverStatusBadge");
    const text = document.getElementById("serverStatusText");
    try {
        const res = await fetch("/api/status");
        if (res.ok) {
            const data = await res.json();
            text.innerText = "Server Online (Port 8080)";
            badge.style.background = "rgba(16, 185, 129, 0.1)";
            badge.style.color = "#10B981";
        }
    } catch (e) {
        text.innerText = "Server Offline";
        badge.style.background = "rgba(239, 68, 68, 0.1)";
        badge.style.color = "#EF4444";
    }
}

// Preset Handlers
function setPresetUrl(url) {
    document.getElementById("baseUrlInput").value = url;
}

function toggleTokenVisibility() {
    const input = document.getElementById("apiTokenInput");
    input.type = input.type === "password" ? "text" : "password";
}

// Test UMS Connection
async function testConnection() {
    const btn = document.getElementById("testConnBtn");
    const resBadge = document.getElementById("connResult");
    const baseUrl = document.getElementById("baseUrlInput").value.trim();
    const account = document.getElementById("accountInput").value.trim();
    const apiToken = document.getElementById("apiTokenInput").value.trim();

    if (!baseUrl) {
        alert("Please enter a UMS Base URL.");
        return;
    }

    btn.disabled = true;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg> Testing...`;
    resBadge.className = "conn-result-badge hidden";

    try {
        const res = await fetch("/api/test-connection", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ baseUrl, account, apiToken })
        });
        const data = await res.json();
        resBadge.classList.remove("hidden");
        if (data.success) {
            resBadge.className = "conn-result-badge success";
            resBadge.innerText = "✓ Connected Successfully";
            addTerminalLine("SUCCESS", "Connection to UMS verified: " + data.message);
        } else {
            resBadge.className = "conn-result-badge error";
            resBadge.innerText = "✗ Connection Failed";
            addTerminalLine("ERROR", "UMS connection failed: " + (data.error || "Unknown error"));
        }
    } catch (e) {
        resBadge.classList.remove("hidden");
        resBadge.className = "conn-result-badge error";
        resBadge.innerText = "✗ Server unreachable";
        addTerminalLine("ERROR", "Server unreachable: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> Test UMS Connection`;
    }
}

// Drag & Drop Handling
function setupDropzone() {
    const dropZone = document.getElementById("dropZone");
    ['dragenter', 'dragover'].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });
    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            processSelectedFile(files[0]);
        }
    });
}

function handleFileSelected(event) {
    const file = event.target.files[0];
    if (file) {
        processSelectedFile(file);
    }
}

function processSelectedFile(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        csvRawContent = e.target.result;
        previewCsvData(csvRawContent, file.name);
    };
    reader.readAsText(file);
}

// Load CSV from Server Path
async function loadCsvFromPath() {
    const path = document.getElementById("csvPathInput").value.trim();
    if (!path) return;
    try {
        const res = await fetch("/api/preview-csv", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ csvPath: path })
        });
        const data = await res.json();
        if (data.success) {
            renderPreviewTable(data.data, path.split('\\').pop().split('/').pop());
        }
    } catch (e) {
        console.warn("Could not pre-load CSV from path:", e);
    }
}

// Load Sample CSV Preset
function loadSampleCsv() {
    const sample = `MeterName,MainTag,taghierachy
MTR-AHU-01,energy,energy/it load
MTR-AHU-01,system,system/ups-in
MTR-AHU-01,tenant,tenant/tenant 1
MTR-AHU-02,energy,energy/it load
MTR-AHU-02,system,system/ups-out
MTR-CHILLER-01,energy,energy/cooling
MTR-CHILLER-01,system,system/chilled-water`;
    csvRawContent = sample;
    previewCsvData(sample, "meter_tags_sample.csv");
}

async function previewCsvData(content, fileName) {
    try {
        const res = await fetch("/api/preview-csv", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ csvData: content })
        });
        const data = await res.json();
        if (data.success) {
            renderPreviewTable(data.data, fileName);
            addTerminalLine("INFO", `Loaded CSV '${fileName}': Detected ${data.totalMeters} unique meter(s).`);
        } else {
            alert("Failed to parse CSV: " + (data.error || ""));
        }
    } catch (e) {
        alert("Error parsing CSV: " + e.message);
    }
}

function renderPreviewTable(meters, fileName) {
    const previewSection = document.getElementById("csvPreviewSection");
    const countBadge = document.getElementById("previewCountBadge");
    const tbody = document.getElementById("previewTableBody");
    const metricMeters = document.getElementById("metricCsvMeters");

    previewSection.classList.remove("hidden");
    countBadge.innerText = `${meters.length} Unique Meter(s) (${fileName})`;
    metricMeters.innerText = meters.length;

    tbody.innerHTML = "";
    meters.forEach(m => {
        const tr = document.createElement("tr");
        const categories = Object.keys(m.tags).join(", ");
        const tagBadges = Object.entries(m.tags).map(([k, v]) => `<span class="tag-badge">${v}</span>`).join(" ");
        tr.innerHTML = `
            <td><strong>${escapeHtml(m.meter)}</strong></td>
            <td>${escapeHtml(categories)}</td>
            <td>${tagBadges}</td>
        `;
        tbody.appendChild(tr);
    });
}

function togglePreviewTable() {
    const tableContainer = document.getElementById("previewTableContainer");
    tableContainer.classList.toggle("hidden");
}

// Date Range Presets
function setStartDatePreset(val) {
    document.getElementById("startDateInput").value = val;
}

function setStartDateDaysAgo(days) {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - days);
    d.setUTCHours(18, 30, 0, 0);
    document.getElementById("startDateInput").value = d.toISOString();
}

function toggleDynamicNow() {
    const check = document.getElementById("useDynamicNowCheck");
    const input = document.getElementById("stopDateInput");
    if (check.checked) {
        input.disabled = true;
        input.value = "";
        input.placeholder = "Auto: Current UTC Timestamp (Now)";
    } else {
        input.disabled = false;
        input.value = new Date().toISOString();
    }
}

function toggleInfluxOptions() {
    const check = document.getElementById("triggerInfluxCheck");
    const container = document.getElementById("influxOptionsContainer");
    container.style.opacity = check.checked ? "1" : "0.4";
    container.style.pointerEvents = check.checked ? "auto" : "none";
}

// Start Execution (Dry Run or Live)
async function startExecution(isDryRun) {
    if (isTaskRunning) {
        alert("A task is already currently running!");
        return;
    }

    const baseUrl = document.getElementById("baseUrlInput").value.trim();
    const account = document.getElementById("accountInput").value.trim();
    const apiToken = document.getElementById("apiTokenInput").value.trim();
    const csvPath = document.getElementById("csvPathInput").value.trim();
    
    if (!baseUrl) {
        alert("Please specify the UMS Base URL.");
        return;
    }

    let startTs = document.getElementById("startDateInput").value.trim();
    let stopTs = document.getElementById("useDynamicNowCheck").checked ? null : document.getElementById("stopDateInput").value.trim();

    const payload = {
        baseUrl: baseUrl,
        account: account,
        apiToken: apiToken,
        csvData: csvRawContent,
        csvPath: csvPath,
        isDryRun: isDryRun,
        triggerInfluxRepopulate: document.getElementById("triggerInfluxCheck").checked,
        repopulateIsChange: 1,
        repopulateStart: startTs,
        repopulateStop: stopTs,
        clearCache: document.getElementById("clearCacheCheck").checked,
        triggerAnalyticsRollup: document.getElementById("triggerRollupsCheck").checked
    };

    setExecutionUiState(true, isDryRun);

    try {
        const res = await fetch("/api/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!data.success) {
            alert("Execution could not start: " + (data.error || ""));
            setExecutionUiState(false);
        }
    } catch (e) {
        alert("Failed to start process: " + e.message);
        setExecutionUiState(false);
    }
}

function setExecutionUiState(running, isDryRun = false) {
    isTaskRunning = running;
    document.getElementById("dryRunBtn").disabled = running;
    document.getElementById("runRepopulateBtn").disabled = running;
    const metricStatus = document.getElementById("metricStatus");
    if (running) {
        metricStatus.innerText = isDryRun ? "Dry Run Running..." : "Repopulating...";
        metricStatus.style.color = "#6366F1";
    } else {
        metricStatus.innerText = "Idle / Finished";
        metricStatus.style.color = "#94A3B8";
    }
}

// Real-time Log Streaming & Terminal
function startLogPolling() {
    if (logPollInterval) clearInterval(logPollInterval);
    logPollInterval = setInterval(async () => {
        try {
            const res = await fetch("/api/stream-logs");
            if (res.ok) {
                const data = await res.json();
                renderLogs(data.logs);
                if (isTaskRunning && !data.running) {
                    setExecutionUiState(false);
                }
            }
        } catch (e) {
            // silent fail during network blip
        }
    }, 10000);
}

function renderLogs(logs) {
    if (!logs || logs.length === lastLogCount) return;
    const terminal = document.getElementById("terminalOutput");
    const autoScroll = document.getElementById("autoScrollCheck").checked;
    const progressBar = document.getElementById("progressBarFill");
    const metricMatched = document.getElementById("metricMatched");

    // Clear initial greeting if real logs arrive
    if (lastLogCount === 0 && logs.length > 0) {
        terminal.innerHTML = "";
    }

    let matchedCounter = 0;

    for (let i = lastLogCount; i < logs.length; i++) {
        const log = logs[i];
        const line = document.createElement("div");
        const levelClass = log.level.toLowerCase();
        line.className = `terminal-line ${levelClass}`;
        line.innerHTML = `<span class="ts">[${log.time}]</span> ${escapeHtml(log.message)}`;
        terminal.appendChild(line);

        if (log.details && log.details.progress !== undefined) {
            progressBar.style.width = `${log.details.progress}%`;
        }

        if (log.message && log.message.includes("Matched '")) {
            matchedCounter++;
        }
    }

    lastLogCount = logs.length;
    if (matchedCounter > 0) {
        metricMatched.innerText = matchedCounter;
    }

    if (autoScroll) {
        terminal.scrollTop = terminal.scrollHeight;
    }
}

function addTerminalLine(level, msg) {
    const terminal = document.getElementById("terminalOutput");
    const line = document.createElement("div");
    const time = new Date().toTimeString().split(' ')[0];
    line.className = `terminal-line ${level.toLowerCase()}`;
    line.innerHTML = `<span class="ts">[${time}]</span> ${escapeHtml(msg)}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function clearConsole() {
    document.getElementById("terminalOutput").innerHTML = "";
    lastLogCount = 0;
    fetch("/api/clear-logs");
}

function copyConsoleLogs() {
    const text = document.getElementById("terminalOutput").innerText;
    navigator.clipboard.writeText(text).then(() => {
        alert("Logs copied to clipboard!");
    });
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
