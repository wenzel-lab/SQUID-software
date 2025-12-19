# ZWO EFW Test Notes

## Current Status

The test script (`test_zwo_efw.py`) has been updated to work around configuration requirements, but there's a library dependency issue.

## Error: undefined symbol: udev_device_get_devnode

The ZWO EFW SDK library requires `libudev` but is having trouble finding the `udev_device_get_devnode` symbol. This is likely because:

1. The SDK library was compiled against a different version of libudev
2. The library needs to be linked at runtime with the correct libudev version

## Solutions to Try

### Option 1: Install libudev-dev (if not already installed)
```bash
sudo apt-get install libudev-dev
```

### Option 2: Check library version compatibility
The system has `libudev1:amd64` version `255.4-1ubuntu8.8`. The SDK may need a specific version.

### Option 3: Set LD_LIBRARY_PATH
Try setting the library path explicitly:
```bash
export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
python tests/squid/test_zwo_efw.py
```

### Option 4: Use a different SDK version
The SDK version 1.8.4 may have compatibility issues. Check if there's a newer version or if the library needs to be recompiled.

## Test Script Fixes Applied

1. ✅ Created cache directory automatically
2. ✅ Avoided importing full config system by defining ZWOFilterWheelConfig locally
3. ✅ Fixed numpy/scipy compatibility (numpy 1.26.4, opencv-python-headless 4.9.0.80)

## Next Steps

Once the libudev issue is resolved, the test should be able to:
1. Load the ZWO EFW SDK library
2. Enumerate connected filter wheels
3. Test position changes
4. Verify all controller functionality


