from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

from agent_core import approval_cli
from agent_core.checkpoints import JsonCheckpointStore
from agent_core.contracts import RunOutcome
from agent_core.mcp_adapter import MCPToolClient
from agent_core.openai_loop import OpenAIReActAgent
from agent_core.sandbox import DockerMCPTransport


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the hand-written OpenAI Responses API ReAct loop."
    )
    approval_cli.add_decision_arguments(parser)
    approval_cli.add_sandbox_arguments(parser, __file__)
    parser.add_argument("--runs", type=Path, default=Path(".runs"))
    parser.add_argument("--model", default="gpt-5")
    return parser


async def _run(args: argparse.Namespace) -> RunOutcome:
    edited = approval_cli.validated_decision(args)
    parameters = DockerMCPTransport().parameters(args.workspace, args.skills)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            checkpoints = JsonCheckpointStore(args.runs)
            agent = OpenAIReActAgent(
                client=AsyncOpenAI(),
                mcp=MCPToolClient(session),
                checkpoints=checkpoints,
                model=args.model,
            )
            if args.resume is None:
                return await agent.start(args.user_input)

            state = checkpoints.load(args.resume)
            if state is None or state.pending_approval is None:
                raise ValueError("resume run has no pending approval")
            return await agent.resume(
                args.resume,
                approval_cli.resume_decision(
                    args,
                    state.pending_approval.digest,
                    edited,
                ),
            )


def main() -> None:
    args = _parser().parse_args()
    print(approval_cli.outcome_json(asyncio.run(_run(args))))


if __name__ == "__main__":
    main()
