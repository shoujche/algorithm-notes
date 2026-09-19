from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from agent_core.contracts import RunOutcome, to_json_value
from agent_core.langgraph_loop import LangGraphReActAgent
from agent_core.mcp_adapter import MCPToolClient
from agent_core.openai_loop import ResumeDecision
from agent_core.sandbox import DockerMCPTransport


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the explicit LangGraph ReAct Agent."
    )
    parser.add_argument("user_input", nargs="?")
    parser.add_argument("--resume", metavar="RUN_ID")
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", metavar="REASON")
    parser.add_argument("--edit-arguments", metavar="JSON")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--skills",
        type=Path,
        default=Path(__file__).with_name("skills"),
    )
    parser.add_argument(
        "--checkpoints",
        type=Path,
        default=Path(".runs") / "langgraph.json",
    )
    parser.add_argument("--model", default="openai:gpt-5")
    return parser


async def _run(args: argparse.Namespace) -> RunOutcome:
    from langchain.chat_models import init_chat_model

    parameters = DockerMCPTransport().parameters(args.workspace, args.skills)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            agent = LangGraphReActAgent(
                model=init_chat_model(args.model),
                mcp=MCPToolClient(session),
                checkpoint_path=args.checkpoints,
            )
            if args.resume is None:
                if not args.user_input:
                    raise ValueError("user_input is required for a new run")
                return await agent.start(args.user_input)

            pending = await agent.pending_approval(args.resume)
            if pending is None:
                raise ValueError("resume run has no pending approval")
            if not args.approve and args.reject is None:
                raise ValueError("--approve or --reject is required with --resume")
            edited = (
                _json_object(args.edit_arguments)
                if args.edit_arguments is not None
                else None
            )
            return await agent.resume(
                args.resume,
                ResumeDecision(
                    action="approve" if args.approve else "reject",
                    digest=pending.digest,
                    reason=args.reject or "",
                    arguments=edited,
                ),
            )


def _json_object(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("edited arguments must be a JSON object")
    return value


def _outcome_json(outcome: RunOutcome) -> str:
    payload: dict[str, Any] = {
        "run_id": outcome.run_id,
        "final_text": outcome.final_text,
    }
    if outcome.pending_approval is not None:
        request = outcome.pending_approval
        payload["pending_approval"] = {
            "tool": request.proposal.tool_name,
            "arguments": to_json_value(request.proposal.arguments),
            "risk": request.risk.value,
            "preview": request.preview,
            "digest": request.digest,
        }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def main() -> None:
    args = _parser().parse_args()
    print(_outcome_json(asyncio.run(_run(args))))


if __name__ == "__main__":
    main()
