"""Turn your Raspberry Pi into a colorful ambient information hub.

This module contains an opinionated but highly extensible implementation of a
"cooler" Raspberry Pi project.  It turns the Pi into an ambient notification
station that reacts to local weather conditions and system health by lighting up
an RGB LED and optionally playing short tones on a buzzer.  A physical button
lets you cycle through the available data feeds.

The script is designed to be executed directly on a Raspberry Pi that has the
following hardware attached:

* A common-anode RGB LED connected to three GPIO pins through appropriate
  current limiting resistors.
* A momentary push button connected to a GPIO pin (internal pull-up is enabled
  by software).
* A passive buzzer or speaker connected to a GPIO pin that supports PWM.  The
  script uses :class:`gpiozero.TonalBuzzer` to play simple tones.

Software wise you will need:

* Python 3.10 or newer.
* The ``gpiozero`` package (preinstalled on Raspberry Pi OS).
* The ``requests`` package for HTTP requests.

Example usage::

    $ python3 cooler_pi.py --latitude 40.7128 --longitude -74.0060 \
        --led-pins 17 27 22 --button-pin 23 --buzzer-pin 18

This starts the ambient hub with weather and system health modes enabled.  Each
press of the button cycles between them.  The LED changes color and a short tone
is played to convey the current status.

The code is structured to make it easy to extend with new data feeds: define a
function that returns :class:`AmbientStatus`, wrap it in :class:`Mode`, and add
it to the list returned by :func:`build_modes`.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import requests
from gpiozero import Button, RGBLED, TonalBuzzer
from gpiozero.tones import Tone


@dataclass
class AmbientStatus:
    """Represents the state that should be shown on the physical hardware."""

    label: str
    color: tuple[float, float, float]
    description: str
    tone: Optional[Tone] = None


@dataclass
class Mode:
    """A data feed that can provide ambient statuses on demand."""

    name: str
    fetch: Callable[[], AmbientStatus]
    update_interval: float


class CoolerPi:
    """Main controller that glues together the hardware and data feeds."""

    def __init__(
        self,
        led: RGBLED,
        button: Button,
        buzzer: TonalBuzzer,
        modes: Iterable[Mode],
        default_mode_index: int = 0,
    ) -> None:
        self.led = led
        self.button = button
        self.buzzer = buzzer
        self.modes: list[Mode] = list(modes)
        if not self.modes:
            raise ValueError("At least one mode must be provided")
        if not 0 <= default_mode_index < len(self.modes):
            raise IndexError("default_mode_index out of range")

        self._mode_index = default_mode_index
        self._mode_change_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self.button.when_pressed = self._on_button_pressed

    def _on_button_pressed(self) -> None:
        """Advance to the next mode when the button is pressed."""

        self._mode_index = (self._mode_index + 1) % len(self.modes)
        logging.info("Switched to mode: %s", self.modes[self._mode_index].name)
        if self._mode_change_event and self._loop:
            self._loop.call_soon_threadsafe(self._mode_change_event.set)

    async def run(self) -> None:
        """Start the asynchronous main loop."""

        logging.info("Starting CoolerPi with %d mode(s)", len(self.modes))
        self._loop = asyncio.get_running_loop()
        self._mode_change_event = asyncio.Event()

        while True:
            mode = self.modes[self._mode_index]
            try:
                status = mode.fetch()
            except Exception as exc:  # noqa: BLE001 - top-level resiliency
                logging.exception("Failed to fetch status for mode %s", mode.name)
                status = AmbientStatus(
                    label=f"{mode.name} error",
                    color=(1.0, 0.0, 0.0),
                    description=str(exc),
                    tone=Tone("A4"),
                )

            await self._display_status(status)

            try:
                await asyncio.wait_for(
                    self._mode_change_event.wait(), timeout=mode.update_interval
                )
            except asyncio.TimeoutError:
                pass
            finally:
                self._mode_change_event.clear()

    async def _display_status(self, status: AmbientStatus) -> None:
        """Update the LED and buzzer to reflect the provided status."""

        logging.debug("Displaying status: %s", status)
        self.led.color = status.color
        logging.info("%s: %s", status.label, status.description)

        if status.tone is not None:
            self.buzzer.play(status.tone)
            # Give the tone a short duration to avoid being annoying.
            await asyncio.sleep(0.6)
            self.buzzer.stop()
        else:
            self.buzzer.stop()


class WeatherFetcher:
    """Retrieve current weather information using the Open-Meteo API."""

    API_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        latitude: float,
        longitude: float,
        timezone_name: str = "auto",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.timezone_name = timezone_name
        self.session = session or requests.Session()

    def fetch(self) -> AmbientStatus:
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "current_weather": True,
            "hourly": "temperature_2m,relativehumidity_2m,precipitation_probability",
            "timezone": self.timezone_name,
        }

        response = self.session.get(self.API_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()

        current = payload.get("current_weather") or {}
        hourly = payload.get("hourly") or {}

        temp_c = float(current.get("temperature", 0.0))
        wind_speed = float(current.get("windspeed", 0.0))
        weather_code = int(current.get("weathercode", -1))
        humidity = _latest(hourly.get("relativehumidity_2m"))
        precip_probability = _latest(hourly.get("precipitation_probability"))

        label = "Weather"
        description = self._build_description(
            temperature=temp_c,
            wind_speed=wind_speed,
            humidity=humidity,
            precip_probability=precip_probability,
            weather_code=weather_code,
        )
        color = self._color_from_temperature(temp_c, precip_probability)
        tone = self._tone_from_wind(wind_speed)
        return AmbientStatus(label=label, color=color, description=description, tone=tone)

    @staticmethod
    def _color_from_temperature(temperature_c: float, precip_probability: float) -> tuple[float, float, float]:
        """Map the temperature and precipitation chance to an RGB color."""

        # Normalize temperature to a pleasant blue (cold) -> red (hot) gradient.
        clamped_temp = max(min(temperature_c, 35.0), -10.0)
        normalized = (clamped_temp + 10.0) / 45.0
        red = normalized
        blue = 1.0 - normalized
        green = 0.3 + 0.7 * (1.0 - abs(normalized - 0.5) * 2)

        # Blend towards teal when there is a strong chance of precipitation.
        precip_factor = min(max(precip_probability / 100.0, 0.0), 1.0)
        red = red * (1.0 - precip_factor)
        green = green * (1.0 - 0.3 * precip_factor) + 0.3 * precip_factor
        blue = min(1.0, blue + 0.7 * precip_factor)
        return (red, green, blue)

    @staticmethod
    def _tone_from_wind(wind_speed_kmh: float) -> Optional[Tone]:
        """Return a tone that rises with wind speed."""

        if wind_speed_kmh <= 5:
            return None

        # Map wind speed to a musical fifth range between G4 and D5.
        min_speed, max_speed = 5.0, 60.0
        clamped = min(max(wind_speed_kmh, min_speed), max_speed)
        scale = (clamped - min_speed) / (max_speed - min_speed)
        base_frequency = Tone("G4").frequency
        target_frequency = base_frequency * (1.5 ** scale)
        return Tone(target_frequency)

    @staticmethod
    def _build_description(
        *,
        temperature: float,
        wind_speed: float,
        humidity: Optional[float],
        precip_probability: Optional[float],
        weather_code: int,
    ) -> str:
        parts = [
            f"Temperature: {temperature:.1f}°C",
            f"Wind: {wind_speed:.1f} km/h",
        ]
        if humidity is not None:
            parts.append(f"Humidity: {humidity:.0f}%")
        if precip_probability is not None:
            parts.append(f"Precipitation chance: {precip_probability:.0f}%")

        description = WEATHER_CODE_DESCRIPTIONS.get(weather_code)
        if description:
            parts.append(description)
        return ", ".join(parts)


class SystemStatusFetcher:
    """Summarize the Pi's local system health."""

    def __init__(self, root_path: Path = Path("/")) -> None:
        self.root_path = root_path

    def fetch(self) -> AmbientStatus:
        load1, load5, _ = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        load_ratio = load5 / cpu_count

        disk_usage = shutil.disk_usage(self.root_path)
        disk_ratio = disk_usage.used / disk_usage.total

        temperature_c = _read_cpu_temperature()

        severity = max(load_ratio, disk_ratio, _normalize_temperature(temperature_c))
        color = _color_from_severity(severity)
        tone = _tone_from_severity(severity)

        description_parts = [
            f"5m load: {load5:.2f}",
            f"Disk used: {disk_ratio * 100:.0f}%",
        ]
        if temperature_c is not None:
            description_parts.append(f"CPU temp: {temperature_c:.1f}°C")
        description = ", ".join(description_parts)
        return AmbientStatus(
            label="System health",
            color=color,
            description=description,
            tone=tone,
        )


def _latest(sequence: Optional[Iterable[float]]) -> Optional[float]:
    if sequence is None:
        return None
    try:
        if hasattr(sequence, "__getitem__"):
            # Many sequences exposed by requests/JSON are already lists.
            return float(sequence[-1])  # type: ignore[index]
        last_value = None
        for last_value in sequence:
            pass
        if last_value is None:
            return None
        return float(last_value)
    except (IndexError, ValueError, TypeError):
        return None


def _read_cpu_temperature() -> Optional[float]:
    """Read the CPU temperature from the Raspberry Pi thermal zone."""

    thermal_file = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        raw = thermal_file.read_text().strip()
        return int(raw) / 1000.0
    except (FileNotFoundError, ValueError):
        return None


def _normalize_temperature(temperature_c: Optional[float]) -> float:
    if temperature_c is None:
        return 0.0
    # Below 50°C is fine, above 80°C is critical.
    return min(max((temperature_c - 50.0) / 30.0, 0.0), 1.0)


def _color_from_severity(severity: float) -> tuple[float, float, float]:
    # Start at soothing green and move towards red as severity increases.
    severity = min(max(severity, 0.0), 1.0)
    red = severity
    green = 1.0 - 0.4 * severity
    blue = max(0.0, 1.0 - severity * 1.2)
    return (red, green, blue)


def _tone_from_severity(severity: float) -> Optional[Tone]:
    if severity < 0.2:
        return None
    min_freq, max_freq = Tone("E4").frequency, Tone("C6").frequency
    frequency = min_freq + (max_freq - min_freq) * min(max(severity, 0.0), 1.0)
    return Tone(frequency)


WEATHER_CODE_DESCRIPTIONS: dict[int, str] = {
    -1: "Unknown weather",
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def build_modes(args: argparse.Namespace) -> list[Mode]:
    """Create the list of active modes based on CLI arguments."""

    modes: list[Mode] = []
    system_fetcher = SystemStatusFetcher(root_path=Path(args.root_path))
    modes.append(
        Mode(
            name="System health",
            fetch=system_fetcher.fetch,
            update_interval=args.system_interval,
        )
    )

    if args.latitude is not None and args.longitude is not None:
        weather_fetcher = WeatherFetcher(
            latitude=args.latitude,
            longitude=args.longitude,
            timezone_name=args.timezone,
        )
        modes.append(
            Mode(
                name="Weather",
                fetch=weather_fetcher.fetch,
                update_interval=args.weather_interval,
            )
        )
    return modes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn a Raspberry Pi into an ambient information hub."
    )
    parser.add_argument(
        "--led-pins",
        nargs=3,
        type=int,
        metavar=("RED", "GREEN", "BLUE"),
        default=(17, 27, 22),
        help="GPIO pins for the RGB LED (default: 17 27 22)",
    )
    parser.add_argument(
        "--button-pin",
        type=int,
        default=23,
        help="GPIO pin wired to the mode toggle button (default: 23)",
    )
    parser.add_argument(
        "--buzzer-pin",
        type=int,
        default=18,
        help="GPIO pin wired to the buzzer (default: 18)",
    )
    parser.add_argument(
        "--latitude",
        type=float,
        help="Latitude for weather lookups (enables the weather mode)",
    )
    parser.add_argument(
        "--longitude",
        type=float,
        help="Longitude for weather lookups (enables the weather mode)",
    )
    parser.add_argument(
        "--timezone",
        default="auto",
        help="Timezone identifier for weather results (default: auto)",
    )
    parser.add_argument(
        "--system-interval",
        type=float,
        default=30.0,
        help="How often to refresh the system health mode, in seconds",
    )
    parser.add_argument(
        "--weather-interval",
        type=float,
        default=300.0,
        help="How often to refresh the weather mode, in seconds",
    )
    parser.add_argument(
        "--root-path",
        default="/",
        help="Filesystem path to monitor for disk usage (default: /)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args()


def create_hardware(args: argparse.Namespace) -> tuple[RGBLED, Button, TonalBuzzer]:
    """Instantiate the gpiozero devices."""

    red, green, blue = args.led_pins
    led = RGBLED(red=red, green=green, blue=blue, pwm=True, active_high=False)
    button = Button(args.button_pin, pull_up=True, bounce_time=0.1)
    buzzer = TonalBuzzer(args.buzzer_pin)
    return led, button, buzzer


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    led, button, buzzer = create_hardware(args)
    modes = build_modes(args)
    controller = CoolerPi(led=led, button=button, buzzer=buzzer, modes=modes)

    try:
        asyncio.run(controller.run())
    except KeyboardInterrupt:
        logging.info("Shutting down due to keyboard interrupt")
    finally:
        led.close()
        button.close()
        buzzer.close()


if __name__ == "__main__":
    main()
