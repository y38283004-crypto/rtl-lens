"""Validated bilingual explanation records."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

RuleId = Literal[
    "width-mismatch",
    "incomplete-assignment",
    "case-incomplete",
    "case-overlap",
    "unused-signal",
    "undriven-signal",
    "multiple-drivers",
    "blocking-in-sequential",
    "always-comb-order",
    "always-never",
    "ascending-range",
    "assignment-in-expression",
    "assignment-to-input",
    "blocking-and-nonblocking",
    "case-with-x",
    "case-x",
    "constant-comparison",
    "combinational-delay",
    "declaration-filename",
    "deprecated-defparam",
    "implicit-net",
    "port-width-mismatch",
    "missing-pin",
    "empty-pin-connection",
    "signedness-mismatch",
    "out-of-range-select",
    "duplicate-definition",
    "undeclared-identifier",
    "unsupported-construct",
    "timescale-mismatch",
]


class LocalizedExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    title: str = Field(min_length=1)
    cause: str = Field(min_length=1)
    risk: str = Field(min_length=1)
    fix: str = Field(min_length=1)


class EngineMapping(BaseModel):
    """A native diagnostic code proven by a packaged example pair."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    engine: Literal["pyslang", "verilator"]
    code: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.()\-]+$")
    verification: Literal["local", "container"]


class ExplanationEntry(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, str_strip_whitespace=True
    )

    schema_version: Literal["1.0"]
    rule_id: RuleId
    severity: Literal["error", "warning", "info"]
    en: LocalizedExplanation
    zh_cn: LocalizedExplanation = Field(alias="zh-CN")
    failing_example: str
    fixed_example: str
    references: tuple[str, ...] = Field(min_length=1)
    review_status: Literal["reviewed"]
    engine_mappings: tuple[EngineMapping, ...] = ()
    mapping_note: str | None = Field(default=None, min_length=12)

    @field_validator("failing_example", "fixed_example")
    @classmethod
    def validate_example_path(cls, value: str, info: ValidationInfo) -> str:
        if "\\" in value:
            raise ValueError("example path must use POSIX separators")
        parts = value.split("/")
        expected_directory = "failing" if info.field_name == "failing_example" else "fixed"
        if len(parts) != 2 or parts[0] != expected_directory:
            raise ValueError(f"example path must be relative beneath {expected_directory}/")
        if any(part in {"", ".", ".."} for part in parts) or not parts[1].endswith(".sv"):
            raise ValueError("example path must name a safe SystemVerilog resource")
        return value

    @model_validator(mode="after")
    def validate_native_mapping_evidence(self) -> ExplanationEntry:
        if not self.engine_mappings and self.mapping_note is None:
            raise ValueError("entries require native mappings or a mapping note")
        pairs = tuple((mapping.engine, mapping.code) for mapping in self.engine_mappings)
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate native mapping")
        if pairs != tuple(sorted(pairs)):
            raise ValueError("native mappings must be sorted by engine and code")
        return self
