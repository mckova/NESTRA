"""Command-line interface installed as ``nestra``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, TextIO

from .providers import create_openai_responses_provider
from .runtime import NestraRuntime
from .server import create_nestra_server
from .storage import FileProjectStore
from .version import VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nestra", description="Evidence-aware routing between retrieval and guarded LLM tiers."
    )
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    _common(ingest, project=True)
    ingest.add_argument("--file", required=True)
    ingest.add_argument("--trust", choices=("trusted", "untrusted"))
    route = sub.add_parser("route")
    _common(route, project=True, question=True)
    query = sub.add_parser("query")
    _common(query, project=True, question=True)
    query.add_argument("--endpoint")
    query.add_argument("--retries", type=int)
    inspect = sub.add_parser("inspect")
    _common(inspect, project=True)
    listing = sub.add_parser("list")
    _common(listing)
    serve = sub.add_parser("serve")
    _common(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--token")
    serve.add_argument("--allow-unauthenticated", action="store_true")
    return parser


def run_cli(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    runtime: NestraRuntime | None = None,
) -> int:
    env = env or os.environ
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
        store = (
            runtime.store
            if runtime
            else FileProjectStore(args.store or env.get("NESTRA_STORE_DIR") or ".nestra")
        )
        router_model = None
        if getattr(args, "router_model", None):
            router_model = json.loads(Path(args.router_model).read_text(encoding="utf-8"))
        nestra = runtime or NestraRuntime(store=store, router_model=router_model)
        if args.command == "ingest":
            parsed = json.loads(Path(args.file).read_text(encoding="utf-8"))
            documents = parsed if isinstance(parsed, list) else parsed.get("documents")
            if args.trust:
                documents = [{**row, "trust": row.get("trust", args.trust)} for row in documents]
            result = nestra.ingest(
                project_id=args.project, documents=documents, default_trust=args.trust
            )
            _output(stdout, {"projectId": result["projectId"], "stats": result["stats"]})
            return 0
        if args.command == "list":
            _output(stdout, {"projects": store.list()})
            return 0
        if args.command == "inspect":
            _output(stdout, store.inspect(args.project))
            return 0
        if args.command in {"route", "query"}:
            input_ = {"project_id": args.project, "question": args.question, "mode": args.mode}
            if args.command == "route":
                _output(stdout, nestra.plan(**input_))
                return 0
            plan = nestra.plan(**input_)
            if plan["providerRequired"] and nestra.provider is None:
                nestra.provider = create_openai_responses_provider(
                    api_key=env.get("OPENAI_API_KEY") or env.get("OPENAI_KEY"),
                    endpoint=args.endpoint or "https://api.openai.com/v1/responses",
                    max_retries=args.retries if args.retries is not None else 1,
                )
            _output(stdout, nestra.query(**input_, actor_id="cli"))
            return 0
        if args.command == "serve":
            if nestra.provider is None and (env.get("OPENAI_API_KEY") or env.get("OPENAI_KEY")):
                nestra.provider = create_openai_responses_provider(
                    api_key=env.get("OPENAI_API_KEY") or env.get("OPENAI_KEY")
                )
            token = env.get("NESTRA_API_TOKEN") or args.token
            server = create_nestra_server(
                runtime=nestra,
                host=args.host,
                port=args.port,
                token=token,
                allow_unauthenticated=args.allow_unauthenticated,
            )
            stdout.write(f"NESTRA {VERSION} listening on http://{args.host}:{server.server_port}\n")
            stdout.flush()
            server.serve_forever()
            return 0
        return 2
    except SystemExit as error:
        return int(error.code or 0)
    except Exception as error:
        stderr.write(f"Error: {error}\n")
        return 1


def main() -> None:
    raise SystemExit(run_cli())


def _common(
    parser: argparse.ArgumentParser, *, project: bool = False, question: bool = False
) -> None:
    parser.add_argument("--store")
    parser.add_argument("--router-model", dest="router_model")
    if project:
        parser.add_argument("--project", required=True)
    if question:
        parser.add_argument("--question", required=True)
        parser.add_argument("--mode", choices=("auto", "retrieval"), default="auto")


def _output(stream: TextIO, value: Any) -> None:
    stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
