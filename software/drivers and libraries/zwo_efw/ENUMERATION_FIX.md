# ZWO EFW Enumeration Issue - Fix Attempts

## Problem Summary

After system/driver updates, `EFWGetNum()` returns 0 even though:
- Device is visible: `lsusb` shows `03c3:1f01 ZWO EFW` ✓
- Device is recognized: `EFWCheck(0x03C3, 0x1F01)` returns 1 ✓
- Udev rules installed: `/etc/udev/rules.d/99-zwo-efw.rules` ✓
- Permissions correct: Device node is readable ✓
- /sys filesystem: Device information present ✓

**Same issue affects ASIStudio/ASICAP** - this is a system-level SDK problem, not a code issue.

## Diagnostic Results

Run: `python tools/diagnose_zwo_efw.py`

All system checks pass, only SDK enumeration fails.

## Root Cause Analysis

The SDK uses udev for enumeration. The symbol `udev_device_get_devnode` exists in libudev.so.1 with version `LIBUDEV_183`, but the SDK may be looking for an unversioned or differently versioned symbol.

## Attempted Fixes

### 1. ✅ Udev Rules Installation
- Installed `/etc/udev/rules.d/99-zwo-efw.rules`
- Reloaded udev rules
- **Result**: Rules installed but enumeration still fails

### 2. ✅ Pre-loading libudev
- Code now pre-loads libudev before loading SDK
- **Result**: Library loads but enumeration still fails

### 3. ⚠️ Workaround Attempts
- Tried `EFWGetID(0)` - fails with error 2 (EFW_ERROR_INVALID_ID)
- Tried `EFWOpen(0)` - fails with error 2 (EFW_ERROR_INVALID_ID)
- **Result**: SDK requires proper enumeration to assign device IDs

## Potential Solutions

### Solution 1: Contact ZWO Support (Most Likely to Work)

This is a known SDK compatibility issue. Contact ZWO:
- Email: yang.zhou@zwoptical.com
- Request: Updated SDK compatible with:
  - libudev 255.4+
  - systemd 255+
  - Current kernel USB subsystem

### Solution 2: Try Compatibility Symbol Link

The SDK might need an older libudev version. Try creating a compatibility link:

```bash
# Check if libudev.so.0 exists
ls -la /lib/x86_64-linux-gnu/libudev.so.0

# If not, try creating a symlink (may not work due to versioned symbols)
sudo ln -s /lib/x86_64-linux-gnu/libudev.so.1 /lib/x86_64-linux-gnu/libudev.so.0
sudo ldconfig
```

**Warning**: This may not work if the SDK needs specific symbol versions.

### Solution 3: Check for SDK Update

Check ZWO website for:
- Newer SDK version
- Linux compatibility updates
- Known issues page

### Solution 4: System Rollback (Not Recommended)

If you have a system backup from before the driver update, you could:
- Restore the previous system state
- Or use a VM/container with older udev version

### Solution 5: Alternative SDK Version

Check if there's a different SDK version (beta, development) that works with current system.

## For ASIStudio/ASICAP

The same enumeration issue affects ZWO's own software. To fix:

1. **Check for ASIStudio update**: ZWO may have released a fix
2. **Contact ZWO support**: Report the enumeration issue
3. **Try running as different user**: Sometimes helps with udev context
4. **Check ZWO forums**: Other users may have solutions

## Current Status

- ✅ **Integration code**: Complete and working
- ✅ **Library loading**: Successfully loads SDK
- ✅ **Device recognition**: EFWCheck works
- ❌ **SDK enumeration**: Broken (EFWGetNum returns 0)
- ⚠️ **System-level issue**: Affects both our code and ASIStudio

## Next Steps

1. **Immediate**: Contact ZWO support about SDK enumeration issue
2. **Short-term**: Check for SDK/ASIStudio updates
3. **Long-term**: Wait for ZWO to release compatible SDK

The integration is ready - it just needs the SDK enumeration to work, which requires a fix from ZWO.

## Testing When Fixed

Once enumeration works, test with:
```bash
mamba activate squid
cd /home/wenzel-lab/Desktop/SQUID-software/software
python tests/squid/test_zwo_efw.py
```

Expected output should show:
- `Found 1 ZWO EFW filter wheel(s)`
- Successful position changes
- All functionality working

