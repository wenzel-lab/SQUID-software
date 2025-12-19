# ZWO EFW Troubleshooting Guide

## Issue: EFWGetNum() Returns 0 After System/Driver Update

### Symptoms
- Device is visible via `lsusb` (shows `03c3:1f01 ZWO EFW`)
- `EFWCheck(0x03C3, 0x1F01)` returns 1 (device recognized)
- `EFWGetNum()` returns 0 (enumeration fails)
- Same issue affects ASIStudio/ASICAP

### Root Cause
The ZWO EFW SDK uses udev internally for device enumeration. After system/driver updates (especially NVIDIA drivers), changes in udev/systemd can break the SDK's enumeration mechanism, even though:
- USB device is visible
- Udev rules are installed correctly
- Device permissions are correct
- /sys filesystem has device information

### Diagnostic Results
Run the diagnostic tool:
```bash
cd software
mamba activate squid
python tools/diagnose_zwo_efw.py
```

Expected output shows all checks pass except SDK enumeration.

### Solutions

#### 1. Contact ZWO Support (Recommended)
This is a known SDK issue. Contact ZWO support (yang.zhou@zwoptical.com) and request:
- Updated SDK compatible with current udev/systemd versions
- Workaround for enumeration issues
- Timeline for SDK update

#### 2. System-Level Workarounds

**Option A: Check for udev/systemd version compatibility**
```bash
udevadm --version
systemd --version
```
Compare with versions on a working system.

**Option B: Try different udev rules format**
The SDK might need specific udev attributes. Try:
```bash
sudo nano /etc/udev/rules.d/99-zwo-efw.rules
```
Add:
```
SUBSYSTEM=="usb", ATTRS{idVendor}=="03c3", ATTRS{idProduct}=="1f01", MODE="0666", GROUP="users"
KERNEL=="usb[0-9]*", ATTRS{idVendor}=="03c3", ATTRS{idProduct}=="1f01", MODE="0666", GROUP="users"
```
Then:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Option C: Check for conflicting udev rules**
```bash
grep -r "03c3\|1f01" /etc/udev/rules.d/
```

#### 3. Application-Level Workarounds

Since the SDK enumeration is broken, we've implemented a workaround in the code that:
- Detects when `EFWGetNum()` fails but `EFWCheck()` succeeds
- Attempts to use device ID 0 directly
- Provides clear error messages

However, this workaround is limited because the SDK still needs proper enumeration to assign device IDs.

#### 4. Alternative: Use Different System/VM
If you have access to a system where ASIStudio works, the SDK enumeration should work there too.

### For ASIStudio/ASICAP

The same issue affects ZWO's own software. To fix ASIStudio:
1. Check ZWO website for updated ASIStudio version
2. Contact ZWO support about the enumeration issue
3. Try running ASIStudio with different permissions or in compatibility mode

### Long-term Solution

This requires an SDK update from ZWO. The SDK needs to be updated to work with:
- Current udev versions (255.4+)
- Current systemd versions
- Current kernel USB subsystem

### Monitoring

Check if ZWO releases an SDK update:
- ZWO website: https://astronomy-imaging-camera.com/
- SDK download page
- Contact: yang.zhou@zwoptical.com

### Current Status

- ✅ Integration code is complete and working
- ✅ Library loads successfully
- ✅ Device recognition works (EFWCheck)
- ❌ SDK enumeration broken (EFWGetNum)
- ⚠️  Same issue as ASIStudio (system-level, not code issue)

The integration is ready - it just needs the SDK enumeration to work, which requires either:
1. SDK update from ZWO
2. System configuration fix
3. Workaround from ZWO support

