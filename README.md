# Spoolman Extension for Moonraker

A custom Moonraker component that automatically exposes active Spoolman filament data to Klipper as `gcode_macro` variables. This enables your printer to automatically access filament information (temperatures, material type, vendor, etc.) without manual configuration.

## W

## Features

- **Event-driven updates**: Automatically updates Klipper variables when the active spool changes in Spoolman
- **Initial load on startup**: Fetches the current active spool when Klipper becomes ready
- **Seamless integration**: Works with existing Moonraker Spoolman integration
- **Safe error handling**: Gracefully handles missing macros or Spoolman connectivity issues

## Exposed Variables

The following filament properties are made available in the `SPOOLMAN_VARS` macro:

- `id`: Filament ID
- `hotend_temp`: Recommended extruder temperature
- `bed_temp`: Recommended bed temperature
- `material`: Material type (e.g., PLA, PETG, ABS)
- `name`: Filament name
- `vendor`: Vendor/manufacturer name

**Note**: These details should be set within the filament section in Spoolman web UI.

## Installation

### Step 1: Clone and Install

Run these commands on your Klipper host (via SSH):

```bash
# Clone the repository
cd ~
git clone https://github.com/YOUR_USERNAME/SpoolmanExtension.git

# Copy the component to Moonraker
cp SpoolmanExtension/spoolman_ext.py ~/moonraker/moonraker/components/

# Remove the cloned directory
rm -rf SpoolmanExtension
```

### Step 2: Configure Moonraker

Add the following below the `[spoolman]` section to your `moonraker.conf`:

```ini
[spoolman_ext]
```

**Note**: The `[spoolman]` section must already be configured for this extension to work.

### Step 3: Add Klipper Macro

Add this macro to your Klipper configuration (e.g., `macros.cfg` or `printer.cfg`):

```gcode
[gcode_macro SPOOLMAN_VARS]
variable_id: None
variable_hotend_temp: None
variable_bed_temp: None
variable_material: None
variable_name: None
variable_vendor: None
gcode:
  # Empty container for Spoolman variables - no logic needed
```

### Step 4: Restart Services

```bash
# Restart Moonraker (or use the web interface)
sudo systemctl restart moonraker

# Restart Klipper (or use the web interface)
sudo systemctl restart klipper
```

## Usage

### Accessing Variables in Your Macros

Once configured, you can access the Spoolman filament data in any of your Klipper macros:

```gcode
[gcode_macro START_PRINT]
gcode:
    {% set spoolman = printer["gcode_macro SPOOLMAN_VARS"] %}
    
    # Use the temperatures from Spoolman
    M104 S{spoolman.hotend_temp}  ; Set extruder temp
    M140 S{spoolman.bed_temp}     ; Set bed temp
    
    # Display filament info
    {action_respond_info("Printing with %s %s" % (spoolman.vendor, spoolman.name))}
    {action_respond_info("Material: %s" % spoolman.material)}
    
    # Wait for temperatures
    M109 S{spoolman.hotend_temp}  ; Wait for extruder
    M190 S{spoolman.bed_temp}     ; Wait for bed
    
    # Continue with your start sequence...
```

### Example: Conditional Logic Based on Material

```gcode
[gcode_macro LOAD_FILAMENT]
gcode:
    {% set spoolman = printer["gcode_macro SPOOLMAN_VARS"] %}
    {% set material = spoolman.material %}
    
    # Material-specific temperatures
    {% if material == "PETG" %}
        M109 S245  ; PETG loading temp
    {% elif material == "ABS" %}
        M109 S255  ; ABS loading temp
    {% else %}
        M109 S215  ; PLA default
    {% endif %}
    
    # Load filament
    G1 E50 F300
```

### Example: Checking if Spool is Selected

```gcode
[gcode_macro PRINT_START_SAFE]
gcode:
    {% set spoolman = printer["gcode_macro SPOOLMAN_VARS"] %}
    
    # Check if a spool is selected
    {% if spoolman.id == "None" %}
        {action_respond_info("WARNING: No active spool selected in Spoolman!")}
        {action_respond_info("Please select a spool before printing.")}
        CANCEL_PRINT
    {% else %}
        {action_respond_info("Using spool ID: %s" % spoolman.id)}
        START_PRINT
    {% endif %}
```

## How It Works

1. The component monitors Spoolman's `active_spool_set` events from Moonraker
2. When the active spool changes (or on Klipper startup), it fetches filament details from the Spoolman API
3. The data is pushed to Klipper using `SET_GCODE_VARIABLE` commands
4. Your macros can then access this data via `printer["gcode_macro SPOOLMAN_VARS"]`

## Requirements

- Moonraker with Spoolman integration configured (`[spoolman]` section)
- Klipper with the `SPOOLMAN_VARS` macro defined
- Network connectivity to your Spoolman server

## Troubleshooting

### Component not loading

Check `moonraker.log` for errors:
```bash
tail -f ~/printer_data/logs/moonraker.log | grep spoolman_ext
```

### Variables not updating

1. Verify the `SPOOLMAN_VARS` macro exists in your Klipper config
2. Check that Spoolman is properly configured in `moonraker.conf`
3. Ensure an active spool is selected in your Spoolman interface
4. Restart both Klipper and Moonraker

### "Macro not found" warnings

Make sure you've added the `[gcode_macro SPOOLMAN_VARS]` to your Klipper configuration and restarted Klipper.

## License

This project is licensed under the GNU General Public License v3.0 - the same license as Moonraker.

For details or visit: https://www.gnu.org/licenses/gpl-3.0.en.html

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request, or raise requests within the Github Issues. It is possible however, that I may seek to encorporate these changes into mainline Moonraker's Spoolman component in the future and remove this repo.

## Acknowledgments

- Built for use with [Moonraker](https://github.com/Arksine/moonraker)
- Integrates with [Spoolman](https://github.com/Donkie/Spoolman)
- Inspired by the Klipper/Moonraker community

## Support

If you encounter issues or have questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the Moonraker logs
3. Open an issue on GitHub with relevant log excerpts