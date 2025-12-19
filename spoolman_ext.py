# Moonraker component to expose active Spoolman filament data
# to Klipper as gcode_macro variables (event-driven, with initial load on klippy ready).

from __future__ import annotations

import logging
from typing import Dict, Optional, Any


class SpoolmanExt:
    def __init__(self, config):
        self.server = config.get_server()
        self.component_name = config.get_name()
        self.log = logging.getLogger(f"moonraker.{self.component_name}")

        # Moonraker components
        self.http_client = self.server.lookup_component("http_client")
        self.klippy_apis = self.server.lookup_component("klippy_apis")

        # Public state
        self.current_spool: Optional[Dict[str, Any]] = None

        # Internal state
        self._macro_checked = False
        self._macro_available = False

        # Read and normalize Spoolman server URL
        spoolman_config = config.getsection("spoolman")
        self.spoolman_url = spoolman_config.get("server").rstrip("/")

        # Determine Moonraker API URL
        host_info = self.server.get_host_info()
        self.moonraker_url = f"http://{host_info['address']}:{host_info['port']}"

        # Register event handlers
        self.server.register_event_handler(
            "spoolman:active_spool_set",
            self._on_active_spool_set,
        )
        self.server.register_event_handler(
            "server:klippy_ready",
            self._on_klippy_ready,
        )

        self.log.info("Component loaded")

    async def _on_klippy_ready(self) -> None:
        """Triggered when Klipper becomes ready."""
        self.log.info("Klippy ready, searching for gcode_macro SPOOLMAN_VARS")
        if not await self._ensure_macro_available():
            return
        self.log.info("Performing initial spool load...")
        await self._load_initial_spool()

    async def _load_initial_spool(self) -> None:
        """Fetch the current active spool from Moonraker's Spoolman status."""
        url = f"{self.moonraker_url}/server/spoolman/spool_id"

        try:
            response = await self.http_client.get(url)
            if response.has_error():
                raise RuntimeError(f"HTTP error {response.status_code}")

            data = response.json()
            self.log.debug("Initial Spoolman status response: %s", data)

            spool_id = data.get("result", {}).get("spool_id")
            if spool_id is not None:
                await self._update_spool_info(spool_id)
            else:
                self.log.info("No active spool on initial load")
                await self._update_klipper(None)

        except Exception as exc:
            self.log.warning(
                "Initial spool load failed (%s). Spoolman may not be ready yet.",
                exc,
            )

    async def _on_active_spool_set(self, event: Dict[str, Any]) -> None:
        """
        Handle spoolman:active_spool_set events.

        Payload:
            {"spool_id": int} or {"spool_id": null}
        """
        if not self._macro_available:
            return
        
        spool_id = event.get("spool_id")

        if spool_id is None:
            self.log.info("Active spool cleared, resetting Klipper variables")
            self.current_spool = None
            await self._update_klipper(None)
            return

        await self._update_spool_info(spool_id)

    async def _update_spool_info(self, spool_id: int) -> None:
        """Fetch filament data for the given spool ID."""
        url = f"{self.spoolman_url}/api/v1/spool/{spool_id}"
        self.log.info("Fetching spool info (ID=%s)", spool_id)

        try:
            response = await self.http_client.get(url)
            if response.has_error():
                raise RuntimeError(f"HTTP error {response.status_code}")

            spool = response.json()
            filament = spool.get("filament")

            if not filament:
                self.log.warning("No filament data found for spool ID %s", spool_id)
                self.current_spool = None
                await self._update_klipper(None)
                return

            extracted = {
                "id": filament.get("id"),
                "hotend_temp": filament.get("settings_extruder_temp"),
                "bed_temp": filament.get("settings_bed_temp"),
                "material": filament.get("material"),
                "name": filament.get("name"),
                "vendor": (
                    filament.get("vendor", {}).get("name")
                    if isinstance(filament.get("vendor"), dict)
                    else None
                ),
            }

            self.current_spool = extracted
            await self._update_klipper(extracted)

        except Exception as exc:
            self.server.add_warning(
                f"{self.component_name}: Failed to query filament {spool_id}: {exc}"
            )
            self.log.warning(
                "Failed to query filament %s: %s",
                spool_id,
                exc,
            )
            self.current_spool = None

    async def _update_klipper(
        self, spool_data: Optional[Dict[str, Any]]
    ) -> None:
        """Push spool data into Klipper via SET_GCODE_VARIABLE."""

        variables = ("id", "hotend_temp", "bed_temp", "material", "name", "vendor")

        try:
            if spool_data is None:
                for var in variables:
                    gcode = (
                        "SET_GCODE_VARIABLE "
                        "MACRO=SPOOLMAN_VARS "
                        f'VARIABLE={var} VALUE="None"'
                    )
                    await self.klippy_apis.run_gcode(gcode)

                self.log.info("SPOOLMAN_VARS cleared")
                return

            for var in variables:
                value = spool_data.get(var)
                value_str = self._escape_gcode_value(value)

                gcode = (
                    "SET_GCODE_VARIABLE "
                    "MACRO=SPOOLMAN_VARS "
                    f'VARIABLE={var} VALUE=\'"{value_str}"\''
                )
                await self.klippy_apis.run_gcode(gcode)

            self.log.info("SPOOLMAN_VARS updated")

        except Exception as exc:
            self.log.warning(
                "Failed to update SPOOLMAN_VARS: %s",
                exc,
            )

    async def _ensure_macro_available(self) -> bool:
        """Check once whether the SPOOLMAN_VARS macro exists by probing it."""
        if self._macro_checked:
            return self._macro_available

        self._macro_checked = True

        try:
            # Probe macro existence with a harmless dummy variable
            gcode = (
                "SET_GCODE_VARIABLE "
                "MACRO=SPOOLMAN_VARS "
                'VARIABLE=id VALUE="None"'
            )
            await self.klippy_apis.run_gcode(gcode)

            self._macro_available = True
            self.log.info("gcode_macro SPOOLMAN_VARS detected")
            return True

        except Exception as exc:
            if "'id'" in str(exc).lower():
                self._macro_available = True
                self.log.info("gcode_macro SPOOLMAN_VARS detected, but missing valid variable/s")
                return True
            else:
                self._macro_available = False
                self.server.add_warning(
                    f"{self.component_name}: gcode_macro SPOOLMAN_VARS not found. "
                    "Spool details will not be pulled from Spoolman."
                )
                self.log.warning(f"Failed sanity check for SPOOLMAN_VARS: {exc}")
                return False

    @staticmethod
    def _escape_gcode_value(value: Any) -> str:
        """Escape values for safe insertion into SET_GCODE_VARIABLE."""
        if value is None:
            return "None"

        text = str(value)
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        text = text.replace("\n", " ").replace("\r", " ")
        return text


def load_component(config):
    """Moonraker component entry point."""
    return SpoolmanExt(config)
