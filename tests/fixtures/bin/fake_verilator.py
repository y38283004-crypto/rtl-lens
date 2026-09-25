"""Cross-platform fake executable used to exercise the real subprocess boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from threading import Thread
from time import sleep

STDIO_OVERFLOW_SIZE = 1024 * 1024 + 1
SARIF_OVERFLOW_SIZE = 16 * 1024 * 1024 + 1


def _mode(arguments: list[str]) -> str:
    prefix = "-DRTL_LENS_MODE="
    return next(
        (argument.removeprefix(prefix) for argument in arguments if argument.startswith(prefix)),
        "ok",
    )


def _sarif_payload(arguments: list[str], source: str) -> dict[str, object]:
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Verilator", "version": "5.040-fake"}},
                "results": [
                    {
                        "ruleId": "WIDTH",
                        "level": "warning",
                        "message": {"text": json.dumps(arguments)},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": source},
                                    "region": {"startLine": 1, "startColumn": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }


def main() -> int:
    arguments = sys.argv[1:]
    if arguments == ["--version"]:
        print("Verilator 5.040-fake")
        return 0

    mode = _mode(arguments)
    if mode == "timeout":
        sleep(5)
    if mode == "stdout-overflow":
        sys.stdout.write("x" * STDIO_OVERFLOW_SIZE)
    if mode == "stderr-overflow":
        sys.stderr.write("x" * STDIO_OVERFLOW_SIZE)
    if mode == "stdout-overflow-hang":
        sys.stdout.buffer.write(b"x" * STDIO_OVERFLOW_SIZE)
        sys.stdout.buffer.flush()
        sleep(5)
    if mode == "stderr-overflow-hang":
        sys.stderr.buffer.write(b"x" * STDIO_OVERFLOW_SIZE)
        sys.stderr.buffer.flush()
        sleep(5)
    if mode == "dual-pipe-pressure":
        chunk = b"x" * (512 * 1024)
        threads = (
            Thread(target=lambda: (sys.stdout.buffer.write(chunk), sys.stdout.buffer.flush())),
            Thread(target=lambda: (sys.stderr.buffer.write(chunk), sys.stderr.buffer.flush())),
        )
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    try:
        output_index = arguments.index("--diagnostics-sarif-output") + 1
        sarif_path = Path(arguments[output_index])
    except (ValueError, IndexError):
        return 64
    if mode == "missing-sarif":
        return 1
    if mode == "malformed-sarif":
        sarif_path.write_text("{", encoding="utf-8")
        return 1
    if mode == "sarif-overflow":
        sarif_path.write_bytes(b"x" * SARIF_OVERFLOW_SIZE)
        return 1

    source_arguments = [
        argument
        for argument in arguments
        if argument.endswith((".sv", ".v")) and not argument.startswith(("-D", "-I"))
    ]
    if any(argument.startswith(("-", "+")) for argument in source_arguments):
        return 65
    source = source_arguments[-1] if source_arguments else "top.sv"
    sarif_path.write_text(
        json.dumps(_sarif_payload(arguments, source)),
        encoding="utf-8",
    )
    return 1 if mode == "nonzero" else 0


if __name__ == "__main__":
    raise SystemExit(main())
