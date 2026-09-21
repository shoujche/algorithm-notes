from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from agent_core import approval_cli
from agent_core.contracts import RunOutcome
from agent_core.langchain_loop import LangChainReActAgent
from agent_core.mcp_adapter import MCPToolClient
from agent_core.sandbox import DockerMCPTransport


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the high-level LangChain ReAct Agent."
    )
    approval_cli.add_decision_arguments(parser)
    approval_cli.add_sandbox_arguments(parser, __file__)
    parser.add_argument(
        "--checkpoints",
        type=Path,
        default=Path(".runs") / "langchain.json",
    )
    parser.add_argument("--model", default="openai:gpt-5")
    return parser


async def _run(args: argparse.Namespace) -> RunOutcome:
    edited = approval_cli.validated_decision(args)

    from langchain.chat_models import init_chat_model

    parameters = DockerMCPTransport().parameters(args.workspace, args.skills)
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            agent = LangChainReActAgent(
                model=init_chat_model(args.model),
                mcp=MCPToolClient(session),
                checkpoint_path=args.checkpoints,
            )
            if args.resume is None:
                return await agent.start(args.user_input)

            pending = await agent.pending_approval(args.resume)
            if pending is None:
                raise ValueError("resume run has no pending approval")
            return await agent.resume(
                args.resume,
                approval_cli.resume_decision(args, pending.digest, edited),
            )


def main() -> None:
    args = _parser().parse_args()
    print(approval_cli.outcome_json(asyncio.run(_run(args))))


if __name__ == "__main__":
    main()
