# Device E2E test plan (Chronicle / Heidi Remote)

Reorganise device tests into **one flow per file**, grouped by feature folder.
Flows and UI labels traced from `scribe-fe-v2` source (`src/features/chronicle/`).

## Structure

```
tests/device-connection/
  conftest.py                       # DevicePage fixture (migrated from tests/devices/)
  test_first_onboarding_flow.py     # remove linked device -> scan -> connect -> setup default note
  test_connected_reconnect_flow.py  # linked+disconnected -> Reconnect -> verify state info
  test_reconnect_stress_flow.py     # disconnect<->reconnect x10, report success rate
  test_startup_autoconnect_flow.py  # quit app -> reopen -> auto-connect -> verify BLE status
  test_remote_lost_flow.py          # remove -> dialog -> "I've lost my device" -> success
tests/ota-upgrade/
  test_ota_upgrade_flow.py          # firmware update modal: confirm -> in-progress -> completed
tests/remote-session-recording/
  test_remote_session_recording.py  # react to physical-device recording (needs device + manual press)
tests/bulk-sync/
  test_bulk_sync_flow.py            # sync-progress UI after offline device recording (needs device)
```

Old `tests/devices/` (6 tests) is migrated into `device-connection/` and removed.

## Page Objects (selectors live here only)

- Extend `pages/device.py`: onboarding modal, remove dialog steps, reconnect,
  device-state reads (serial/firmware/battery/status badge), connected-via label.
- New `pages/firmware.py`: OTA modal (confirm/in-progress/completed/failed views).
- New `pages/bulk_sync.py`: BulkSyncWidget + sync detail card.

## Markers

- `@pytest.mark.needs_device` — requires a real Chronicle paired/nearby; skips otherwise.
- `@pytest.mark.needs_manual` — requires a human to press the physical device button
  (remote recording start/stop/pause has NO app-side control — it's device-driven).
- Reuse existing skip pattern: `if not devices.has_device_card(): pytest.skip(...)`.

## Key UI labels (verified against source; text-match for now, aria-labels later)

### Device card (connected/disconnected)
- Status row: `Status:` + badge `Connected` / `Disconnected` / `Limited Connection`
- Connected sub-label: `Connected via Bluetooth` / `Connected via USB (Transfer mode)`
- Buttons: `Reconnect` (-> `Reconnecting…` while busy) / `Disconnect`
- Info labels: `Serial Number`, `Battery` ({n}%), `Firmware version`

### First onboarding
- Initial pairing card: button `Connect my Heidi Remote`
- Onboarding modal title: `Adding device`; scan heading `Searching for devices`;
  device rows = accessible name is the device NAME; footer `Search again`
- Connecting (non-dismissible): `Connecting to device`
- Connected (non-dismissible): `Successfully connected`, button `Setup my device`
- Setup wizard title `Heidi Remote Setup`; default-note step heading
  `Select your default note`, combobox testTag `setup-default-note-combobox`,
  button `Confirm`; language step `Confirm`/`Skip`

### Remove / lost device
- Card button: `Remove device` -> dialog title `Removing device`
- Connected path: `Remove your Heidi Remote device?` -> `Remove device` / `No, keep this device`
- Disconnected path: `Keep your device close and connected` ->
  `Try again` / ghost `I've lost my device`
- Lost warning: `You may lose your unsynced sessions` -> `Yes, remove` / `No, keep for now`
- Removing (non-dismissible): `Removing device`
- Success: `Your Heidi Remote has been successfully removed`, button `Dismiss`

### OTA
- Banner card: title `New Firmware Update`, button `Update`
- Confirm view: `New firmware available`, button `Upgrade now` / `Remind me later`
- In-progress (non-dismissible): `Update in progress` + {n}% (NO per-phase text)
- Completed: `Successfully updated`, button `Done`
- Failed: `We ran into some issues`, button `Try later`

### Remote session recording (device-driven, no app button)
- Input selector trigger testid `v2-input-source-trigger`, device row label `Heidi Remote`
- Live indicator: bars + timer + `Heidi Remote`; controls tooltips
  `Pause transcribing` / `Resume transcribing` / `Stop transcribing`
- Toasts: `New session started via Heidi Remote`, `Heidi Remote is recording offline`
- Status popover testid `device-status-popover-card`: `Bluetooth` / `Disconnected`

### Bulk sync (Rust auto-triggered; no start button)
- Widget testid `bulk-sync-widget`; title `Syncing`
- Download subtitle: `Transferring via USB-C` / `Wi-Fi` / `Bluetooth`
- Detail card: `Syncing sessions {n}/{total}`; terminal `Syncing complete` /
  `Syncing Interrupted` / `Bulk sync failed` (+ `Retry sync`)

## Hard constraints (from source trace)

1. **Remote recording uses the same session controls.** The physical device
   button and the in-app session controls (Transcribe / Pause transcribing /
   End recording) are interchangeable once the device is connected. So the
   remote-session test is **software-driven** (select 'Heidi Remote' input, then
   start/pause/resume/stop via the session controls) — no manual button press.
   Audio is the device mic (not BlackHole), so it asserts the FLOW, not content.
2. **Bulk sync auto-triggers from Rust** — only `Retry sync` + transport switches
   are clickable. Tests verify progress UI while a real sync runs.
3. **OTA needs a device with an available firmware update** — otherwise skip.
4. Several modals are **non-dismissible** (connecting, connected, setup wizard,
   removing, OTA in-progress) — no Close control there.
5. Selectors are **text-based for now** (few testids). i18n/copy changes will
   break them; a follow-up PR adds aria-labels to scribe-fe-v2.
