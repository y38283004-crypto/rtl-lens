"""Exercise each built distribution as an installed release candidate."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path
from typing import BinaryIO

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMAND_TIMEOUT_SECONDS = 180
FAILURE_OUTPUT_LIMIT = 4_000
RESOURCE_ATTRIBUTES = {
    "action",
    "cite",
    "data",
    "formaction",
    "href",
    "poster",
    "src",
    "srcset",
}
CSS_URL = re.compile(
    r"\burl\s*\(\s*(?:'([^']*)'|\"([^\"]*)\"|([^)]*))\s*\)",
    flags=re.IGNORECASE,
)
CSS_URL_OPEN = re.compile(r"\burl\s*\(", flags=re.IGNORECASE)


class _ReportHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.declarations: list[str] = []
        self.start_tags: list[str] = []
        self.end_tags: list[str] = []
        self.attributes: list[tuple[str, str, str | None]] = []
        self.style_contents: list[str] = []
        self._style_depth = 0

    def handle_decl(self, decl: str) -> None:
        self.declarations.append(decl)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tags.append(tag)
        self.attributes.extend((tag, name, value) for name, value in attrs)
        if tag == "style":
            self._style_depth += 1

    def handle_endtag(self, tag: str) -> None:
        self.end_tags.append(tag)
        if tag == "style":
            self._style_depth = max(0, self._style_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.style_contents.append(data)


def _assert_self_contained_html(html: str) -> None:
    parser = _ReportHTMLParser()
    parser.feed(html)
    parser.close()
    assert parser.declarations == ["doctype html"]
    for required_tag in ("html", "head", "body", "main", "style"):
        assert parser.start_tags.count(required_tag) == 1
        assert parser.end_tags.count(required_tag) == 1
    assert parser.start_tags.count("script") >= 1
    assert parser.start_tags.count("script") == parser.end_tags.count("script")
    resource_references = [
        (tag, name, value)
        for tag, name, value in parser.attributes
        if name.casefold() in RESOURCE_ATTRIBUTES
    ]
    assert resource_references == []
    assert re.search(r"default-src\s+'none'", html)
    assert re.search(r"connect-src\s+'none'", html)
    assert re.search(r"(?i)(?:https?:)?//", html) is None
    styles = "\n".join(parser.style_contents)
    assert re.search(r"(?i)@import\b", styles) is None
    css_urls = list(CSS_URL.finditer(styles))
    assert len(css_urls) == len(CSS_URL_OPEN.findall(styles))
    for match in css_urls:
        value = next(group for group in match.groups() if group is not None).strip()
        assert value.startswith("#") or value.casefold().startswith("data:")


def _bounded_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    def normalized(value: str | bytes | None) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value or ""

    output = f"stdout:\n{normalized(stdout)}\nstderr:\n{normalized(stderr)}"
    if len(output) <= FAILURE_OUTPUT_LIMIT:
        return output
    return f"{output[:FAILURE_OUTPUT_LIMIT]}\n... output truncated ..."


def _drain_pipe(
    stream: BinaryIO,
    retained: bytearray,
    retained_limit: int,
    errors: list[str],
) -> None:
    try:
        while chunk := stream.read(8_192):
            remaining = retained_limit - len(retained)
            if remaining > 0:
                retained.extend(chunk[:remaining])
    except OSError as error:
        errors.append(str(error)[:FAILURE_OUTPUT_LIMIT])
    finally:
        stream.close()


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_bytes = bytearray()
    stderr_bytes = bytearray()
    reader_errors: list[str] = []
    stdout_limit = FAILURE_OUTPUT_LIMIT // 2
    stderr_limit = FAILURE_OUTPUT_LIMIT - stdout_limit
    readers = (
        threading.Thread(
            target=_drain_pipe,
            args=(process.stdout, stdout_bytes, stdout_limit, reader_errors),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_pipe,
            args=(process.stderr, stderr_bytes, stderr_limit, reader_errors),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()

    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait(timeout=10)

    for reader in readers:
        reader.join(timeout=10)
    if any(reader.is_alive() for reader in readers):
        pytest.fail("subprocess output drain did not stop after process exit", pytrace=False)
    if reader_errors:
        pytest.fail(f"subprocess output drain failed: {reader_errors[0]}", pytrace=False)

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if timed_out:
        pytest.fail(
            f"command timed out after {timeout} seconds\n{_bounded_output(stdout, stderr)}",
            pytrace=False,
        )
    if returncode != 0:
        pytest.fail(
            f"command exited {returncode}\n{_bounded_output(stdout, stderr)}",
            pytrace=False,
        )
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def _find_uv() -> str | None:
    discovered = shutil.which("uv")
    if discovered is not None:
        return discovered
    sibling = Path(sys.executable).with_name("uv.exe" if os.name == "nt" else "uv")
    return str(sibling) if sibling.is_file() else None


def test_run_retains_only_bounded_subprocess_output(tmp_path: Path) -> None:
    """Catch subprocess capture that grows with child stdout or stderr volume."""
    emitted_bytes = FAILURE_OUTPUT_LIMIT * 4
    completed = _run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"sys.stdout.buffer.write(b'o' * {emitted_bytes}); "
                f"sys.stderr.buffer.write(b'e' * {emitted_bytes})"
            ),
        ],
        cwd=tmp_path,
        timeout=30,
    )

    retained_bytes = len(completed.stdout.encode()) + len(completed.stderr.encode())
    assert completed.stdout
    assert completed.stderr
    assert retained_bytes <= FAILURE_OUTPUT_LIMIT


@pytest.mark.parametrize(
    "stylesheet",
    (
        '@import "theme.css";',
        ".hero { background-image: url(images/hero.png); }",
    ),
)
def test_html_self_containment_rejects_external_css_references(stylesheet: str) -> None:
    """Catch CSS that can cause a nominally standalone report to fetch a resource."""
    html = f"""<!doctype html>
<html><head>
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; connect-src 'none'">
<style>{stylesheet}</style>
</head><body><main></main><script>void 0</script></body></html>
"""

    with pytest.raises(AssertionError):
        _assert_self_contained_html(html)


def _environment_executables(environment: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        scripts = environment / "Scripts"
        return scripts / "python.exe", scripts / "rtl-lens.exe"
    binaries = environment / "bin"
    return binaries / "python", binaries / "rtl-lens"


@pytest.fixture(scope="module")
def release_artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    uv = _find_uv()
    if uv is None:
        pytest.skip("uv is required for installed release-candidate evidence")

    distribution_directory = tmp_path_factory.mktemp("release-distributions")
    _run(
        [uv, "build", "--no-sources", "--out-dir", str(distribution_directory)],
        cwd=ROOT,
    )
    wheels = tuple(distribution_directory.glob("*.whl"))
    sdists = tuple(distribution_directory.glob("*.tar.gz"))
    assert len(wheels) == 1, f"expected one wheel, found {len(wheels)}"
    assert len(sdists) == 1, f"expected one sdist, found {len(sdists)}"
    return {"wheel": wheels[0], "sdist": sdists[0]}


@pytest.mark.parametrize("artifact_kind", ("wheel", "sdist"))
def test_installed_artifact_scans_clean_redacted_project(
    artifact_kind: str,
    release_artifacts: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Catch a distribution that builds but cannot perform an isolated installed scan."""
    uv = _find_uv()
    assert uv is not None
    artifact = release_artifacts[artifact_kind]
    environment = tmp_path / f"{artifact_kind}-environment"
    project = tmp_path / f"{artifact_kind}-project"
    assert not project.resolve().is_relative_to(ROOT)

    _run([uv, "venv", str(environment), "--python", sys.executable], cwd=tmp_path)
    environment_python, console_script = _environment_executables(environment)
    _run(
        [uv, "pip", "install", "--python", str(environment_python), str(artifact)],
        cwd=tmp_path,
    )
    _run([uv, "pip", "check", "--python", str(environment_python)], cwd=tmp_path)

    imported = _run(
        [
            str(environment_python),
            "-I",
            "-c",
            ("from pathlib import Path; import rtl_lens; print(Path(rtl_lens.__file__).resolve())"),
        ],
        cwd=tmp_path,
        timeout=30,
    )
    imported_path = Path(imported.stdout.strip()).resolve()
    assert imported_path.is_file()
    assert imported_path.is_relative_to(environment.resolve())

    project.mkdir()
    (project / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (project / ".rtl-lens.toml").write_text(
        """[scan]
source_roots = ["."]
engine_mode = "disabled"
redact_sources = true
fail_on = "error"
""",
        encoding="utf-8",
    )
    _run(
        [str(console_script), "scan", ".", "--config", ".rtl-lens.toml"],
        cwd=project,
        timeout=60,
    )

    output = project / ".rtl-lens"
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    metadata = report["metadata"]
    assert metadata["requested_engines"] == ["pyslang"]
    assert metadata["completed_engines"] == ["pyslang"]
    assert metadata["source_count"] == 1
    assert metadata["scan_state"] == "complete"
    assert metadata["redacted"] is True
    assert report["findings"] == []

    html = (output / "report.html").read_text(encoding="utf-8")
    _assert_self_contained_html(html)
