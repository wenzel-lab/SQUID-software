#!/usr/bin/env python3
"""
Diagnostic script for ZWO EFW enumeration issues.

This script helps diagnose why EFWGetNum() returns 0 even though the device is visible.
"""

import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def check_usb_device():
    """Check if device is visible via USB."""
    print("=" * 60)
    print("1. USB Device Check")
    print("=" * 60)
    result = subprocess.run(["lsusb", "-d", "03c3:1f01"], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout:
        print(f"✓ Device found: {result.stdout.strip()}")
        return True
    else:
        print("✗ Device not found via lsusb")
        return False

def check_udev_rules():
    """Check if udev rules are installed."""
    print("\n" + "=" * 60)
    print("2. Udev Rules Check")
    print("=" * 60)
    rules_file = "/etc/udev/rules.d/99-zwo-efw.rules"
    if os.path.exists(rules_file):
        print(f"✓ Udev rules file exists: {rules_file}")
        with open(rules_file, 'r') as f:
            content = f.read()
            print(f"  Content: {content.strip()}")
        return True
    else:
        print(f"✗ Udev rules file not found: {rules_file}")
        print("  Install with: sudo cp software/drivers\\ and\\ libraries/zwo_efw/efw.rules /etc/udev/rules.d/99-zwo-efw.rules")
        return False

def check_device_permissions():
    """Check device file permissions."""
    print("\n" + "=" * 60)
    print("3. Device Permissions Check")
    print("=" * 60)
    # Find the device node
    result = subprocess.run(["lsusb", "-d", "03c3:1f01"], capture_output=True, text=True)
    if result.returncode == 0:
        # Parse bus and device number
        line = result.stdout.strip()
        if "Bus" in line and "Device" in line:
            parts = line.split()
            bus_idx = parts.index("Bus")
            dev_idx = parts.index("Device")
            bus = int(parts[bus_idx + 1])
            dev = int(parts[dev_idx + 1].rstrip(':'))
            dev_path = f"/dev/bus/usb/{bus:03d}/{dev:03d}"
            
            if os.path.exists(dev_path):
                stat = os.stat(dev_path)
                mode = oct(stat.st_mode)[-3:]
                print(f"✓ Device node exists: {dev_path}")
                print(f"  Permissions: {mode}")
                print(f"  Owner: {stat.st_uid}, Group: {stat.st_gid}")
                
                # Check if readable
                if os.access(dev_path, os.R_OK):
                    print("  ✓ Device is readable")
                else:
                    print("  ✗ Device is NOT readable")
                    return False
                return True
            else:
                print(f"✗ Device node not found: {dev_path}")
                return False
    return False

def check_sys_files():
    """Check /sys filesystem for device information."""
    print("\n" + "=" * 60)
    print("4. /sys Filesystem Check")
    print("=" * 60)
    
    # Find device in /sys/bus/usb/devices
    found = False
    for root, dirs, files in os.walk("/sys/bus/usb/devices"):
        for d in dirs:
            vid_file = os.path.join(root, d, "idVendor")
            pid_file = os.path.join(root, d, "idProduct")
            if os.path.exists(vid_file) and os.path.exists(pid_file):
                try:
                    with open(vid_file, 'r') as f:
                        vid = f.read().strip()
                    with open(pid_file, 'r') as f:
                        pid = f.read().strip()
                    if vid.lower() == "03c3" and pid.lower() == "1f01":
                        print(f"✓ Device found in /sys: {os.path.join(root, d)}")
                        print(f"  VID: {vid}, PID: {pid}")
                        found = True
                        
                        # Check if device path is accessible
                        dev_path = os.path.join(root, d)
                        if os.access(dev_path, os.R_OK):
                            print("  ✓ Device path is readable")
                        else:
                            print("  ✗ Device path is NOT readable")
                except:
                    pass
        if found:
            break
    
    if not found:
        print("✗ Device not found in /sys/bus/usb/devices")
        return False
    return True

def check_sdk_enumeration():
    """Check SDK enumeration."""
    print("\n" + "=" * 60)
    print("5. SDK Enumeration Check")
    print("=" * 60)
    
    try:
        import ctypes
        lib_path = "/home/wenzel-lab/Downloads/efw/lib/x64/libEFWFilter.so"
        
        if not os.path.exists(lib_path):
            print(f"✗ SDK library not found: {lib_path}")
            return False
        
        # Pre-load libudev
        try:
            import ctypes.util
            udev_path = ctypes.util.find_library("udev")
            if udev_path:
                ctypes.CDLL(udev_path, ctypes.RTLD_GLOBAL)
        except:
            pass
        
        lib = ctypes.CDLL(lib_path, ctypes.RTLD_GLOBAL)
        
        # Test EFWCheck
        lib.EFWCheck.restype = ctypes.c_int
        lib.EFWCheck.argtypes = [ctypes.c_int, ctypes.c_int]
        check_result = lib.EFWCheck(0x03C3, 0x1F01)
        print(f"EFWCheck(0x03C3, 0x1F01) = {check_result} {'✓' if check_result else '✗'}")
        
        # Test EFWGetNum
        lib.EFWGetNum.restype = ctypes.c_int
        num = lib.EFWGetNum()
        print(f"EFWGetNum() = {num} {'✓' if num > 0 else '✗'}")
        
        if num == 0 and check_result == 1:
            print("\n⚠ Issue confirmed: Device is recognized but enumeration fails")
            print("  This is the same issue affecting ASIStudio after system updates")
            return False
        
        return num > 0
    except Exception as e:
        print(f"✗ Error testing SDK: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all diagnostic checks."""
    print("ZWO EFW Diagnostic Tool")
    print("=" * 60)
    
    results = {
        "USB Device": check_usb_device(),
        "Udev Rules": check_udev_rules(),
        "Device Permissions": check_device_permissions(),
        "Sys Filesystem": check_sys_files(),
        "SDK Enumeration": check_sdk_enumeration(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for check, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{check:20s}: {status}")
    
    if not results["SDK Enumeration"] and results["USB Device"]:
        print("\n" + "=" * 60)
        print("Recommendations")
        print("=" * 60)
        print("1. The SDK enumeration is broken (same issue as ASIStudio)")
        print("2. This is likely due to changes in udev/systemd after driver updates")
        print("3. Possible solutions:")
        print("   a) Contact ZWO support for updated SDK compatible with current system")
        print("   b) Try downgrading udev/systemd (not recommended)")
        print("   c) Use a different system or VM where enumeration works")
        print("   d) Wait for ZWO to release SDK update")

if __name__ == "__main__":
    main()

