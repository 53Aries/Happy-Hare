# Load Cell Filament Sensor
#
# Virtual filament switch sensor that monitors load cell force readings
# to detect filament presence/loading for MMU systems like Happy Hare
#
# Copyright (C) 2026  Your Name
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging

# Virtual endstop that triggers based on load cell force readings
class LoadCellEndstop:
    RETRY_TIME = 0.010  # Check every 10ms during homing
    
    def __init__(self, load_cell_sensor):
        self.load_cell_sensor = load_cell_sensor
        self.load_cell = load_cell_sensor.load_cell
        self.mcu_endstop = None
        self._trigger_completion = None
        self._last_trigger_time = None
        self._homing = False
        self._trigger_state = False
        
    def get_mcu(self):
        return self.load_cell.sensor.get_mcu()
    
    def add_stepper(self, stepper):
        # Virtual endstop doesn't need stepper tracking
        pass
    
    def get_steppers(self):
        return []
    
    def home_start(self, print_time, sample_time, sample_count, rest_time, 
                   triggered=True):
        self._trigger_completion = self.load_cell_sensor.printer.get_reactor().completion()
        self._last_trigger_time = None
        self._homing = True
        self._trigger_state = triggered
        
        # Check if already triggered
        if self.load_cell_sensor.check_triggered() == triggered:
            self._last_trigger_time = print_time
            self._trigger_completion.complete(True)
        else:
            # Schedule periodic checks
            self._schedule_check(print_time)
        
        return self._trigger_completion
    
    def _schedule_check(self, eventtime):
        reactor = self.load_cell_sensor.printer.get_reactor()
        waketime = eventtime + self.RETRY_TIME
        
        def check_trigger(waketime):
            if not self._homing:
                return reactor.NEVER
            
            triggered = self.load_cell_sensor.check_triggered()
            if triggered == self._trigger_state:
                mcu = self.get_mcu()
                self._last_trigger_time = mcu.estimated_print_time(waketime)
                self._trigger_completion.complete(True)
                return reactor.NEVER
            
            return waketime + self.RETRY_TIME
        
        reactor.register_callback(lambda et: reactor.register_timer(check_trigger, waketime))
    
    def home_wait(self, home_end_time):
        self._homing = False
        self._trigger_completion = None
        
        if self._last_trigger_time is None:
            return home_end_time
        
        return self._last_trigger_time
    
    def query_endstop(self, print_time):
        return self.load_cell_sensor.check_triggered()


# Main class for load cell filament sensor
class LoadCellFilamentSensor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.name = config.get_name().split()[-1]
        
        # Get the load cell reference
        load_cell_name = config.get('load_cell')
        self.load_cell = None
        self.printer.register_event_handler("klippy:ready", 
                                           lambda: self._handle_ready(load_cell_name))
        
        # Force detection parameters
        self.trigger_force = config.getfloat('trigger_force', 30.0, minval=5.0, maxval=200.0)
        self.baseline_force = 0.0
        self.tare_on_home = config.getboolean('tare_on_home', True)
        self.tare_on_extruder_entry = config.getboolean('tare_on_extruder_entry', True)
        
        # Filtering parameters
        self.sample_count = config.getint('sample_count', 3, minval=1, maxval=10)
        self.hysteresis = config.getfloat('hysteresis', 5.0, minval=0.0, maxval=50.0)
        
        # Event handling for runout helper compatibility
        self.event_delay = config.getfloat('event_delay', 0.1, minval=0.0)
        self.pause_on_runout = config.getboolean('pause_on_runout', False)
        
        # State tracking
        self.filament_present = False
        self.sensor_enabled = True
        self._force_buffer = []
        
        # Create virtual endstop
        self.endstop = LoadCellEndstop(self)
        
        # Register with pins
        ppins = self.printer.lookup_object('pins')
        ppins.register_chip('load_cell_filament_sensor', self)
        
        # Register gcode commands
        gcode = self.printer.lookup_object('gcode')
        gcode.register_mux_command("QUERY_FILAMENT_SENSOR", "SENSOR", self.name,
                                  self.cmd_QUERY_FILAMENT_SENSOR,
                                  desc=self.cmd_QUERY_FILAMENT_SENSOR_help)
        gcode.register_mux_command("SET_FILAMENT_SENSOR", "SENSOR", self.name,
                                  self.cmd_SET_FILAMENT_SENSOR,
                                  desc=self.cmd_SET_FILAMENT_SENSOR_help)
        gcode.register_mux_command("LOAD_CELL_SENSOR_TARE", "SENSOR", self.name,
                                  self.cmd_LOAD_CELL_SENSOR_TARE,
                                  desc=self.cmd_LOAD_CELL_SENSOR_TARE_help)
        
        # Register internal command for MMU sensor event handling
        gcode.register_command('__LOAD_CELL_SENSOR_MMU_INSERT', 
                              self.cmd_MMU_SENSOR_INSERT_HANDLER,
                              desc="Internal handler for MMU sensor insert events")
    
    def _handle_ready(self, load_cell_name):
        # Look up the load cell object
        try:
            self.load_cell = self.printer.lookup_object('load_cell ' + load_cell_name)
        except:
            self.load_cell = self.printer.lookup_object(load_cell_name)
        
        if not self.load_cell:
            raise self.printer.config_error(
                "load_cell_filament_sensor: load_cell '%s' not found" % load_cell_name)
        
        # Subscribe to load cell force updates
        self.load_cell.add_client(self._force_update)
        # Check if MMU is configured and hook into extruder entry sensor if requested
        if self.tare_on_extruder_entry:
            try:
                # Try to wrap the MMU's sensor insert command to tare before processing
                gcode = self.printer.lookup_object('gcode')
                original_cmd = gcode.register_command('__MMU_SENSOR_INSERT', None)
                if original_cmd:
                    # Store original command and re-register with our wrapper
                    self._original_mmu_insert = original_cmd
                    gcode.register_command('__MMU_SENSOR_INSERT', self._wrap_mmu_sensor_insert)
                    logging.info("LoadCellFilamentSensor '%s' hooked into MMU extruder entry sensor for auto-tare"
                                % self.name)
            except Exception as e:
                logging.info("LoadCellFilamentSensor '%s': MMU integration not available (%s), auto-tare on extruder entry disabled"
                            % (self.name, str(e)))
        
        
        # Initial tare
        if self.tare_on_home:
            self._tare_baseline()
        
        logging.info("LoadCellFilamentSensor '%s' initialized with trigger_force=%.1fg, baseline=%.1fg"
                    % (self.name, self.trigger_force, self.baseline_force))
    
    def _force_update(self, msg):
        """Callback for load cell force updates"""
        if not self.sensor_enabled:
            return True
        
        samples = msg.get('data', [])
        for sample in samples:
            force = sample[1]  # [time, force_g, counts, tare_counts]
            if force is not None:
                self._force_buffer.append(force)
                # Keep only recent samples
                if len(self._force_buffer) > self.sample_count * 2:
                    self._force_buffer.pop(0)
        
        return True
    
    def _tare_baseline(self):
        """Set current force as baseline for triggering"""
        if not self.load_cell or not self.load_cell.is_calibrated():
            logging.warning("LoadCellFilamentSensor: Cannot tare - load cell not calibrated")
            return
        
        # Wait a moment for buffer to fill
        self.reactor.pause(self.reactor.monotonic() + 0.2)
        
        if len(self._force_buffer) >= self.sample_count:
            recent_samples = self._force_buffer[-self.sample_count:]
            self.baseline_force = sum(recent_samples) / len(recent_samples)
            logging.info("LoadCellFilamentSensor '%s' tared: baseline=%.2fg" 
                        % (self.name, self.baseline_force))
    
    def get_averaged_force(self):
        """Get averaged force from recent samples"""
        if len(self._force_buffer) < self.sample_count:
            return 0.0
        
        recent_samples = self._force_buffer[-self.sample_count:]
        return sum(recent_samples) / len(recent_samples)
    
    def check_triggered(self):
        """Check if filament is detected (force exceeds threshold)"""
        if not self.sensor_enabled or not self.load_cell:
            return self.filament_present
        
        avg_force = self.get_averaged_force()
        force_delta = abs(avg_force - self.baseline_force)
        
        # Hysteresis: different thresholds for detecting and releasing
        if self.filament_present:
            # Requires force to drop below trigger - hysteresis to clear
            triggered = force_delta >= (self.trigger_force - self.hysteresis)
        else:
            # Requires force to exceed trigger force
            triggered = force_delta >= self.trigger_force
        
        if triggered != self.filament_present:
            self.filament_present = triggered
            logging.debug("LoadCellFilamentSensor '%s': filament %s (force=%.2fg, delta=%.2fg, threshold=%.2fg)"
                         % (self.name, "detected" if triggered else "cleared",
                            avg_force, force_delta, self.trigger_force))
        
        return self.filament_present
    
    def get_mcu(self):
        """Return the MCU for button registration"""
        if self.load_cell and hasattr(self.load_cell, 'sensor'):
            return self.load_cell.sensor.get_mcu()
        # Fallback during initialization
        return None
    
    def setup_pin(self, pin_type, pin_params):
        """Setup virtual endstop or digital_out pin"""
        if pin_type == 'endstop':
            return self.endstop
        elif pin_type == 'digital_out':
            # Return self for switch sensors - they just need query_endstop
            return self
        else:
            raise self.printer.error(
                "load_cell_filament_sensor pin type '%s' not supported" % pin_type)
    
    def query_endstop(self, print_time):
        """Query method for switch sensors"""
        return self.check_triggered()
    
    def get_status(self, eventtime):
        """Status for Klipper's status reporting"""
        avg_force = self.get_averaged_force()
        return {
            'filament_detected': bool(self.filament_present),
            'enabled': bool(self.sensor_enabled),
            'force': round(avg_force, 2),
            'baseline_force': round(self.baseline_force, 2),
            'trigger_force': self.trigger_force,
            'force_delta': round(abs(avg_force - self.baseline_force), 2)
        }
    
    # GCode Commands
    cmd_QUERY_FILAMENT_SENSOR_help = "Query the status of the Load Cell Filament Sensor"
    def cmd_QUERY_FILAMENT_SENSOR(self, gcmd):
        triggered = self.check_triggered()
        avg_force = self.get_averaged_force()
        force_delta = abs(avg_force - self.baseline_force)
        
        if triggered:
            msg = "Load Cell Sensor %s: filament detected (force: %.2fg, delta: %.2fg, threshold: %.2fg)" \
                  % (self.name, avg_force, force_delta, self.trigger_force)
    
    def _wrap_mmu_sensor_insert(self, gcmd):
        """Wrapper for MMU sensor insert command to auto-tare on extruder entry"""
        sensor = gcmd.get('SENSOR', "")
        
        # If this is the extruder entry sensor, tare the load cell first
        if sensor == "extruder" and self.tare_on_extruder_entry:
            logging.debug("LoadCellFilamentSensor '%s': Auto-taring on extruder entry sensor trigger" 
                         % self.name)
            self._tare_baseline()
        
        # Call the original MMU command
        if hasattr(self, '_original_mmu_insert'):
            self._original_mmu_insert(gcmd)
    
    def cmd_MMU_SENSOR_INSERT_HANDLER(self, gcmd):
        """Internal handler for MMU sensor insert events"""
        sensor = gcmd.get('SENSOR', "")
        if sensor == "extruder" and self.tare_on_extruder_entry:
            logging.debug("LoadCellFilamentSensor '%s': Auto-taring on extruder entry" % self.name)
            self._tare_baseline()
        else:
            msg = "Load Cell Sensor %s: filament not detected (force: %.2fg, delta: %.2fg, threshold: %.2fg)" \
                  % (self.name, avg_force, force_delta, self.trigger_force)
        gcmd.respond_info(msg)
    
    cmd_SET_FILAMENT_SENSOR_help = "Enable/disable the filament sensor"
    def cmd_SET_FILAMENT_SENSOR(self, gcmd):
        self.sensor_enabled = bool(gcmd.get_int("ENABLE", 1))
        gcmd.respond_info("Load Cell Filament Sensor '%s' %s" 
                         % (self.name, "enabled" if self.sensor_enabled else "disabled"))
    
    cmd_LOAD_CELL_SENSOR_TARE_help = "Tare the baseline force for this sensor"
    def cmd_LOAD_CELL_SENSOR_TARE(self, gcmd):
        self._tare_baseline()
        gcmd.respond_info("Load Cell Filament Sensor '%s' tared: baseline=%.2fg" 
                         % (self.name, self.baseline_force))


def load_config_prefix(config):
    return LoadCellFilamentSensor(config)
