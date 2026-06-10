from dataclasses import dataclass

import pyvisa


@dataclass(frozen=True)
class VisaInstrumentInfo:
    resource: str
    idn: str

    @property
    def label(self):
        if not self.idn:
            return self.resource

        parts = [part.strip() for part in self.idn.split(",")]
        if len(parts) >= 4:
            manufacturer, model, serial, _firmware = parts[:4]
            return f"{manufacturer} {model} S/N {serial}"

        return f"{self.idn} ({self.resource})"


def discover_visa_instruments(timeout_ms=2000):
    resource_manager = pyvisa.ResourceManager()
    instruments = []

    try:
        for resource in resource_manager.list_resources():
            idn = query_idn(resource_manager, resource, timeout_ms)
            instruments.append(VisaInstrumentInfo(resource=resource, idn=idn))
    finally:
        resource_manager.close()

    return instruments


def query_idn(resource_manager, resource, timeout_ms):
    instrument = None

    try:
        instrument = resource_manager.open_resource(resource)
        instrument.timeout = timeout_ms
        instrument.write_termination = "\n"
        instrument.read_termination = "\n"
        return instrument.query("*IDN?").strip()
    except Exception as exc:
        return f"No *IDN? response: {exc}"
    finally:
        if instrument is not None:
            instrument.close()

