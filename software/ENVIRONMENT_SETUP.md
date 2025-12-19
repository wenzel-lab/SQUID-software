# SquidStation Python Environment Setup

## Mamba Environment: `squid`

A fresh mamba environment has been created for running SquidStation with ZWO EFW filter wheel support.

### Activation

```bash
mamba activate squid
```

### Environment Details

- **Python Version**: 3.11.14
- **Location**: `/home/wenzel-lab/miniforge3/envs/squid`

### Installed Packages

The environment includes all necessary dependencies for SquidStation:

#### Core Dependencies
- `pydantic` - Configuration management
- `numpy`, `scipy`, `pandas` - Numerical computing
- `opencv-python-headless`, `opencv-contrib-python-headless` - Image processing
- `tifffile`, `imageio` - Image I/O
- `scikit-image` - Image analysis

#### GUI Dependencies
- `qtpy`, `PyQt5` - GUI framework
- `napari[all]` - Image viewer
- `matplotlib` - Plotting

#### Acquisition & Processing
- `dask`, `dask_image` - Parallel processing
- `ome_zarr`, `aicsimageio` - Image formats
- `basicpy` - Background subtraction

#### Hardware Control
- `pyserial` - Serial communication
- `pyvisa`, `hidapi` - Instrument control
- `ctypes` (built-in) - For ZWO EFW SDK

#### Testing
- `pytest`, `pytest-qt`, `pytest-xvfb` - Testing framework

#### Other
- `gitpython` - Version control integration
- `lxml` - XML processing
- `crc` - Checksum calculation

### Running SquidStation

1. Activate the environment:
   ```bash
   mamba activate squid
   ```

2. Navigate to the software directory:
   ```bash
   cd /home/wenzel-lab/Desktop/SQUID-software/software
   ```

3. Run SquidStation:
   ```bash
   python main_hcs.py
   ```

### Testing ZWO EFW Integration

Test the ZWO EFW filter wheel:
```bash
mamba activate squid
cd /home/wenzel-lab/Desktop/SQUID-software/software
python tests/squid/test_zwo_efw.py
```

### Note on Numpy Version

There is a version conflict warning between `numpy` (2.2.6) and `scipy` (requires numpy<1.29.0). This is a known issue with the current package versions. The code should still function correctly, but if you encounter issues, you can downgrade numpy:

```bash
mamba activate squid
pip install "numpy<1.29.0,>=1.22.4"
```

However, this may conflict with `opencv-contrib-python-headless` which requires numpy>=2. In practice, the code should work with numpy 2.2.6.

### Environment Variables

If needed, you can set PYTHONPATH to include the software directory:
```bash
export PYTHONPATH=/home/wenzel-lab/Desktop/SQUID-software/software:$PYTHONPATH
```

### Deactivation

To deactivate the environment:
```bash
mamba deactivate
```


