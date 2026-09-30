"""OpenTelemetry + Langfuse tracing setup."""
from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from orchestrix.config import get_settings

logger = logging.getLogger(__name__)


def setup_tracing() -> None:
    """Initialise OpenTelemetry + Langfuse."""
    settings = get_settings()

    resource = Resource.create({"service.name": "orchestrix", "service.version": "0.1.0"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        )
    )
    trace.set_tracer_provider(provider)

    logger.info("OpenTelemetry tracing initialized → %s", settings.otel_exporter_otlp_endpoint)


def get_tracer(name: str):
    return trace.get_tracer(name)
