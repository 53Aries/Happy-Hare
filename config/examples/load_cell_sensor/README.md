# Load Cell Filament Sensor for Happy Hare MMU

This implementation creates a virtual filament sensor that monitors your load cell probe to detect when filament reaches the nozzle during MMU loading operations.

## Overview

The load cell filament sensor monitors force readings from your load cell probe and triggers when the force exceeds a threshold, indicating filament has pushed into the nozzle. This functions similarly to the `toolhead_switch` sensor but uses force detection instead of a physical switch.

## How It Works

1. **Baseline Taring**: The sensor establishes a baseline force reading when idle (no filament)
2. **Force Monitoring**: Continuously monitors load cell force readings
3. **Filament Detection**: When force delta exceeds `trigger_force`, filament is detected
4. **Hysteresis**: Uses hysteresis to prevent oscillation between triggered/not-triggered states
5. **Averaging**: Averages multiple samples for stability and noise rejection
6. **Auto-Tare on Extruder Entry** (Optional): When enabled and extruder entry sensor is configured, automatically tares the baseline when Happy Hare detects filament at the extruder entry sensor, providing a fresh baseline right before filament reaches the nozzle

## Installation

### Files Installed

1. **Python Module**: `klippy/extras/load_cell_filament_sensor.py`
   - Core sensor implementation

2. **Configuration**: `printer.cfg`
   - Sensor configuration section added

3. **MMU Integration**: `mmu/base/mmu_hardware.cfg`
   - Updated `toolhead_switch_pin` to use virtual sensor

4. **Testing Macros**: `Macros/load_cell_sensor_test.cfg`
   - Helper macros for testing and calibration

## Configuration

### Sensor Settings (in printer.cfg)

```ini
[load_cell_filament_sensor toolhead]
load_cell: load_cell_probe        # Reference to your load_cell_probe
trigger_force: 30.0                # Force threshold in grams (ADJUST THIS)
hysteresis: 5.0                    # Force hysteresis to prevent bouncing
sample_count: 3                    # Number of samples to average
tare_on_home: True                 # Auto-tare on startup
tare_on_extruder_entry: True       # Auto-tare when extruder entry sensor triggers (requires extruder_switch_pin configured)
event_delay: 0.1                   # Delay between sensor events
```

### Key Parameters to Adjust

- **trigger_force**: The critical parameter. Set this to a value that reliably detects filament but doesn't false trigger. Start with 30g and adjust based on testing.
- **hysteresis**: Prevents rapid on/off cycling. If you see oscillation, increase this.
- **tare_on_extruder_entry**: Automatically tares the sensor when Happy Hare detects filament at the extruder entry sensor. This provides a fresh baseline right before filament reaches the nozzle. Requires `extruder_switch_pin` to be configured in mmu_hardware.cfg.
- **sample_count**: More samples = more stable but slightly slower response. 3-5 is a good range.

## Calibration Process

### Step 1: Initial Testing

1. **Restart Klipper** to load the new module

2. **Check load cell is working**:
   ```
   LOAD_CELL_READ LOAD_CELL=load_cell_probe
   ```

3. **Test the sensor exists**:
   ```
   TEST_LOAD_CELL_SENSOR
   ```

### Step 2: Establish Baseline

1. **Ensure NO filament is loaded** in the hotend

2. **Tare the sensor**:
   ```
   LOAD_CELL_SENSOR_TARE SENSOR=toolhead
   ```

3. **Verify baseline**:
   ```
   TEST_LOAD_CELL_SENSOR
   ```
   - Note the "Baseline Force" value
   - Should be close to 0g if load cell is properly tared

### Step 3: Measure Filament Force

1. **Manually load filament** to the nozzle (extruder cold, just push by hand)

2. **Check force reading**:
   ```
   TEST_LOAD_CELL_SENSOR
   ```
   - Note the "Current Force" and "Force Delta" values
   - The "Force Delta" shows how much force is from the filament

3. **Try different amounts** of filament pressure:
   - Light touch: minimal force
   - Normal loading: moderate force
   - Pushing hard: high force

### Step 4: Set Trigger Threshold

1. **Choose trigger_force value**:
   - Should be **higher** than baseline noise
   - Should be **lower** than normal filament loading force
   - Recommendation: Set to **50-70%** of the filament loading force

   Example:
   - Baseline noise: ±2g
   - Filament loading force: 50g
   - Set trigger_force: 30g (60% of loading force)

2. **Update printer.cfg**:
   ```ini
   trigger_force: 30.0  # Adjust this value
   ```

3. **Restart Klipper**

### Step 5: Test Detection

1. **With no filament loaded**:
   ```
   TEST_LOAD_CELL_SENSOR
   ```
   - Should show "NO FILAMENT"

2. **Load filament manually** and check:
   ```
   TEST_LOAD_CELL_SENSOR
   ```
   - Should show "FILAMENT DETECTED"

3. **Unload and check again**:
   ```
   TEST_LOAD_CELL_SENSOR
   ```
   - Should return to "NO FILAMENT"

### Step 6: Monitor During Loading

For continuous monitoring:
```
MONITOR_LOAD_CELL_SENSOR DURATION=30 INTERVAL=1
```

This will display sensor readings every second for 30 seconds, useful for watching what happens during actual MMU loading.

## Testing with Happy Hare

### Test Homing Move

Once calibrated, test the sensor as an endstop:

```
MMU_TEST_HOMING_MOVE MOTOR=gear+extruder MOVE=50 ENDSTOP=toolhead STOP_ON_ENDSTOP=1
```

This simulates Happy Hare homing to the toolhead sensor. The move should stop when filament triggers the load cell.

### Full MMU Testing

1. **Load filament through MMU**:
   ```
   MMU_SELECT GATE=0
   MMU_LOAD
   ```

2. **Watch for sensor detection** during loading

3. **Check Happy Hare logs** for sensor triggering

## Troubleshooting

### Issue: Auto-tare not working with extruder entry sensor

**Verify:**
- `extruder_switch_pin` is configured in mmu_hardware.cfg
- `tare_on_extruder_entry: True` in load_cell_filament_sensor config
- Check Klipper logs for "hooked into MMU extruder entry sensor" message
- Run `MMU_STATUS` to verify extruder sensor is detected

### Issue: Sensor never triggers

**Solutions:**
- Reduce `trigger_force` value
- Verify load cell is calibrated: `LOAD_CELL_READ`
- Check filament is actually pushing into nozzle
- Tare the sensor: `LOAD_CELL_SENSOR_TARE SENSOR=toolhead`

### Issue: False triggers (triggers when no filament)

**Solutions:**
- Increase `trigger_force` value
- Increase `hysteresis` value
- Tare the sensor when printer is at operating temperature
- Check for mechanical vibration affecting load cell

### Issue: Inconsistent triggering

**Solutions:**
- Increase `sample_count` for more averaging
- Check load cell mounting is rigid
- Verify load cell is not near saturation (check `LOAD_CELL_DIAGNOSTIC`)
- Consider adding/adjusting load cell filters in H36.cfg

### Issue: "Load cell not calibrated" error

**Solutions:**
- Run load cell calibration: `LOAD_CELL_CALIBRATE LOAD_CELL=load_cell_probe`
- Verify `counts_per_gram` and `reference_tare_counts` in SAVE_CONFIG section
- Restart Klipper after calibration

### Issue: Slow response

**Solutions:**
- Reduce `sample_count` (but may reduce stability)
- Verify load cell sample rate is adequate (currently 660 Hz)
- Check for excessive filtering in load cell config

## Advanced Configuration

### Temperature Compensation
The sensor has multiple strategies to handle this:

**1. Auto-Tare on Extruder Entry (Recommended)**

When `tare_on_extruder_entry: True` and you have an extruder entry sensor configured:
- The load cell automatically tares when Happy Hare detects filament at the extruder entry
- This provides a fresh baseline right before fi

**3. Re-tare between prints** if needed and auto-tare is disabledlament reaches the nozzle area
- Eliminates thermal drift between prints since taring happens during each load sequence
**2. Manual Tare at Operating Temperature**

For manual taring at operating temperature:or current thermal state

**2. Manual Tare at Operating Temperature**
1. **Tare at operating temperature**:
   - Heat the hotend and bed
   - Let printer stabilize for 5-10 minutes
   - Run `LOAD_CELL_SENSOR_TARE SENSOR=toolhead`

2. **Re-tare between prints** if needed

### Multiple Sensors

You can create multiple load cell filament sensors if you have multiple load cells:

```ini
[load_cell_filament_sensor sensor1]
load_cell: load_cell_probe_1
trigger_force: 30.0

[load_cell_filament_sensor sensor2]
load_cell: load_cell_probe_2
trigger_force: 35.0
```

### Integration with Other Systems

The sensor implements the standard Klipper filament_switch_sensor interface, so it should work with:
- Happy Hare MMU (primary use case)
- Any system expecting a filament sensor
- Macros using `QUERY_FILAMENT_SENSOR`

## GCode Commands

### Sensor Control

- `QUERY_FILAMENT_SENSOR SENSOR=toolhead` - Check sensor status
- `SET_FILAMENT_SENSOR SENSOR=toolhead ENABLE=1` - Enable sensor
- `SET_FILAMENT_SENSOR SENSOR=toolhead ENABLE=0` - Disable sensor
- `LOAD_CELL_SENSOR_TARE SENSOR=toolhead` - Tare baseline force

### Testing Macros

- `TEST_LOAD_CELL_SENSOR` - Display all sensor readings
- `CALIBRATE_LOAD_CELL_SENSOR` - Show calibration instructions
- `MONITOR_LOAD_CELL_SENSOR` - Continuous monitoring
- `LOAD_CELL_SENSOR_STATUS` - Quick status check

## Technical Details

### Virtual Endstop Implementation

The sensor creates a virtual endstop that:
- Polls force readings during homing moves
- Completes homing when force threshold is exceeded
- Returns the print_time when trigger occurred
- Compatible with Klipper's standard homing system

### Force Detection Algorithm

```
force_delta = |current_force - baseline_force|

if filament_present:
    triggered = force_delta >= (trigger_force - hysteresis)
else:
    triggered = force_delta >= trigger_force
```

This provides hysteresis: requires higher force to trigger, lower force to release.

### Sample Averaging

Uses a rolling buffer of recent samples:
- Maintains last `sample_count * 2` samples
- Averages last `sample_count` samples for detection
- Provides noise rejection and stability

## Performance Considerations

### Sample Rate
- Load cell runs at 660 Hz (samples per second)
- Virtual sensor checks force every 10ms during homing
- Adequate for typical MMU loading speeds (10-50 mm/s)

### Latency
- Total detection latency: ~30-50ms
  - Sample averaging: 5-15ms (3 samples @ 660Hz)
  - Homing check interval: 10ms
  - Python processing: 5-15ms

### Accuracy
- Force resolution: ~0.1g (depends on load cell calibration)
- Trigger repeatability: ±2-5g (depends on mechanical setup)

## Safety Notes

⚠️ **Important Considerations:**

1. **Temperature Effects**: Load cells drift with temperature. Re-tare as needed.

2. **Mechanical Stability**: Load cell must be rigidly mounted. Vibration = false triggers.

3. **Force Limits**: Ensure trigger force is well below your load cell's force_safety_limit (currently 1500g).

4. **Heater Off**: For best results during calibration, turn off heaters to eliminate thermal drift.

5. **Backup Method**: Consider keeping the extruder_switch_pin as a backup sensor.

## Future Enhancements

Potential improvements:
- [ ] Automatic threshold learning
- [ ] Temperature compensation algorithm  
- [ ] Multi-point calibration
- [ ] Force profile logging
- [ ] Integration with load cell probe's existing filters

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Run diagnostics: `LOAD_CELL_DIAGNOSTIC LOAD_CELL=load_cell_probe`
3. Monitor sensor: `MONITOR_LOAD_CELL_SENSOR DURATION=30`
4. Check Klipper logs: `~/printer_data/logs/klippy.log`

## Credits

Developed for use with:
- Klipper 3D printer firmware
- Happy Hare MMU system by moggieuk
- Load cell probe implementation by Gareth Farrington

## License

This implementation is distributed under the GNU GPLv3 license, consistent with Klipper.
