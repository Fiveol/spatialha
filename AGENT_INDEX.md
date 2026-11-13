# spatialha Repository Index

## Overview
**spatialha** is a Home Assistant custom integration (domain: `spatialha`) that provides BLE-based indoor positioning and target tracking. It estimates device locations using RSSI trilateration from placed BLE scanners across multiple floors, and tracks "home/away" status for defined targets.

---

## Repository Structure

```
custom_components/spatialha/
├── __init__.py      # Main integration: setup/teardown, panel registration
├── const.py         # Constants (DOMAIN = "spatialha")
├── config_flow.py   # Config flow (single-instance allowed)
├── ble.py           # BLE scanning, iBeacon parsing, per-scanner RSSI
├── floorplan.py     # Floorplan model, defaults, clamping, storage
├── positioning.py   # Trilateration engine (RSSI→distance, 3D solve)
├── targets.py       # Target state computation, device_tracker updates
├── storage.py       # .storage/spatialha/* with legacy migration
├── websocket.py     # WebSocket API registration
├── ws_ble.py        # WebSocket: BLE get_data, subscribe
├── ws_floorplan.py  # WebSocket: floorplan get/set/subscribe
├── ws_targets.py    # WebSocket: targets CRUD, subscribe
├── ws_settings.py   # WebSocket: settings/get/set, tracked CRUD
├── gps.py           # GPS device_tracker entity listing
└── device_tracker.py# Device tracker platform: spatialhaTargetTracker
├── frontend/
│   ├── spatialha-panel.js  # Main panel entry point
│   └── modules/
│       ├── ble.js          # BLE data display
│       ├── fp-canvas.js    # Canvas rendering
│       ├── fp-data.js      # Floorplan data transforms
│       ├── fp-ui.js        # UI components
│       ├── gps.js          # GPS entity display
│       ├── home3d.js       # 3D visualization
│       ├── settings.js     # Settings UI
│       ├── targets.js      # Target management UI
│       └── utils.js        # Utility functions
└── strings.json          # i18n strings for config flow
```

---

## Core Data Flow

### BLE Scanning Pipeline
1. **`_async_start_ble_polling()`** (`__init__.py`) — Starts `async_track_time_interval` polling at `UPDATE_INTERVAL` (default 1.0s).
2. **`_async_update_ble_data_and_push()`** (`__init__.py`) — On each tick:
   - Calls `_get_ble_data(hass)` to scan BLE via HA Bluetooth API
   - Parses iBeacon advertisements (manufacturer_data 0x004C)
   - Filters sightings by staleness (180s default, or `interval*3`)
   - Performs 3D trilateration via `positioning.estimate_positions()`
   - Persists to `.storage/spatialha/ble_data` and `.storage/spatialha/sightings`
   - Pushes `ble_update` events to WebSocket subscribers
   - Calls `_async_update_target_trackers()` to recompute target states

3. **`_get_ble_data()`** (`ble.py`) — Core scanning function that returns:
   - `scanners`: list of `{source, name, adapter, type}`
   - `sightings`: list of per-scanner `{address, name, rssi, source, scanner_name, service_uuids, ibeacon}`
   - `devices`: unique devices with `per_scanner` RSSI map and `positions` (from trilateration)
   - `positions`: estimated 3D positions per device

### Target Tracking
- **`_compute_target_state()`** (`targets.py`) — Determines "home"/"not_home"/"not_home":
  - **BLE**: if all assigned BLE device addresses are seen (have at least one non-None RSSI sighting)
  - **GPS**: if all assigned `device_tracker` entity states are "home"
  - No assigned devices → "not_home"
- **`_async_update_target_trackers()`** (`targets.py`) — For each target, computes state and updates HA `device_tracker` entities. Pushes `targets_update` events to subscribers.

### Floorplan Management
- **`_async_load_floorplan()` / `_async_save_floorplan()`** (`floorplan.py`) — Storage in `.storage/spatialha/floorplan`
- Floor format: `{units, active_floor_id, door_defaults, window_defaults, floors[]}`
  - Each floor has: `id, name, level, offset_x, offset_y, scale, rotation, width, depth, height, points, walls, rooms, doors, windows, receivers, scanners`
- **`_clamp_point_to_floor()`** — Constrains points to floor bounds
- **Legacy migration** — `_async_migrate_legacy_storage()` moves dot-prefixed files to folder structure

### 3D Positioning (Trilateration)
- **`rssi_to_distance()`** — Log-distance path loss: `d = 10^((tx_power - rssi)/(10*n))`
- **`trilaterate()`** — Weighted linear least-squares for 2D/3D
- **`solve_3d()`** — Full 3D solver across multiple floors:
  - Stacks floor bases via `floor_bases()` (each floor's height + `FLOOR_GAP = 1.5m`)
  - Coplanar anchors (same z) → 2D solve with z held at weighted mean
  - Non-coplanar → full 3D sphere intersection via `_three_sphere_candidates()`
  - Refines via Gauss-Newton with Levenberg-Marquardt damping
  - Starts from multiple seeds: centroid, floor extremes, analytic mirrors, linearized init
- **`estimate_positions()`** — Main entry: for each BLE device, gathers anchors from all scanners on all floors, calls `solve_3d()`, assigns device to the floor whose z-range contains the result

### Storage Layout
| Key | Path | Format |
|---|---|---|
| `STORAGE_KEY_SETTINGS` | `.storage/spatialha/settings` | `{"update_interval": 1.0}` |
| `STORAGE_KEY_BLE_DATA` | `.storage/spatialha/ble_data` | BLE devices/sightings dict |
| `STORAGE_KEY_BLE_SIGHTINGS` | `.storage/spatialha/sightings` | Separate sightings file |
| `STORAGE_KEY_TARGETS` | `.storage/spatialha/targets` | `{"targets": [ {...} ]}` |
| `STORAGE_KEY_TRACKED` | `.storage/spatialha/tracked` | `{"devices": ["AA:BB:CC:...], ...}` |
| `STORAGE_KEY_FLOORPLAN` | `.storage/spatialha/floorplan` | Floorplan dict |
| `STORAGE_VERSION` | `1` | — |

---

## WebSocket API

All frontend queries go through registered WebSocket commands (`websocket.py`). Commands are prefixed with `spatialha/`:

| Command | Handler | Description |
|---|---|---|
| `spatialha/get_version` | `handle_get_version` | Return integration version |
| `spatialha/get_info` | `handle_get_info` | Version + HA version |
| `spatialha/ble/get_data` | `handle_ble_get_data` | Full BLE device data |
| `spatialha/ble/subscribe` | `handle_ble_subscribe` | Subscribe to `ble_update` events |
| `spatialha/floorplan/get` | `handle_floorplan_get` | Load floorplan |
| `spatialha/floorplan/set` | `handle_floorplan_set` | Save floorplan |
| `spatialha/floorplan/subscribe` | `handle_floorplan_subscribe` | Floorplan update events |
| `spatialha/targets/list` | `handle_targets_list` | List targets with computed state |
| `spatialha/targets/create` | `handle_targets_create` | Create new target + tracker entity |
| `spatialha/targets/update` | `handle_targets_update` | Update target fields |
| `spatialha/targets/delete` | `handle_targets_delete` | Delete target + remove tracker |
| `spatialha/targets/subscribe` | `handle_targets_subscribe` | Target update events |
| `spatialha/settings/get` | `handle_settings_get` | Load settings |
| `spatialha/settings/set` | `handle_settings_set` | Update `update_interval`, restart polling |
| `spatialha/tracked/get` | `handle_tracked_get` | List tracked devices |
| `spatialha/tracked/set` | `handle_tracked_set` | Add/remove tracked device |
| `spatialha/tracked/clear` | `handle_tracked_clear` | Clear all tracked devices |

All commands have capital-alias variants (`.../get_capital`, etc.) for backward compatibility.

---

## Device Tracker

- **`spatialhaTargetTracker`** (`device_tracker.py`) extends `TrackerEntity`
- Set up in `async_setup_entry()` — one tracker per target
- State computed via `_compute_target_state()` (BLE + GPS)
- Icon per target type: `mdi:account` for Person, `mdi:help-circle` for Other
- Source type: `BLUETOOTH`
- Extra attributes: `target_type`, `ble_devices`, `target_id`

---

## Frontend Modules

| Module | Purpose |
|---|---|
| `spatialha-panel.js` | Panel entry point, loads all other modules |
| `ble.js` | BLE device list, signal strength display, iBeacon details |
| `fp-canvas.js` | Canvas rendering of floorplan with devices |
| `fp-data.js` | Floorplan data transforms (world↔local coordinate conversion) |
| `fp-ui.js` | UI: floor editor, adding walls/doors/windows, scanner placement |
| `gps.js` | GPS entity list, tracking toggle |
| `home3d.js` | 3D visualization of positioned devices across floors |
| `settings.js` | Settings: update interval, target management |
| `targets.js` | Target CRUD, GPS entity assignment, BLE device assignment |
| `utils.js` | Shared utilities (coordinate transforms, formatting) |

Key data flow in frontend:
- Floorplan coordinates stored in floor-local frame, converted to world XY via `_floor_frame()` (scale, offset, rotation)
- `fp-data.js` mirrors the backend `_to_world()` / `_to_local()` functions from `positioning.py`
- 3D positions from backend flow through `home3d.js` with floor stacking (z = floor_base + scanner_height)
- Target states (`home`/`not_home`) driven by WebSocket `targets_update` events

---

## Key Constants

| Constant | Value | Meaning |
|---|---|---|
| `DEFAULT_UPDATE_INTERVAL` | `1.0` | BLE polling interval (seconds) |
| `DEFAULT_TX_POWER` | `-59.0` | Default Tx power for RSSI→distance (dBm) |
| `DEFAULT_PATH_LOSS_N` | `2.0` | Path loss exponent |
| `MIN_DISTANCE` | `0.2` | Clamp minimum distance (meters) |
| `MAX_DISTANCE` | `50.0` | Clamp maximum distance (meters) |
| `FLOOR_GAP` | `1.5` | Z-gap between stacked floors |
| `SCANNER_HEIGHT` | `1.0` | Scanner z-height above floor |
| `COPLANAR_Z_EPS` | `0.5` | If max(z) - min(z) < this, treat as coplanar (2D solve) |

---

## Integration Lifecycle

1. **Setup** (`async_setup_entry`):
   - Remove duplicate panels
   - Register WebSocket commands
   - Load settings, targets, floorplan from storage
   - Start BLE polling
   - Forward to `device_tracker` platform — creates one `spatialhaTargetTracker` per target
   - Register static frontend serving at `/api/panels/spatialha/...`

2. **Polling Loop** (every `update_interval`):
   - Scan BLE → filter stale sightings → trilateration → estimate positions
   - Persist BLE data to `.storage/`
   - Push `ble_update` to BLE subscribers
   - Recompute all target states → push `targets_update` to target subscribers
   - Update HA `device_tracker` entity states

3. **User Actions** (via WebSocket or frontend):
   - Create/update/delete targets → storage + tracker entity updates
   - Adjust floorplan → save to storage + push `floorplan_update`
   - Change `update_interval` → persist + restart polling
   - Track/untrack BLE addresses → `.storage/spatialha/tracked`

4. **Unload** (`async_unload_entry`):
   - Unforward `device_tracker`
   - Remove all spatialha panels
   - Cancel BLE polling interval
   - Clean up cached data (keep settings/targets for next setup)