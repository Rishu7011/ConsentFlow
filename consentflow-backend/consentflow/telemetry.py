"""
consentflow/telemetry.py — OpenTelemetry tracer factory (Step 7).

Usage
-----
Call ``configure_otel()`` once during application startup (inside the
FastAPI lifespan, guarded by ``settings.otel_enabled``).

Every gate wrapper calls ``get_tracer(name)`` to obtain a tracer.  In
production this returns a real SDK tracer that sends spans to the OTLP
collector.  In tests, inject a ``NonRecordingTracer`` directly so no
network calls are made.

Design
------
* ``configure_otel()`` is **idempotent** — safe to call more than once.
* ``get_tracer()`` always returns a valid tracer; if OTel is not
  configured it returns the no-op ``NonRecordingTracer`` from the API
  package — consistent with the OTel Python SDK spec.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def configure_otel(endpoint: str, service_name: str) -> None:
    """
    Set up a global OTLP gRPC exporter + batch span processor.

    Parameters
    ----------
    endpoint:     OTLP gRPC endpoint, e.g. ``"http://otel-collector:4317"``.
    service_name: Value written to the ``service.name`` resource attribute.

    Notes
    -----
    Imports are lazy so the module can be imported in test environments
    that may not have ``grpcio`` installed.
    """
    from opentelemetry import trace  # noqa: PLC0415
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource  # noqa: PLC0415
    from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415

    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    logger.info(
        "OTel configured — service=%s  endpoint=%s",
        service_name,
        endpoint,
    )


def get_tracer(name: str) -> Any:
    """
    Return the global OTel tracer for *name*.

    If ``configure_otel()`` has not been called this returns the
    no-op ``NonRecordingTracer`` — zero overhead, no network I/O.

    Parameters
    ----------
    name: Instrumentation scope name, typically the gate module name.
    """
    from opentelemetry import trace  # noqa: PLC0415

    return trace.get_tracer(name)
