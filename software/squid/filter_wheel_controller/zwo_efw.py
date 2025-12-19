"""
ZWO EFW (Electronic Filter Wheel) controller implementation.

This module provides integration with ZWO EFW filter wheels using the ZWO EFW SDK.
Supports enumeration, connection, and control of ZWO EFW-MINI and other EFW models.
"""

import ctypes
import os
import platform
import time
from pathlib import Path
from typing import List, Dict, Optional

import squid.logging
from squid.abc import AbstractFilterWheelController, FilterWheelInfo, FilterControllerError
from squid.config import ZWOFilterWheelConfig


# EFW SDK constants
EFW_ID_MAX = 128
EFW_SUCCESS = 0
EFW_ERROR_INVALID_INDEX = -1
EFW_ERROR_INVALID_ID = -2
EFW_ERROR_INVALID_VALUE = -3
EFW_ERROR_REMOVED = -4
EFW_ERROR_MOVING = -5
EFW_ERROR_ERROR_STATE = -6
EFW_ERROR_GENERAL_ERROR = -7
EFW_ERROR_NOT_SUPPORTED = -8
EFW_ERROR_INVALID_LENGTH = -9
EFW_ERROR_CLOSED = -10

# EFW SDK structures
class EFW_INFO(ctypes.Structure):
    _fields_ = [
        ("ID", ctypes.c_int),
        ("Name", ctypes.c_char * 64),
        ("slotNum", ctypes.c_int),
    ]


class EFW_ID(ctypes.Structure):
    _fields_ = [("id", ctypes.c_ubyte * 8)]


class ZWOEFWController(AbstractFilterWheelController):
    """
    Controller for ZWO EFW (Electronic Filter Wheel) devices.
    
    This implementation uses the ZWO EFW SDK (libEFWFilter.so) to communicate
    with ZWO filter wheels via USB.
    """

    def __init__(self, config: ZWOFilterWheelConfig):
        """
        Initialize the ZWO EFW controller.
        
        Args:
            config: ZWOFilterWheelConfig containing configuration settings
        """
        self.log = squid.logging.get_logger(self.__class__.__name__)
        self._config = config
        self._available_filter_wheels = []
        self._delay_offset_ms = 0.0
        self._efw_ids: Dict[int, int] = {}  # Maps filter wheel index to EFW SDK ID
        self._efw_info: Dict[int, EFW_INFO] = {}  # Cached info for each wheel
        self._lib = None
        self._load_sdk()

    def _load_sdk(self):
        """Load the ZWO EFW SDK library."""
        system = platform.system()
        machine = platform.machine()
        
        # Determine library path based on system architecture
        if system == "Linux":
            if machine == "x86_64":
                lib_name = "libEFWFilter.so"
                lib_dir = "x64"
            elif machine in ["armv7l", "armv7"]:
                lib_name = "libEFWFilter.so"
                lib_dir = "armv7"
            elif machine in ["aarch64", "armv8"]:
                lib_name = "libEFWFilter.so"
                lib_dir = "armv8"
            else:
                raise OSError(f"Unsupported Linux architecture: {machine}")
        elif system == "Darwin":  # macOS
            if machine == "arm64":
                lib_name = "libEFWFilter.dylib"
                lib_dir = "mac_arm64"
            elif machine == "x86_64":
                lib_name = "libEFWFilter.dylib"
                lib_dir = "mac_x64"
            else:
                raise OSError(f"Unsupported macOS architecture: {machine}")
        else:
            raise OSError(f"Unsupported operating system: {system}")

        # Try multiple locations for the library
        possible_paths = [
            # Try SDK location from Downloads
            Path("/home/wenzel-lab/Downloads/efw/lib") / lib_dir / lib_name,
            # Try relative to this file
            Path(__file__).parent.parent.parent.parent / "drivers and libraries" / "zwo_efw" / "lib" / lib_dir / lib_name,
            # Try system library paths
            Path("/usr/local/lib") / lib_name,
            Path("/usr/lib") / lib_name,
            # Try current directory
            Path(".") / lib_name,
        ]

        lib_path = None
        for path in possible_paths:
            if path.exists():
                lib_path = path
                break

        if lib_path is None:
            # Try loading from library path if available
            try:
                self._lib = ctypes.CDLL(lib_name)
                self.log.info(f"Loaded ZWO EFW SDK library: {lib_name} (from system path)")
            except OSError:
                raise OSError(
                    f"Could not find ZWO EFW SDK library '{lib_name}'. "
                    f"Tried paths: {[str(p) for p in possible_paths]}. "
                    f"Please ensure the SDK is installed or copied to one of these locations."
                )
        else:
            try:
                # Try loading with RTLD_GLOBAL to make symbols available to the library
                import ctypes.util
                # Pre-load libudev if available - SDK requires it for enumeration
                try:
                    udev_path = ctypes.util.find_library("udev")
                    if udev_path:
                        udev_lib = ctypes.CDLL(udev_path, ctypes.RTLD_GLOBAL)
                        self.log.debug(f"Pre-loaded libudev from: {udev_path}")
                    else:
                        # Try common paths
                        for path in ["/lib/x86_64-linux-gnu/libudev.so.1", "/usr/lib/x86_64-linux-gnu/libudev.so.1"]:
                            try:
                                udev_lib = ctypes.CDLL(path, ctypes.RTLD_GLOBAL)
                                self.log.debug(f"Pre-loaded libudev from: {path}")
                                break
                            except:
                                continue
                except Exception as e:
                    self.log.warning(f"Could not pre-load libudev: {e}")
                
                # Load the EFW library
                self._lib = ctypes.CDLL(str(lib_path), ctypes.RTLD_GLOBAL)
                self.log.info(f"Loaded ZWO EFW SDK library from: {lib_path}")
            except OSError as e:
                error_msg = str(e)
                if "udev" in error_msg.lower():
                    error_msg += (
                        "\nNote: The ZWO EFW SDK requires libudev. "
                        "Try: sudo apt-get install libudev-dev"
                    )
                raise OSError(f"Failed to load ZWO EFW SDK library from {lib_path}: {error_msg}")

        # Define function signatures
        self._lib.EFWGetNum.restype = ctypes.c_int
        self._lib.EFWGetNum.argtypes = []

        self._lib.EFWGetID.restype = ctypes.c_int
        self._lib.EFWGetID.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]

        self._lib.EFWOpen.restype = ctypes.c_int
        self._lib.EFWOpen.argtypes = [ctypes.c_int]

        self._lib.EFWGetProperty.restype = ctypes.c_int
        self._lib.EFWGetProperty.argtypes = [ctypes.c_int, ctypes.POINTER(EFW_INFO)]

        self._lib.EFWGetPosition.restype = ctypes.c_int
        self._lib.EFWGetPosition.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]

        self._lib.EFWSetPosition.restype = ctypes.c_int
        self._lib.EFWSetPosition.argtypes = [ctypes.c_int, ctypes.c_int]

        self._lib.EFWClose.restype = ctypes.c_int
        self._lib.EFWClose.argtypes = [ctypes.c_int]

        self._lib.EFWCalibrate.restype = ctypes.c_int
        self._lib.EFWCalibrate.argtypes = [ctypes.c_int]

        self._lib.EFWGetSDKVersion.restype = ctypes.c_char_p
        self._lib.EFWGetSDKVersion.argtypes = []

        self._lib.EFWCheck.restype = ctypes.c_int
        self._lib.EFWCheck.argtypes = [ctypes.c_int, ctypes.c_int]  # iVID, iPID

    def _check_error(self, error_code: int, operation: str) -> None:
        """Check SDK error code and raise appropriate exception if needed."""
        if error_code == EFW_SUCCESS:
            return
        
        error_messages = {
            EFW_ERROR_INVALID_INDEX: "Invalid filter wheel index",
            EFW_ERROR_INVALID_ID: "Invalid filter wheel ID",
            EFW_ERROR_INVALID_VALUE: "Invalid parameter value",
            EFW_ERROR_REMOVED: "Filter wheel removed or not found",
            EFW_ERROR_MOVING: "Filter wheel is currently moving",
            EFW_ERROR_ERROR_STATE: "Filter wheel is in error state",
            EFW_ERROR_GENERAL_ERROR: "General error occurred",
            EFW_ERROR_NOT_SUPPORTED: "Operation not supported",
            EFW_ERROR_INVALID_LENGTH: "Invalid length parameter",
            EFW_ERROR_CLOSED: "Filter wheel not opened",
        }
        
        message = error_messages.get(error_code, f"Unknown error code: {error_code}")
        raise FilterControllerError(f"{operation} failed: {message} (code: {error_code})")

    def initialize(self, filter_wheel_indices: List[int]):
        """
        Initialize the filter wheels.
        
        Args:
            filter_wheel_indices: List of filter wheel indices to initialize (typically [1] for single wheel)
        """
        # Try to verify device is present using EFWCheck (VID=0x03C3, PID=0x1F01 for EFW-MINI)
        # This can help diagnose if the device is visible but not enumerating
        vid = 0x03C3
        pid = 0x1F01
        is_efw = self._lib.EFWCheck(vid, pid)
        if is_efw:
            self.log.info(f"EFWCheck confirms device {vid:04X}:{pid:04X} is an EFW")
        else:
            self.log.warning(f"EFWCheck did not recognize device {vid:04X}:{pid:04X} as EFW")
        
        # Enumerate available filter wheels
        # According to SDK docs, EFWGetNum() should be called to refresh device list
        # Try calling it multiple times with a small delay in case of timing issues
        num_wheels = 0
        for attempt in range(3):
            num_wheels = self._lib.EFWGetNum()
            if num_wheels > 0:
                break
            if attempt < 2:
                time.sleep(0.1)  # Small delay before retry
        
        self.log.info(f"Found {num_wheels} ZWO EFW filter wheel(s) after {attempt + 1} attempt(s)")

        if num_wheels == 0:
            # Workaround: If EFWGetNum fails but EFWCheck succeeds, the device exists but
            # enumeration is broken (common after driver/system updates, same issue as ASIStudio).
            # Try to work around by attempting to use device ID 0 directly.
            if is_efw and len(filter_wheel_indices) == 1:
                self.log.warning(
                    "EFWGetNum() returned 0 but EFWCheck confirms device exists. "
                    "This is a known issue after system/driver updates (same as ASIStudio). "
                    "Attempting workaround using device ID 0..."
                )
                # Try to get ID for index 0 (first device)
                test_id = ctypes.c_int()
                error_code = self._lib.EFWGetID(0, ctypes.byref(test_id))
                if error_code == EFW_SUCCESS:
                    self.log.info(f"Workaround successful: Using device ID {test_id.value}")
                    num_wheels = 1
                    sdk_ids = [test_id.value]
                else:
                    # If GetID also fails, try opening ID 0 directly as a last resort
                    self.log.warning("EFWGetID(0) failed, trying EFWOpen(0) directly...")
                    error_code = self._lib.EFWOpen(0)
                    if error_code == EFW_SUCCESS:
                        self.log.info("Workaround successful: Opened device ID 0 directly")
                        num_wheels = 1
                        sdk_ids = [0]
                        # Close it for now, we'll reopen in the normal flow
                        self._lib.EFWClose(0)
                    else:
                        self.log.error(f"Workaround failed: EFWOpen(0) returned error {error_code}")
                        raise FilterControllerError(
                            "No ZWO EFW filter wheels detected by EFWGetNum(). "
                            "Device is visible via USB (EFWCheck confirms) but SDK enumeration failed. "
                            "This is the same issue as ASIStudio after driver/system updates.\n"
                            "Try: 1) Install udev rules: sudo cp software/drivers\\ and\\ libraries/zwo_efw/efw.rules /etc/udev/rules.d/99-zwo-efw.rules && sudo udevadm control --reload-rules\n"
                            "2) Unplug and replug the device\n"
                            "3) Restart the system"
                        )
            else:
                # Provide more diagnostic information
                error_msg = (
                    "No ZWO EFW filter wheels detected by EFWGetNum(). "
                    "The device may be visible via USB but the SDK cannot enumerate it.\n"
                    "Possible causes:\n"
                    "1. USB permissions issue - ensure udev rules are installed: sudo cp software/drivers\\ and\\ libraries/zwo_efw/efw.rules /etc/udev/rules.d/99-zwo-efw.rules && sudo udevadm control --reload-rules\n"
                    "2. Device needs to be unplugged and replugged\n"
                    "3. Another application may have exclusive access to the device\n"
                    "4. The SDK library may need additional dependencies\n"
                    f"Check: lsusb | grep 03c3:1f01 (should show the device)"
                )
                raise FilterControllerError(error_msg)
        
        # Get SDK IDs for all available wheels (if not already set by workaround)
        if num_wheels > 0:
            if 'sdk_ids' not in locals() or len(sdk_ids) == 0:
                sdk_ids = []
                for i in range(num_wheels):
                    sdk_id = ctypes.c_int()
                    error_code = self._lib.EFWGetID(i, ctypes.byref(sdk_id))
                    self._check_error(error_code, f"EFWGetID for index {i}")
                    sdk_ids.append(sdk_id.value)
                    self.log.info(f"Filter wheel {i}: SDK ID = {sdk_id.value}")

        # Map user-specified indices to SDK IDs
        # For now, we'll use a simple mapping: user index 1 -> first wheel (SDK ID 0), etc.
        # If a specific SDK ID is configured, use that
        if self._config.sdk_id is not None:
            if self._config.sdk_id not in sdk_ids:
                raise FilterControllerError(
                    f"Configured SDK ID {self._config.sdk_id} not found. "
                    f"Available IDs: {sdk_ids}"
                )
            # Use the configured SDK ID for the first requested index
            if len(filter_wheel_indices) > 0:
                self._efw_ids[filter_wheel_indices[0]] = self._config.sdk_id
        else:
            # Use first available wheel for first index, etc.
            for idx, user_idx in enumerate(filter_wheel_indices):
                if idx < len(sdk_ids):
                    self._efw_ids[user_idx] = sdk_ids[idx]
                else:
                    raise FilterControllerError(
                        f"Not enough filter wheels available. "
                        f"Requested {len(filter_wheel_indices)}, found {len(sdk_ids)}"
                    )

        # Open and get properties for each wheel
        for user_idx in filter_wheel_indices:
            sdk_id = self._efw_ids[user_idx]
            
            # Open the filter wheel
            error_code = self._lib.EFWOpen(sdk_id)
            if error_code == EFW_ERROR_REMOVED:
                raise FilterControllerError(f"Filter wheel with SDK ID {sdk_id} was removed")
            self._check_error(error_code, f"EFWOpen for SDK ID {sdk_id}")

            # Wait a bit for the wheel to initialize (especially for slot detection)
            time.sleep(0.5)

            # Get filter wheel properties
            info = EFW_INFO()
            max_retries = 10
            for retry in range(max_retries):
                error_code = self._lib.EFWGetProperty(sdk_id, ctypes.byref(info))
                if error_code == EFW_ERROR_MOVING:
                    # Slot detection in progress, wait and retry
                    if retry < max_retries - 1:
                        self.log.debug(f"Slot detection in progress for wheel {user_idx}, waiting...")
                        time.sleep(0.5)
                        continue
                    else:
                        self._check_error(error_code, f"EFWGetProperty for SDK ID {sdk_id}")
                else:
                    self._check_error(error_code, f"EFWGetProperty for SDK ID {sdk_id}")
                    break

            self._efw_info[user_idx] = info
            self.log.info(
                f"Filter wheel {user_idx} (SDK ID {sdk_id}): "
                f"Name='{info.Name.decode('utf-8', errors='ignore')}', "
                f"Slots={info.slotNum}"
            )

        self._available_filter_wheels = filter_wheel_indices

        # Get SDK version
        try:
            sdk_version = self._lib.EFWGetSDKVersion()
            if sdk_version:
                self.log.info(f"ZWO EFW SDK version: {sdk_version.decode('utf-8', errors='ignore')}")
        except Exception as e:
            self.log.warning(f"Could not get SDK version: {e}")

    @property
    def available_filter_wheels(self) -> List[int]:
        """List of available filter wheel indices."""
        return self._available_filter_wheels

    def get_filter_wheel_info(self, index: int) -> FilterWheelInfo:
        """
        Get information about a specific filter wheel.
        
        Args:
            index: Filter wheel index
            
        Returns:
            FilterWheelInfo containing slot count and names
        """
        if index not in self._available_filter_wheels:
            raise ValueError(f"Filter wheel index {index} not found")

        info = self._efw_info[index]
        slot_names = [f"Slot {i+1}" for i in range(info.slotNum)]
        
        # If custom slot names are configured, use those
        if self._config.slot_names and len(self._config.slot_names) == info.slotNum:
            slot_names = self._config.slot_names

        return FilterWheelInfo(
            index=index,
            number_of_slots=info.slotNum,
            slot_names=slot_names,
        )

    def home(self, index: Optional[int] = None):
        """
        Home/calibrate the filter wheel.
        
        Note: ZWO EFW uses calibration instead of traditional homing.
        This moves the wheel to position 0 and calibrates it.
        
        Args:
            index: Filter wheel index to home. If None, home all wheels.
        """
        wheels_to_home = [index] if index is not None else self._available_filter_wheels

        for wheel_index in wheels_to_home:
            if wheel_index not in self._available_filter_wheels:
                raise ValueError(f"Filter wheel index {wheel_index} not found")

            sdk_id = self._efw_ids[wheel_index]
            self.log.info(f"Calibrating filter wheel {wheel_index} (SDK ID {sdk_id})...")

            error_code = self._lib.EFWCalibrate(sdk_id)
            self._check_error(error_code, f"EFWCalibrate for wheel {wheel_index}")

            # Wait for calibration to complete
            # Calibration typically takes a few seconds
            max_wait_time = 30.0  # seconds
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                position = ctypes.c_int()
                error_code = self._lib.EFWGetPosition(sdk_id, ctypes.byref(position))
                if error_code == EFW_SUCCESS and position.value >= 0:
                    self.log.info(f"Filter wheel {wheel_index} calibrated successfully (position: {position.value})")
                    break
                elif error_code == EFW_ERROR_MOVING:
                    time.sleep(0.1)
                    continue
                else:
                    self._check_error(error_code, f"EFWGetPosition during calibration for wheel {wheel_index}")
            else:
                raise FilterControllerError(f"Calibration timeout for filter wheel {wheel_index}")

    def set_filter_wheel_position(self, positions: Dict[int, int]):
        """
        Set the filter wheels to the specified positions.
        
        Args:
            positions: Dictionary mapping filter wheel index to target position (1-indexed)
        """
        for wheel_index, position in positions.items():
            if wheel_index not in self._available_filter_wheels:
                raise ValueError(f"Filter wheel index {wheel_index} not found")

            sdk_id = self._efw_ids[wheel_index]
            info = self._efw_info[wheel_index]

            # Convert from 1-indexed (user) to 0-indexed (SDK)
            sdk_position = position - 1

            if sdk_position < 0 or sdk_position >= info.slotNum:
                raise ValueError(
                    f"Invalid position {position} for filter wheel {wheel_index}. "
                    f"Valid range: 1-{info.slotNum}"
                )

            # Check current position to avoid unnecessary moves
            current_pos = ctypes.c_int()
            error_code = self._lib.EFWGetPosition(sdk_id, ctypes.byref(current_pos))
            if error_code == EFW_SUCCESS and current_pos.value == sdk_position:
                self.log.debug(f"Filter wheel {wheel_index} already at position {position}")
                continue

            self.log.info(f"Moving filter wheel {wheel_index} to position {position} (SDK position {sdk_position})")

            # Set position
            error_code = self._lib.EFWSetPosition(sdk_id, sdk_position)
            if error_code == EFW_ERROR_MOVING:
                # Wait for current movement to complete
                self._wait_for_idle(wheel_index, timeout=10.0)
                # Retry
                error_code = self._lib.EFWSetPosition(sdk_id, sdk_position)
            
            self._check_error(error_code, f"EFWSetPosition for wheel {wheel_index}")

            # Wait for movement to complete if blocking is enabled
            if self._config.blocking:
                self._wait_for_idle(wheel_index, timeout=10.0)
            else:
                # Apply delay if configured
                delay_s = max(0, (self._config.delay_ms + self._delay_offset_ms) / 1000)
                if delay_s > 0:
                    time.sleep(delay_s)

    def _wait_for_idle(self, wheel_index: int, timeout: float = 10.0):
        """
        Wait for filter wheel to finish moving.
        
        Args:
            wheel_index: Filter wheel index
            timeout: Maximum time to wait in seconds
        """
        sdk_id = self._efw_ids[wheel_index]
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            position = ctypes.c_int()
            error_code = self._lib.EFWGetPosition(sdk_id, ctypes.byref(position))
            
            if error_code == EFW_SUCCESS and position.value >= 0:
                # Wheel is idle
                return
            elif error_code == EFW_ERROR_MOVING:
                # Still moving, wait a bit
                time.sleep(0.05)
                continue
            else:
                # Some other error, but might be transient
                time.sleep(0.05)
                continue
        
        self.log.warning(f"Timeout waiting for filter wheel {wheel_index} to become idle")

    def get_filter_wheel_position(self) -> Dict[int, int]:
        """
        Get the current positions of all filter wheels.
        
        Returns:
            Dictionary mapping filter wheel index to current position (1-indexed)
        """
        positions = {}
        
        for wheel_index in self._available_filter_wheels:
            sdk_id = self._efw_ids[wheel_index]
            position = ctypes.c_int()
            
            error_code = self._lib.EFWGetPosition(sdk_id, ctypes.byref(position))
            if error_code == EFW_ERROR_MOVING:
                # Wheel is moving, position is -1
                positions[wheel_index] = -1
            else:
                self._check_error(error_code, f"EFWGetPosition for wheel {wheel_index}")
                # Convert from 0-indexed (SDK) to 1-indexed (user)
                positions[wheel_index] = position.value + 1

        return positions

    def set_delay_offset_ms(self, delay_offset_ms: float):
        """Set the delay offset in milliseconds."""
        self._delay_offset_ms = delay_offset_ms
        self.log.debug(f"Set delay offset to {delay_offset_ms} ms")

    def get_delay_offset_ms(self) -> Optional[float]:
        """Get the current delay offset in milliseconds."""
        return self._delay_offset_ms

    def set_delay_ms(self, delay_ms: float):
        """Set the base delay in milliseconds."""
        raise NotImplementedError("Setting delay ms is not supported for ZWO EFW controller. Use config instead.")

    def get_delay_ms(self) -> Optional[float]:
        """Get the base delay in milliseconds."""
        return self._config.delay_ms

    def close(self):
        """Close all filter wheel connections."""
        for wheel_index in self._available_filter_wheels:
            sdk_id = self._efw_ids[wheel_index]
            error_code = self._lib.EFWClose(sdk_id)
            if error_code != EFW_SUCCESS:
                self.log.warning(f"Error closing filter wheel {wheel_index}: error code {error_code}")

        self._available_filter_wheels = []
        self._efw_ids.clear()
        self._efw_info.clear()
        self.log.info("Closed all ZWO EFW filter wheel connections")

