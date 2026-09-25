"""Keep the documented public onboarding contract executable."""

from __future__ import annotations

import hashlib
import re
import struct
import tomllib
from pathlib import Path
from urllib.parse import unquote

import pytest
import yaml
from typer.testing import CliRunner

from rtl_lens.cli import app
from rtl_lens.config import load_config
from rtl_lens.models.project import ProjectConfig

ROOT = Path(__file__).resolve().parents[2]
USER_DOCS = (
    Path("README.md"),
    Path("README.zh-CN.md"),
    Path("docs/getting-started.md"),
    Path("docs/configuration.md"),
    Path("docs/architecture.md"),
    Path("docs/privacy.md"),
)
CORE_COMMANDS = (
    "rtl-lens init .",
    "rtl-lens doctor .",
    "rtl-lens scan .",
    "rtl-lens explain width-mismatch",
    "rtl-lens version",
)
CONFIG_START = "<!-- rtl-lens-config-example:start -->"
CONFIG_END = "<!-- rtl-lens-config-example:end -->"
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
GOVERNANCE_FILES = (
    Path("CONTRIBUTING.md"),
    Path("SECURITY.md"),
    Path("CODE_OF_CONDUCT.md"),
    Path("CHANGELOG.md"),
    Path("LICENSE"),
    Path("docs/maintenance.md"),
    Path(".github/ISSUE_TEMPLATE/bug.yml"),
    Path(".github/ISSUE_TEMPLATE/feature.yml"),
    Path(".github/PULL_REQUEST_TEMPLATE.md"),
)
APACHE_LICENSE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
# SHA-256 of https://www.apache.org/licenses/LICENSE-2.0.txt, including its leading LF.


def _read(relative_path: Path) -> str:
    path = ROOT / relative_path
    assert path.is_file(), f"missing user documentation: {relative_path}"
    return path.read_text(encoding="utf-8")


def _config_block(document: str) -> str:
    start = document.index(CONFIG_START) + len(CONFIG_START)
    end = document.index(CONFIG_END, start)
    return document[start:end].strip() + "\n"


def _relative_targets(relative_path: Path, document: str) -> list[Path]:
    targets: list[Path] = []
    for match in MARKDOWN_LINK.finditer(document):
        target = match.group(1).split(maxsplit=1)[0].strip("<>")
        target = target.split("#", maxsplit=1)[0]
        if not target or target.startswith(("http:", "https:", "mailto:")):
            continue
        targets.append((ROOT / relative_path.parent / unquote(target)).resolve())
    return targets


def test_user_documentation_exists_and_has_bilingual_navigation() -> None:
    """Catch a public README or required bilingual section being removed."""
    documents = {path: _read(path) for path in USER_DOCS}
    english = documents[Path("README.md")]
    chinese = documents[Path("README.zh-CN.md")]

    for heading in ("Installation", "Quick start", "Privacy", "Limitations", "Contributing"):
        assert f"## {heading}" in english
    for heading in ("安装", "快速开始", "隐私", "局限", "参与贡献"):
        assert f"## {heading}" in chinese
    assert re.search(r"(?i)canonical user-documentation source of truth", english)
    assert "[简体中文说明](README.zh-CN.md)" in english
    assert "[English README](README.md)" in chinese
    assert re.search(r"(?i)(canonical|source of truth)", chinese)


def test_readmes_publish_the_same_validated_configuration_and_command_contract(
    tmp_path: Path,
) -> None:
    """Catch a command/configuration that readers cannot run from either README."""
    english = _read(Path("README.md"))
    chinese = _read(Path("README.zh-CN.md"))
    for document in (english, chinese):
        for command in CORE_COMMANDS:
            assert command in document
        for public_fact in (
            "Python >=3.11,<3.14",
            "PySlang >=11,<12",
            "Verilator >=5.040",
            "Apache-2.0",
        ):
            assert public_fact in document
        assert re.search(r"(?i)(development|pre-release|开发|预发布)", document)

    block = _config_block(english)
    assert block == _config_block(chinese)
    config_path = tmp_path / ".rtl-lens.toml"
    config_path.write_text(block, encoding="utf-8")
    loaded = load_config(tmp_path, config_path=config_path)
    assert isinstance(loaded, ProjectConfig)

    project = tmp_path / "readme-project"
    source = project / "src"
    source.mkdir(parents=True)
    (source / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    config_path = project / ".rtl-lens.toml"
    config_path.write_text(block, encoding="utf-8")

    runner = CliRunner()
    scanned = runner.invoke(app, ["scan", str(project), "--config", str(config_path)])
    assert scanned.exit_code == 0, scanned.output
    assert (project / ".rtl-lens" / "report.json").is_file()
    assert (project / ".rtl-lens" / "report.html").is_file()


def test_documented_commands_run_against_a_real_minimal_project(tmp_path: Path) -> None:
    """Catch documentation drift from the actual Typer application contract."""
    project = tmp_path / "project"
    source = project / "src"
    source.mkdir(parents=True)
    (source / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    runner = CliRunner()

    initialized = runner.invoke(app, ["init", str(project)])
    assert initialized.exit_code == 0, initialized.output
    assert runner.invoke(app, ["doctor", str(project)]).exit_code == 0
    scanned = runner.invoke(app, ["scan", str(project)])
    assert scanned.exit_code == 0, scanned.output
    assert (project / ".rtl-lens" / "report.json").is_file()
    assert (project / ".rtl-lens" / "report.html").is_file()
    assert runner.invoke(app, ["explain", "width-mismatch"]).exit_code == 0
    assert runner.invoke(app, ["version"]).exit_code == 0


def test_relative_documentation_links_resolve_inside_the_repository() -> None:
    """Catch navigation links that lead readers outside a checked-out repository."""
    documents = list(USER_DOCS)
    for optional in (Path("CONTRIBUTING.md"), Path("docs/maintenance.md")):
        if (ROOT / optional).is_file():
            documents.append(optional)
    for document_path in documents:
        for target in _relative_targets(document_path, _read(document_path)):
            assert target.is_relative_to(ROOT), f"link escapes repository: {target}"
            assert target.exists(), f"broken link in {document_path}: {target.relative_to(ROOT)}"


@pytest.mark.parametrize("path", GOVERNANCE_FILES, ids=str)
def test_governance_file_exists(path: Path) -> None:
    """Identify each missing public governance entry independently."""
    assert (ROOT / path).is_file(), f"missing governance file: {path}"


def test_license_is_canonical_and_readmes_link_governance() -> None:
    """Keep licensing bytes and bilingual governance navigation intact."""
    assert _read(Path(".gitattributes")).strip() == "LICENSE text eol=lf"
    license_bytes = (ROOT / "LICENSE").read_bytes()
    assert hashlib.sha256(license_bytes).hexdigest() == APACHE_LICENSE_SHA256
    with (ROOT / "pyproject.toml").open("rb") as metadata_file:
        metadata = tomllib.load(metadata_file)
    assert metadata["project"]["license"] == "Apache-2.0"
    for readme in (Path("README.md"), Path("README.zh-CN.md")):
        targets = _relative_targets(readme, _read(readme))
        for target in (
            "CONTRIBUTING.md",
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
            "docs/maintenance.md",
        ):
            assert (ROOT / target).resolve() in targets


def test_conduct_and_security_policies_route_private_reports_without_fabrication() -> None:
    """Keep sensitive reports out of public issues without inventing contact promises."""
    conduct = _read(Path("CODE_OF_CONDUCT.md"))
    assert "Contributor Covenant 3.0" in conduct
    assert "https://www.contributor-covenant.org/version/3/0/code_of_conduct/" in conduct
    assert "CC BY-SA 4.0" in conduct
    assert "Security → Advisories → Report a vulnerability" in conduct
    assert "[Conduct]" in conduct
    assert not re.search(
        r"(?i)(?:customization note|\[(?:insert|contact|note:)[^]]*\]|TODO|TBD|FIXME)",
        conduct,
    )
    for heading in (
        "Encouraged Behaviors",
        "Restricted Behaviors",
        "Addressing and Repairing Harm",
    ):
        assert f"## {heading}" in conduct
    for rung in (
        "Warning",
        "Temporarily Limited Activities",
        "Temporary Suspension",
        "Permanent Ban",
    ):
        assert rung in conduct

    security = " ".join(_read(Path("SECURITY.md")).replace("*", "").split())
    assert re.search(r"(?i)do not.*public issue", security)
    assert "Security → Advisories → Report a vulnerability" in security
    assert re.search(r"(?i)no stable version.*supported", security)
    for detail in ("version", "reproduction", "impact", "sanitized"):
        assert detail in security.lower()
    assert not re.search(r"(?i)[\w.+-]+@[\w.-]+|\bSLA\b|respond within|response within", security)
    assert "no response-time guarantee" in security


def test_contributing_and_maintenance_policies_have_operational_honest_guidance() -> None:
    """Require a reproducible contribution path and realistic maintenance commitments."""
    contributing = _read(Path("CONTRIBUTING.md"))
    for requirement in (
        "setup",
        "TDD",
        "focused",
        "full",
        "YAML",
        "failing",
        "fixed",
        "tools/generate_rule_docs.py --check",
        "unknown diagnostic",
        "translation",
        "Security → Advisories → Report a vulnerability",
        "Apache-2.0",
    ):
        assert requirement.lower() in contributing.lower()

    maintenance = " ".join(_read(Path("docs/maintenance.md")).split())
    for requirement in (
        "weekly",
        "monthly",
        "30 days",
        "60 days",
        "90 days",
        "bug",
        "enhancement",
        "documentation",
        "no guarantee",
        "stars",
    ):
        assert requirement.lower() in maintenance.lower()
    assert (
        "maintainership does not buy, exchange, bot, coerce, or otherwise manipulate stars."
        in maintenance.lower()
    )
    assert (
        "adoption evidence, reproducible successful scans, issue quality, and useful contributions "
        "are more meaningful than star counts." in maintenance.lower()
    )


def test_issue_forms_are_safe_actionable_and_schema_valid() -> None:
    """Keep public forms useful while excluding confidential-reporting fields."""
    forms: dict[str, dict[str, object]] = {}
    for name in ("bug", "feature"):
        with (ROOT / ".github" / "ISSUE_TEMPLATE" / f"{name}.yml").open(
            encoding="utf-8"
        ) as form_file:
            form = yaml.safe_load(form_file)
        assert isinstance(form, dict)
        forms[name] = form

    assert {path.name for path in (ROOT / ".github/ISSUE_TEMPLATE").iterdir()} == {
        "bug.yml",
        "feature.yml",
    }
    for name, form in forms.items():
        assert isinstance(form.get("name"), str) and form["name"]
        assert isinstance(form.get("description"), str) and form["description"]
        assert not {"labels", "assignees"}.intersection(form)
        body = form.get("body")
        assert isinstance(body, list)
        assert all(isinstance(field, dict) for field in body)
        field_ids = [field.get("id") for field in body if isinstance(field, dict) and "id" in field]
        assert all(
            isinstance(field_id, str) and re.fullmatch(r"[\w-]+", field_id)
            for field_id in field_ids
        )
        assert len(field_ids) == len(set(field_ids))
        checkboxes = []
        for field in body:
            assert field.get("type") in {"markdown", "input", "textarea", "checkboxes"}
            attributes = field.get("attributes")
            assert isinstance(attributes, dict)
            if field["type"] == "markdown":
                assert isinstance(attributes.get("value"), str)
                continue
            assert field.get("id") and isinstance(attributes.get("label"), str)
            assert not re.search(r"(?i)secret|contact|email|upload|attachment", field["id"])
            if field["type"] == "checkboxes":
                checkboxes.extend(attributes.get("options", []))
            else:
                assert field.get("validations", {}).get("required") is True
        assert any(
            option.get("required") is True and "code of conduct" in option.get("label", "").lower()
            for option in checkboxes
        )
        text = yaml.safe_dump(form, allow_unicode=True).lower()
        assert "security → advisories → report a vulnerability" in text
        assert "do not report security vulnerabilities or conduct concerns here" in text
        assert "sanitized" in text
        assert "ip address" in text
        assert "secret" in text
        assert "email" not in {field_id.lower() for field_id in field_ids}
        assert "contact" not in {field_id.lower() for field_id in field_ids}

    bug = forms["bug"]
    feature = forms["feature"]
    bug_ids = {field["id"] for field in bug["body"] if isinstance(field, dict) and "id" in field}
    feature_ids = {
        field["id"] for field in feature["body"] if isinstance(field, dict) and "id" in field
    }
    assert {
        "version",
        "operating_system",
        "python_version",
        "engine_versions",
        "minimal_rtl",
        "config",
        "command",
        "expected",
        "actual",
        "reproduction",
    } <= bug_ids
    assert {"problem", "desired_result", "alternatives", "evidence", "contribute"} <= feature_ids


def test_pr_template_and_changelog_set_an_unreleased_public_contract() -> None:
    """Require reviewers to consider public interfaces and prevent invented releases."""
    template = _read(Path(".github/PULL_REQUEST_TEMPLATE.md")).lower()
    for requirement in (
        "scope",
        "linked issue",
        "tests",
        "results",
        "public interface",
        "report schema",
        "docs",
        "i18n",
        "security",
        "privacy",
        "dependencies",
        "licensing",
        "checklist",
    ):
        assert requirement in template

    changelog = _read(Path("CHANGELOG.md"))
    assert "# Changelog" in changelog
    assert "Keep a Changelog" in changelog
    assert re.findall(r"(?m)^## (.+)$", changelog) == ["[Unreleased]"]
    assert set(re.findall(r"(?m)^### (.+)$", changelog)) <= {
        "Added",
        "Changed",
        "Deprecated",
        "Removed",
        "Fixed",
        "Security",
    }


def test_report_preview_is_a_linked_large_png_without_publication_claims() -> None:
    """Catch a placeholder screenshot or unsupported public-service promise."""
    preview = ROOT / "docs" / "assets" / "report-preview.png"
    payload = preview.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", payload[16:24])
    assert width >= 1000
    assert height >= 600
    assert "docs/assets/report-preview.png" in _read(Path("README.md"))

    all_docs = "\n".join(_read(path) for path in USER_DOCS)
    prohibited = (
        r"(?i)pip install rtl-lens(?![^\n]*(?:unavailable|not available|不可用|未提供))",
        r"(?i)(?:stable|stable release|正式稳定版)\s*0\.2",
        r"(?i)(?:guaranteed|保证).{0,40}(?:stars|performance|星标|性能)",
        r"(?i)(?<!not )(?:sends?|collects?|includes?)\s+telemetry",
        r"(?i)(?:uploads?\s+(?:source|reports?)\s+to|uses?)\s+(?:the\s+)?cloud",
    )
    for pattern in prohibited:
        assert not re.search(pattern, all_docs), pattern
