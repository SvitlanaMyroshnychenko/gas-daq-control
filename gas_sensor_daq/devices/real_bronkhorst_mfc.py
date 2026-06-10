class RealBronkhorstMFC:
    """Placeholder for future Bronkhorst F-201CV propar integration."""

    def __init__(self, port="COM3"):
        self.port = port
        self.master = None

    def connect(self):
        raise ConnectionError(
            "Real Bronkhorst support is not implemented yet. "
            'Expected first hardware test: master = propar.master("COM3"); master.get_nodes()'
        )

    def set_nh3_flow(self, value_sccm):
        raise ConnectionError("Bronkhorst MFC is not connected.")

    def set_air_flow(self, value_sccm):
        raise ConnectionError("Bronkhorst MFC is not connected.")

    def air_purge(self):
        raise ConnectionError("Bronkhorst MFC is not connected.")

    def set_humidity(self, enabled):
        raise ConnectionError("Humidity controller is not connected.")

    def set_heating(self, enabled):
        raise ConnectionError("Heating controller is not connected.")

    def get_state(self):
        raise ConnectionError("Bronkhorst MFC is not connected.")

    def close(self):
        self.master = None
