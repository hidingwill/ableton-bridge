/**
 * AbletonMCP Beta — M4L Bridge — m4l_bridge.js
 *
 * This script runs inside a Max for Live [js] object and provides
 * deep Live Object Model (LOM) access for the AbletonMCP Beta server.
 *
 * Communication uses native OSC messages via udpreceive/udpsend:
 *   - The MCP server sends OSC messages like /ping, /discover_params, etc.
 *   - Max's udpreceive parses OSC and sends the address + args to this [js]
 *   - Responses are base64-encoded JSON sent back via outlet → udpsend
 *
 * The Max patch needs:
 *   [udpreceive 9878] → [js m4l_bridge.js] → [udpsend 127.0.0.1 9879]
 */

// Max [js] object configuration
inlets  = 1;
outlets = 1;

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
function loadbang() {
    post("AbletonMCP Beta M4L Bridge v3.6.0 starting...\n");
    post("Listening for OSC commands on port 9878.\n");
    post("Dashboard: http://127.0.0.1:9880\n");
}

// ---------------------------------------------------------------------------
// OSC message routing
//
// Max's udpreceive outputs OSC addresses as message names to the [js] object.
// The OSC address "/ping" arrives with messagename = "/ping" (with slash).
// Since "/ping" is not a valid JS function name, everything lands in
// anything(). We route based on messagename.
// ---------------------------------------------------------------------------
function anything() {
    var args = arrayfromargs(arguments);
    var addr = messagename;

    // Strip leading slash if present (Max keeps it from OSC addresses)
    var cmd = addr;
    if (cmd.charAt(0) === "/") {
        cmd = cmd.substring(1);
    }

    switch (cmd) {

        case "ping":
            handlePing(args);
            break;

        case "discover_params":
            handleDiscoverParams(args);
            break;

        case "get_hidden_params":
            handleGetHiddenParams(args);
            break;

        case "set_hidden_param":
            handleSetHiddenParam(args);
            break;

        case "batch_set_hidden_params":
            handleBatchSetHiddenParams(args);
            break;

        case "check_dashboard":
            handleCheckDashboard(args);
            break;

        // --- Phase 2: Device Chain Navigation ---
        case "discover_chains":
            handleDiscoverChains(args);
            break;

        case "get_chain_device_params":
            handleGetChainDeviceParams(args);
            break;

        case "set_chain_device_param":
            handleSetChainDeviceParam(args);
            break;

        // --- Phase 3: Simpler/Sample Deep Access ---
        case "get_simpler_info":
            handleGetSimplerInfo(args);
            break;

        case "set_simpler_sample_props":
            handleSetSimplerSampleProps(args);
            break;

        case "simpler_slice":
            handleSimplerSlice(args);
            break;

        // --- Phase 4: Wavetable Modulation ---
        case "get_wavetable_info":
            handleGetWavetableInfo(args);
            break;

        case "set_wavetable_modulation":
            handleSetWavetableModulation(args);
            break;

        case "set_wavetable_props":
            handleSetWavetableProps(args);
            break;

        // --- Diagnostic ---
        case "probe_device_info":
            handleProbeDeviceInfo(args);
            break;

        // --- Device Property Access ---
        case "get_device_property":
            handleGetDeviceProperty(args);
            break;

        case "set_device_property":
            handleSetDeviceProperty(args);
            break;

        // --- Phase 7: Cue Points & Locators ---
        case "get_cue_points":
            handleGetCuePoints(args);
            break;

        case "jump_to_cue_point":
            handleJumpToCuePoint(args);
            break;

        // --- Phase 8: Groove Pool ---
        case "get_groove_pool":
            handleGetGroovePool(args);
            break;

        case "set_groove_properties":
            handleSetGrooveProperties(args);
            break;

        // --- Phase 6: Event-Driven Monitoring ---
        case "observe_property":
            handleObserveProperty(args);
            break;

        case "stop_observing":
            handleStopObserving(args);
            break;

        case "get_observed_changes":
            handleGetObservedChanges(args);
            break;

        // --- Phase 9: Undo-Clean Parameter Control ---
        case "set_param_clean":
            handleSetParamClean(args);
            break;

        // --- Phase 5: Audio Analysis ---
        case "analyze_audio":
            handleAnalyzeAudio(args);
            break;

        case "analyze_spectrum":
            handleAnalyzeSpectrum(args);
            break;

        // --- Cross-Track MSP Analysis (send-based routing) ---
        case "analyze_cross_track":
            handleAnalyzeCrossTrack(args);
            break;

        // --- Phase 10: App Version Detection ---
        case "get_app_version":
            handleGetAppVersion(args);
            break;

        // --- Phase 11: Automation State Introspection ---
        case "get_automation_states":
            handleGetAutomationStates(args);
            break;

        // --- Phase 12: Note Surgery by ID ---
        case "get_clip_notes_by_id":
            handleGetClipNotesById(args);
            break;

        case "modify_clip_notes":
            handleModifyClipNotes(args);
            break;

        case "remove_clip_notes_by_id":
            handleRemoveClipNotesById(args);
            break;

        // --- Phase 13: Chain-Level Mixing ---
        case "get_chain_mixing":
            handleGetChainMixing(args);
            break;

        case "set_chain_mixing":
            handleSetChainMixing(args);
            break;

        // --- Phase 14: Device AB Comparison ---
        case "device_ab_compare":
            handleDeviceAbCompare(args);
            break;

        // --- Phase 15: Clip Scrubbing ---
        case "clip_scrub":
            handleClipScrub(args);
            break;

        // --- Phase 16: Split Stereo Panning ---
        case "get_split_stereo":
            handleGetSplitStereo(args);
            break;

        case "set_split_stereo":
            handleSetSplitStereo(args);
            break;

        default:
            post("AbletonMCP Beta Bridge: unknown command: '" + cmd + "' (raw: '" + addr + "')\n");
            break;
    }
}

// ---------------------------------------------------------------------------
// Command handlers — each receives native OSC-typed arguments
// ---------------------------------------------------------------------------

function handlePing(args) {
    // args: [request_id (string)]
    var requestId = (args.length > 0) ? args[0].toString() : "";
    var response = {
        status: "success",
        result: { m4l_bridge: true, version: "3.6.0" },
        id: requestId
    };
    sendResponse(JSON.stringify(response));
}

// ---------------------------------------------------------------------------
// Phase 10: Application Version Detection
// ---------------------------------------------------------------------------

function handleGetAppVersion(args) {
    // args: [request_id (string)]
    var requestId = (args.length > 0) ? args[0].toString() : "";

    try {
        var app = new LiveAPI(null, "live_app");
        if (!app || !app.id || parseInt(app.id) === 0) {
            sendError("Cannot access live_app object", requestId);
            return;
        }

        var result = {};
        try { result.major = parseInt(app.call("get_major_version")); } catch (e) { result.major = null; }
        try { result.minor = parseInt(app.call("get_minor_version")); } catch (e) { result.minor = null; }
        try { result.bugfix = parseInt(app.call("get_bugfix_version")); } catch (e) { result.bugfix = null; }
        try {
            var vs = app.get("version");
            result.version_string = (vs !== undefined && vs !== null) ? vs.toString() : null;
        } catch (e) { result.version_string = null; }

        // Build display string
        if (result.major !== null && result.minor !== null && result.bugfix !== null) {
            result.display = "Ableton Live " + result.major + "." + result.minor + "." + result.bugfix;
        }

        sendResult(result, requestId);
    } catch (e) {
        sendError("Failed to get app version: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 11: Automation State Introspection
//
// DeviceParameter.automation_state:
//   0 = none (no automation envelope)
//   1 = active (automation present and active)
//   2 = overridden (automation present but manually overridden)
// ---------------------------------------------------------------------------

function handleGetAutomationStates(args) {
    // args: [track_index (int), device_index (int), request_id (string)]
    if (args.length < 3) {
        sendError("get_automation_states requires track_index, device_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[2].toString();

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi = new LiveAPI(null, devicePath);

    if (!_validateApi(deviceApi, requestId, "No device at track " + trackIdx + " device " + deviceIdx)) return;

    var deviceName = "";
    try { deviceName = deviceApi.get("name").toString(); } catch (e) {}
    var deviceClass = "";
    try { deviceClass = deviceApi.get("class_name").toString(); } catch (e) {}

    var paramCount = 0;
    try { paramCount = parseInt(deviceApi.getcount("parameters")); } catch (e) {}

    // Use chunked reading to avoid overloading LiveAPI
    // Read automation_state for all parameters, only include non-zero (has automation)
    var CHUNK_SIZE = 4;
    var automatedParams = [];
    var cursor = new LiveAPI(null, devicePath);

    for (var i = 0; i < paramCount; i++) {
        cursor.goto(devicePath + " parameters " + i);
        if (!cursor.id || parseInt(cursor.id) === 0) continue;

        try {
            var state = parseInt(cursor.get("automation_state"));
            if (state > 0) {
                var paramInfo = {
                    index: i,
                    automation_state: state,
                    state_name: (state === 1) ? "active" : (state === 2) ? "overridden" : "unknown"
                };
                try { paramInfo.name = cursor.get("name").toString(); } catch (e2) {}
                try { paramInfo.value = parseFloat(cursor.get("value")); } catch (e2) {}
                try { paramInfo.min = parseFloat(cursor.get("min")); } catch (e2) {}
                try { paramInfo.max = parseFloat(cursor.get("max")); } catch (e2) {}
                automatedParams.push(paramInfo);
            }
        } catch (e) {
            // Some parameters may not support automation_state — skip silently
        }
    }

    sendResult({
        device_name: deviceName,
        device_class: deviceClass,
        parameter_count: paramCount,
        automated_parameters: automatedParams,
        automated_count: automatedParams.length
    }, requestId);
}

function handleDiscoverParams(args) {
    // args: [track_index (int), device_index (int), request_id (string)]
    if (args.length < 3) {
        sendError("discover_params requires track_index, device_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[2].toString();

    // Use chunked async discovery to avoid crashing Ableton.
    // Synchronous iteration of 40+ params with full readParamInfo() (7 get()
    // calls each) exceeds Max [js] scheduler tolerance and crashes.
    _startChunkedDiscover(trackIdx, deviceIdx, requestId);
}

function handleGetHiddenParams(args) {
    // args: [track_index (int), device_index (int), request_id (string)]
    if (args.length < 3) {
        sendError("get_hidden_params requires track_index, device_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[2].toString();

    _startChunkedDiscover(trackIdx, deviceIdx, requestId);
}

function handleSetHiddenParam(args) {
    // args: [track_index (int), device_index (int), parameter_index (int), value (float), request_id (string)]
    if (args.length < 5) {
        sendError("set_hidden_param requires track_index, device_index, parameter_index, value, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var paramIdx  = parseInt(args[2]);
    var value     = parseFloat(args[3]);
    var requestId = args[4].toString();

    var result = setHiddenParam(trackIdx, deviceIdx, paramIdx, value);
    sendResult(result, requestId);
}

// ---------------------------------------------------------------------------
// Chunked parameter discovery
//
// Reading all parameters for a large device (e.g. Wavetable, 93 params) in a
// single synchronous call crashes Ableton — the Max [js] scheduler can't
// handle ~280+ LiveAPI get() calls without yielding.  Threshold is around
// 30 params × 7 get() calls = ~210 calls.
//
// Solution: process params in small chunks with deferred callbacks between
// them, same pattern as batch_set_hidden_params.
// ---------------------------------------------------------------------------
var DISCOVER_CHUNK_SIZE = 4;    // params per chunk (4 × 7 gets = 28 — well under limit)
var DISCOVER_CHUNK_DELAY = 50;  // ms between chunks

var _discoverState = null;

function _startChunkedDiscover(trackIdx, deviceIdx, requestId) {
    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    _startChunkedDiscoverAtPath(devicePath, requestId);
}

function _startChunkedDiscoverAtPath(devicePath, requestId) {
    if (_discoverState) {
        sendError("Discovery busy - try again shortly", requestId);
        return;
    }

    var cursor = new LiveAPI(null, devicePath);

    if (!cursor || !cursor.id || parseInt(cursor.id) === 0) {
        sendError("No device found at path: " + devicePath, requestId);
        return;
    }

    var deviceName  = cursor.get("name").toString();
    var deviceClass = cursor.get("class_name").toString();
    var paramCount  = parseInt(cursor.getcount("parameters"));

    _discoverState = {
        devicePath:  devicePath,
        deviceName:  deviceName,
        deviceClass: deviceClass,
        paramCount:  paramCount,
        cursor:      cursor,
        idx:         0,
        parameters:  [],
        requestId:   requestId
    };

    // Start processing the first chunk
    _discoverNextChunk();
}

function _discoverNextChunk() {
    if (!_discoverState) return;

    var s = _discoverState;
    try {
        var end = Math.min(s.idx + DISCOVER_CHUNK_SIZE, s.paramCount);

        for (var i = s.idx; i < end; i++) {
            s.cursor.goto(s.devicePath + " parameters " + i);

            if (!s.cursor.id || parseInt(s.cursor.id) === 0) {
                continue;
            }

            var paramInfo = readParamInfo(s.cursor, i);
            s.parameters.push(paramInfo);
        }

        s.idx = end;

        if (s.idx >= s.paramCount) {
            // All chunks done — clean up cursor and send response
            s.cursor.goto(s.devicePath);

            sendResult({
                device_name:     s.deviceName,
                device_class:    s.deviceClass,
                parameter_count: s.parameters.length,
                parameters:      s.parameters
            }, s.requestId);
            _discoverState = null;
        } else {
            // Schedule the next chunk after a short delay
            var t = new Task(_discoverNextChunk);
            t.schedule(DISCOVER_CHUNK_DELAY);
        }
    } catch (e) {
        var rid = s.requestId;
        try { s.cursor.goto(s.devicePath); } catch (ignore) {}
        _discoverState = null;
        sendError("Discovery failed at param " + s.idx + ": " + safeErrorMessage(e), rid);
    }
}

// ---------------------------------------------------------------------------
// Batch set: chunked processing to avoid freezing Ableton
//
// Instead of setting all parameters in one synchronous loop (which can
// crash Ableton when there are 50-90+ params), we process them in small
// chunks with a deferred callback between each chunk.  This yields control
// back to Ableton's main thread so it can update the UI and stay alive.
// ---------------------------------------------------------------------------
var BATCH_CHUNK_SIZE = 6;     // params per chunk — keep small to stay safe
var BATCH_CHUNK_DELAY = 50;   // ms between chunks

// Persistent state for the current batch operation
var _batchState = null;

function handleBatchSetHiddenParams(args) {
    // args: [track_index (int), device_index (int), params_json_b64 (string), request_id (string)]
    if (_batchState) {
        var rid = args.length > 0 ? args[args.length - 1].toString() : "";
        sendError("Batch operation busy - try again shortly", rid);
        return;
    }
    if (args.length < 4) {
        sendError("batch_set_hidden_params requires track_index, device_index, params_json_b64, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);

    // Max's udpreceive may split long OSC string arguments across multiple
    // args.  Reassemble: everything between the two int args and the last
    // arg (request_id) is the base64 payload.
    var requestId = args[args.length - 1].toString();
    var paramsB64 = _reassembleB64(args, 2);
    if (!paramsB64) { sendError("Missing payload data", requestId); return; }

    post("batch_set: args.length=" + args.length + " b64len=" + paramsB64.length + "\n");

    // Decode the base64-encoded JSON parameter array
    var paramsJson;
    try {
        paramsJson = _base64decode(paramsB64);
    } catch (e) {
        sendError("Failed to decode params_json_b64: " + safeErrorMessage(e), requestId);
        return;
    }
    post("batch_set: decoded json len=" + paramsJson.length + "\n");

    var paramsList;
    try {
        paramsList = JSON.parse(paramsJson);
    } catch (e) {
        sendError("Failed to parse params JSON: " + safeErrorMessage(e), requestId);
        return;
    }

    if (!paramsList || !paramsList.length) {
        sendError("params list is empty", requestId);
        return;
    }

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!_validateApi(deviceApi, requestId, "No device found at track " + trackIdx + " device " + deviceIdx)) return;

    // Filter out parameter index 0 ("Device On") to avoid accidentally
    // disabling the device — a common cause of unexpected behavior.
    var safeParams = [];
    var skippedDeviceOn = false;
    for (var i = 0; i < paramsList.length; i++) {
        if (parseInt(paramsList[i].index) === 0) {
            skippedDeviceOn = true;
            continue;
        }
        safeParams.push(paramsList[i]);
    }

    if (safeParams.length === 0) {
        sendResult({
            params_set: 0,
            params_failed: 0,
            total_requested: paramsList.length,
            skipped_device_on: skippedDeviceOn,
            message: "No settable parameters after filtering."
        }, requestId);
        return;
    }

    // Initialize chunked batch state
    // paramCursor: reusable LiveAPI object navigated via goto() — avoids creating
    // N new LiveAPI objects (same fix as discoverParams/discoverChainsAtPath)
    _batchState = {
        devicePath:  devicePath,
        paramsList:  safeParams,
        requestId:   requestId,
        cursor:      0,
        paramCursor: new LiveAPI(null, devicePath),
        okCount:     0,
        failCount:   0,
        errors:      [],
        skippedDeviceOn: skippedDeviceOn,
        totalRequested:  paramsList.length
    };

    // Start processing the first chunk
    _batchProcessNextChunk();
}

function _batchProcessNextChunk() {
    if (!_batchState) return;

    var s = _batchState;

    try {
        var end = Math.min(s.cursor + BATCH_CHUNK_SIZE, s.paramsList.length);

        for (var i = s.cursor; i < end; i++) {
            var paramIdx = parseInt(s.paramsList[i].index);
            var value    = parseFloat(s.paramsList[i].value);

            // Reuse paramCursor via goto() instead of new LiveAPI() per param
            try {
                s.paramCursor.goto(s.devicePath + " parameters " + paramIdx);
            } catch (e) {
                s.errors.push({ index: paramIdx, error: "LiveAPI error: " + e.toString() });
                s.failCount++;
                continue;
            }

            if (!s.paramCursor.id || parseInt(s.paramCursor.id) === 0) {
                s.errors.push({ index: paramIdx, error: "not found" });
                s.failCount++;
                continue;
            }

            try {
                var minVal  = parseFloat(s.paramCursor.get("min"));
                var maxVal  = parseFloat(s.paramCursor.get("max"));
                var clamped = Math.max(minVal, Math.min(maxVal, value));
                s.paramCursor.set("value", clamped);
                s.okCount++;
            } catch (e) {
                s.errors.push({ index: paramIdx, error: e.toString() });
                s.failCount++;
            }
        }

        s.cursor = end;

        if (s.cursor >= s.paramsList.length) {
            // All chunks done — send the response
            var result = {
                params_set:      s.okCount,
                params_failed:   s.failCount,
                total_requested: s.totalRequested
            };
            if (s.skippedDeviceOn) {
                result.skipped_device_on = true;
            }
            // Only include error details (not full results) to keep response small
            if (s.errors.length > 0) {
                result.errors = s.errors;
            }
            sendResult(result, s.requestId);
            _batchState = null;
        } else {
            // Schedule the next chunk after a short delay
            var t = new Task(_batchProcessNextChunk);
            t.schedule(BATCH_CHUNK_DELAY);
        }
    } catch (e) {
        var rid = s ? s.requestId : "";
        _batchState = null;
        sendError("Batch processing failed at cursor " + (s ? s.cursor : "?") + ": " + safeErrorMessage(e), rid);
    }
}

function handleCheckDashboard(args) {
    var requestId = (args.length > 0) ? args[0].toString() : "";
    var response = {
        status: "success",
        result: {
            dashboard_url: "http://127.0.0.1:9880",
            bridge_version: "3.6.0",
            message: "Open the dashboard URL in your browser to view server status"
        },
        id: requestId
    };
    sendResponse(JSON.stringify(response));
}

// ---------------------------------------------------------------------------
// Phase 2: Device Chain Navigation
//
// Racks (Instrument Rack, Audio Effect Rack, Drum Rack) contain chains,
// each chain contains devices. Drum Racks also have drum_pads with chains.
// LOM paths:
//   live_set tracks T devices D chains C
//   live_set tracks T devices D chains C devices CD
//   live_set tracks T devices D drum_pads N chains C devices CD
// ---------------------------------------------------------------------------

function handleDiscoverChains(args) {
    // args: [track_index (int), device_index (int), extra_path (string), request_id (string)]
    // Backward-compatible: if only 3 args, extra_path is empty
    if (args.length < 3) {
        sendError("discover_chains requires track_index, device_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var extraPath = "";
    var requestId;

    if (args.length >= 4) {
        extraPath = args[2].toString();
        requestId = args[3].toString();
    } else {
        requestId = args[2].toString();
    }

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    if (extraPath && extraPath !== "") {
        devicePath = devicePath + " " + extraPath;
    }
    post("discover_chains: path=" + devicePath + "\n");

    var result = discoverChainsAtPath(devicePath);
    sendResult(result, requestId);
}

function discoverChainsAtPath(devicePath) {
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!deviceApi || !deviceApi.id || parseInt(deviceApi.id) === 0) {
        return { error: "No device found at path: " + devicePath };
    }

    var deviceName  = deviceApi.get("name").toString();
    var deviceClass = deviceApi.get("class_name").toString();

    // Check if this device can have chains
    var canHaveChains = false;
    try { canHaveChains = (parseInt(deviceApi.get("can_have_chains")) === 1); } catch (e) {}

    var hasDrumPads = false;
    try { hasDrumPads = (parseInt(deviceApi.get("can_have_drum_pads")) === 1); } catch (e) {}

    if (!canHaveChains) {
        return {
            device_name: deviceName,
            device_class: deviceClass,
            can_have_chains: false,
            has_drum_pads: false,
            message: "This device does not support chains."
        };
    }

    var result = {
        device_name: deviceName,
        device_class: deviceClass,
        can_have_chains: true,
        has_drum_pads: hasDrumPads
    };

    // Reuse 2 LiveAPI cursors via goto() to avoid exhausting Max's object table.
    // Previously created ~193 LiveAPI objects for a 16-pad drum rack; now only 3 total.
    var cursor = new LiveAPI(null, devicePath);
    var innerCursor = new LiveAPI(null, devicePath);

    // Enumerate chains
    var chainCount = 0;
    try { chainCount = parseInt(deviceApi.getcount("chains")); } catch (e) {}

    var chains = [];
    for (var c = 0; c < chainCount; c++) {
        var chainPath = devicePath + " chains " + c;
        cursor.goto(chainPath);
        if (!cursor.id || parseInt(cursor.id) === 0) continue;

        var chainInfo = {
            index: c,
            name: ""
        };
        try { chainInfo.name = cursor.get("name").toString(); } catch (e) {}

        // Enumerate devices in this chain
        var devCount = 0;
        try { devCount = parseInt(cursor.getcount("devices")); } catch (e) {}

        var chainDevices = [];
        for (var d = 0; d < devCount; d++) {
            innerCursor.goto(chainPath + " devices " + d);
            if (!innerCursor.id || parseInt(innerCursor.id) === 0) continue;

            var cdInfo = { index: d, name: "", class_name: "" };
            try { cdInfo.name = innerCursor.get("name").toString(); } catch (e) {}
            try { cdInfo.class_name = innerCursor.get("class_name").toString(); } catch (e) {}
            try { cdInfo.can_have_chains = (parseInt(innerCursor.get("can_have_chains")) === 1); } catch (e) {}
            chainDevices.push(cdInfo);
        }
        chainInfo.devices = chainDevices;
        chainInfo.device_count = chainDevices.length;
        chains.push(chainInfo);
    }
    result.chains = chains;
    result.chain_count = chains.length;

    // Enumerate return chains (Rack-level return chains, e.g. Instrument Rack sends)
    var returnChainCount = 0;
    try { returnChainCount = parseInt(deviceApi.getcount("return_chains")); } catch (e) {}
    if (returnChainCount > 0) {
        var returnChains = [];
        for (var rc = 0; rc < returnChainCount; rc++) {
            var rcPath = devicePath + " return_chains " + rc;
            cursor.goto(rcPath);
            if (!cursor.id || parseInt(cursor.id) === 0) continue;

            var rcInfo = { index: rc, name: "" };
            try { rcInfo.name = cursor.get("name").toString(); } catch (e) {}

            // Enumerate devices in this return chain
            var rcDevCount = 0;
            try { rcDevCount = parseInt(cursor.getcount("devices")); } catch (e) {}
            var rcDevices = [];
            for (var rcd = 0; rcd < rcDevCount; rcd++) {
                innerCursor.goto(rcPath + " devices " + rcd);
                if (!innerCursor.id || parseInt(innerCursor.id) === 0) continue;
                var rcdInfo = { index: rcd, name: "", class_name: "" };
                try { rcdInfo.name = innerCursor.get("name").toString(); } catch (e) {}
                try { rcdInfo.class_name = innerCursor.get("class_name").toString(); } catch (e) {}
                rcDevices.push(rcdInfo);
            }
            rcInfo.devices = rcDevices;
            rcInfo.device_count = rcDevices.length;
            returnChains.push(rcInfo);
        }
        result.return_chains = returnChains;
        result.return_chain_count = returnChains.length;
    }

    // Enumerate drum pads (only if this is a Drum Rack)
    if (hasDrumPads) {
        var drumPads = [];
        var padCount = 0;
        try { padCount = parseInt(deviceApi.getcount("drum_pads")); } catch (e) {}

        for (var p = 0; p < padCount; p++) {
            var padPath = devicePath + " drum_pads " + p;
            cursor.goto(padPath);
            if (!cursor.id || parseInt(cursor.id) === 0) continue;

            // Only include pads that have chains (i.e. have content)
            var padChainCount = 0;
            try { padChainCount = parseInt(cursor.getcount("chains")); } catch (e) {}
            if (padChainCount === 0) continue;

            var padInfo = { index: p, name: "", note: -1, chain_count: padChainCount };
            try { padInfo.name = cursor.get("name").toString(); } catch (e) {}
            try { padInfo.note = parseInt(cursor.get("note")); } catch (e) {}
            try { padInfo.mute = (parseInt(cursor.get("mute")) === 1); } catch (e) {}
            try { padInfo.solo = (parseInt(cursor.get("solo")) === 1); } catch (e) {}
            try { padInfo.in_note = parseInt(cursor.get("in_note")); } catch (e) {}
            try { padInfo.out_note = parseInt(cursor.get("out_note")); } catch (e) {}
            try { padInfo.choke_group = parseInt(cursor.get("choke_group")); } catch (e) {}

            // Get devices in the first chain of this pad
            if (padChainCount > 0) {
                var padChainPath = padPath + " chains 0";
                innerCursor.goto(padChainPath);
                var padDevCount = 0;
                try { padDevCount = parseInt(innerCursor.getcount("devices")); } catch (e) {}
                var padDevices = [];
                for (var pd = 0; pd < padDevCount; pd++) {
                    innerCursor.goto(padChainPath + " devices " + pd);
                    if (!innerCursor.id || parseInt(innerCursor.id) === 0) continue;
                    var pdInfo = { index: pd, name: "", class_name: "" };
                    try { pdInfo.name = innerCursor.get("name").toString(); } catch (e) {}
                    try { pdInfo.class_name = innerCursor.get("class_name").toString(); } catch (e) {}
                    padDevices.push(pdInfo);
                }
                padInfo.devices = padDevices;
            }

            drumPads.push(padInfo);
        }
        result.drum_pads = drumPads;
        result.populated_pad_count = drumPads.length;
    }

    return result;
}

function handleGetChainDeviceParams(args) {
    // args: [track_index, device_index, chain_index, chain_device_index, request_id]
    if (args.length < 5) {
        sendError("get_chain_device_params requires track_index, device_index, chain_index, chain_device_index, request_id", "");
        return;
    }
    var trackIdx      = parseInt(args[0]);
    var deviceIdx     = parseInt(args[1]);
    var chainIdx      = parseInt(args[2]);
    var chainDevIdx   = parseInt(args[3]);
    var requestId     = args[4].toString();

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx
                   + " chains " + chainIdx + " devices " + chainDevIdx;
    // Use chunked discovery — same crash-safe pattern as handleDiscoverParams
    _startChunkedDiscoverAtPath(devicePath, requestId);
}

function handleSetChainDeviceParam(args) {
    // args: [track_index, device_index, chain_index, chain_device_index, param_index, value, request_id]
    if (args.length < 7) {
        sendError("set_chain_device_param requires track_index, device_index, chain_index, chain_device_index, param_index, value, request_id", "");
        return;
    }
    var trackIdx      = parseInt(args[0]);
    var deviceIdx     = parseInt(args[1]);
    var chainIdx      = parseInt(args[2]);
    var chainDevIdx   = parseInt(args[3]);
    var paramIdx      = parseInt(args[4]);
    var value         = parseFloat(args[5]);
    var requestId     = args[6].toString();

    var paramPath = "live_set tracks " + trackIdx + " devices " + deviceIdx
                  + " chains " + chainIdx + " devices " + chainDevIdx
                  + " parameters " + paramIdx;

    var paramApi = new LiveAPI(null, paramPath);
    if (!paramApi || !paramApi.id || parseInt(paramApi.id) === 0) {
        sendError("No parameter found at path: " + paramPath, requestId);
        return;
    }

    try {
        var paramName = paramApi.get("name").toString();
        var minVal    = parseFloat(paramApi.get("min"));
        var maxVal    = parseFloat(paramApi.get("max"));
        var clamped   = Math.max(minVal, Math.min(maxVal, value));
        paramApi.set("value", clamped);
        // NO readback — get() after set() can crash Ableton

        sendResult({
            parameter_name:  paramName,
            parameter_index: paramIdx,
            requested_value: value,
            actual_value:    clamped,
            was_clamped:     (clamped !== value)
        }, requestId);
    } catch (e) {
        sendError("Failed to set chain device parameter: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 3: Simpler / Sample Deep Access
//
// SimplerDevice has a 'sample' child object (LOM Sample) with properties:
//   start_marker, end_marker, file_path, gain, length, sample_rate,
//   slices, slicing_sensitivity, warp_markers, warp_mode, warping, etc.
// Functions: insert_slice, move_slice, remove_slice, clear_slices, reset_slices
// SimplerDevice props: playback_mode, multi_sample_mode, voices
// SimplerDevice funcs: crop, reverse, warp_as, warp_double, warp_half
// ---------------------------------------------------------------------------

function handleGetSimplerInfo(args) {
    // args: [track_index, device_index, request_id]
    if (args.length < 3) {
        sendError("get_simpler_info requires track_index, device_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[2].toString();

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!_validateApi(deviceApi, requestId, "No device found at track " + trackIdx + " device " + deviceIdx)) return;

    var className = "";
    try { className = deviceApi.get("class_name").toString(); } catch (e) {}

    if (className !== "OriginalSimpler") {
        sendError("Device is not a Simpler (class: " + className + ")", requestId);
        return;
    }

    var result = {
        device_name: "",
        device_class: className
    };
    try { result.device_name = deviceApi.get("name").toString(); } catch (e) {}

    // SimplerDevice properties
    try { result.playback_mode = parseInt(deviceApi.get("playback_mode")); } catch (e) {}
    try { result.multi_sample_mode = parseInt(deviceApi.get("multi_sample_mode")); } catch (e) {}
    try { result.pad_slicing = parseInt(deviceApi.get("pad_slicing")); } catch (e) {}
    try { result.retrigger = (parseInt(deviceApi.get("retrigger")) === 1); } catch (e) {}
    try { result.voices = parseInt(deviceApi.get("voices")); } catch (e) {}

    // Sample child
    var samplePath = devicePath + " sample";
    var sampleApi;
    try {
        sampleApi = new LiveAPI(null, samplePath);
    } catch (e) {
        result.sample = null;
        result.message = "No sample loaded";
        sendResult(result, requestId);
        return;
    }

    if (!sampleApi || !sampleApi.id || parseInt(sampleApi.id) === 0) {
        result.sample = null;
        result.message = "No sample loaded";
        sendResult(result, requestId);
        return;
    }

    var sample = {};
    try { sample.file_path         = sampleApi.get("file_path").toString(); } catch (e) {}
    try { sample.length            = parseInt(sampleApi.get("length")); } catch (e) {}
    try { sample.sample_rate       = parseInt(sampleApi.get("sample_rate")); } catch (e) {}
    try { sample.start_marker      = parseInt(sampleApi.get("start_marker")); } catch (e) {}
    try { sample.end_marker        = parseInt(sampleApi.get("end_marker")); } catch (e) {}
    try { sample.gain              = parseFloat(sampleApi.get("gain")); } catch (e) {}
    try { sample.warping           = (parseInt(sampleApi.get("warping")) === 1); } catch (e) {}
    try { sample.warp_mode         = parseInt(sampleApi.get("warp_mode")); } catch (e) {}
    try { sample.slicing_sensitivity = parseFloat(sampleApi.get("slicing_sensitivity")); } catch (e) {}

    // Warp mode name mapping
    var warpModeMap = { 0: "beats", 1: "tones", 2: "texture", 3: "re_pitch", 4: "complex", 5: "complex_pro", 6: "rex" };
    if (sample.warp_mode !== undefined) {
        sample.warp_mode_name = warpModeMap[sample.warp_mode] || "unknown";
    }

    // Read slices
    try {
        var slicesRaw = sampleApi.get("slices");
        if (slicesRaw) {
            var sliceStr = slicesRaw.toString();
            if (sliceStr && sliceStr !== "null" && sliceStr !== "") {
                sample.slices = sliceStr;
            }
        }
    } catch (e) {}

    // Read warp markers
    try {
        var markersRaw = sampleApi.get("warp_markers");
        if (markersRaw) {
            var markerStr = markersRaw.toString();
            if (markerStr && markerStr !== "null" && markerStr !== "") {
                sample.warp_markers = markerStr;
            }
        }
    } catch (e) {}

    // Beats-specific properties
    try { sample.beats_granulation_resolution  = parseInt(sampleApi.get("beats_granulation_resolution")); } catch (e) {}
    try { sample.beats_transient_envelope      = parseInt(sampleApi.get("beats_transient_envelope")); } catch (e) {}
    try { sample.beats_transient_loop_mode     = parseInt(sampleApi.get("beats_transient_loop_mode")); } catch (e) {}
    // Texture-specific
    try { sample.texture_flux       = parseFloat(sampleApi.get("texture_flux")); } catch (e) {}
    try { sample.texture_grain_size = parseFloat(sampleApi.get("texture_grain_size")); } catch (e) {}
    // Tones-specific
    try { sample.tones_grain_size   = parseFloat(sampleApi.get("tones_grain_size")); } catch (e) {}
    // Complex Pro specific
    try { sample.complex_pro_envelope  = parseFloat(sampleApi.get("complex_pro_envelope")); } catch (e) {}
    try { sample.complex_pro_formants  = parseFloat(sampleApi.get("complex_pro_formants")); } catch (e) {}

    result.sample = sample;
    sendResult(result, requestId);
}

function handleSetSimplerSampleProps(args) {
    // args: [track_index, device_index, props_json_b64, request_id]
    if (args.length < 4) {
        sendError("set_simpler_sample_props requires track_index, device_index, props_json_b64, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[args.length - 1].toString();

    // Reassemble b64 payload (Max may split long strings)
    var propsB64 = _reassembleB64(args, 2);
    if (!propsB64) { sendError("Missing payload data", requestId); return; }

    var propsJson;
    try { propsJson = _base64decode(propsB64); } catch (e) {
        sendError("Failed to decode props_json_b64: " + safeErrorMessage(e), requestId);
        return;
    }
    var props;
    try { props = JSON.parse(propsJson); } catch (e) {
        sendError("Failed to parse props JSON: " + safeErrorMessage(e), requestId);
        return;
    }

    var samplePath = "live_set tracks " + trackIdx + " devices " + deviceIdx + " sample";
    var sampleApi;
    try {
        sampleApi = new LiveAPI(null, samplePath);
    } catch (e) {
        sendError("No sample found: " + safeErrorMessage(e), requestId);
        return;
    }

    if (!sampleApi || !sampleApi.id || parseInt(sampleApi.id) === 0) {
        sendError("No sample loaded in Simpler at track " + trackIdx + " device " + deviceIdx, requestId);
        return;
    }

    // Settable sample properties (object map for O(1) lookup)
    var _simplerSettable = {
        "start_marker":1, "end_marker":1, "warping":1, "warp_mode":1,
        "slicing_sensitivity":1, "gain":1,
        "beats_granulation_resolution":1, "beats_transient_envelope":1, "beats_transient_loop_mode":1,
        "texture_flux":1, "texture_grain_size":1, "tones_grain_size":1,
        "complex_pro_envelope":1, "complex_pro_formants":1
    };

    var setCount = 0;
    var errors = [];
    for (var key in props) {
        if (!props.hasOwnProperty(key)) continue;
        if (!_simplerSettable[key]) {
            errors.push({ property: key, error: "not a settable property" });
            continue;
        }
        try {
            sampleApi.set(key, props[key]);
            setCount++;
        } catch (e) {
            errors.push({ property: key, error: e.toString() });
        }
    }

    var result = { properties_set: setCount };
    if (errors.length > 0) result.errors = errors;
    sendResult(result, requestId);
}

function handleSimplerSlice(args) {
    // args: [track_index, device_index, action ("insert"|"remove"|"clear"|"reset"), slice_time (float, for insert/remove), request_id]
    if (args.length < 4) {
        sendError("simpler_slice requires track_index, device_index, action, request_id (slice_time for insert/remove)", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var action    = args[2].toString();

    var sliceTime = 0;
    var requestId;
    if (action === "move") {
        if (args.length < 6) {
            sendError("simpler_slice move requires old_time, new_time, and request_id", "");
            return;
        }
        sliceTime = parseFloat(args[3]);
        requestId = args[args.length - 1].toString();
    } else if (action === "insert" || action === "remove") {
        if (args.length < 5) {
            sendError("simpler_slice " + action + " requires slice_time and request_id", "");
            return;
        }
        sliceTime = parseFloat(args[3]);
        requestId = args[args.length - 1].toString();
    } else {
        requestId = args[args.length - 1].toString();
    }

    var samplePath = "live_set tracks " + trackIdx + " devices " + deviceIdx + " sample";
    var sampleApi;
    try {
        sampleApi = new LiveAPI(null, samplePath);
    } catch (e) {
        sendError("No sample found: " + safeErrorMessage(e), requestId);
        return;
    }

    if (!sampleApi || !sampleApi.id || parseInt(sampleApi.id) === 0) {
        sendError("No sample loaded in Simpler", requestId);
        return;
    }

    try {
        switch (action) {
            case "insert":
                sampleApi.call("insert_slice", sliceTime);
                sendResult({ action: "insert", slice_time: sliceTime }, requestId);
                break;
            case "remove":
                sampleApi.call("remove_slice", sliceTime);
                sendResult({ action: "remove", slice_time: sliceTime }, requestId);
                break;
            case "clear":
                sampleApi.call("clear_slices");
                sendResult({ action: "clear" }, requestId);
                break;
            case "move":
                var newTime = parseFloat(args[4]);
                sampleApi.call("move_slice", sliceTime, newTime);
                sendResult({ action: "move", old_time: sliceTime, new_time: newTime }, requestId);
                break;
            case "reset":
                sampleApi.call("reset_slices");
                sendResult({ action: "reset" }, requestId);
                break;
            default:
                sendError("Unknown slice action: " + action + " (use insert, remove, move, clear, reset)", requestId);
                break;
        }
    } catch (e) {
        sendError("Slice operation failed: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 4: Wavetable Modulation Matrix
//
// WavetableDevice (class_name "InstrumentVector") has:
//   Properties: filter_routing, mono_poly, poly_voices,
//     oscillator_1/2_effect_mode, oscillator_1/2_wavetable_category,
//     oscillator_1/2_wavetable_index, oscillator_1/2_wavetables (list),
//     oscillator_wavetable_categories (list), unison_mode, unison_voice_count,
//     visible_modulation_target_names (list)
//   Functions:
//     get_modulation_value(target_idx, source_idx) -> float
//     set_modulation_value(target_idx, source_idx, value)
//     add_parameter_to_modulation_matrix(parameter)
//     is_parameter_modulatable(parameter) -> bool
//     get_modulation_target_parameter_name(idx) -> string
// ---------------------------------------------------------------------------

function handleGetWavetableInfo(args) {
    // args: [track_index, device_index, request_id]
    if (args.length < 3) {
        sendError("get_wavetable_info requires track_index, device_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[2].toString();

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!_validateApi(deviceApi, requestId, "No device found at track " + trackIdx + " device " + deviceIdx)) return;

    var className = "";
    try { className = deviceApi.get("class_name").toString(); } catch (e) {}

    if (className !== "InstrumentVector") {
        sendError("Device is not a Wavetable (class: " + className + ")", requestId);
        return;
    }

    var result = {
        device_name: "",
        device_class: className
    };
    try { result.device_name = deviceApi.get("name").toString(); } catch (e) {}

    // Oscillator settings
    try { result.oscillator_1_effect_mode = parseInt(deviceApi.get("oscillator_1_effect_mode")); } catch (e) {}
    try { result.oscillator_2_effect_mode = parseInt(deviceApi.get("oscillator_2_effect_mode")); } catch (e) {}
    try { result.oscillator_1_wavetable_category = parseInt(deviceApi.get("oscillator_1_wavetable_category")); } catch (e) {}
    try { result.oscillator_1_wavetable_index    = parseInt(deviceApi.get("oscillator_1_wavetable_index")); } catch (e) {}
    try { result.oscillator_2_wavetable_category = parseInt(deviceApi.get("oscillator_2_wavetable_category")); } catch (e) {}
    try { result.oscillator_2_wavetable_index    = parseInt(deviceApi.get("oscillator_2_wavetable_index")); } catch (e) {}

    // Wavetable lists
    try {
        var cats = deviceApi.get("oscillator_wavetable_categories");
        if (cats) result.wavetable_categories = cats.toString();
    } catch (e) {}

    try {
        var wt1 = deviceApi.get("oscillator_1_wavetables");
        if (wt1) result.oscillator_1_wavetables = wt1.toString();
    } catch (e) {}

    try {
        var wt2 = deviceApi.get("oscillator_2_wavetables");
        if (wt2) result.oscillator_2_wavetables = wt2.toString();
    } catch (e) {}

    // Voice / unison properties — readable but NOT writable via M4L
    try { result.filter_routing     = parseInt(deviceApi.get("filter_routing")); } catch (e) {}
    try { result.mono_poly          = parseInt(deviceApi.get("mono_poly")); } catch (e) {}
    try { result.poly_voices        = parseInt(deviceApi.get("poly_voices")); } catch (e) {}
    try { result.unison_mode        = parseInt(deviceApi.get("unison_mode")); } catch (e) {}
    try { result.unison_voice_count = parseInt(deviceApi.get("unison_voice_count")); } catch (e) {}

    // Modulation targets
    try {
        var targetNames = deviceApi.get("visible_modulation_target_names");
        if (targetNames) result.modulation_target_names = targetNames.toString();
    } catch (e) {}

    // Read current modulation matrix values for visible targets
    // Sources: 0=Env2, 1=Env3, 2=LFO1, 3=LFO2 (standard Wavetable layout)
    try {
        var targetNamesArr = result.modulation_target_names;
        if (targetNamesArr) {
            var names = targetNamesArr.split(",");
            var modMatrix = [];
            for (var t = 0; t < names.length && t < 50; t++) {
                var row = { target_index: t, target_name: names[t] };
                var hasValue = false;
                for (var src = 0; src < 4; src++) {
                    try {
                        var modVal = deviceApi.call("get_modulation_value", t, src);
                        if (modVal !== undefined && modVal !== null) {
                            var fVal = parseFloat(modVal);
                            if (fVal !== 0.0) {
                                if (!row.sources) row.sources = {};
                                var srcName = ["Env2", "Env3", "LFO1", "LFO2"][src];
                                row.sources[srcName] = fVal;
                                hasValue = true;
                            }
                        }
                    } catch (e) {}
                }
                if (hasValue) modMatrix.push(row);
            }
            if (modMatrix.length > 0) result.active_modulations = modMatrix;
        }
    } catch (e) {}

    sendResult(result, requestId);
}

function handleSetWavetableModulation(args) {
    // args: [track_index, device_index, target_index, source_index, amount, request_id]
    if (args.length < 6) {
        sendError("set_wavetable_modulation requires track_index, device_index, target_index, source_index, amount, request_id", "");
        return;
    }
    var trackIdx    = parseInt(args[0]);
    var deviceIdx   = parseInt(args[1]);
    var targetIdx   = parseInt(args[2]);
    var sourceIdx   = parseInt(args[3]);
    var amount      = parseFloat(args[4]);
    var requestId   = args[5].toString();

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!_validateApi(deviceApi, requestId, "No device found")) return;

    try {
        deviceApi.call("set_modulation_value", targetIdx, sourceIdx, amount);

        // Read back the value to confirm
        var actualVal = parseFloat(deviceApi.call("get_modulation_value", targetIdx, sourceIdx));
        var srcNames = ["Env2", "Env3", "LFO1", "LFO2"];

        sendResult({
            target_index: targetIdx,
            source_index: sourceIdx,
            source_name:  srcNames[sourceIdx] || ("Source " + sourceIdx),
            requested_amount: amount,
            actual_amount: actualVal
        }, requestId);
    } catch (e) {
        sendError("Failed to set modulation: " + safeErrorMessage(e), requestId);
    }
}

function handleSetWavetableProps(args) {
    // args: [track_index, device_index, props_json_b64, request_id]
    if (args.length < 4) {
        sendError("set_wavetable_props requires track_index, device_index, props_json_b64, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[args.length - 1].toString();

    var propsB64 = _reassembleB64(args, 2);
    if (!propsB64) { sendError("Missing payload data", requestId); return; }

    var propsJson;
    try { propsJson = _base64decode(propsB64); } catch (e) {
        sendError("Failed to decode props_json_b64: " + safeErrorMessage(e), requestId);
        return;
    }
    var props;
    try { props = JSON.parse(propsJson); } catch (e) {
        sendError("Failed to parse props JSON: " + safeErrorMessage(e), requestId);
        return;
    }

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!_validateApi(deviceApi, requestId, "No device found")) return;

    // Tier 1: Oscillator properties — reliably settable via LiveAPI.set()
    var tier1Map = {
        "oscillator_1_effect_mode": true, "oscillator_2_effect_mode": true,
        "oscillator_1_wavetable_category": true, "oscillator_1_wavetable_index": true,
        "oscillator_2_wavetable_category": true, "oscillator_2_wavetable_index": true
    };
    // Tier 2: Voice/unison/filter properties — these are handled by the MCP
    // server via TCP (set_device_parameter). LiveAPI.set() silently fails for these.
    var tier2Map = {
        "filter_routing": true, "mono_poly": true, "poly_voices": true,
        "unison_mode": true, "unison_voice_count": true
    };

    var setCount = 0;
    var errors = [];
    var details = [];
    for (var key in props) {
        if (!props.hasOwnProperty(key)) continue;

        // Check which tier (O(1) lookup)
        var isTier1 = !!tier1Map[key];
        var isTier2 = !isTier1 && !!tier2Map[key];
        if (!isTier1 && !isTier2) {
            errors.push({ property: key, error: "not a settable property" });
            continue;
        }

        // Tier 2 properties: skip — the server routes these via TCP instead
        if (isTier2) {
            details.push({ property: key, value: Number(props[key]), note: "skipped — use TCP set_device_parameter instead" });
            continue;
        }

        var val = Number(props[key]);

        // Fire-and-forget set() — NO get() calls to avoid Ableton crashes
        try {
            deviceApi.set(key, val);
        } catch (e) {
            errors.push({ property: key, error: e.toString() });
            continue;
        }

        setCount++;
        details.push({ property: key, value: val });
    }

    var result = { properties_set: setCount };
    if (details.length > 0) result.details = details;
    if (errors.length > 0) result.errors = errors;
    sendResult(result, requestId);
}

// ---------------------------------------------------------------------------
// Diagnostic: probe device info + try setting "read-only" properties
// ---------------------------------------------------------------------------

function handleProbeDeviceInfo(args) {
    // args: [track_index, device_index, request_id]
    if (args.length < 3) {
        sendError("probe_device_info requires track_index, device_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var requestId = args[2].toString();

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!_validateApi(deviceApi, requestId, "No device found at track " + trackIdx + " device " + deviceIdx)) return;

    var result = {};

    // 1. Dump device info (shows properties, children, functions)
    try {
        var info = deviceApi.get("info").toString();
        result.info = info;
    } catch (e) {
        result.info_error = e.toString();
    }

    // 2. Read current values of tier-2 properties
    var tier2Props = ["unison_mode", "unison_voice_count", "poly_voices", "filter_routing", "mono_poly"];
    var beforeValues = {};
    for (var i = 0; i < tier2Props.length; i++) {
        var prop = tier2Props[i];
        try {
            beforeValues[prop] = deviceApi.get(prop).toString();
        } catch (e) {
            beforeValues[prop] = "ERROR: " + e.toString();
        }
    }
    result.before_values = beforeValues;

    // 3. Try setting each property via set(), then readback
    var setAttempts = {};
    for (var j = 0; j < tier2Props.length; j++) {
        var prop2 = tier2Props[j];
        var testVal = 1; // Safe test value for all (Classic/Parallel/Poly/1 voice)
        var attempt = {};
        try {
            deviceApi.set(prop2, testVal);
            attempt.set_no_crash = true;
        } catch (e) {
            attempt.set_error = e.toString();
        }
        // Readback to see if it actually changed
        try {
            var after = deviceApi.get(prop2).toString();
            attempt.after_set = after;
            attempt.changed = (after !== beforeValues[prop2]);
        } catch (e) {
            attempt.readback_error = e.toString();
        }
        setAttempts[prop2] = attempt;
    }
    result.set_attempts = setAttempts;

    // 4. Try call() with various method name patterns
    var callAttempts = {};
    for (var k = 0; k < tier2Props.length; k++) {
        var prop3 = tier2Props[k];
        var testVal2 = 2; // Different value to distinguish from set() test
        var callResult = {};

        // Try: deviceApi.call(prop_name, value)
        try {
            deviceApi.call(prop3, testVal2);
            callResult.call_direct = "no error";
        } catch (e) {
            callResult.call_direct = "ERROR: " + e.toString();
        }

        // Try: deviceApi.call("set_" + prop_name, value)
        try {
            deviceApi.call("set_" + prop3, testVal2);
            callResult.call_set_prefix = "no error";
        } catch (e) {
            callResult.call_set_prefix = "ERROR: " + e.toString();
        }

        // Readback after call attempts
        try {
            var afterCall = deviceApi.get(prop3).toString();
            callResult.after_call = afterCall;
            callResult.changed_from_before = (afterCall !== beforeValues[prop3]);
        } catch (e) {
            callResult.readback_error = e.toString();
        }

        callAttempts[prop3] = callResult;
    }
    result.call_attempts = callAttempts;

    // 5. Try accessing properties through children paths
    var childAttempts = {};
    var childPaths = [
        "live_set tracks " + trackIdx + " devices " + deviceIdx + " parameters",
        "live_set tracks " + trackIdx + " devices " + deviceIdx + " view"
    ];
    for (var p = 0; p < childPaths.length; p++) {
        try {
            var childApi = new LiveAPI(null, childPaths[p]);
            if (childApi && childApi.id && parseInt(childApi.id) !== 0) {
                childAttempts[childPaths[p]] = {
                    id: childApi.id.toString(),
                    info: childApi.get("info").toString().substring(0, 500)
                };
            } else {
                childAttempts[childPaths[p]] = "no object";
            }
        } catch (e) {
            childAttempts[childPaths[p]] = "ERROR: " + e.toString();
        }
    }
    result.child_paths = childAttempts;

    // 6. Restore original values (best effort)
    for (var r = 0; r < tier2Props.length; r++) {
        var prop4 = tier2Props[r];
        var origVal = beforeValues[prop4];
        if (origVal && origVal.indexOf("ERROR") === -1) {
            try { deviceApi.set(prop4, parseInt(origVal)); } catch (e) {}
        }
    }

    sendResult(result, requestId);
}

// ---------------------------------------------------------------------------
// Device Property Access — get/set device-level LOM properties
// ---------------------------------------------------------------------------

function handleGetDeviceProperty(args) {
    // args: [track_index (int), device_index (int), property_name (string), request_id (string)]
    if (args.length < 4) {
        sendError("get_device_property requires track_index, device_index, property_name, request_id", "");
        return;
    }
    var trackIdx     = parseInt(args[0]);
    var deviceIdx    = parseInt(args[1]);
    var propertyName = args[2].toString();
    var requestId    = args[3].toString();

    var result = getDeviceProperty(trackIdx, deviceIdx, propertyName);
    sendResult(result, requestId);
}

function handleSetDeviceProperty(args) {
    // args: [track_index (int), device_index (int), property_name (string), value (float), request_id (string)]
    if (args.length < 5) {
        sendError("set_device_property requires track_index, device_index, property_name, value, request_id", "");
        return;
    }
    var trackIdx     = parseInt(args[0]);
    var deviceIdx    = parseInt(args[1]);
    var propertyName = args[2].toString();
    var value        = parseFloat(args[3]);
    var requestId    = args[4].toString();

    var result = setDeviceProperty(trackIdx, deviceIdx, propertyName, value);
    sendResult(result, requestId);
}

// ---------------------------------------------------------------------------
// Phase 12: Note Surgery by ID (M4L-exclusive — in-place editing via stable note IDs)
//
// LiveAPI call() for dict-returning functions:
//   In Max JS, call() on get_notes_extended returns a flattened array of
//   key-value pairs. We parse this into note objects with note_id.
//   apply_note_modifications takes {"notes": [...]} dict.
//   remove_notes_by_id takes a list of note IDs.
// ---------------------------------------------------------------------------

function _getClipApi(trackIdx, clipIdx) {
    var clipPath = "live_set tracks " + trackIdx + " clip_slots " + clipIdx + " clip";
    var clipApi = new LiveAPI(null, clipPath);
    if (!clipApi || !clipApi.id || parseInt(clipApi.id) === 0) {
        return null;
    }
    return clipApi;
}

function _parseNotesFromCall(rawResult) {
    // LiveAPI call() for get_notes_extended/get_all_notes_extended returns
    // data in various formats depending on Max version. We handle:
    // 1. If it's already a JS object/array (Max 12+)
    // 2. If it's a flattened key-value string array from LiveAPI
    // 3. If it's a dict reference string
    if (!rawResult) return [];

    // If rawResult has a "notes" key directly (Dict-like return)
    if (typeof rawResult === "object" && rawResult.notes) {
        return rawResult.notes;
    }

    // If it's a string, try JSON parse
    if (typeof rawResult === "string") {
        try {
            var parsed = JSON.parse(rawResult);
            if (parsed && parsed.notes) return parsed.notes;
            if (Array.isArray(parsed)) return parsed;
        } catch (e) {}
    }

    // If it's an array (flattened from LiveAPI), parse key-value pairs
    if (rawResult && typeof rawResult === "object" && rawResult.length !== undefined) {
        var arr = [];
        for (var i = 0; i < rawResult.length; i++) {
            arr.push(rawResult[i]);
        }
        // Try to detect if this is a Dict reference
        if (arr.length === 2 && arr[0] === "notes") {
            // Might be a dict name reference — try Dict access
            try {
                var d = new Dict();
                d.parse(rawResult.toString());
                if (d.contains("notes")) {
                    var notesArr = [];
                    var count = d.getsize("notes");
                    for (var ni = 0; ni < count; ni++) {
                        var note = d.get("notes[" + ni + "]");
                        if (note) notesArr.push(note);
                    }
                    return notesArr;
                }
            } catch (e2) {}
        }
        return arr;
    }

    return [];
}

function handleGetClipNotesById(args) {
    // args: [track_index (int), clip_index (int), request_id (string)]
    if (args.length < 3) {
        sendError("get_clip_notes_by_id requires track_index, clip_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var clipIdx   = parseInt(args[1]);
    var requestId = args[2].toString();

    var clipApi = _getClipApi(trackIdx, clipIdx);
    if (!clipApi) {
        sendError("No clip at track " + trackIdx + " slot " + clipIdx, requestId);
        return;
    }

    try {
        // Check this is a MIDI clip
        var isMidi = false;
        try { isMidi = (parseInt(clipApi.get("is_midi_clip")) === 1); } catch (e) {}
        if (!isMidi) {
            sendError("Clip is not a MIDI clip", requestId);
            return;
        }

        // Use get_notes_extended to get notes with IDs
        // Args order: from_pitch, pitch_span, from_time, time_span
        var rawNotes = clipApi.call("get_notes_extended", 0, 128, 0.0, 99999.0);

        // Parse the result — handling multiple return formats
        var notes = _parseNotesFromCall(rawNotes);

        // Get clip info
        var clipName = "";
        try { clipName = clipApi.get("name").toString(); } catch (e) {}
        var clipLength = 4.0;
        try { clipLength = parseFloat(clipApi.get("length")); } catch (e) {}

        sendResult({
            clip_name: clipName,
            clip_length: clipLength,
            note_count: notes.length,
            notes: notes,
            has_note_ids: true
        }, requestId);
    } catch (e) {
        sendError("Failed to get clip notes with IDs: " + safeErrorMessage(e), requestId);
    }
}

function handleModifyClipNotes(args) {
    // args: [track_index (int), clip_index (int), modifications_b64 (string), request_id (string)]
    if (args.length < 4) {
        sendError("modify_clip_notes requires track_index, clip_index, modifications_b64, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var clipIdx   = parseInt(args[1]);
    var modsB64   = args[2].toString();
    var requestId = args[3].toString();

    var clipApi = _getClipApi(trackIdx, clipIdx);
    if (!clipApi) {
        sendError("No clip at track " + trackIdx + " slot " + clipIdx, requestId);
        return;
    }

    var modsJson;
    try { modsJson = _base64decode(modsB64); } catch (e) {
        sendError("Failed to decode modifications base64: " + safeErrorMessage(e), requestId);
        return;
    }

    var modifications;
    try { modifications = JSON.parse(modsJson); } catch (e) {
        sendError("Failed to parse modifications JSON: " + safeErrorMessage(e), requestId);
        return;
    }

    try {
        // apply_note_modifications expects {"notes": [...]} dict
        var notesList = modifications;
        if (!Array.isArray(notesList) && notesList.notes) {
            notesList = notesList.notes;
        }

        clipApi.call("apply_note_modifications", {"notes": notesList});

        sendResult({
            modified_count: Array.isArray(notesList) ? notesList.length : 0,
            status: "applied"
        }, requestId);
    } catch (e) {
        sendError("Failed to apply note modifications: " + safeErrorMessage(e), requestId);
    }
}

function handleRemoveClipNotesById(args) {
    // args: [track_index (int), clip_index (int), note_ids_b64 (string), request_id (string)]
    if (args.length < 4) {
        sendError("remove_clip_notes_by_id requires track_index, clip_index, note_ids_b64, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var clipIdx   = parseInt(args[1]);
    var idsB64    = args[2].toString();
    var requestId = args[3].toString();

    var clipApi = _getClipApi(trackIdx, clipIdx);
    if (!clipApi) {
        sendError("No clip at track " + trackIdx + " slot " + clipIdx, requestId);
        return;
    }

    var idsJson;
    try { idsJson = _base64decode(idsB64); } catch (e) {
        sendError("Failed to decode note_ids base64: " + safeErrorMessage(e), requestId);
        return;
    }

    var noteIds;
    try { noteIds = JSON.parse(idsJson); } catch (e) {
        sendError("Failed to parse note_ids JSON: " + safeErrorMessage(e), requestId);
        return;
    }

    try {
        // remove_notes_by_id takes a list of note IDs
        clipApi.call("remove_notes_by_id", noteIds);

        sendResult({
            removed_count: Array.isArray(noteIds) ? noteIds.length : 0,
            status: "removed"
        }, requestId);
    } catch (e) {
        sendError("Failed to remove notes by ID: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 13: Chain-Level Mixing
//
// Chain.mixer_device → ChainMixerDevice with:
//   volume (DeviceParameter), panning (DeviceParameter),
//   sends (list of DeviceParameter), chain_activator (DeviceParameter = mute)
// ---------------------------------------------------------------------------

function handleGetChainMixing(args) {
    // args: [track_idx, device_idx, chain_idx, request_id]
    if (args.length < 4) {
        sendError("get_chain_mixing requires track_index, device_index, chain_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var chainIdx  = parseInt(args[2]);
    var requestId = args[3].toString();

    var chainPath = "live_set tracks " + trackIdx + " devices " + deviceIdx + " chains " + chainIdx;
    var chainApi = new LiveAPI(null, chainPath);
    if (!chainApi || !chainApi.id || parseInt(chainApi.id) === 0) {
        sendError("No chain at " + chainPath, requestId);
        return;
    }

    try {
        var result = {};
        try { result.name = chainApi.get("name").toString(); } catch (e) {}
        try { result.color = parseInt(chainApi.get("color")); } catch (e) {}
        try { result.mute = (parseInt(chainApi.get("mute")) === 1); } catch (e) {}
        try { result.solo = (parseInt(chainApi.get("solo")) === 1); } catch (e) {}

        // Navigate to mixer_device using a single reusable cursor
        var mixerPath = chainPath + " mixer_device";
        var cursor = new LiveAPI(null, mixerPath);

        if (cursor && cursor.id && parseInt(cursor.id) !== 0) {
            var sendCount = 0;
            try { sendCount = parseInt(cursor.getcount("sends")); } catch (e) {}

            // Volume
            cursor.goto(mixerPath + " volume");
            if (cursor.id && parseInt(cursor.id) !== 0) {
                result.volume = {};
                try { result.volume.value = parseFloat(cursor.get("value")); } catch (e) {}
                try { result.volume.min = parseFloat(cursor.get("min")); } catch (e) {}
                try { result.volume.max = parseFloat(cursor.get("max")); } catch (e) {}
                try { result.volume.name = cursor.get("name").toString(); } catch (e) {}
            }

            // Panning
            cursor.goto(mixerPath + " panning");
            if (cursor.id && parseInt(cursor.id) !== 0) {
                result.panning = {};
                try { result.panning.value = parseFloat(cursor.get("value")); } catch (e) {}
                try { result.panning.min = parseFloat(cursor.get("min")); } catch (e) {}
                try { result.panning.max = parseFloat(cursor.get("max")); } catch (e) {}
            }

            // Chain activator (mute toggle via device parameter)
            cursor.goto(mixerPath + " chain_activator");
            if (cursor.id && parseInt(cursor.id) !== 0) {
                result.chain_activator = {};
                try { result.chain_activator.value = parseFloat(cursor.get("value")); } catch (e) {}
            }

            // Sends
            if (sendCount > 0) {
                var sends = [];
                for (var s = 0; s < sendCount; s++) {
                    cursor.goto(mixerPath + " sends " + s);
                    if (!cursor.id || parseInt(cursor.id) === 0) continue;
                    var sendInfo = { index: s };
                    try { sendInfo.value = parseFloat(cursor.get("value")); } catch (e) {}
                    try { sendInfo.min = parseFloat(cursor.get("min")); } catch (e) {}
                    try { sendInfo.max = parseFloat(cursor.get("max")); } catch (e) {}
                    try { sendInfo.name = cursor.get("name").toString(); } catch (e) {}
                    sends.push(sendInfo);
                }
                result.sends = sends;
            }
        }

        sendResult(result, requestId);
    } catch (e) {
        sendError("Failed to get chain mixing: " + safeErrorMessage(e), requestId);
    }
}

function handleSetChainMixing(args) {
    // args: [track_idx, device_idx, chain_idx, props_b64, request_id]
    if (args.length < 5) {
        sendError("set_chain_mixing requires track_index, device_index, chain_index, props_b64, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var chainIdx  = parseInt(args[2]);
    var propsB64  = args[3].toString();
    var requestId = args[4].toString();

    var propsJson;
    try { propsJson = _base64decode(propsB64); } catch (e) {
        sendError("Failed to decode props base64: " + safeErrorMessage(e), requestId);
        return;
    }
    var props;
    try { props = JSON.parse(propsJson); } catch (e) {
        sendError("Failed to parse props JSON: " + safeErrorMessage(e), requestId);
        return;
    }

    var chainPath = "live_set tracks " + trackIdx + " devices " + deviceIdx + " chains " + chainIdx;
    var mixerPath = chainPath + " mixer_device";
    var changes = {};

    try {
        // Volume
        if (props.volume !== undefined) {
            var volApi = new LiveAPI(null, mixerPath + " volume");
            if (volApi && volApi.id && parseInt(volApi.id) !== 0) {
                volApi.set("value", parseFloat(props.volume));
                changes.volume = parseFloat(props.volume);
            }
        }

        // Panning
        if (props.panning !== undefined) {
            var panApi = new LiveAPI(null, mixerPath + " panning");
            if (panApi && panApi.id && parseInt(panApi.id) !== 0) {
                panApi.set("value", parseFloat(props.panning));
                changes.panning = parseFloat(props.panning);
            }
        }

        // Chain activator (1=active/unmuted, 0=deactivated/muted)
        if (props.chain_activator !== undefined) {
            var actApi = new LiveAPI(null, mixerPath + " chain_activator");
            if (actApi && actApi.id && parseInt(actApi.id) !== 0) {
                actApi.set("value", parseFloat(props.chain_activator));
                changes.chain_activator = parseFloat(props.chain_activator);
            }
        }

        // Sends (array of {index, value} or just {send_0: value, send_1: value})
        if (props.sends !== undefined) {
            var sendChanges = [];
            if (Array.isArray(props.sends)) {
                for (var si = 0; si < props.sends.length; si++) {
                    var sendSpec = props.sends[si];
                    var sendIdx = sendSpec.index !== undefined ? sendSpec.index : si;
                    var sendApi = new LiveAPI(null, mixerPath + " sends " + sendIdx);
                    if (sendApi && sendApi.id && parseInt(sendApi.id) !== 0) {
                        sendApi.set("value", parseFloat(sendSpec.value));
                        sendChanges.push({ index: sendIdx, value: parseFloat(sendSpec.value) });
                    }
                }
            }
            changes.sends = sendChanges;
        }

        // Mute/solo on the chain itself (not mixer_device)
        if (props.mute !== undefined) {
            var chainApi = new LiveAPI(null, chainPath);
            chainApi.set("mute", parseInt(props.mute));
            changes.mute = parseInt(props.mute);
        }
        if (props.solo !== undefined) {
            var chainApi2 = new LiveAPI(null, chainPath);
            chainApi2.set("solo", parseInt(props.solo));
            changes.solo = parseInt(props.solo);
        }

        sendResult({ changes: changes, status: "applied" }, requestId);
    } catch (e) {
        sendError("Failed to set chain mixing: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 14: Device AB Comparison (Live 12.3+)
//
// Device.can_compare_ab (bool, Get/Observe)
// Device.is_using_compare_preset_b (bool, Get/Observe)
// Device.save_preset_to_compare_ab_slot() (Call)
// ---------------------------------------------------------------------------

function handleDeviceAbCompare(args) {
    // args: [track_idx, device_idx, action (string), request_id]
    if (args.length < 4) {
        sendError("device_ab_compare requires track_index, device_index, action, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var action    = args[2].toString();
    var requestId = args[3].toString();

    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi = new LiveAPI(null, devicePath);
    if (!_validateApi(deviceApi, requestId, "No device at track " + trackIdx + " device " + deviceIdx)) return;

    try {
        // Check if AB comparison is supported
        var canAB = false;
        try { canAB = (parseInt(deviceApi.get("can_compare_ab")) === 1); } catch (e) {
            sendError("AB comparison not available (requires Live 12.3+)", requestId);
            return;
        }

        if (!canAB) {
            sendError("This device does not support AB comparison", requestId);
            return;
        }

        if (action === "get_state") {
            var result = {};
            result.can_compare_ab = true;
            try { result.is_using_b = (parseInt(deviceApi.get("is_using_compare_preset_b")) === 1); } catch (e) { result.is_using_b = null; }
            try { result.device_name = deviceApi.get("name").toString(); } catch (e) {}
            sendResult(result, requestId);

        } else if (action === "save") {
            // Save current state to the other slot (toggles A↔B storage)
            deviceApi.call("save_preset_to_compare_ab_slot");
            var isB = false;
            try { isB = (parseInt(deviceApi.get("is_using_compare_preset_b")) === 1); } catch (e) {}
            sendResult({
                status: "saved",
                is_using_b: isB,
                note: "Saved current state to the other AB slot"
            }, requestId);

        } else if (action === "toggle") {
            // Toggle between A and B presets
            // In Live, toggling is done by the AB button which switches is_using_compare_preset_b
            // From the API, we call save_preset_to_compare_ab_slot to swap
            deviceApi.call("save_preset_to_compare_ab_slot");
            var isB2 = false;
            try { isB2 = (parseInt(deviceApi.get("is_using_compare_preset_b")) === 1); } catch (e) {}
            sendResult({
                status: "toggled",
                is_using_b: isB2
            }, requestId);

        } else {
            sendError("Unknown AB compare action: " + action + " (use get_state, save, or toggle)", requestId);
        }
    } catch (e) {
        sendError("AB comparison failed: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 15: Clip Scrubbing (M4L-exclusive)
//
// Clip.scrub(beat_time) — quantized scrubbing within a clip
// Clip.stop_scrub() — stop scrubbing
// Different from Song.scrub_by which moves global transport
// ---------------------------------------------------------------------------

function handleClipScrub(args) {
    // args: [track_idx, clip_idx, action (string), beat_time (float), request_id]
    if (args.length < 5) {
        sendError("clip_scrub requires track_index, clip_index, action, beat_time, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var clipIdx   = parseInt(args[1]);
    var action    = args[2].toString();
    var beatTime  = parseFloat(args[3]);
    var requestId = args[4].toString();

    var clipApi = _getClipApi(trackIdx, clipIdx);
    if (!clipApi) {
        sendError("No clip at track " + trackIdx + " slot " + clipIdx, requestId);
        return;
    }

    try {
        if (action === "scrub") {
            clipApi.call("scrub", beatTime);
            sendResult({ status: "scrubbing", beat_time: beatTime }, requestId);

        } else if (action === "stop_scrub") {
            clipApi.call("stop_scrub");
            sendResult({ status: "stopped" }, requestId);

        } else {
            sendError("Unknown clip_scrub action: " + action + " (use scrub or stop_scrub)", requestId);
        }
    } catch (e) {
        sendError("Clip scrub failed: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 16: Split Stereo Panning (M4L-exclusive)
//
// Track.mixer_device.left_split_stereo (DeviceParameter)
// Track.mixer_device.right_split_stereo (DeviceParameter)
// ---------------------------------------------------------------------------

function handleGetSplitStereo(args) {
    // args: [track_idx, request_id]
    if (args.length < 2) {
        sendError("get_split_stereo requires track_index, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var requestId = args[1].toString();

    var basePath = "live_set tracks " + trackIdx + " mixer_device";

    try {
        var result = {};

        var leftApi = new LiveAPI(null, basePath + " left_split_stereo");
        if (leftApi && leftApi.id && parseInt(leftApi.id) !== 0) {
            result.left = {};
            try { result.left.value = parseFloat(leftApi.get("value")); } catch (e) {}
            try { result.left.min = parseFloat(leftApi.get("min")); } catch (e) {}
            try { result.left.max = parseFloat(leftApi.get("max")); } catch (e) {}
            try { result.left.name = leftApi.get("name").toString(); } catch (e) {}
        }

        var rightApi = new LiveAPI(null, basePath + " right_split_stereo");
        if (rightApi && rightApi.id && parseInt(rightApi.id) !== 0) {
            result.right = {};
            try { result.right.value = parseFloat(rightApi.get("value")); } catch (e) {}
            try { result.right.min = parseFloat(rightApi.get("min")); } catch (e) {}
            try { result.right.max = parseFloat(rightApi.get("max")); } catch (e) {}
            try { result.right.name = rightApi.get("name").toString(); } catch (e) {}
        }

        if (!result.left && !result.right) {
            sendError("Split stereo not available on track " + trackIdx, requestId);
            return;
        }

        sendResult(result, requestId);
    } catch (e) {
        sendError("Failed to get split stereo: " + safeErrorMessage(e), requestId);
    }
}

function handleSetSplitStereo(args) {
    // args: [track_idx, left_value (float), right_value (float), request_id]
    if (args.length < 4) {
        sendError("set_split_stereo requires track_index, left_value, right_value, request_id", "");
        return;
    }
    var trackIdx   = parseInt(args[0]);
    var leftValue  = parseFloat(args[1]);
    var rightValue = parseFloat(args[2]);
    var requestId  = args[3].toString();

    var basePath = "live_set tracks " + trackIdx + " mixer_device";
    var changes = {};

    try {
        var leftApi = new LiveAPI(null, basePath + " left_split_stereo");
        if (leftApi && leftApi.id && parseInt(leftApi.id) !== 0) {
            leftApi.set("value", leftValue);
            changes.left = leftValue;
        }

        var rightApi = new LiveAPI(null, basePath + " right_split_stereo");
        if (rightApi && rightApi.id && parseInt(rightApi.id) !== 0) {
            rightApi.set("value", rightValue);
            changes.right = rightValue;
        }

        if (Object.keys(changes).length === 0) {
            sendError("Split stereo not available on track " + trackIdx, requestId);
            return;
        }

        sendResult({ changes: changes, status: "applied" }, requestId);
    } catch (e) {
        sendError("Failed to set split stereo: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Shared validation & utility helpers
// ---------------------------------------------------------------------------

function _validateApi(api, requestId, msg) {
    if (!api || !api.id || parseInt(api.id) === 0) {
        sendError(msg || "No device found", requestId);
        return false;
    }
    return true;
}

function _reassembleB64(args, startIdx) {
    var parts = [];
    for (var a = startIdx; a < args.length - 1; a++) {
        parts.push(args[a].toString());
    }
    return parts.length > 0 ? parts.join("") : null;
}

// ---------------------------------------------------------------------------
// Response helpers
// ---------------------------------------------------------------------------

function sendResult(result, requestId) {
    if (result.error) {
        sendError(result.error, requestId);
        return;
    }
    var response = {
        status: "success",
        result: result,
        id: requestId
    };
    sendResponse(JSON.stringify(response));
}

function safeErrorMessage(e) {
    // Keep short, non-internal messages; return generic text for internal details.
    var msg = (e && typeof e.toString === "function") ? e.toString() : "unknown";
    if (msg.length > 200 || msg.indexOf("live_set") !== -1 || msg.indexOf("\\") !== -1) {
        return "internal error";
    }
    return msg;
}

function sendError(message, requestId) {
    var response = {
        status: "error",
        message: message,
        id: requestId
    };
    sendResponse(JSON.stringify(response));
}

// ---------------------------------------------------------------------------
// Chunked response sending  (Revision 4)
//
// Max's [js] outlet() has a practical symbol size limit of ~8KB.  Responses
// larger than that crash Ableton.  Standard base64 '+' and '/' characters
// also confuse Max's OSC routing.
//
// Previous revisions failed because:
//   Rev 1-2: Non-base64 prefixes crash OSC layer
//   Rev 3:   _jsonEscape() inflates pieces (doubling every " char)
//   Rev 3b:  O(n^2) char-by-char _toUrlSafeBase64() on 16KB string locks
//            up the JS engine; full 16KB intermediate string in memory
//
// Rev 4 solution — chunk JSON first, encode pieces independently:
//   1. If small (≤ 1500 chars JSON) → encode + URL-safe + outlet directly
//   2. If large → split raw JSON into 2000-char pieces
//   3. Each piece: base64 → URL-safe → wrap in envelope → base64 → URL-safe
//   4. ALL chunks deferred via Task.schedule() (not synchronous)
//   5. Each outlet() sends ~3.6KB — well under 8KB limit
//
// Key safety properties:
//   - Never creates the full base64 string in memory
//   - .replace() for URL-safe conversion is O(n) native, not O(n^2) loop
//   - Each operation works on ≤ ~3.6KB strings — no memory pressure
//   - First chunk is deferred (not synchronous from discovery callback)
// ---------------------------------------------------------------------------
var RESPONSE_PIECE_SIZE  = 2000;  // chars of RAW JSON per chunk (conservative)
var RESPONSE_CHUNK_DELAY = 50;    // ms between outlet() calls
var _responseSendState   = null;  // global state for deferred chunk sending
var _responseSendQueue   = [];    // queued responses when send is busy

function _toUrlSafe(b64) {
    // O(n) native .replace() — NOT char-by-char concatenation
    return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function sendResponse(jsonStr) {
    // If a chunked send is in progress, queue this response (regardless of size)
    if (_responseSendState) {
        _responseSendQueue.push(jsonStr);
        post("sendResponse: queued (send busy), queue depth=" + _responseSendQueue.length + "\n");
        return;
    }

    // Small response — encode + send directly (backward compatible)
    if (jsonStr.length <= 1500) {
        outlet(0, _toUrlSafe(_base64encode(jsonStr)));
        return;
    }

    // Large response — store raw JSON, defer ALL chunk sending via Task

    var totalChunks = Math.ceil(jsonStr.length / RESPONSE_PIECE_SIZE);
    post("sendResponse: " + jsonStr.length + " chars JSON -> " + totalChunks + " chunks\n");

    _responseSendState = {
        jsonStr:     jsonStr,
        totalChunks: totalChunks,
        idx:         0
    };

    // DEFER first chunk — don't send synchronously from discovery callback
    var t = new Task(_sendNextResponsePiece);
    t.schedule(RESPONSE_CHUNK_DELAY);
}

function _sendNextResponsePiece() {
    if (!_responseSendState) return;
    var s = _responseSendState;

    try {
        // Extract this piece of raw JSON
        var start = s.idx * RESPONSE_PIECE_SIZE;
        var end   = Math.min(start + RESPONSE_PIECE_SIZE, s.jsonStr.length);
        var piece = s.jsonStr.substring(start, end);

        // Encode piece independently → URL-safe base64 (O(n) via .replace())
        var pieceB64 = _toUrlSafe(_base64encode(piece));

        // Wrap in chunk envelope, encode envelope, send
        // pieceB64 is pure [A-Za-z0-9_-] — no escaping needed in the JSON string
        var envelope = '{"_c":' + s.idx + ',"_t":' + s.totalChunks + ',"_d":"' + pieceB64 + '"}';
        var envelopeB64 = _toUrlSafe(_base64encode(envelope));
        outlet(0, envelopeB64);
    } catch (e) {
        post("_sendNextResponsePiece error: " + e.toString() + "\n");
        _responseSendState = null;
        _drainResponseQueue();
        return;
    }

    s.idx++;
    if (s.idx < s.totalChunks) {
        var t = new Task(_sendNextResponsePiece);
        t.schedule(RESPONSE_CHUNK_DELAY);
    } else {
        _responseSendState = null;
        _drainResponseQueue();
    }
}

function _drainResponseQueue() {
    while (_responseSendQueue.length > 0) {
        var next = _responseSendQueue.shift();
        sendResponse(next);
        // If sendResponse started a chunked send, stop draining —
        // the next drain will happen when _sendNextResponsePiece completes
        if (_responseSendState) break;
    }
}

// ---------------------------------------------------------------------------
// Base64 encode — Max's JS engine doesn't have btoa
// ---------------------------------------------------------------------------
var _b64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function _base64encode(str) {
    var result = "";
    var i = 0;
    while (i < str.length) {
        var c1 = str.charCodeAt(i++) || 0;
        var c2 = str.charCodeAt(i++) || 0;
        var c3 = str.charCodeAt(i++) || 0;
        var triplet = (c1 << 16) | (c2 << 8) | c3;
        result += _b64chars.charAt((triplet >> 18) & 63);
        result += _b64chars.charAt((triplet >> 12) & 63);
        result += (i - 1 > str.length) ? "=" : _b64chars.charAt((triplet >> 6) & 63);
        result += (i > str.length) ? "=" : _b64chars.charAt(triplet & 63);
    }
    return result;
}

function _base64decode(str) {
    var lookup = {};
    for (var c = 0; c < _b64chars.length; c++) {
        lookup[_b64chars.charAt(c)] = c;
    }
    // Also accept URL-safe base64 variants (- instead of +, _ instead of /)
    lookup["-"] = 62;
    lookup["_"] = 63;
    str = str.replace(/=/g, "");
    var result = "";
    var i = 0;
    while (i < str.length) {
        var b0 = lookup[str.charAt(i++)] || 0;
        var b1 = lookup[str.charAt(i++)] || 0;
        var b2 = lookup[str.charAt(i++)] || 0;
        var b3 = lookup[str.charAt(i++)] || 0;
        var triplet = (b0 << 18) | (b1 << 12) | (b2 << 6) | b3;
        result += String.fromCharCode((triplet >> 16) & 255);
        if (i - 2 < str.length) result += String.fromCharCode((triplet >> 8) & 255);
        if (i - 1 < str.length) result += String.fromCharCode(triplet & 255);
    }
    return result;
}

// ---------------------------------------------------------------------------
// LOM access: set a specific parameter by its LOM index
// ---------------------------------------------------------------------------
function setHiddenParam(trackIdx, deviceIdx, paramIdx, value) {
    var paramPath = "live_set tracks " + trackIdx
                  + " devices " + deviceIdx
                  + " parameters " + paramIdx;
    var paramApi  = new LiveAPI(null, paramPath);

    if (!paramApi || !paramApi.id || parseInt(paramApi.id) === 0) {
        return { error: "No parameter found at index " + paramIdx + "." };
    }

    try {
        var paramName = paramApi.get("name").toString();
        var minVal    = parseFloat(paramApi.get("min"));
        var maxVal    = parseFloat(paramApi.get("max"));

        var clamped = Math.max(minVal, Math.min(maxVal, value));
        paramApi.set("value", clamped);
        // NO readback — get() after set() can crash Ableton (same pattern as wavetable fix)

        return {
            parameter_name:  paramName,
            parameter_index: paramIdx,
            requested_value: value,
            actual_value:    clamped,
            was_clamped:     (clamped !== value)
        };
    } catch (e) {
        return { error: "Failed to set parameter " + paramIdx + ": " + e.toString() };
    }
}

// ---------------------------------------------------------------------------
// LOM access: get a device-level property (not an indexed parameter)
// ---------------------------------------------------------------------------
function getDeviceProperty(trackIdx, deviceIdx, propertyName) {
    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!deviceApi || !deviceApi.id || parseInt(deviceApi.id) === 0) {
        return { error: "No device found at track " + trackIdx + " device " + deviceIdx + "." };
    }

    try {
        var deviceName  = deviceApi.get("name").toString();
        var deviceClass = deviceApi.get("class_name").toString();
        var rawValue    = deviceApi.get(propertyName);

        var currentValue;
        if (rawValue === undefined || rawValue === null) {
            return { error: "Property '" + propertyName + "' returned null/undefined on this device." };
        }
        var numVal = parseFloat(rawValue.toString());
        currentValue = isNaN(numVal) ? rawValue.toString() : numVal;

        return {
            device_name:   deviceName,
            device_class:  deviceClass,
            property_name: propertyName,
            value:         currentValue
        };
    } catch (e) {
        return { error: "Failed to get property '" + propertyName + "' on device: " + e.toString() };
    }
}

// ---------------------------------------------------------------------------
// LOM access: set a device-level property (not an indexed parameter)
// ---------------------------------------------------------------------------
function setDeviceProperty(trackIdx, deviceIdx, propertyName, value) {
    var devicePath = "live_set tracks " + trackIdx + " devices " + deviceIdx;
    var deviceApi  = new LiveAPI(null, devicePath);

    if (!deviceApi || !deviceApi.id || parseInt(deviceApi.id) === 0) {
        return { error: "No device found at track " + trackIdx + " device " + deviceIdx + "." };
    }

    var _readonlyMap = {
        "class_name":1, "class_display_name":1, "type":1,
        "can_have_chains":1, "can_have_drum_pads":1,
        "canonical_parent":1, "view":1, "parameters":1,
        "is_active":1
    };
    if (_readonlyMap[propertyName]) {
        return { error: "Property '" + propertyName + "' is read-only and cannot be set." };
    }

    try {
        var deviceName  = deviceApi.get("name").toString();
        var deviceClass = deviceApi.get("class_name").toString();

        var oldRaw = deviceApi.get(propertyName);
        var oldNum = parseFloat(oldRaw.toString());
        var oldValue = isNaN(oldNum) ? oldRaw.toString() : oldNum;

        // Convert to integer if value is whole number (LOM device props are often enum ints)
        var setValue = value;
        if (value === Math.floor(value)) {
            setValue = Math.floor(value);
        }

        deviceApi.set(propertyName, setValue);

        var newRaw = deviceApi.get(propertyName);
        var newNum = parseFloat(newRaw.toString());
        var newValue = isNaN(newNum) ? newRaw.toString() : newNum;

        return {
            device_name:     deviceName,
            device_class:    deviceClass,
            property_name:   propertyName,
            old_value:       oldValue,
            new_value:       newValue,
            requested_value: value,
            success:         (newValue !== oldValue || newValue == value)
        };
    } catch (e) {
        return { error: "Failed to set property '" + propertyName + "' on device: " + e.toString() };
    }
}

// ---------------------------------------------------------------------------
// readParamInfo — extract all useful info from a single parameter LiveAPI
// ---------------------------------------------------------------------------
function readParamInfo(paramApi, index) {
    var info = {
        index:        index,
        name:         "",
        value:        0,
        min:          0,
        max:          0,
        is_quantized: false,
        default_value: 0
    };

    try { info.name          = paramApi.get("name").toString(); }         catch (e) {}
    try { info.value         = parseFloat(paramApi.get("value")); }       catch (e) {}
    try { info.min           = parseFloat(paramApi.get("min")); }         catch (e) {}
    try { info.max           = parseFloat(paramApi.get("max")); }         catch (e) {}
    try { info.is_quantized  = (parseInt(paramApi.get("is_quantized")) === 1); } catch (e) {}
    try { info.default_value = parseFloat(paramApi.get("default_value")); } catch (e) {}

    if (info.is_quantized) {
        try {
            var items = paramApi.get("value_items");
            if (items) {
                info.value_items = items.toString();
            }
        } catch (e) {}
    }

    return info;
}

// ---------------------------------------------------------------------------
// Phase 7: Cue Points & Locators
//
// Cue points (locators) are arrangement markers accessible via:
//   live_set cue_points N  (children of live_set)
// Properties: name (str), time (float, in beats)
// ---------------------------------------------------------------------------

function handleGetCuePoints(args) {
    // args: [request_id (string)]
    var requestId = (args.length > 0) ? args[0].toString() : "";

    try {
        var api = new LiveAPI(null, "live_set");
        if (!api || !api.id || parseInt(api.id) === 0) {
            sendError("Could not access live_set", requestId);
            return;
        }

        var count = 0;
        try { count = parseInt(api.getcount("cue_points")); } catch (e) {}

        var cuePoints = [];
        var cursor = new LiveAPI(null, "live_set");

        for (var i = 0; i < count; i++) {
            cursor.goto("live_set cue_points " + i);
            if (!cursor.id || parseInt(cursor.id) === 0) continue;

            var cp = { index: i };
            try { cp.name = cursor.get("name").toString(); } catch (e) { cp.name = ""; }
            try { cp.time = parseFloat(cursor.get("time")); } catch (e) { cp.time = 0; }
            cuePoints.push(cp);
        }

        sendResult({
            cue_point_count: cuePoints.length,
            cue_points: cuePoints
        }, requestId);
    } catch (e) {
        sendError("Failed to get cue points: " + safeErrorMessage(e), requestId);
    }
}

function handleJumpToCuePoint(args) {
    // args: [cue_point_index (int), request_id (string)]
    if (args.length < 2) {
        sendError("jump_to_cue_point requires cue_point_index, request_id", "");
        return;
    }
    var cpIndex   = parseInt(args[0]);
    var requestId = args[1].toString();

    try {
        var cpApi = new LiveAPI(null, "live_set cue_points " + cpIndex);
        if (!cpApi || !cpApi.id || parseInt(cpApi.id) === 0) {
            sendError("No cue point found at index " + cpIndex, requestId);
            return;
        }

        var cpTime = parseFloat(cpApi.get("time"));
        var cpName = cpApi.get("name").toString();

        // Set the song position to the cue point time
        var songApi = new LiveAPI(null, "live_set");
        songApi.set("current_song_time", cpTime);

        sendResult({
            jumped_to: cpIndex,
            name: cpName,
            time: cpTime
        }, requestId);
    } catch (e) {
        sendError("Failed to jump to cue point: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 8: Groove Pool Access
//
// Grooves live under live_set groove_pool:
//   live_set groove_pool grooves N
// Groove properties: name, base (float 0-1), timing (float 0-1),
//   velocity (float 0-1), random (float 0-1), quantize_rate (int)
// ---------------------------------------------------------------------------

function handleGetGroovePool(args) {
    // args: [request_id (string)]
    var requestId = (args.length > 0) ? args[0].toString() : "";

    try {
        var poolApi = new LiveAPI(null, "live_set groove_pool");
        if (!poolApi || !poolApi.id || parseInt(poolApi.id) === 0) {
            sendError("Could not access groove pool", requestId);
            return;
        }

        var count = 0;
        try { count = parseInt(poolApi.getcount("grooves")); } catch (e) {}

        var grooves = [];
        var cursor = new LiveAPI(null, "live_set groove_pool");

        for (var i = 0; i < count; i++) {
            cursor.goto("live_set groove_pool grooves " + i);
            if (!cursor.id || parseInt(cursor.id) === 0) continue;

            var g = { index: i };
            try { g.name = cursor.get("name").toString(); } catch (e) { g.name = ""; }
            try { g.base = parseFloat(cursor.get("base")); } catch (e) {}
            try { g.timing = parseFloat(cursor.get("timing")); } catch (e) {}
            try { g.velocity = parseFloat(cursor.get("velocity")); } catch (e) {}
            try { g.random = parseFloat(cursor.get("random")); } catch (e) {}
            try { g.quantize_rate = parseInt(cursor.get("quantize_rate")); } catch (e) {}
            grooves.push(g);
        }

        sendResult({
            groove_count: grooves.length,
            grooves: grooves
        }, requestId);
    } catch (e) {
        sendError("Failed to get groove pool: " + safeErrorMessage(e), requestId);
    }
}

function handleSetGrooveProperties(args) {
    // args: [groove_index (int), props_json_b64 (string), request_id (string)]
    if (args.length < 3) {
        sendError("set_groove_properties requires groove_index, props_json_b64, request_id", "");
        return;
    }
    var grooveIdx = parseInt(args[0]);
    var requestId = args[args.length - 1].toString();

    // Reassemble b64 payload (Max may split long strings)
    var propsB64 = _reassembleB64(args, 1);
    if (!propsB64) { sendError("Missing payload data", requestId); return; }

    var propsJson;
    try { propsJson = _base64decode(propsB64); } catch (e) {
        sendError("Failed to decode props_json_b64: " + safeErrorMessage(e), requestId);
        return;
    }
    var props;
    try { props = JSON.parse(propsJson); } catch (e) {
        sendError("Failed to parse props JSON: " + safeErrorMessage(e), requestId);
        return;
    }

    try {
        var grooveApi = new LiveAPI(null, "live_set groove_pool grooves " + grooveIdx);
        if (!grooveApi || !grooveApi.id || parseInt(grooveApi.id) === 0) {
            sendError("No groove found at index " + grooveIdx, requestId);
            return;
        }

        var _grooveSettable = {"base":1, "timing":1, "velocity":1, "random":1, "quantize_rate":1};
        var setCount = 0;
        var errors = [];
        var details = [];

        for (var key in props) {
            if (!props.hasOwnProperty(key)) continue;
            if (!_grooveSettable[key]) {
                errors.push({ property: key, error: "not a settable property" });
                continue;
            }
            try {
                grooveApi.set(key, props[key]);
                setCount++;
                details.push({ property: key, value: props[key] });
            } catch (e) {
                errors.push({ property: key, error: e.toString() });
            }
        }

        var result = { groove_index: grooveIdx, properties_set: setCount };
        if (details.length > 0) result.details = details;
        if (errors.length > 0) result.errors = errors;
        sendResult(result, requestId);
    } catch (e) {
        sendError("Failed to set groove properties: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 6: Event-Driven Monitoring via live.observer pattern
//
// Max's LiveAPI in [js] supports callbacks via the second constructor arg.
// When a property changes, the callback fires with the new value.
// We store changes in a ring buffer and return them on demand.
// ---------------------------------------------------------------------------
var _observers = {};       // key = "path:property", value = {api, changes[]}
var MAX_OBSERVER_CHANGES = 200;  // ring buffer cap per observer

function handleObserveProperty(args) {
    // args: [lom_path (string), property_name (string), request_id (string)]
    if (args.length < 3) {
        sendError("observe_property requires lom_path, property_name, request_id", "");
        return;
    }
    var lomPath      = args[0].toString();
    var propertyName = args[1].toString();
    var requestId    = args[2].toString();

    var key = lomPath + ":" + propertyName;
    if (_observers[key]) {
        sendResult({ already_observing: true, key: key }, requestId);
        return;
    }

    try {
        // Create a LiveAPI with a callback function
        var obs = {
            changes: [],
            dropped: 0,
            api: null
        };

        // Store observer state before creating the API
        _observers[key] = obs;

        // Create LiveAPI with property observation
        var api = new LiveAPI(function(args) {
            // args is an array: [property_name, value]
            if (args && args.length >= 2) {
                var entry = {
                    property: args[0].toString(),
                    value: args[1],
                    time: Date.now()
                };
                if (obs.changes.length >= MAX_OBSERVER_CHANGES) {
                    obs.changes.shift();
                    obs.dropped++;
                }
                obs.changes.push(entry);
            }
        }, lomPath);

        if (!api || !api.id || parseInt(api.id) === 0) {
            delete _observers[key];
            sendError("Invalid LOM path: " + lomPath, requestId);
            return;
        }

        // Start observing the property
        api.property = propertyName;
        obs.api = api;

        sendResult({
            observing: true,
            key: key,
            path: lomPath,
            property: propertyName
        }, requestId);
    } catch (e) {
        delete _observers[key];
        sendError("Failed to start observing: " + safeErrorMessage(e), requestId);
    }
}

function handleStopObserving(args) {
    // args: [lom_path (string), property_name (string), request_id (string)]
    if (args.length < 3) {
        sendError("stop_observing requires lom_path, property_name, request_id", "");
        return;
    }
    var lomPath      = args[0].toString();
    var propertyName = args[1].toString();
    var requestId    = args[2].toString();

    var key = lomPath + ":" + propertyName;
    if (!_observers[key]) {
        sendResult({ was_observing: false, key: key }, requestId);
        return;
    }

    try {
        // Clear the property observation
        if (_observers[key].api) {
            _observers[key].api.property = "";
        }
    } catch (e) {}

    var changeCount = _observers[key].changes.length;
    delete _observers[key];

    sendResult({
        stopped: true,
        key: key,
        pending_changes_discarded: changeCount
    }, requestId);
}

function handleGetObservedChanges(args) {
    // args: [request_id (string)]
    var requestId = (args.length > 0) ? args[0].toString() : "";

    var allChanges = {};
    var totalChanges = 0;

    var totalDropped = 0;
    for (var key in _observers) {
        if (!_observers.hasOwnProperty(key)) continue;
        var obs = _observers[key];
        if (obs.changes.length > 0 || obs.dropped > 0) {
            allChanges[key] = obs.changes.slice(); // copy
            totalChanges += obs.changes.length;
            if (obs.dropped > 0) {
                totalDropped += obs.dropped;
            }
            obs.changes = []; // clear after reading
            obs.dropped = 0; // reset dropped counter
        }
    }

    var result = {
        total_changes: totalChanges,
        observer_count: Object.keys(_observers).length,
        changes: allChanges
    };
    if (totalDropped > 0) {
        result.total_dropped = totalDropped;
    }
    sendResult(result, requestId);
}

// ---------------------------------------------------------------------------
// Phase 9: Undo-Clean Parameter Control
//
// In Max's [js] context, we can set parameter values using the LiveAPI
// in a way that groups with the current undo step (or we can use
// begin_undo_step / end_undo_step for control). For "clean" sets,
// we suppress undo by not calling begin_undo_step.
//
// Note: True undo-free sets require live.remote~ in the Max patch.
// This JS-only approach sets the value via LiveAPI which creates minimal
// undo entries. The MCP tool documents this limitation.
// ---------------------------------------------------------------------------

function handleSetParamClean(args) {
    // args: [track_index (int), device_index (int), parameter_index (int), value (float), request_id (string)]
    if (args.length < 5) {
        sendError("set_param_clean requires track_index, device_index, parameter_index, value, request_id", "");
        return;
    }
    var trackIdx  = parseInt(args[0]);
    var deviceIdx = parseInt(args[1]);
    var paramIdx  = parseInt(args[2]);
    var value     = parseFloat(args[3]);
    var requestId = args[4].toString();

    var paramPath = "live_set tracks " + trackIdx + " devices " + deviceIdx + " parameters " + paramIdx;

    try {
        var paramApi = new LiveAPI(null, paramPath);
        if (!paramApi || !paramApi.id || parseInt(paramApi.id) === 0) {
            sendError("No parameter found at " + paramPath, requestId);
            return;
        }

        var paramName = paramApi.get("name").toString();
        var minVal    = parseFloat(paramApi.get("min"));
        var maxVal    = parseFloat(paramApi.get("max"));
        var clamped   = Math.max(minVal, Math.min(maxVal, value));

        // Set value directly — in [js] context this creates a minimal undo entry
        paramApi.set("value", clamped);

        sendResult({
            parameter_name: paramName,
            parameter_index: paramIdx,
            requested_value: value,
            actual_value: clamped,
            was_clamped: (clamped !== value),
            note: "Set via M4L bridge. For true undo-free sets, live.remote~ is needed in the Max patch."
        }, requestId);
    } catch (e) {
        sendError("Failed to set parameter cleanly: " + safeErrorMessage(e), requestId);
    }
}

// ---------------------------------------------------------------------------
// Phase 5: Audio Analysis
//
// Audio analysis in [js] relies on data fed from MSP objects in the Max patch.
// The Max patch should route: plugin~ → analysis objects → [js] via messages.
//
// For now, we provide a LOM-based approach that reads track meter levels
// (output_meter_left/right) which are always available without MSP setup.
// Full FFT/spectral analysis requires additional Max patch objects.
// ---------------------------------------------------------------------------

// Audio analysis data store — populated by Max patch messages
// Cross-track analysis state (send-route-capture-restore flow)
var _crossTrackState = null;

var _audioAnalysis = {
    rms_left: 0, rms_right: 0,
    peak_left: 0, peak_right: 0,
    spectrum: null,
    last_update: 0
};

// Called from Max patch: [js] receives "audio_data rms_l rms_r peak_l peak_r"
function audio_data() {
    var args = arrayfromargs(arguments);
    if (args.length >= 4) {
        _audioAnalysis.rms_left   = parseFloat(args[0]);
        _audioAnalysis.rms_right  = parseFloat(args[1]);
        _audioAnalysis.peak_left  = parseFloat(args[2]);
        _audioAnalysis.peak_right = parseFloat(args[3]);
        _audioAnalysis.last_update = Date.now();
    }
}

// Called from Max patch: [js] receives "spectrum_data bin0 bin1 bin2 ..."
function spectrum_data() {
    var args = arrayfromargs(arguments);
    if (args.length > 0) {
        var bins = [];
        var sumSquares = 0;
        var maxVal = 0;
        for (var i = 0; i < args.length; i++) {
            var v = parseFloat(args[i]);
            bins.push(v);
            sumSquares += v * v;
            if (v > maxVal) maxVal = v;
        }
        _audioAnalysis.spectrum = bins;
        // Auto-derive RMS/peak from spectrum when audio_data chain isn't connected
        if (_audioAnalysis.rms_left === 0 && _audioAnalysis.peak_left === 0) {
            var rms = Math.sqrt(sumSquares / bins.length);
            _audioAnalysis.rms_left = rms;
            _audioAnalysis.rms_right = rms;   // mono approximation from spectrum
            _audioAnalysis.peak_left = maxVal;
            _audioAnalysis.peak_right = maxVal;
        }
        _audioAnalysis.last_update = Date.now();
    }
}

function handleAnalyzeAudio(args) {
    // args: [track_index (int), request_id (string)]
    // track_index: >= 0 = specific track, -1 = device's own track, -2 = master track
    var trackIndex = -1;
    var requestId = "";
    if (args.length >= 2) {
        trackIndex = parseInt(args[0]);
        requestId = args[1].toString();
    } else if (args.length === 1) {
        // Backward compat: single arg = request_id only (default to own track)
        requestId = args[0].toString();
    }

    // First include MSP data from device's own track (always from _audioAnalysis)
    var result = {
        source: "lom_meters",
        rms_left: _audioAnalysis.rms_left,
        rms_right: _audioAnalysis.rms_right,
        peak_left: _audioAnalysis.peak_left,
        peak_right: _audioAnalysis.peak_right,
        last_update: _audioAnalysis.last_update
    };

    // Read the target track's output meter from LOM
    try {
        var lomPath;
        if (trackIndex >= 0) {
            lomPath = "live_set tracks " + trackIndex;
        } else if (trackIndex === -2) {
            lomPath = "live_set master_track";
        } else {
            // -1 or default: device's own track
            lomPath = "this_device canonical_parent";
        }
        result.target_track_index = trackIndex;

        var trackApi = new LiveAPI(null, lomPath);
        if (trackApi && trackApi.id && parseInt(trackApi.id) !== 0) {
            try { result.output_meter_left  = parseFloat(trackApi.get("output_meter_left")); } catch (e) {}
            try { result.output_meter_right = parseFloat(trackApi.get("output_meter_right")); } catch (e) {}
            try { result.output_meter_peak_left  = parseFloat(trackApi.get("output_meter_peak_level")); } catch (e) {}
            try { result.track_name = trackApi.get("name").toString(); } catch (e) {}
        }
    } catch (e) {
        result.meter_error = e.toString();
    }

    if (_audioAnalysis.last_update > 0) {
        result.has_msp_data = true;
        result.msp_data_age_ms = Date.now() - _audioAnalysis.last_update;
    } else {
        result.has_msp_data = false;
        result.note = "MSP audio analysis not configured. Connect plugin~ to analysis objects in the Max patch for RMS/peak data.";
    }

    sendResult(result, requestId);
}

function handleAnalyzeSpectrum(args) {
    // args: [request_id (string)]
    var requestId = (args.length > 0) ? args[0].toString() : "";

    if (!_audioAnalysis.spectrum || _audioAnalysis.spectrum.length === 0) {
        sendResult({
            has_spectrum: false,
            note: "No spectral data available. Connect fft~ -> cartopol~ -> the [js] object via 'spectrum_data' messages in the Max patch."
        }, requestId);
        return;
    }

    // Find dominant frequency bin
    var bins = _audioAnalysis.spectrum;
    var maxVal = 0;
    var maxIdx = 0;
    for (var i = 0; i < bins.length; i++) {
        if (bins[i] > maxVal) {
            maxVal = bins[i];
            maxIdx = i;
        }
    }

    // Calculate spectral centroid
    var weightedSum = 0;
    var totalEnergy = 0;
    for (var j = 0; j < bins.length; j++) {
        weightedSum += j * bins[j];
        totalEnergy += bins[j];
    }
    var centroid = (totalEnergy > 0) ? (weightedSum / totalEnergy) : 0;

    sendResult({
        has_spectrum: true,
        bin_count: bins.length,
        dominant_bin: maxIdx,
        dominant_magnitude: maxVal,
        spectral_centroid: centroid,
        data_age_ms: Date.now() - _audioAnalysis.last_update,
        bins: bins
    }, requestId);
}

// ---------------------------------------------------------------------------
// Cross-Track MSP Analysis (send-based routing)
// ---------------------------------------------------------------------------

// Determine which return track the device is on (-1 if not on a return track)
function _findDeviceReturnTrackIndex() {
    var parentTrack = new LiveAPI(null, "this_device canonical_parent");
    if (!parentTrack || !parentTrack.id || parseInt(parentTrack.id) === 0) {
        return -1;
    }
    var parentId = parseInt(parentTrack.id);

    var songApi = new LiveAPI(null, "live_set");
    var returnCount = parseInt(songApi.getcount("return_tracks"));

    for (var i = 0; i < returnCount; i++) {
        var rtApi = new LiveAPI(null, "live_set return_tracks " + i);
        if (rtApi && rtApi.id && parseInt(rtApi.id) === parentId) {
            return i;
        }
    }
    return -1;
}

function handleAnalyzeCrossTrack(args) {
    // args: [track_index (int), wait_ms (int), request_id (string)]
    if (_crossTrackState) {
        var rid = args.length > 0 ? args[args.length - 1].toString() : "";
        sendError("Cross-track analysis busy - try again shortly", rid);
        return;
    }
    if (args.length < 3) {
        sendError("analyze_cross_track requires track_index, wait_ms, request_id", "");
        return;
    }

    var trackIndex = parseInt(args[0]);
    var waitMs     = parseInt(args[1]);
    var requestId  = args[2].toString();

    // Clamp wait time: minimum 300ms, maximum 2000ms
    waitMs = Math.max(300, Math.min(2000, waitMs));

    // Step 1: Find which return track our device is on
    var returnTrackIndex = _findDeviceReturnTrackIndex();
    if (returnTrackIndex < 0) {
        sendError(
            "M4L bridge device is NOT on a return track. " +
            "Cross-track analysis requires the Audio Effect device on a return track (e.g. Return A).",
            requestId
        );
        return;
    }

    // Step 2: Validate target track exists
    var trackApi = new LiveAPI(null, "live_set tracks " + trackIndex);
    if (!trackApi || !trackApi.id || parseInt(trackApi.id) === 0) {
        sendError("Track " + trackIndex + " not found", requestId);
        return;
    }
    var trackName = "";
    try { trackName = trackApi.get("name").toString(); } catch (e) {}

    // Step 3: Access the target track's send to our return track
    var sendPath = "live_set tracks " + trackIndex + " mixer_device sends " + returnTrackIndex;
    var sendApi = new LiveAPI(null, sendPath);
    if (!sendApi || !sendApi.id || parseInt(sendApi.id) === 0) {
        sendError(
            "Cannot access send " + returnTrackIndex + " on track " + trackIndex +
            ". Track may not have enough sends.",
            requestId
        );
        return;
    }

    // Step 4: Save original send value
    var originalSendValue = parseFloat(sendApi.get("value"));

    // Step 5: Set send to maximum (1.0)
    var maxSend = parseFloat(sendApi.get("max"));
    sendApi.set("value", maxSend);

    // Step 6: Clear stale MSP data so we capture fresh data
    _audioAnalysis.rms_left = 0;
    _audioAnalysis.rms_right = 0;
    _audioAnalysis.peak_left = 0;
    _audioAnalysis.peak_right = 0;
    _audioAnalysis.spectrum = null;
    _audioAnalysis.last_update = 0;

    // Step 7: Store state and schedule deferred capture
    _crossTrackState = {
        trackIndex:        trackIndex,
        trackName:         trackName,
        returnTrackIndex:  returnTrackIndex,
        sendPath:          sendPath,
        originalSendValue: originalSendValue,
        requestId:         requestId,
        waitMs:            waitMs,
        startTime:         Date.now()
    };

    post("Cross-track analysis: routing track " + trackIndex + " -> return " + returnTrackIndex +
         " (send was " + originalSendValue.toFixed(3) + ", set to " + maxSend.toFixed(3) +
         ", wait " + waitMs + "ms)\n");

    // Schedule the capture after waitMs
    var captureTask = new Task(_crossTrackCapture);
    captureTask.schedule(waitMs);
}

function _crossTrackCapture() {
    if (!_crossTrackState) return;
    var s = _crossTrackState;

    try {
        // Step 1: Capture current MSP analysis data
        // Use value-based detection instead of timestamp comparison (more robust)
        var hasMspData = (
            _audioAnalysis.rms_left !== 0 ||
            _audioAnalysis.rms_right !== 0 ||
            _audioAnalysis.peak_left !== 0 ||
            _audioAnalysis.peak_right !== 0 ||
            (_audioAnalysis.spectrum !== null && _audioAnalysis.spectrum.length > 0)
        );

        // Diagnostic: log what MSP values we captured
        post("Cross-track capture: MSP rms_l=" + _audioAnalysis.rms_left.toFixed(6) +
             " rms_r=" + _audioAnalysis.rms_right.toFixed(6) +
             " peak_l=" + _audioAnalysis.peak_left.toFixed(6) +
             " peak_r=" + _audioAnalysis.peak_right.toFixed(6) +
             " spectrum=" + (_audioAnalysis.spectrum ? _audioAnalysis.spectrum.length + " bands" : "null") +
             " last_update=" + _audioAnalysis.last_update +
             " hasMspData=" + hasMspData + "\n");

        var capturedSpectrum = null;
        if (_audioAnalysis.spectrum && _audioAnalysis.spectrum.length > 0) {
            capturedSpectrum = [];
            for (var i = 0; i < _audioAnalysis.spectrum.length; i++) {
                capturedSpectrum.push(_audioAnalysis.spectrum[i]);
            }
        }

        // Step 2: Read LOM meters on the return track (our device track)
        var returnMeterLeft = 0, returnMeterRight = 0;
        try {
            var rtApi = new LiveAPI(null, "live_set return_tracks " + s.returnTrackIndex);
            returnMeterLeft = parseFloat(rtApi.get("output_meter_left"));
            returnMeterRight = parseFloat(rtApi.get("output_meter_right"));
        } catch (e) {}

        // Step 3: Read LOM meters on the source track
        var sourceMeterLeft = 0, sourceMeterRight = 0;
        try {
            var srcApi = new LiveAPI(null, "live_set tracks " + s.trackIndex);
            sourceMeterLeft = parseFloat(srcApi.get("output_meter_left"));
            sourceMeterRight = parseFloat(srcApi.get("output_meter_right"));
        } catch (e) {}

        // Step 4: ALWAYS restore original send value
        try {
            var restoreApi = new LiveAPI(null, s.sendPath);
            restoreApi.set("value", s.originalSendValue);
        } catch (restoreErr) {
            post("WARNING: Failed to restore send value: " + restoreErr.toString() + "\n");
        }

        // Step 5: Build result
        var result = {
            source: "cross_track_msp",
            track_index: s.trackIndex,
            track_name: s.trackName,
            return_track_index: s.returnTrackIndex,
            capture_wait_ms: s.waitMs,
            actual_capture_time_ms: Date.now() - s.startTime,
            has_msp_data: hasMspData,
            rms_left: _audioAnalysis.rms_left,
            rms_right: _audioAnalysis.rms_right,
            peak_left: _audioAnalysis.peak_left,
            peak_right: _audioAnalysis.peak_right,
            source_output_meter_left: sourceMeterLeft,
            source_output_meter_right: sourceMeterRight,
            return_output_meter_left: returnMeterLeft,
            return_output_meter_right: returnMeterRight,
            original_send_value: s.originalSendValue,
            send_restored: true
        };

        if (capturedSpectrum) {
            result.has_spectrum = true;
            result.spectrum = capturedSpectrum;
            result.bin_count = capturedSpectrum.length;

            // Compute dominant bin and spectral centroid
            var maxVal = 0, maxIdx = 0;
            var weightedSum = 0, totalEnergy = 0;
            for (var j = 0; j < capturedSpectrum.length; j++) {
                if (capturedSpectrum[j] > maxVal) {
                    maxVal = capturedSpectrum[j];
                    maxIdx = j;
                }
                weightedSum += j * capturedSpectrum[j];
                totalEnergy += capturedSpectrum[j];
            }
            result.dominant_bin = maxIdx;
            result.dominant_magnitude = maxVal;
            result.spectral_centroid = (totalEnergy > 0) ? (weightedSum / totalEnergy) : 0;
        } else {
            result.has_spectrum = false;
        }

        if (!hasMspData) {
            result.note = "No fresh MSP data received during capture window. " +
                "Ensure audio is playing on the source track and the Max patch " +
                "has plugin~ -> peakamp~/fffb~ -> snapshot~ -> [js] wired.";
        }

        post("Cross-track analysis complete: track " + s.trackIndex +
             " -> return " + s.returnTrackIndex +
             " (send restored to " + s.originalSendValue.toFixed(3) + ")\n");

        _crossTrackState = null;
        sendResult(result, s.requestId);

    } catch (e) {
        // ALWAYS restore send even on error
        try {
            var errRestoreApi = new LiveAPI(null, s.sendPath);
            errRestoreApi.set("value", s.originalSendValue);
        } catch (ignore) {}

        var rid = s.requestId;
        _crossTrackState = null;
        sendError("Cross-track capture failed: " + safeErrorMessage(e), rid);
    }
}
