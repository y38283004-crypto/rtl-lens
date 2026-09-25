"""Generate or verify the committed bilingual diagnostic guide pages."""

from __future__ import annotations

import argparse
from pathlib import Path

from rtl_lens.knowledge.docs import write_rule_docs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated docs have drifted")
    arguments = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "docs" / "rules"

    try:
        paths = write_rule_docs(output, check=arguments.check)
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")
    action = "verified" if arguments.check else "generated"
    print(f"{action} {len(paths)} rule documentation files in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
