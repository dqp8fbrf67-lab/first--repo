# Cooler Pi Ambient Hub

`cooler_pi.py` turns a stock Raspberry Pi into a vibrant ambient information hub
that reacts to the weather outside and the health of the device itself.  It
drives an RGB LED, buzzer, and push button using [`gpiozero`](https://gpiozero.readthedocs.io/).

## Hardware shopping list

- Common-anode RGB LED with three current-limiting resistors (220 Ω works well).
- Momentary push button.
- Passive buzzer or small speaker.
- Jumper wires and a breadboard (or a custom PCB/hat).

The defaults in the script expect the following wiring (all BCM numbering):

| Component | Pin(s) |
|-----------|--------|
| LED red   | 17     |
| LED green | 27     |
| LED blue  | 22     |
| Button    | 23     |
| Buzzer    | 18     |

Feel free to change the pins through the CLI arguments documented below.

## Software prerequisites

```bash
sudo apt update
sudo apt install python3-gpiozero python3-requests
```

Everything else ships with Python.

## Running the hub

```bash
python3 cooler_pi.py \
  --latitude 40.7128 --longitude -74.0060 \
  --led-pins 17 27 22 --button-pin 23 --buzzer-pin 18
```

- Each button press cycles through the available modes.
- The weather mode uses the free [Open-Meteo](https://open-meteo.com/) API — no
  API key is required.
- The system health mode tracks load average, disk usage, and CPU temperature.

### Useful flags

- `--system-interval` controls how often the system information is refreshed
  (defaults to 30 seconds).
- `--weather-interval` controls how often weather data is downloaded (defaults
  to 5 minutes).
- `--log-level DEBUG` is helpful when you extend the project with more modes.

## Extending the project

1. Write a function that returns an `AmbientStatus` instance.
2. Wrap it in a `Mode` dataclass with an appropriate refresh interval.
3. Append it to the list returned by `build_modes`.
4. Add any new hardware you might need.

The `CoolerPi` controller handles button presses, LED updates, and short buzzer
notifications so your mode can focus purely on data collection and mapping it to
colors.
