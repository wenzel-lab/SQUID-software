# ZWO EFW Filter Wheel Integration

This directory contains the ZWO EFW (Electronic Filter Wheel) SDK and integration for SquidStation.

## Setup Instructions

### 1. Install udev Rules (for USB access)

The udev rules file has been installed to `/etc/udev/rules.d/99-zwo-efw.rules` to allow non-root access to the EFW device.

If you need to install it manually:
```bash
sudo cp efw.rules /etc/udev/rules.d/99-zwo-efw.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

After installing the rules, unplug and replug the EFW device, or log out and back in.

### 2. Verify USB Connection

Check that the EFW is detected:
```bash
lsusb | grep -i "03c3:1f01"
```

You should see:
```
Bus XXX Device XXX: ID 03c3:1f01 ZWO EFW
```

### 3. Configure SquidStation

In `control/_def.py`, set:
```python
USE_EMISSION_FILTER_WHEEL = True
EMISSION_FILTER_WHEEL_TYPE = "ZWO"
EMISSION_FILTER_WHEEL_INDICES = [1]  # Typically [1] for single wheel

# Optional ZWO-specific settings:
ZWO_EMISSION_FILTER_WHEEL_SDK_ID = None  # None = auto-detect first wheel
ZWO_EMISSION_FILTER_WHEEL_DELAY_MS = 0.0  # Delay in non-blocking mode (ms)
ZWO_EMISSION_FILTER_WHEEL_BLOCKING = True  # Wait for movement to complete
ZWO_EMISSION_FILTER_WHEEL_SLOT_NAMES = None  # Optional: ["DAPI", "GFP", "RFP", ...]
```

### 4. Test the Integration

Run the test script:
```bash
cd software
python tests/squid/test_zwo_efw.py
```

## Library Locations

The SDK library (`libEFWFilter.so`) is located in:
- `lib/x64/` - For x86_64 systems
- `lib/armv7/` - For ARMv7 systems
- `lib/armv8/` - For ARMv8/aarch64 systems

The controller will automatically search for the library in:
1. `/home/wenzel-lab/Downloads/efw/lib/{arch}/`
2. `software/drivers and libraries/zwo_efw/lib/{arch}/`
3. System library paths (`/usr/local/lib`, `/usr/lib`)
4. Current directory

## Features

- **Automatic enumeration**: Detects all connected ZWO EFW devices
- **Position control**: Set filter wheel positions (1-indexed for user convenience)
- **Blocking/non-blocking modes**: Choose whether to wait for movement completion
- **Calibration**: Support for EFW calibration (homing)
- **Error handling**: Comprehensive error reporting with SDK error codes
- **Multi-wheel support**: Can control multiple EFW wheels (if multiple are connected)

## SDK Documentation

The ZWO EFW SDK header file is available at:
- `include/EFW_filter.h`

For more information, refer to the ZWO EFW SDK documentation.

## Known Issue: Enumeration Failure After System Updates

**If `EFWGetNum()` returns 0 even though the device is visible:**

This is a known issue affecting both our integration and ASIStudio/ASICAP after system/driver updates. The SDK's udev-based enumeration mechanism breaks due to changes in udev/systemd versions.

**Symptoms:**
- Device visible via `lsusb` (03c3:1f01)
- `EFWCheck()` returns 1 (device recognized)
- `EFWGetNum()` returns 0 (enumeration fails)

**Solutions:**
1. **Contact ZWO Support** (recommended): Request SDK update compatible with current system
   - Email: yang.zhou@zwoptical.com
   - Mention: Enumeration issue after system update, same as ASIStudio
2. **Check for SDK/ASIStudio updates**: ZWO may have released a fix
3. **Run diagnostic tool**: `python tools/diagnose_zwo_efw.py` to verify all system checks

See `TROUBLESHOOTING.md` and `ENUMERATION_FIX.md` for detailed information.

## Troubleshooting

### Library not found
- Ensure the library file exists in one of the search paths
- Check file permissions: `chmod 755 lib/x64/libEFWFilter.so`
- Verify architecture: `uname -m` should match the library directory

### Permission denied
- Ensure udev rules are installed and reloaded
- Check that your user is in the `users` group: `groups`
- Try unplugging and replugging the device

### Device not detected
- Check USB connection: `lsusb | grep 03c3`
- Try different USB port
- Check if device is in use by another application (e.g., ASIStudio)

### Slot detection issues
- The EFW may need a few seconds after connection to detect slots
- Try running calibration: `controller.home(1)`


