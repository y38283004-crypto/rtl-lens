"""Real-process tests for safe, bounded Verilator execution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from rtl_lens.engines import verilator_engine
from rtl_lens.engines.verilator_engine import VerilatorEngine
from rtl_lens.models.engine import EngineRequest, EngineState
from rtl_lens.models.project import ResolvedProject

FAKE_VERILATOR = Path(__file__).parents[1] / "fixtures" / "bin" / "fake_verilator.py"
NATIVE_FAKE_SOURCE = Path(__file__).parents[1] / "fixtures" / "bin" / "fake_verilator.c"


def _project(root: Path, *, mode: str = "ok") -> ResolvedProject:
    source = root / "rtl" / "top.sv"
    source.parent.mkdir(parents=True)
    source.write_text("module top; endmodule\n", encoding="utf-8")
    return ResolvedProject(
        root=root,
        sources=(Path("rtl/top.sv"),),
        defines=(f"RTL_LENS_MODE={mode}",),
    )


def _run(root: Path, *, mode: str = "ok", timeout: int = 3):
    return VerilatorEngine(FAKE_VERILATOR).run(
        EngineRequest(project=_project(root, mode=mode), timeout_seconds=timeout)
    )


def _compile_native_fake(output_directory: Path) -> Path:
    compiler = next(
        (
            resolved
            for name in ("cc", "gcc", "clang")
            if (resolved := shutil.which(name)) is not None
        ),
        None,
    )
    if compiler is None:
        pytest.skip("native-wrapper executable-path proof requires a compatible cc, gcc, or clang")
    executable = output_directory / ("fake-verilator.exe" if os.name == "nt" else "fake-verilator")
    completed = subprocess.run(
        [compiler, str(NATIVE_FAKE_SOURCE), "-o", str(executable)],
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return executable


def test_native_fake_skips_without_a_compatible_compiler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A platform lacking cc, gcc, and clang must skip only the native-wrapper proof."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(
        pytest.skip.Exception,
        match="cc, gcc, or clang",
    ):
        _compile_native_fake(tmp_path)


def test_real_fake_preserves_malicious_arguments_without_a_shell(tmp_path: Path) -> None:
    """Joining argv into a command string would create the sentinel or split malicious values."""
    source = Path("rtl/top file & harmless.sv")
    include_dir = Path("include dir & harmless")
    define = "ATTACK=1; touch shell-sentinel & type nul > shell-sentinel"
    (tmp_path / source).parent.mkdir(parents=True)
    (tmp_path / source).write_text("module top; endmodule\n", encoding="utf-8")
    (tmp_path / include_dir).mkdir()
    project = ResolvedProject(
        root=tmp_path,
        sources=(source,),
        include_dirs=(include_dir,),
        defines=(define,),
    )

    result = VerilatorEngine(FAKE_VERILATOR).run(EngineRequest(project=project, timeout_seconds=3))

    assert result.state is EngineState.COMPLETED
    assert not (tmp_path / "shell-sentinel").exists()
    received = json.loads(result.diagnostics[0].message)
    sarif_index = received.index("--diagnostics-sarif-output")
    assert received[:sarif_index] == ["--lint-only"]
    assert received[sarif_index + 2 :] == [
        "--Wall",
        f"-D{define}",
        f"-I{include_dir.as_posix()}",
        source.as_posix(),
    ]


def test_real_fake_prefixes_option_like_root_source_names(tmp_path: Path) -> None:
    """Bare '-' or '+' source basenames must never be reinterpreted as Verilator options."""
    sources = (Path("-name.sv"), Path("+name.sv"))
    define = "ATTACK=1; touch option-sentinel & type nul > option-sentinel"
    for source in sources:
        (tmp_path / source).write_text("module top; endmodule\n", encoding="utf-8")
    project = ResolvedProject(root=tmp_path, sources=sources, defines=(define,))

    result = VerilatorEngine(FAKE_VERILATOR).run(EngineRequest(project=project, timeout_seconds=3))

    assert result.state is EngineState.COMPLETED
    assert not (tmp_path / "option-sentinel").exists()
    received = json.loads(result.diagnostics[0].message)
    assert received[-2:] == ["./+name.sv", "./-name.sv"]
    assert result.diagnostics[0].location.path == "-name.sv"


def test_relative_native_executable_path_survives_project_cwd_change(tmp_path: Path) -> None:
    """Resolving a path-like executable under the project cwd must not lose the wrapper."""
    with TemporaryDirectory(prefix=".rtl-lens-native-test-", dir=Path.cwd()) as native_dir:
        wrapper_directory = Path(native_dir) / "native tools"
        wrapper_directory.mkdir()
        wrapper = _compile_native_fake(wrapper_directory)
        relative_wrapper = Path(os.path.relpath(wrapper, Path.cwd()))
        project_root = tmp_path / "project"
        source = project_root / "rtl" / "top.sv"
        source.parent.mkdir(parents=True)
        source.write_text("module top; endmodule\n", encoding="utf-8")
        engine = VerilatorEngine(relative_wrapper)
        project = ResolvedProject(root=project_root, sources=(Path("rtl/top.sv"),))

        assert engine.available() is True
        assert engine.version() == "5.040-native-fake"
        result = engine.run(EngineRequest(project=project, timeout_seconds=3))

        assert result.state is EngineState.COMPLETED
        assert result.version == "5.040-native-fake"
        assert result.diagnostics[0].message == "native wrapper invoked"


def test_verilator_uses_deterministic_define_include_and_source_order(tmp_path: Path) -> None:
    """Forwarding model insertion order must not make invocation or reports nondeterministic."""
    sources = (Path("z file.sv"), Path("a&safe.v"))
    includes = (Path("z inc"), Path("a&inc"))
    for source in sources:
        (tmp_path / source).write_text("module top; endmodule\n", encoding="utf-8")
    for include in includes:
        (tmp_path / include).mkdir()
    project = ResolvedProject(
        root=tmp_path,
        sources=sources,
        include_dirs=includes,
        defines=("ZED=1", "ALPHA=2"),
    )

    result = VerilatorEngine(FAKE_VERILATOR).run(EngineRequest(project=project, timeout_seconds=3))

    assert result.state is EngineState.COMPLETED
    received = json.loads(result.diagnostics[0].message)
    assert received[-6:] == [
        "-DALPHA=2",
        "-DZED=1",
        "-Ia&inc",
        "-Iz inc",
        "a&safe.v",
        "z file.sv",
    ]


def test_subprocess_configuration_supplements_real_shell_safety_proof(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Changing cwd, timeout, or shell flags must be visible at the adapter boundary."""
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def capture(arguments: list[str], **kwargs: Any) -> verilator_engine._ProcessResult:
        calls.append((arguments, kwargs))
        sarif_path = Path(arguments[arguments.index("--diagnostics-sarif-output") + 1])
        payload = json.loads(
            (
                Path(__file__).parents[1] / "fixtures" / "sarif" / "verilator-width.sarif.json"
            ).read_text(encoding="utf-8")
        )
        sarif_path.write_text(json.dumps(payload), encoding="utf-8")
        return verilator_engine._ProcessResult(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(verilator_engine, "_run_bounded_process", capture)
    engine = VerilatorEngine(Path("verilator"))
    monkeypatch.setattr(engine, "version", lambda: "5.040")

    result = engine.run(EngineRequest(project=_project(tmp_path), timeout_seconds=3))

    assert result.state is EngineState.COMPLETED
    _, options = calls[0]
    assert options["cwd"] == tmp_path.resolve()
    assert options["timeout_seconds"] == 3
    assert options["stdout_limit"] == 1024 * 1024
    assert options["stderr_limit"] == 1024 * 1024


def test_nonzero_exit_with_valid_sarif_is_completed_analysis(tmp_path: Path) -> None:
    """Treating lint findings as process failure must discard valid structured diagnostics."""
    result = _run(tmp_path, mode="nonzero")

    assert result.state is EngineState.COMPLETED
    assert result.failure is None
    assert result.diagnostics[0].original_code == "WIDTH"


@pytest.mark.parametrize(
    ("mode", "kind"),
    [
        ("missing-sarif", "missing_sarif"),
        ("malformed-sarif", "malformed_sarif"),
        ("stdout-overflow", "stdout_limit_exceeded"),
        ("stderr-overflow", "stderr_limit_exceeded"),
        ("sarif-overflow", "sarif_limit_exceeded"),
    ],
)
def test_invalid_or_oversized_adapter_output_is_a_bounded_failure(
    tmp_path: Path, mode: str, kind: str
) -> None:
    """Accepting missing, malformed, or unbounded output must breach the adapter contract."""
    result = _run(tmp_path, mode=mode)

    assert result.state is EngineState.FAILED
    assert result.diagnostics == ()
    assert result.failure is not None
    assert result.failure.kind == kind
    assert 0 < len(result.failure.message) <= 500


def test_timeout_is_a_bounded_failed_run(tmp_path: Path) -> None:
    """Leaking TimeoutExpired or waiting indefinitely must violate the engine boundary."""
    result = _run(tmp_path, mode="timeout", timeout=1)

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "timeout"
    assert len(result.failure.message) <= 500


def test_missing_executable_is_a_structured_failed_run(tmp_path: Path) -> None:
    """Leaking FileNotFoundError must violate the common adapter failure contract."""
    engine = VerilatorEngine(tmp_path / "missing-verilator")

    result = engine.run(EngineRequest(project=_project(tmp_path / "project"), timeout_seconds=3))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "FileNotFoundError"
    assert len(result.failure.message) <= 500


def test_verilator_version_and_availability_use_real_fake_executable() -> None:
    """Breaking script-prefix resolution must make the cross-platform fake unusable."""
    engine = VerilatorEngine(FAKE_VERILATOR)

    assert engine.available() is True
    assert engine.version() == "5.040-fake"


def test_verilator_rejects_include_directory_that_escapes_root(tmp_path: Path) -> None:
    """Forwarding an unchecked include directory must expose files outside the project."""
    source = tmp_path / "project" / "top.sv"
    source.parent.mkdir()
    source.write_text("module top; endmodule\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    project = ResolvedProject(
        root=source.parent,
        sources=(Path("top.sv"),),
        include_dirs=(outside,),
    )

    result = VerilatorEngine(FAKE_VERILATOR).run(EngineRequest(project=project, timeout_seconds=3))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "path_escape"
