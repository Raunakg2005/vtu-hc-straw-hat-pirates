"""Command-line interface.

    qday scan  --host example.com --path ./src [--json] [--fail-on critical]
    qday cbom  --host example.com --path ./src -o cbom.json
    qday forecast RSA-2048 [--scenario roadmap|trend] [--rsa-source gidney2025|gidney_ekera2019]
    qday shor  --N 15 --a 7 [--counting 3] [--backend aer]
    qday grover --bits 3 --secret 6 [--backend aer]
    qday pqc

Exit codes: 0 ok, 1 findings at or above --fail-on, 2 bad input.
"""

import argparse
import json
import sys

from .catalog import size_parameter
from .forecast.estimates import requirements_for
from .forecast.risk import assess_all
from .forecast.roadmap import SCENARIOS, first_break_year
from .safety import InputError, validate_host

RISK_ORDER = ["safe", "unknown", "medium", "high", "critical"]


def _collect(hosts, path, verify=True):
    from .scanner.code import scan_code
    from .scanner.tls import scan_tls

    assets, errors, valid = [], [], []
    for raw in hosts or []:  # each --host is one host: never split a value into several
        try:
            host = validate_host(raw)
        except InputError as exc:
            errors.append(f"{raw}: {exc}")
            continue
        if host not in valid:
            valid.append(host)
    if not valid and not path:
        raise InputError("nothing to scan: give at least one valid --host or a --path")
    scanned = 0
    for host in valid:
        try:
            assets += scan_tls(host, verify=verify)["assets"]
            scanned += 1
        except Exception as exc:  # report and keep scanning the rest
            errors.append(f"{host}: {exc}")
    if path:
        assets += scan_code(path)["assets"]
        scanned += 1
    if not scanned:
        raise InputError("every target failed: " + "; ".join(errors))
    return assets, errors


def cmd_scan(args) -> int:
    assets, errors = _collect(args.host, args.path, verify=not args.insecure)
    assessed = assess_all(assets, migration_years=args.migration, shelf_life=args.shelf_life,
                          scenario=args.scenario, rsa_source=args.rsa_source)
    if args.json:
        print(json.dumps({"assets": assessed, "errors": errors}, indent=2, default=str))
    else:
        for err in errors:
            print(f"warning: {err}", file=sys.stderr)
        for a in assessed:
            year = a["break_year"] or "-"
            print(f"{a['risk']:9s} {a['algorithm']:22s} {a['location']:40s} breaks {year!s:5s} "
                  f"fix: {a['replacement'] or '-'}")
        print(f"{len(assessed)} findings")
    if args.fail_on:
        bar = RISK_ORDER.index(args.fail_on)
        if any(RISK_ORDER.index(a["risk"]) >= bar for a in assessed if a["risk"] in RISK_ORDER):
            return 1
    return 0


def cmd_cbom(args) -> int:
    from .scanner.cbom import build_cbom

    assets, errors = _collect(args.host, args.path, verify=not args.insecure)
    for err in errors:
        print(f"warning: {err}", file=sys.stderr)
    bom = json.dumps(build_cbom(assets, target=args.name), indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf8") as fh:
            fh.write(bom)
        print(f"wrote {args.output} ({len(assets)} assets)")
    else:
        print(bom)
    return 0


def cmd_forecast(args) -> int:
    req = requirements_for(size_parameter(args.algorithm), args.rsa_source)
    if req is None:
        print(f"no published estimate for {args.algorithm!r} (supports RSA-<bits>, ECDSA/ECDH-P-256/384/521, "
              "X25519, Ed25519)", file=sys.stderr)
        return 2
    year = first_break_year(req, args.scenario)
    print(json.dumps({"algorithm": args.algorithm, "scenario": args.scenario, **req,
                      "first_break_year": year}, indent=2))
    return 0


def cmd_shor(args) -> int:
    from .quantum import shor
    from .quantum.runner import run_sampler

    qc = shor.order_finding_circuit(args.a, args.N, args.counting)
    res = run_sampler([qc], args.backend, shots=args.shots)["circuits"][0]
    r = shor.analyse_counts(res["counts"], args.a, args.N, args.counting)
    print(json.dumps({k: r[k] for k in ("N", "a", "true_order", "most_likely_order", "factors",
                                         "success_probability", "random_noise_baseline")}, indent=2))
    return 0


def cmd_grover(args) -> int:
    from .quantum import grover
    from .quantum.runner import run_sampler

    if not 0 <= args.secret < 2**args.bits:
        raise InputError(f"secret must be in [0, {2**args.bits - 1}]")
    c = grover.toy_encrypt(5, args.secret, args.bits)
    it = grover.optimal_iterations(args.bits)
    res = run_sampler([grover.grover_key_search_circuit(5, c, it, args.bits)], args.backend, shots=args.shots)
    r = grover.analyse_counts(res["circuits"][0]["counts"], 5, c, it, args.bits)
    print(json.dumps({k: r[k] for k in ("recovered_key", "key_is_correct", "success_probability",
                                         "theoretical_success", "iterations")}, indent=2))
    return 0


def cmd_pqc(args) -> int:
    from .migrate.pqc import hybrid_key_exchange

    h = hybrid_key_exchange()
    print(json.dumps({k: v for k, v in h.items() if k != "ml_kem_ms"}, indent=2))
    return 0 if h["keys_match"] and h["message_roundtrip"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qday", description="Quantum threat forecasting for cryptography")
    sub = p.add_subparsers(dest="command", required=True)

    def targets(sp):
        sp.add_argument("--host", action="append", default=[], help="TLS endpoint (repeatable)")
        sp.add_argument("--path", help="source folder to scan")
        sp.add_argument("--insecure", action="store_true", help="do not verify certificates")

    def forecast_opts(sp):
        sp.add_argument("--scenario", choices=list(SCENARIOS), default="trend")
        sp.add_argument("--rsa-source", choices=["gidney2025", "gidney_ekera2019"], default="gidney2025")

    s = sub.add_parser("scan", help="find quantum-vulnerable cryptography")
    targets(s)
    forecast_opts(s)
    s.add_argument("--shelf-life", type=float, default=10)
    s.add_argument("--migration", type=float, default=3)
    s.add_argument("--json", action="store_true")
    s.add_argument("--fail-on", choices=RISK_ORDER[2:], help="exit 1 if any finding is at least this risky")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("cbom", help="export a CycloneDX 1.6 CBOM")
    targets(c)
    c.add_argument("-o", "--output")
    c.add_argument("--name", default="q-day scan")
    c.set_defaults(func=cmd_cbom)

    f = sub.add_parser("forecast", help="break year for one algorithm")
    f.add_argument("algorithm", help="e.g. RSA-2048, ECDSA-P-256")
    forecast_opts(f)
    f.set_defaults(func=cmd_forecast)

    sh = sub.add_parser("shor", help="run Shor's order finding")
    sh.add_argument("--N", type=int, default=15, choices=[15, 21])
    sh.add_argument("--a", type=int, default=7)
    sh.add_argument("--counting", type=int, default=3)
    sh.add_argument("--backend", default="aer")
    sh.add_argument("--shots", type=int, default=4000)
    sh.set_defaults(func=cmd_shor)

    g = sub.add_parser("grover", help="run Grover key search")
    g.add_argument("--bits", type=int, default=3, choices=[3, 4])
    g.add_argument("--secret", type=int, default=6)
    g.add_argument("--backend", default="aer")
    g.add_argument("--shots", type=int, default=4000)
    g.set_defaults(func=cmd_grover)

    q = sub.add_parser("pqc", help="hybrid X25519 + ML-KEM-768 handshake")
    q.set_defaults(func=cmd_pqc)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:  # e.g. a base not coprime to N
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
