"""Public command-line interface composed from RTL Lens application services."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.text import Text

from rtl_lens.config import CONFIG_FILENAME, load_config
from rtl_lens.engines.base import AnalysisEngine
from rtl_lens.engines.verilator_engine import VerilatorEngine
from rtl_lens.knowledge import KnowledgeStore, LocalizedExplanation
from rtl_lens.models.diagnostic import Severity
from rtl_lens.models.project import ProjectConfig
from rtl_lens.models.report import ScanState
from rtl_lens.project import resolve_project
from rtl_lens.renderers import render_terminal, write_html_report, write_json_report
from rtl_lens.security.paths import resolve_output_root, resolve_report_destination
from rtl_lens.security.redaction import RedactionPolicy
from rtl_lens.services.scan import ScanService, preflight_scan_configuration
from rtl_lens.version import (
    PYSLANG_COMPATIBILITY,
    VERILATOR_COMPATIBILITY,
    package_version,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Offline, explainable RTL diagnostics.",
)

_STARTER_CONFIG = """[scan]
source_roots = ["."]
timeout = 30
language = "en"
engine_mode = "auto"
output_dir = ".rtl-lens"
redact_sources = false
redact_path_prefixes = []
redact_environment_variables = []
fail_on = "error"
graph_display_limit = 200
"""
_ERROR_LIMIT = 500


def _console() -> Console:
    return Console()


def _pyslang_engine() -> AnalysisEngine:
    from rtl_lens.engines.pyslang_engine import PySlangEngine

    return PySlangEngine()


def _message(error: BaseException) -> str:
    try:
        value = str(error).strip() or type(error).__name__
    except Exception:  # noqa: BLE001 - error presentation must remain total.
        value = f"{type(error).__name__} (message unavailable)"
    return value[:_ERROR_LIMIT]


def _error(prefix: str, error: BaseException | str) -> None:
    detail = error if isinstance(error, str) else _message(error)
    line = Text(prefix, style="bold red")
    line.append(str(detail)[:_ERROR_LIMIT])
    try:
        _console().print(line)
    except Exception:  # noqa: BLE001 - retain a plain-text last-resort channel.
        typer.echo(f"{prefix}{str(detail)[:_ERROR_LIMIT]}")


def _project_root(path: Path) -> Path:
    root = path.resolve()
    if not root.is_dir():
        raise ValueError(f"project directory does not exist: {path}")
    return root


def _validate_config_option(config_path: Path | None) -> Path | None:
    if config_path is None:
        return None
    resolved = config_path.resolve()
    if not resolved.is_file():
        raise ValueError(f"configuration file does not exist: {config_path}")
    return resolved


def _destinations_collide(json_destination: Path, html_destination: Path) -> bool:
    return json_destination.resolve() == html_destination.resolve()


def _redaction_policy(root: Path, config: ProjectConfig) -> RedactionPolicy | None:
    if not config.scan.redact_sources:
        return None
    prefixes = tuple(
        (prefix if prefix.is_absolute() else root / prefix).resolve()
        for prefix in config.scan.redact_path_prefixes
    )
    return RedactionPolicy.from_environment(
        home=Path.home(),
        path_prefixes=prefixes,
        variable_names=config.scan.redact_environment_variables,
    )


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(help="RTL project directory.")] = Path("."),
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Project .rtl-lens.toml file."),
    ] = None,
    fail_on: Annotated[
        Severity | None,
        typer.Option("--fail-on", help="Lowest severity that fails policy."),
    ] = None,
    json_path: Annotated[
        Path | None,
        typer.Option("--json", help="JSON report destination."),
    ] = None,
    html_path: Annotated[
        Path | None,
        typer.Option("--html", help="HTML report destination."),
    ] = None,
) -> None:
    """Scan an RTL project and write terminal, JSON, and HTML reports."""
    try:
        root = _project_root(path)
        config_path = _validate_config_option(config)
        overrides: dict[str, object] | None = (
            {"scan.fail_on": fail_on.value} if fail_on is not None else None
        )
        project_config = load_config(root, overrides, config_path=config_path)
        json_destination = resolve_report_destination(
            root, project_config.scan.output_dir, json_path, "report.json"
        )
        html_destination = resolve_report_destination(
            root, project_config.scan.output_dir, html_path, "report.html"
        )
        if _destinations_collide(json_destination, html_destination):
            raise ValueError("JSON and HTML reports require different destinations")
        project = resolve_project(root, project_config)
        preflight_scan_configuration(project, project_config)
    except Exception as error:  # noqa: BLE001 - invalid input is a public exit contract.
        _error("Invalid project or configuration: ", error)
        raise typer.Exit(3) from None

    outcome = None
    try:
        outcome = ScanService((_pyslang_engine(), VerilatorEngine())).scan(project, project_config)
        console = _console()
        render_terminal(outcome.report, console)
        if outcome.report.metadata.scan_state is ScanState.PARTIAL:
            console.print(
                Text(
                    "completeness warning: optional analysis did not finish; "
                    "policy uses completed engines only.",
                    style="bold yellow",
                )
            )
        json_destination.parent.mkdir(parents=True, exist_ok=True)
        html_destination.parent.mkdir(parents=True, exist_ok=True)
        redaction_policy = _redaction_policy(root, project_config)
        if redaction_policy is None:
            write_json_report(outcome.report, json_destination)
            write_html_report(
                outcome.report,
                html_destination,
                graph_display_limit=project_config.scan.graph_display_limit,
            )
        else:
            write_json_report(
                outcome.report,
                json_destination,
                redaction_policy=redaction_policy,
            )
            write_html_report(
                outcome.report,
                html_destination,
                graph_display_limit=project_config.scan.graph_display_limit,
                redaction_policy=redaction_policy,
            )
        console.print(Text(f"JSON report: {json_destination}"))
        console.print(Text(f"HTML report: {html_destination}"))
    except Exception as error:  # noqa: BLE001 - runtime failures are bounded exit 2.
        _error("Scan runtime failure: ", error)
        exit_code = 3 if outcome is not None and outcome.exit_code == 3 else 2
        raise typer.Exit(exit_code) from None

    raise typer.Exit(outcome.exit_code)


def _write_new_config(destination: Path) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(destination, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(_STARTER_CONFIG.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        destination.unlink(missing_ok=True)
        raise


def _replace_config(destination: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f"{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(_STARTER_CONFIG.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


@app.command("init")
def initialize(
    path: Annotated[Path, typer.Argument(help="Project directory.")] = Path("."),
    force: Annotated[
        bool,
        typer.Option("--force", help="Atomically replace an existing configuration."),
    ] = False,
) -> None:
    """Create a reviewed starter .rtl-lens.toml configuration."""
    try:
        root = _project_root(path)
        destination = root / CONFIG_FILENAME
        if destination.exists() and not force:
            raise FileExistsError(f"configuration already exists: {destination}")
        if force:
            _replace_config(destination)
        else:
            _write_new_config(destination)
        load_config(root)
        _console().print(Text(f"Created configuration: {destination}"))
    except FileExistsError as error:
        _error("Initialization refused: ", error)
        raise typer.Exit(3) from None
    except ValueError as error:
        _error("Invalid project: ", error)
        raise typer.Exit(3) from None
    except Exception as error:  # noqa: BLE001 - filesystem failures are runtime failures.
        _error("Initialization failed: ", error)
        raise typer.Exit(2) from None


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _is_writable_directory(path: Path) -> bool:
    return path.is_dir() and os.access(path, os.W_OK)


def _check_line(status: str, label: str, detail: str) -> Text:
    style = {"PASS": "bold green", "WARN": "bold yellow", "FAIL": "bold red"}[status]
    line = Text(f"{status:<4}", style=style)
    line.append(f" | {label} | {detail[:_ERROR_LIMIT]}")
    return line


@app.command()
def doctor(
    path: Annotated[Path, typer.Argument(help="Project directory.")] = Path("."),
) -> None:
    """Run independent, read-only environment checks."""
    checks: list[tuple[str, str, str]] = []
    required_runtime_failed = False
    invalid_project = False

    supported_python = (3, 11) <= sys.version_info[:2] < (3, 14)
    checks.append(
        (
            "PASS" if supported_python else "FAIL",
            "Python",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )
    required_runtime_failed |= not supported_python

    try:
        engine = _pyslang_engine()
        if not engine.available():
            raise RuntimeError("required bindings are unavailable")
        checks.append(("PASS", "PySlang", engine.version()))
    except Exception as error:  # noqa: BLE001 - one doctor check cannot stop the rest.
        checks.append(("FAIL", "PySlang", _message(error)))
        required_runtime_failed = True

    try:
        verilator = VerilatorEngine()
        if verilator.available():
            checks.append(("PASS", "Verilator", verilator.version()))
        else:
            checks.append(("WARN", "Verilator", "optional executable not found"))
    except Exception as error:  # noqa: BLE001 - optional tool check remains isolated.
        checks.append(("WARN", "Verilator", _message(error)))

    root: Path | None = None
    project_config: ProjectConfig | None = None
    try:
        root = _project_root(path)
        project_config = load_config(root)
        checks.append(("PASS", "Configuration", "valid"))
    except Exception as error:  # noqa: BLE001 - invalid configuration is reported as data.
        checks.append(("FAIL", "Configuration", _message(error)))
        invalid_project = True

    try:
        if root is not None and project_config is not None:
            output = resolve_output_root(root, project_config.scan.output_dir)
            existing = _nearest_existing_parent(output)
            if output.exists() and not output.is_dir():
                checks.append(("FAIL", "Output directory", f"not a directory: {output}"))
                invalid_project = True
            elif _is_writable_directory(existing):
                checks.append(("PASS", "Output directory", f"writable parent: {existing}"))
            else:
                checks.append(("FAIL", "Output directory", f"not writable: {existing}"))
                invalid_project = True
        else:
            checks.append(("FAIL", "Output directory", "configuration unavailable"))
    except Exception as error:  # noqa: BLE001 - output probe failure is isolated.
        checks.append(("FAIL", "Output directory", _message(error)))
        invalid_project = True

    try:
        container = shutil.which("docker") or shutil.which("podman")
        checks.append(
            (
                "PASS" if container else "WARN",
                "Container",
                container or "Docker/Podman not found (optional)",
            )
        )
    except Exception as error:  # noqa: BLE001 - optional probe failure is isolated.
        checks.append(("WARN", "Container", _message(error)))

    try:
        console = _console()
        console.print(Text("RTL Lens doctor", style="bold"))
        for status, label, detail in checks:
            console.print(_check_line(status, label, detail))
    except Exception as error:  # noqa: BLE001 - presentation failure is bounded.
        _error("Doctor presentation failure: ", error)
        raise typer.Exit(3 if invalid_project else 2) from None
    if invalid_project:
        raise typer.Exit(3)
    if required_runtime_failed:
        raise typer.Exit(2)


def _render_locale(
    title: str,
    explanation: LocalizedExplanation,
    labels: tuple[str, str, str],
) -> None:
    console = _console()
    console.print(Text(title, style="bold"))
    console.print(Text(explanation.title, style="bold"))
    for label, value in zip(
        labels, (explanation.cause, explanation.risk, explanation.fix), strict=True
    ):
        line = Text(f"{label}: ", style="bold")
        line.append(value)
        console.print(line)


@app.command()
def explain(rule: Annotated[str, typer.Argument(help="Canonical rule ID.")]) -> None:
    """Show the reviewed English and Simplified Chinese explanation for a rule."""
    try:
        store = KnowledgeStore.load_default()
        english = store.get(rule, "en")
        chinese = store.get(rule, "zh-CN")
    except Exception as error:  # noqa: BLE001 - packaged-resource failure is runtime exit 2.
        _error("Explanation store failure: ", error)
        raise typer.Exit(2) from None
    if english is None or chinese is None:
        _error("Unknown rule: ", rule)
        raise typer.Exit(3)
    try:
        _render_locale("English", english, ("Cause", "Risk", "Fix"))
        _render_locale("简体中文", chinese, ("原因", "风险", "修复"))
    except Exception as error:  # noqa: BLE001 - presentation failure is runtime exit 2.
        _error("Explanation presentation failure: ", error)
        raise typer.Exit(2) from None


@app.command()
def version() -> None:
    """Print RTL Lens and supported analyzer versions."""
    try:
        installed_version = package_version()
        console = _console()
        console.print(Text(f"RTL Lens {installed_version}"))
        console.print(Text(f"PySlang compatibility: {PYSLANG_COMPATIBILITY}"))
        console.print(Text(f"Verilator compatibility: {VERILATOR_COMPATIBILITY}"))
    except Exception as error:  # noqa: BLE001 - metadata/UI failures are runtime exit 2.
        _error("Version lookup failure: ", error)
        raise typer.Exit(2) from None


if __name__ == "__main__":
    app()
