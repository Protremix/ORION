# ORION — Physical Intelligence OS

A simulation-first Physical Intelligence Operating System integrating reasoning,
long-term memory, multimodal perception, and world models for robotics, automotive,
drones, and smart home applications.

## License

Apache 2.0 — See [LICENSE](LICENSE) for details.

## Installation

```bash
pip install -e ".[dev]"
```

## Testing

```bash
pytest --tb=short -q -m "not live"
```

## Architecture

See `ORION_ARCHITECTURE_V0.6.md` for the full architecture specification.

## Documentation

- `docs/` — Safety, hardware, regulatory, and performance documentation
- `docs/adr/` — Architecture Decision Records
- `docs/audits/` — Audit reports
