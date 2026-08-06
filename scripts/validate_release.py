"""Fail-fast validation for a Python NESTRA release checkout."""

from __future__ import annotations

import compileall
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, validate

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 development environments
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nestra.ml.logistic import LearnedRouterModel  # noqa: E402
from nestra.version import VERSION  # noqa: E402


def main() -> int:
    errors: list[str] = []
    required = [
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "CHANGELOG.md",
        "pyproject.toml",
        "src/nestra/__init__.py",
        "src/nestra/runtime.py",
        "src/nestra/ml/logistic.py",
        "src/nestra/models/micro-safety-demo.json",
        "schemas/project-input.schema.json",
        "schemas/nestra-config.schema.json",
        "schemas/query-result.schema.json",
        "schemas/router-model.schema.json",
        "models/router/micro-safety-demo.json",
        "docs/learned-router.md",
        "examples/sdk/learned_router.py",
        "openapi/nestra.openapi.yaml",
        ".github/workflows/ci.yml",
    ]
    for relative in required:
        if not (ROOT / relative).is_file():
            errors.append(f"missing release file: {relative}")
    try:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if project["version"] != VERSION:
            errors.append(f"package version {project['version']} does not match runtime {VERSION}")
        if project.get("name") != "nestra-ai":
            errors.append("distribution name must be nestra-ai")
        if project.get("scripts") != {"nestra": "nestra.cli:main"}:
            errors.append("the only public CLI entry point must be nestra")
    except Exception as error:
        errors.append(f"invalid pyproject.toml: {error}")
    parsed_schemas: dict[str, dict] = {}
    for path in (ROOT / "schemas").glob("*.json"):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            parsed_schemas[path.name] = schema
        except Exception as error:
            errors.append(f"invalid JSON {path.name}: {error}")
    try:
        repository_model = json.loads(
            (ROOT / "models/router/micro-safety-demo.json").read_text(encoding="utf-8")
        )
        packaged_model = json.loads(
            (ROOT / "src/nestra/models/micro-safety-demo.json").read_text(encoding="utf-8")
        )
        LearnedRouterModel(repository_model)
        validate(repository_model, parsed_schemas["router-model.schema.json"])
        if repository_model != packaged_model:
            errors.append("repository and packaged router artifacts differ")
        if repository_model.get("status") != "experimental":
            errors.append("bundled router must remain experimental")
        if repository_model.get("provenance", {}).get("containsRawText") is not False:
            errors.append("router artifact must declare containsRawText=false")
        if repository_model.get("provenance", {}).get("implementation") != "python":
            errors.append("router artifact must be trained by Python")
    except Exception as error:
        errors.append(f"invalid learned-router artifact: {error}")
    openapi = (ROOT / "openapi/nestra.openapi.yaml").read_text(encoding="utf-8")
    if f"\n  version: {VERSION}\n" not in openapi:
        errors.append("OpenAPI version does not match Python package")
    try:
        parsed_openapi = yaml.safe_load(openapi)
        if parsed_openapi.get("openapi") != "3.1.0":
            errors.append("OpenAPI document must use version 3.1.0")
        for relative in (
            "compose.yaml",
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            ".github/dependabot.yml",
        ):
            yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
    except Exception as error:
        errors.append(f"invalid YAML contract: {error}")
    if not compileall.compile_dir(ROOT / "src/nestra", quiet=1, force=True):
        errors.append("Python source compilation failed")
    cross_import = re.compile(r"(?:from|import)\s+.*agent[_-]hive", re.I)
    for path in (ROOT / "src/nestra").rglob("*.py"):
        if cross_import.search(path.read_text(encoding="utf-8")):
            errors.append(f"cross-project import found: {path.relative_to(ROOT)}")
    source_roots = [
        ROOT / name for name in ("src", "tests", "scripts", "examples", "benchmarks", "bin")
    ]
    legacy = [
        path
        for source_root in source_roots
        if source_root.exists()
        for suffix in ("*.mjs", "*.cjs", "*.js")
        for path in source_root.rglob(suffix)
    ]
    if legacy:
        errors.append(
            "JavaScript files remain after the Python migration: "
            + ", ".join(str(path.relative_to(ROOT)) for path in legacy[:5])
        )
    if (ROOT / "package.json").exists() or (ROOT / "package-lock.json").exists():
        errors.append("Node package metadata remains after the Python migration")
    legacy_brand = re.compile(
        "|".join(
            (
                "agent" + "_nest",
                "agent" + "-nest",
                "Agent" + " Nest",
                "Agent" + "Nest",
                "NEST" + "_API_TOKEN",
                "NEST" + "_STORE_DIR",
            )
        )
    )
    brand_roots = [
        ROOT / name
        for name in (
            ".github",
            "benchmarks",
            "docs",
            "examples",
            "models",
            "openapi",
            "schemas",
            "scripts",
            "src",
            "tests",
        )
    ]
    brand_files = [
        ROOT / name
        for name in (
            ".dockerignore",
            ".env.example",
            ".gitignore",
            "AGENTS.md",
            "CHANGELOG.md",
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.md",
            "Dockerfile",
            "README.he.md",
            "README.md",
            "ROADMAP.md",
            "SECURITY.md",
            "SUPPORT.md",
            "compose.yaml",
            "pyproject.toml",
        )
    ]
    brand_files.extend(
        path
        for brand_root in brand_roots
        if brand_root.exists()
        for path in brand_root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".md", ".py", ".toml", ".yaml", ".yml"}
    )
    for path in brand_files:
        if legacy_brand.search(path.read_text(encoding="utf-8")):
            errors.append(f"legacy predecessor branding found: {path.relative_to(ROOT)}")
    if errors:
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"NESTRA {VERSION} Python release validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
