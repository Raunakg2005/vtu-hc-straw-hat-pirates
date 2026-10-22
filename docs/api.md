# API reference

Everything the dashboard and the CLI do is available from Python. A typical use:

```python
from qday.scanner.code import scan_code
from qday.scanner.tls import scan_tls
from qday.forecast.risk import assess_all
from qday.scanner.cbom import build_cbom

assets = scan_code("./src")["assets"] + scan_tls("example.com")["assets"]
findings = assess_all(assets, migration_years=3, shelf_life=10, scenario="trend")
critical = [f for f in findings if f["risk"] == "critical"]
cbom = build_cbom(assets, target="my-service")   # CycloneDX 1.6, a plain dict
```

## Scanning

::: qday.scanner.code

::: qday.scanner.tls

::: qday.scanner.cbom

::: qday.safety

## Algorithm catalog

::: qday.catalog

## Forecast and risk

::: qday.forecast.estimates

::: qday.forecast.roadmap

::: qday.forecast.risk

::: qday.forecast.calibrated

## Quantum attacks

::: qday.quantum.shor

::: qday.quantum.grover

::: qday.quantum.runner

::: qday.quantum.stats

::: qday.quantum.validation

::: qday.quantum.debug

## Post-quantum migration

::: qday.migrate.pqc

## Command line

::: qday.cli
