# VMExporter

Exports data from VictoriaMetrics in metrics (`application/openmetrics-text`) format via HTTP API.

Query the `--path` parameter (`/export` by default) with additional `target` parameter with VictoriaMetrics
address and optional `last` parameter with amount last seconds to be exported (to avoid manually calculating
`start` and `end` parameters).

The `start`, `end` and `match[]` (which is `{__name__!=''}` by default) are described in
[VictoriaMetrics docs](https://docs.victoriametrics.com/#how-to-export-time-series).

## Running

Server options are:

- `-H addr`, `--host addr`: host to bind to (default: `0.0.0.0`)
- `-P port`, `--port port`: port to bind to (default: `8080`)
- `-U path`, `--path path`: path to serve exported metrics on (default: `/export`)
- `-s path`, `--self path`: path to serve own metrics on (default: `/metrics`)

## Example

Lets assume we have VictoriaMetrics (single instance version) running on `http://192.168.1.110:8428` and exporter
running on `http://localhost:8080`. Then querying for the last 60 seconds metrics starting with `redis_` name
prefix will look like:

```bash session
curl -s "http://localhost:8080/export?target=http://192.168.1.110:8428&last=60&match%5B%5D=%7B__name__=~%27redis.*%27%7D" | head
```

And this will output something like this, in Prometheus-parsable format:

```plain
redis_aof_rewrite_scheduled{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 0 1706632255817
redis_aof_last_cow_size_bytes{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 0 1706632255817
redis_allocator_rss_bytes{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 2666496 1706632255817
redis_defrag_key_misses{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 0 1706632255817
redis_pubsub_channels{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 0 1706632255817
redis_module_fork_in_progress{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 0 1706632255817
redis_slowlog_last_id{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 0 1706632255817
redis_tracking_total_prefixes{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 0 1706632255817
redis_memory_used_dataset_bytes{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 237456 1706632255817
redis_config_maxclients{job="redis_exporter_targets",instance="redis://host.docker.internal:6380"} 10000 1706632255817
```

Thus this tool may be used to export some metrics for external Prometheus/VictoriaMetrics, such as exporting couple of 
bussiness-related metrics from incapsulated project infrastructure.

Or, which was the main goal, use multi-target-like scraping in environment where it is not possible (e.g. you only can provide
only scrape URLs to externap monitoring department) by running own VictoriaMetrics with small retention period.

Note what target parameter should include scheme (`http://`) and query parameters are URL-encoded.

## Metrics

### Additional metrics exported on `--self` option path (default: `/metrics`):

| Name                         | Type    | Labels                                              | Description                       |
|------------------------------|---------|-----------------------------------------------------|-----------------------------------|
| `vmexporter_export_duration` | Gauge   | `target`                                            | Last export duration (in seconds) |
| `vmexporter_export_count`    | Counter | `target`                                            | Exports done total                |
| `vmexporter_export_failures` | Counter | `target`                                            | Exports failed total              |
| `vmexporter_export_metrics`  | Counter | `target`                                            | Exported metrics total            |
| `vmexporter`                 | Info    | `version`, `major`, `minor`, `patchlevel`, `status` | `vmexporter` version information  |

### Default `prometheus_client` metrics are:

| Name                                    | Type    | Labels       | Description                                                                                          |
|-----------------------------------------|---------|--------------|------------------------------------------------------------------------------------------------------|
| `python_gc_objects_collected_total`     | Counter | `generation`                                                | Objects collected during GC                           |
| `python_gc_objects_uncollectable_total` | Counter | `generation`                                                | Uncollectable objects found during GC                 |
| `python_gc_collections_tota`            | Counter | `generation`                                                | Number of times this generation was                   |
| `python_info`                           | Gauge   | `implementation`, `major`, `minor`, `patchlevel`, `version` | Python platform information                           |
| `process_virtual_memory_bytes`          | Gauge   |                                                             | Virtual memory size in bytes                          |
| `process_resident_memory_bytes`         | Gauge   |                                                             | Resident memory size in bytes                         |
| `process_start_time_seconds`            | Gauge   |                                                             | Start time of the process since unix epoch in seconds |
| `process_cpu_seconds_total`             | Gauge   |                                                             | Total user and system CPU time spent in seconds       |
| `process_open_fds`                      | Gauge   |                                                             | Number of open file descriptors                       |
| `process_max_fds`                       | Gauge   |                                                             | Maximum number of open file descriptors               |
