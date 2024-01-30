# /usr/bin/env python3

"""
Exports data from VictoriaMetrics in metrics (application/openmetrics-text)
format via HTTP API.

Query the --path parameter (/export by default) with additional target
parameter with VictoriaMetrics address and optional last parameter with amount
last seconds to be exported (to avoid manually calculating start and end
parameters).

The start, end and match[] (which is {__name__!=''} by default) are described
in VictoriaMetrics docs:
https://docs.victoriametrics.com/#how-to-export-time-series.
"""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, Namespace
from contextlib import suppress
from json import JSONDecodeError, loads
from logging import Logger, getLogger
from time import time
from typing import Any
from http import HTTPStatus

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError
from aiohttp.web import run_app  # type: ignore
from aiohttp.web import Application, Request, Response, get
from multidict import MultiMapping
from prometheus_client import Counter, Gauge, Info, generate_latest
from yarl import URL

__prog__ = "vmexporter"
__version__ = "1.0.0"
__status__ = "Release"
__author__ = "Alexander Pozlevich"
__email__ = "apozlevich@gmail.com"

logger: Logger = getLogger(name=__name__)

# Export own info metric
Info(
    name=__prog__,
    documentation=f"{__prog__} version information",
    labelnames=("version", "status"),
).labels(__version__, __status__).info(
    val=dict(zip(("major", "minor", "patchlevel"), __version__.split(sep=".")))
)


# Measure exporting time
DURATION_METRIC: Gauge = Gauge(
    namespace=__prog__,
    subsystem="export",
    name="duration",
    documentation="Last export duration",
    labelnames=("target",),
)

# Export status counters
EXPORT_COUNT: Counter = Counter(
    namespace=__prog__,
    subsystem="export",
    name="count",
    documentation="Exports done total",
    labelnames=("target",),
)

EXPORT_FAILS: Counter = Counter(
    namespace=__prog__,
    subsystem="export",
    name="failures",
    documentation="Exports failed total",
    labelnames=("target",),
)

EXPORT_LINES: Counter = Counter(
    namespace=__prog__,
    subsystem="export",
    name="metrics",
    documentation="Exported metrics total",
    labelnames=("target",),
)


async def handle_metrics(_: Request) -> Response:
    """Serve own metrics."""

    body: bytes = generate_latest()
    return Response(body=body, status=HTTPStatus.OK, content_type="text/plain")


def make_url(query: MultiMapping[str]) -> str:
    url: str = "/api/v1/export?"

    # Export last N seconds if set to
    if "last" in query:
        start: str | None = str(object=time() - float(query["last"]))

    else:
        start: str | None = query.get("start")

    end: str | None = query.get("end")

    if start:
        url = f"{url}start={start}&"

    if end:
        url = f"{url}end={end}&"

    if "match[]" in query:
        url = f"{url}match[]={query['match[]']}"

    else:
        url = f"{url}match[]={{__name__!=''}}"

    return url


async def handle_export(request: Request) -> Response:
    """Perform actual metrics export."""

    if not "target" in request.query:
        return Response(
            status=HTTPStatus.BAD_REQUEST,
            body=b"Missing 'target' query field",
            content_type="text/plain",
        )

    export_start: float = time()
    target: str = request.query["target"]
    body: str = ""
    url: str = make_url(query=request.query)

    try:
        async with ClientSession(
            base_url=target,
            headers=request.headers,
        ) as session:
            async with session.get(url=URL(val=url, encoded=True)) as response:
                lines: list[str] = (await response.text()).splitlines()
                for line in lines:
                    json_metric: dict[str, Any] = loads(s=line)

                    metric: dict[str, str] = json_metric["metric"]
                    values: list[float | None] = json_metric["values"]
                    timestamps: list[int] = json_metric["timestamps"]
                    metric_name: str = metric.pop("__name__")

                    # Render metrics manually since there is no timestamp support anymore in prometheus_client.
                    # Actually main trouble is what labels count may vary in export and prometheus_client fails.
                    for value, timestamp in zip(values, timestamps):
                        # There may be 'null' values actually
                        labels: str = ",".join(f'{k}="{v}"' for k, v in metric.items())
                        body += f"{metric_name}{{{labels}}} {value if value is not None else 0} {timestamp}\n"

    except (ClientError, JSONDecodeError, ValueError) as exc:
        EXPORT_FAILS.labels(request.query["target"]).inc()
        return Response(
            status=HTTPStatus.BAD_REQUEST,
            body=str(object=exc),
            content_type="text/plain",
        )

    export_duration: float = time() - export_start
    DURATION_METRIC.labels(target).set(value=export_duration)
    EXPORT_COUNT.labels(target).inc()
    EXPORT_LINES.labels(target).inc(amount=len(lines))

    return Response(body=body, status=200, content_type="text/plain")


def make_app(
    path: str,
    self: str,
) -> Application:
    """Application factory."""

    app: Application = Application()

    app.add_routes(
        routes=[
            get(path=path, handler=handle_export),
            get(path=self, handler=handle_metrics),
        ]
    )

    return app


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        args_parser = ArgumentParser(
            prog=__prog__,
            description=__doc__,
            epilog=f"Written by {__author__} <{__email__}>.",
            formatter_class=lambda prog: ArgumentDefaultsHelpFormatter(
                prog=prog,
                max_help_position=36,
            ),
        )
        args_parser.add_argument(
            "--version",
            action="version",
            version=f"{__prog__} v{__version__} ({__status__})",
        )

        server_args = args_parser.add_argument_group(title="server options")
        server_args.add_argument(
            "-H",
            "--host",
            default="0.0.0.0",
            metavar="addr",
            help="host to bind to",
        )
        server_args.add_argument(
            "-P",
            "--port",
            type=int,
            default=8080,
            metavar="port",
            help="port to bind to",
        )
        server_args.add_argument(
            "-U",
            "--path",
            default="/export",
            metavar="path",
            help="path to serve exported metrics on",
        )
        server_args.add_argument(
            "-s",
            "--self",
            default="/metrics",
            metavar="path",
            help="path to serve own metrics on",
        )

        args: Namespace = args_parser.parse_args()
        vmexport: Application = make_app(
            path=args.path,
            self=args.self,
        )

        run_app(app=vmexport, host=args.host, port=args.port, print=None)
