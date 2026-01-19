# Load Cell Filament Sensor for Happy Hare MMU

## Overview

This feature allows you to use a load cell probe as a virtual toolhead filament sensor for Happy Hare MMU. Instead of using a physical switch, the system detects filament by monitoring force changes when filament pushes into the nozzle.

## Features

- **Virtual Endstop**: Creates a virtual filament sensor from load cell force readings
- **Auto-Tare**: Automatically tares when extruder entry sensor triggers (optional)
- **Force-Based Detection**: Detects filament contact through force changes
- **Hysteresis & Filtering**: Stable detection with noise rejection
- **Self-Contained**: All code in Happy Hare extras (no Klipper modification needed)

## Files Included

- **`extras/load_cell_filament_sensor.py`** - Main Python module
- **`config/examples/load_cell_sensor/README.md`** - Complete user guide with calibration steps
- **`config/examples/load_cell_sensor/example-printer.cfg`** - Example printer.cfg configuration
- **`config/examples/load_cell_sensor/example-mmu_hardware.cfg`** - Example MMU hardware configuration
- **`config/examples/load_cell_sensor/load_cell_sensor_test.cfg`** - Testing and calibration macros

## Quick Start

### 1. Prerequisites

- Happy Hare MMU installed
- Load cell probe configured and calibrated (e.g., for Z probing)
- Klipper with load cell support

### 2. Installation

The Python module is automatically loaded with Happy Hare since it's in the `extras/` directory.

### 3. Configuration

**Add to printer.cfg:**
```ini
[load_cell_filament_sensor toolhead]
load_cell: load_cell_probe
trigger_force: 30.0
hysteresis: 5.0
sample_count: 3
tare_on_home: True
tare_on_extruder_entry: True
event_delay: 0.1
```

**Modify mmu_hardware.cfg:**
```ini
[mmu_sensors]
extruder_switch_pin: your_mcu:PA8  # Optional but recommended
toolhead_switch_pin: load_cell_filament_sensor:toolhead
```

### 4. Calibration

1. Restart Klipper
2. Tare the sensor: `LOAD_CELL_SENSOR_TARE SENSOR=toolhead`
3. Manually load filament and observe force: `TEST_LOAD_CELL_SENSOR`
4. Adjust `trigger_force` to 50-70% of the loading force
5. Test: `MMU_TEST_HOMING_MOVE MOTOR=gear+extruder MOVE=50 ENDSTOP=toolhead STOP_ON_ENDSTOP=1`

## How It Works

1. **Baseline**: Sensor establishes baseline force reading (no filament)
2. **Auto-Tare**: When extruder entry sensor triggers, load cell tares (optional)
3. **Detection**: As filament pushes into nozzle, force increases
4. **Trigger**: When force delta exceeds threshold, sensor triggers
5. **Homing**: Happy Hare receives endstop signal and completes load

## Documentation

See `config/examples/load_cell_sensor/README.md` for:
- Detailed calibration procedure
- Troubleshooting guide
- Technical details
- GCode commands
- Advanced configuration

## Requirements

- Load cell probe with force measurement capability
- Load cell calibrated in Klipper (`counts_per_gram` and `reference_tare_counts`)
- Happy Hare MMU v3.0+

## Advantages

- ✅ No additional hardware needed (reuses existing load cell)
- ✅ Very sensitive force-based detection
- ✅ Auto-tare eliminates thermal drift
- ✅ Self-contained in Happy Hare (no Klipper modification)
- ✅ Configurable sensitivity

## Support

For issues or questions:
1. Check the detailed README in `config/examples/load_cell_sensor/`
2. Test with provided macros: `TEST_LOAD_CELL_SENSOR`
3. Review Klipper logs: `~/printer_data/logs/klippy.log`

## Credits

- Happy Hare MMU by moggieuk
- Load cell probe implementation by Gareth Farrington

## License

GNU GPLv3 (consistent with Klipper and Happy Hare)
