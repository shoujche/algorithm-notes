# ReAct Agent Learning Chapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent Agent section whose first chapter teaches and runs the same sandboxed, approval-aware ReAct loop with the OpenAI SDK, LangChain, and explicit LangGraph.

**Architecture:** The three orchestrators share contracts, policy, checkpoint, Skill metadata, and one stdio MCP server running inside a locked-down Docker container. The Astro page imports the real Python, Docker, and Skill source files with `?raw`, explains each abstraction, and animates pause/resume without executing model code in the browser.

**Tech Stack:** Astro 4, TypeScript, Python 3.12, uv, OpenAI Responses API, LangChain, LangGraph, MCP Python SDK, Docker, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-react-agent-loop-design.md`

## Global Constraints

- Work on `feature/react-agent-loop`; do not push or deploy before user review.
- Never hardcode credentials. Only the host process may read `OPENAI_API_KEY`; never pass it to Docker.
- Use MCP stdio locally; do not expose an unauthenticated HTTP MCP endpoint.
- All model, Skill, MCP, tool, and workspace data is untrusted.
- `write_file` and `run_command` always require approval; approval never bypasses policy.
- Docker runs non-root, without network, with a read-only root filesystem and bounded CPU, memory, PIDs, time, and output.
- File paths must remain inside `/workspace`; reject absolute paths, traversal, and symlink escape.
- Commands use an argv array with `shell=False` and an executable allowlist.
- Tests use fake models by default and must not require an API key.
- Keep source comments and page explanations in Chinese; retain important English terms.

---

### Task 1: Python project, contracts, policy, and checkpoint store

**Files:**
- Create: `src/code/agent/react-agent-loop/pyproject.toml`
- Create: `src/code/agent/react-agent-loop/.env.example`
- Create: `src/code/agent/react-agent-loop/agent_core/__init__.py`
- Create: `src/code/agent/react-agent-loop/agent_core/contracts.py`
- Create: `src/code/agent/react-agent-loop/agent_core/policy.py`
- Create: `src/code/agent/react-agent-loop/agent_core/checkpoints.py`
- Create: `src/code/agent/react-agent-loop/tests/test_policy.py`
- Create: `src/code/agent/react-agent-loop/tests/test_checkpoints.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `Risk`, `ToolProposal`, `ApprovalRequest`, `ToolResult`, `RunState`, and `RunOutcome`.
- Produces: `ToolPolicy.classify(proposal)`, `ToolPolicy.approval_for(proposal)`, and `approval_digest(proposal)`.
- Produces: `JsonCheckpointStore.save/load/delete(run_id)` using atomic replace and mode `0o600`.

- [ ] **Step 1: Add project metadata and failing contract/policy tests**

  Configure Python `>=3.12`, runtime dependencies for OpenAI, LangChain, LangGraph, MCP, and Pydantic, plus pytest/pytest-asyncio dev dependencies. Add tests asserting:

  ```python
  assert ToolPolicy().classify(ToolProposal("c1", "read_file", {"path": "a.py"})) is Risk.READ_ONLY
  assert ToolPolicy().classify(ToolProposal("c2", "write_file", {"path": "a.py", "content": "x"})) is Risk.APPROVAL
  assert approval_digest(proposal) == approval_digest(proposal)
  assert approval_digest(proposal) != approval_digest(changed_proposal)
  ```

- [ ] **Step 2: Run tests and verify collection/import failure**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_policy.py -q`

  Expected: FAIL because `agent_core.contracts` does not exist.

- [ ] **Step 3: Implement immutable contracts and deny-by-default policy**

  Use string enums and frozen dataclasses/Pydantic models. Unknown tools must return `Risk.DENY`; only the four read tools are automatic and only `write_file`/`run_command` are approvable. Hash canonical JSON with SHA-256 for integrity only, not authentication.

- [ ] **Step 4: Add failing checkpoint tests**

  Test round-trip, unknown run ID, invalid run ID characters, atomic replacement, and `0o600` permissions. Store state under a configurable `.runs` directory and never serialize secrets.

- [ ] **Step 5: Implement `JsonCheckpointStore` and run tests**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_policy.py src/code/agent/react-agent-loop/tests/test_checkpoints.py -q`

  Expected: PASS.

- [ ] **Step 6: Ignore runtime artifacts and commit**

  Ignore `src/code/agent/react-agent-loop/.runs/`, `workspace/`, and `.venv/`. Generate and commit `src/code/agent/react-agent-loop/uv.lock`; never commit runtime state.

  Commit: `feat(agent): add shared contracts and approval policy`

---

### Task 2: Progressive Skill discovery

**Files:**
- Create: `src/code/agent/react-agent-loop/agent_core/skills.py`
- Create: `src/code/agent/react-agent-loop/skills/workspace-helper/SKILL.md`
- Create: `src/code/agent/react-agent-loop/tests/test_skills.py`

**Interfaces:**
- Produces: `SkillSummary(name: str, description: str)`.
- Produces: `list_skills(root: Path) -> list[SkillSummary]`.
- Produces: `read_skill(root: Path, name: str, max_bytes: int = 32768) -> str`.

- [ ] **Step 1: Write failing Skill tests**

  Cover valid YAML frontmatter, sorted summaries, missing description, duplicate names, invalid names, oversized files, absolute/traversal names, and symlink escape.

- [ ] **Step 2: Verify tests fail**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_skills.py -q`

  Expected: FAIL because `agent_core.skills` does not exist.

- [ ] **Step 3: Implement strict Skill discovery**

  Parse only `name` and `description`; require names matching `^[a-z0-9][a-z0-9-]{0,63}$`; canonicalize beneath the trusted root; read UTF-8 with a byte cap. Do not execute Skill content or let it change policy.

- [ ] **Step 4: Write the workspace helper Skill**

  Its instructions require inspect-before-edit, explicit write proposals, relevant verification, workspace-only paths, and no credential access or output.

- [ ] **Step 5: Run tests and commit**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_skills.py -q`

  Expected: PASS.

  Commit: `feat(agent): add progressive Skill loading`

---

### Task 3: Sandboxed MCP file and command tools

**Files:**
- Create: `src/code/agent/react-agent-loop/agent_core/workspace.py`
- Create: `src/code/agent/react-agent-loop/mcp_server.py`
- Create: `src/code/agent/react-agent-loop/tests/test_workspace.py`
- Create: `src/code/agent/react-agent-loop/tests/test_mcp_server.py`

**Interfaces:**
- Produces: `WorkspaceTools(root, skills_root, command_allowlist, timeout_seconds, max_output_bytes)`.
- Produces async methods matching MCP tools: `list_files`, `read_file`, `write_file`, `run_command`, `list_skills`, `read_skill`.
- Produces an MCP stdio entrypoint under `if __name__ == "__main__":`.

- [ ] **Step 1: Write failing workspace boundary tests**

  Verify normal reads/writes and rejection of `/etc/passwd`, `../x`, a symlink to an outside file, files over the size cap, invalid UTF-8, disallowed executables, empty argv, invalid cwd, timeout, and output truncation.

- [ ] **Step 2: Verify tests fail**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_workspace.py -q`

  Expected: FAIL because `WorkspaceTools` is missing.

- [ ] **Step 3: Implement workspace tools**

  Use `Path.resolve(strict=False)` plus `relative_to(root.resolve())`, reject symlink components, use `subprocess.run(argv, shell=False, cwd=..., timeout=..., capture_output=True, env=minimal_env)`, and return structured JSON-safe results.

- [ ] **Step 4: Write failing MCP schema tests**

  In-process MCP tests must assert exactly six tool names, strict input schemas, and correct read-only/destructive/idempotent annotations.

- [ ] **Step 5: Expose tools through the current stable MCP API**

  Use current MCP Python SDK documentation, pin the compatible SDK in `uv.lock`, and keep transport at stdio. Log only event type, tool name, call ID, duration, and status.

- [ ] **Step 6: Run focused and full tests, then commit**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_workspace.py src/code/agent/react-agent-loop/tests/test_mcp_server.py -q`

  Expected: PASS.

  Commit: `feat(agent): add secure MCP workspace tools`

---

### Task 4: Docker MCP transport and isolation

**Files:**
- Create: `src/code/agent/react-agent-loop/sandbox/Dockerfile`
- Create: `src/code/agent/react-agent-loop/agent_core/sandbox.py`
- Create: `src/code/agent/react-agent-loop/tests/test_sandbox_config.py`
- Create: `src/code/agent/react-agent-loop/tests/test_sandbox_integration.py`

**Interfaces:**
- Produces: `DockerSandboxConfig.build_argv(workspace, skills_dir) -> list[str]`.
- Produces: `DockerMCPTransport` parameters consumable by the shared MCP client.

- [ ] **Step 1: Write failing Docker argv tests**

  Assert argv contains `--network=none`, `--read-only`, `--cap-drop=ALL`, non-root user, PID/memory/CPU limits, read-write workspace mount, read-only Skill mount, tmpfs `/tmp`, and no host environment or API key forwarding.

- [ ] **Step 2: Verify config tests fail**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_sandbox_config.py -q`

- [ ] **Step 3: Implement the minimal image and safe Docker launcher**

  Use `python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7`, create an unprivileged user, install only locked runtime dependencies, copy server code read-only, and make stdio the container entrypoint.

- [ ] **Step 4: Add opt-in Docker integration tests**

  Mark tests `docker`; verify UID is non-zero, network access fails, `/workspace` persists, host files are invisible, the root filesystem rejects writes, and `OPENAI_API_KEY` is absent.

- [ ] **Step 5: Build and run Docker tests**

  Run:

  ```bash
  docker build -t algorithm-notes-agent-tools src/code/agent/react-agent-loop
  uv run --project src/code/agent/react-agent-loop pytest -m docker src/code/agent/react-agent-loop/tests/test_sandbox_integration.py -q
  ```

  Expected: PASS.

- [ ] **Step 6: Commit**

  Commit: `feat(agent): isolate MCP tools in Docker`

---

### Task 5: Shared MCP adapter and pure OpenAI Responses loop

**Files:**
- Create: `src/code/agent/react-agent-loop/agent_core/mcp_adapter.py`
- Create: `src/code/agent/react-agent-loop/agent_core/openai_loop.py`
- Create: `src/code/agent/react-agent-loop/pure_openai.py`
- Create: `src/code/agent/react-agent-loop/tests/fakes.py`
- Create: `src/code/agent/react-agent-loop/tests/test_openai_loop.py`

**Interfaces:**
- Produces: `MCPToolClient.list_function_tools()` and `MCPToolClient.call(name, arguments)`.
- Produces: `OpenAIReActAgent.start(user_input) -> RunOutcome`.
- Produces: `OpenAIReActAgent.resume(run_id, decision) -> RunOutcome`.

- [ ] **Step 1: Write failing adapter and loop tests**

  Fake MCP and fake Responses clients must cover direct final answer, read-only call, sensitive call returning `PendingApproval`, approve, reject, edited write, unknown tool, malformed JSON arguments, max turns, max tool calls, API retry exhaustion, and duplicate `call_id`.

- [ ] **Step 2: Verify tests fail**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_openai_loop.py -q`

- [ ] **Step 3: Implement MCP-to-Responses schema adaptation**

  Convert MCP input schemas to strict OpenAI function tools. Preserve tool names and descriptions, reject unsupported schemas explicitly, and map results to JSON strings.

- [ ] **Step 4: Implement the hand-written loop**

  Use `client.responses.create`, inspect all output items, preserve response state with `previous_response_id`, submit exact `function_call_output.call_id`, and return rather than execute when approval is required. Never use the OpenAI Agents SDK.

- [ ] **Step 5: Implement resume semantics**

  Load the checkpoint, validate decision and digest, execute at most once, append rejection as a tool result when denied, then continue the same response chain.

- [ ] **Step 6: Run tests and commit**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_openai_loop.py -q`

  Expected: PASS without `OPENAI_API_KEY`.

  Commit: `feat(agent): implement pure OpenAI ReAct loop`

---

### Task 6: LangChain high-level Agent

**Files:**
- Create: `src/code/agent/react-agent-loop/agent_core/langchain_loop.py`
- Create: `src/code/agent/react-agent-loop/langchain_agent.py`
- Create: `src/code/agent/react-agent-loop/tests/test_langchain_loop.py`

**Interfaces:**
- Produces: `LangChainReActAgent.start(user_input) -> RunOutcome`.
- Produces: `LangChainReActAgent.resume(run_id, decision) -> RunOutcome`.

- [ ] **Step 1: Write failing high-level Agent tests**

  Use fake chat model and fake tools. Assert read tools execute automatically, write/command calls interrupt, same thread ID resumes, approve/reject/edit decisions map correctly, and limits/tool errors become controlled outcomes.

- [ ] **Step 2: Verify tests fail**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_langchain_loop.py -q`

- [ ] **Step 3: Implement with documented high-level APIs**

  Use `create_agent`, MCP-adapted tools, `HumanInTheLoopMiddleware`, model/tool call limits, tool error handling, and a persistent checkpointer. Build `interrupt_on` from local policy, not solely MCP annotations.

- [ ] **Step 4: Normalize framework output**

  Convert LangChain interrupts and final messages into the shared `RunOutcome`, keeping approval display identical to the OpenAI version.

- [ ] **Step 5: Run tests and commit**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_langchain_loop.py -q`

  Expected: PASS without network access.

  Commit: `feat(agent): add LangChain Agent comparison`

---

### Task 7: Explicit LangGraph Agent

**Files:**
- Create: `src/code/agent/react-agent-loop/agent_core/langgraph_loop.py`
- Create: `src/code/agent/react-agent-loop/langgraph_agent.py`
- Create: `src/code/agent/react-agent-loop/tests/test_langgraph_loop.py`

**Interfaces:**
- Produces graph nodes `call_model`, `route_response`, `request_approval`, `execute_tools`, `record_observation`, and `finish`.
- Produces: `LangGraphReActAgent.start(user_input) -> RunOutcome`.
- Produces: `LangGraphReActAgent.resume(run_id, decision) -> RunOutcome`.

- [ ] **Step 1: Write failing graph transition tests**

  Assert final-answer routing, read-only routing, approval interrupt payload, stable `thread_id`, resume with `Command`, rejection observation, edited arguments, and exactly-once execution if an interrupted node replays.

- [ ] **Step 2: Verify tests fail**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_langgraph_loop.py -q`

- [ ] **Step 3: Implement typed graph state and nodes**

  Keep `interrupt()` before any side effect in the approval node. Put tool execution in its own node and check the call ledger before dispatch.

- [ ] **Step 4: Add conditional edges and persistence**

  Compile with a persistent checkpointer; use plain input for a new turn and `Command(resume=decision)` only for interrupted runs.

- [ ] **Step 5: Run tests and commit**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_langgraph_loop.py -q`

  Expected: PASS.

  Commit: `feat(agent): add explicit LangGraph Agent`

---

### Task 8: Unified CLI and parity tests

**Files:**
- Create: `src/code/agent/react-agent-loop/cli.py`
- Create: `src/code/agent/react-agent-loop/tests/test_cli.py`
- Create: `src/code/agent/react-agent-loop/tests/test_agent_parity.py`

**Interfaces:**
- Consumes all three `start`/`resume` interfaces.
- Produces CLI subcommands `openai`, `langchain`, and `langgraph`.
- Produces resume flags `--approve`, `--reject REASON`, and `--edit-json FILE`.

- [ ] **Step 1: Write failing CLI tests**

  Assert mutually exclusive decisions, safe run IDs, readable approval previews, paused exit code, final exit code, missing Docker diagnostics, missing API key diagnostics without printing secret values, and no approval bypass.

- [ ] **Step 2: Verify tests fail**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests/test_cli.py -q`

- [ ] **Step 3: Implement CLI dependency wiring**

  Keep imports side-effect free. Instantiate the real OpenAI client and Docker MCP transport only after argument validation. Format output through shared event renderers.

- [ ] **Step 4: Add parity scenarios**

  Feed each implementation equivalent fake model actions and assert the normalized sequence:

  ```text
  user -> skill_list -> skill_read -> file_read -> write_proposed
       -> paused -> approved -> write_result -> final
  ```

- [ ] **Step 5: Run all Python tests and commit**

  Run: `uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests -m "not docker" -q`

  Expected: PASS and no network/API key requirement.

  Commit: `feat(agent): add resumable Agent CLI`

---

### Task 9: Register the Agent category and navigation

**Files:**
- Modify: `src/data/topics.ts`
- Modify: `src/pages/index.astro`
- Modify: `src/components/SiteHeader.astro`
- Modify: `src/components/Sidebar.astro`
- Modify: `src/layouts/BaseLayout.astro`

**Interfaces:**
- Produces: `Category = 'algo' | 'python' | 'agent'`.
- Produces: `categoryConfig` containing label, route prefix, and chapter list derivation.
- Registers the ten page section IDs from the design.

- [ ] **Step 1: Add the typed category registry**

  Register `A01`, derive `agentChapters`, and centralize route prefixes so home cards and sidebar links cannot disagree.

- [ ] **Step 2: Update home, header, sidebar, and metadata**

  Add Agent navigation and active state; update copy to “算法、Python 与 Agent 学习手记”. Preserve responsive behavior.

- [ ] **Step 3: Run Astro build**

  Run: `npm run build`

  Expected: PASS before the page is linked as ready, or fail only for the intentionally missing page; create the page shell immediately if routing validation requires it.

- [ ] **Step 4: Commit**

  Commit: `feat(site): add Agent top-level section`

---

### Task 10: Data manifest, loop animation, and detailed chapter

**Files:**
- Create: `src/data/react-agent-loop-code.ts`
- Create: `src/components/AgentLoopAnim.astro`
- Create: `src/pages/agent/react-agent-loop.astro`
- Modify: `src/styles/global.css` only for genuinely reusable styles

**Interfaces:**
- Manifest exports all displayed source strings and `CODE_DIR`.
- Animation exposes no props and owns unique DOM IDs.
- Page section IDs exactly match `topics.ts`.

- [ ] **Step 1: Build the raw-source manifest**

  Import the three entrypoints, common contracts/policy, Skill, MCP server, Dockerfile, and CLI with `?raw`. Group the three orchestration implementations into `CodeVariant[]` labels `OpenAI SDK`, `LangChain`, and `LangGraph`.

- [ ] **Step 2: Implement the deterministic animation**

  Use the existing frame pattern and safe DOM APIs. Frames cover user, Skill discovery, read, write proposal, checkpoint pause, approval, Docker execution, observation, and final answer. Respect reduced motion by disabling autoplay.

- [ ] **Step 3: Write the chapter**

  Implement all ten sections from the spec. Each section contains a question, mental model, data flow, selected real code, failure modes, memory cue, and interview follow-up. Explain that LangChain `create_agent` uses LangGraph internally and that the pure SDK local MCP path requires schema adaptation.

- [ ] **Step 4: Keep page output safe**

  Do not interpolate model/tool output with `innerHTML`. Static trusted captions may use markup only if hardcoded; otherwise construct nodes with `textContent`.

- [ ] **Step 5: Build and commit**

  Run: `npm run build`

  Expected: PASS.

  Commit: `feat(agent): add ReAct Agent learning chapter`

---

### Task 11: Documentation, complete verification, and review handoff

**Files:**
- Modify: `README.md`
- Modify: `python-interview-design.md`
- Modify: `docs/superpowers/plans/2026-09-16-react-agent-loop.md` to check completed steps

**Interfaces:**
- README links every displayed real source file.
- Historical design reflects the final three-section site architecture.

- [x] **Step 1: Update documentation**

  Add the Agent source directory and file descriptions to README. Update the earlier Python design so it no longer claims Agent is `P08`; keep a note that the final decision moved Agent to an independent section.

- [x] **Step 2: Run formatting/static diagnostics**

  Run:

  ```bash
  uv run --project src/code/agent/react-agent-loop python -m compileall -q src/code/agent/react-agent-loop
  uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests -m "not docker" -q
  npm run build
  git diff --check
  ```

  Expected: every command exits 0.

- [ ] **Step 3: Run Docker verification**

  Run:

  ```bash
  docker build -f src/code/agent/react-agent-loop/sandbox/Dockerfile -t algorithm-notes-agent-tools src/code/agent/react-agent-loop
  uv run --project src/code/agent/react-agent-loop pytest src/code/agent/react-agent-loop/tests -m docker -q
  ```

  Expected: every isolation assertion passes. If Docker daemon is unavailable, report the blocker; do not replace it with host execution.

- [ ] **Step 4: Run browser verification**

  Start `npm run preview`; use Playwright to verify:

  - Agent header and home card route correctly;
  - all ten sidebar anchors exist and highlight;
  - three code tabs switch and link to correct source files;
  - animation reaches every frame and resets;
  - reduced-motion mode does not autoplay;
  - mobile layout has no horizontal overflow;
  - browser console has no errors.

- [x] **Step 5: Security review of deliverables**

  Search tracked changes for credentials, private keys, certificates, unsafe crypto, `shell=True`, unbounded subprocesses, host-path mounts, `innerHTML` with dynamic values, and MCP HTTP exposure. Record certificates/crypto as not applicable if absent.

- [x] **Step 6: Final branch status and review gate**

  Confirm the branch is `feature/react-agent-loop`, working tree is clean, tests are recorded, and no push occurred. Present changed files, screenshots, commands/results, security controls, and known limitations. Wait for explicit user approval before push or deployment.
