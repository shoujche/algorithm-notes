// ReAct Agent 章节代码清单：全部通过 Vite 的 `?raw` 读入 src/code/agent/react-agent-loop/ 下的
// 真实源文件（就是 pytest 跑的那几个文件），页面上看到的每一行都能在仓库里找到。
// 页面只展示其中的片段时，用下面的 block() / excerpt() 按「行」精确切出连续区间；
// 切不中就直接抛错让 `npm run build` 失败，避免页面上出现手写的示意代码。

import type { CodeVariant } from './linked-list-code';

// —— 公共内核 ——
import contractsSource from '../code/agent/react-agent-loop/agent_core/contracts.py?raw';
import policySource from '../code/agent/react-agent-loop/agent_core/policy.py?raw';
import checkpointsSource from '../code/agent/react-agent-loop/agent_core/checkpoints.py?raw';
import skillsSource from '../code/agent/react-agent-loop/agent_core/skills.py?raw';
import mcpAdapterSource from '../code/agent/react-agent-loop/agent_core/mcp_adapter.py?raw';
import sandboxSource from '../code/agent/react-agent-loop/agent_core/sandbox.py?raw';
import workspaceSource from '../code/agent/react-agent-loop/agent_core/workspace.py?raw';

// —— 三种编排层 ——
import openaiLoopSource from '../code/agent/react-agent-loop/agent_core/openai_loop.py?raw';
import langchainLoopSource from '../code/agent/react-agent-loop/agent_core/langchain_loop.py?raw';
import langgraphLoopSource from '../code/agent/react-agent-loop/agent_core/langgraph_loop.py?raw';

// —— 三个可执行入口 ——
import pureOpenaiSource from '../code/agent/react-agent-loop/pure_openai.py?raw';
import langchainAgentSource from '../code/agent/react-agent-loop/langchain_agent.py?raw';
import langgraphAgentSource from '../code/agent/react-agent-loop/langgraph_agent.py?raw';

// —— MCP Server / 统一 CLI / 沙盒镜像 / Skill ——
import mcpServerSource from '../code/agent/react-agent-loop/mcp_server.py?raw';
import cliSource from '../code/agent/react-agent-loop/cli.py?raw';
import dockerfileSource from '../code/agent/react-agent-loop/sandbox/Dockerfile?raw';
import skillDocSource from '../code/agent/react-agent-loop/skills/workspace-helper/SKILL.md?raw';

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/agent/react-agent-loop';

/** 缩进层级（Python 以缩进划分块，直接拿来当切片依据） */
const indentOf = (line: string): number => line.length - line.trimStart().length;

/**
 * 按 Python 缩进切出一个完整的 def / class 块（含紧邻其上的装饰器）。
 * header 必须与源文件中的某一行完全相同，否则抛错终止构建。
 */
function block(source: string, header: string): string {
  const lines = source.split('\n');
  const found = lines.indexOf(header);
  if (found < 0) throw new Error(`源码块起点未命中：${JSON.stringify(header)}`);

  const indent = indentOf(header);
  let start = found;
  while (start > 0) {
    const previous = lines[start - 1];
    if (!previous.trim().startsWith('@') || indentOf(previous) !== indent) break;
    start -= 1;
  }

  let end = lines.length;
  for (let i = found + 1; i < lines.length; i += 1) {
    if (!lines[i].trim()) continue;
    if (indentOf(lines[i]) <= indent) {
      end = i;
      break;
    }
  }
  while (end > found + 1 && !lines[end - 1].trim()) end -= 1;
  return lines.slice(start, end).join('\n');
}

/** 切出 [firstLine, lastLine] 之间的连续区间，两端都必须与源文件整行完全相同。 */
function excerpt(source: string, firstLine: string, lastLine: string): string {
  const lines = source.split('\n');
  const start = lines.indexOf(firstLine);
  if (start < 0) throw new Error(`源码片段起点未命中：${JSON.stringify(firstLine)}`);
  const end = lines.indexOf(lastLine, start + 1);
  if (end < 0) throw new Error(`源码片段终点未命中：${JSON.stringify(lastLine)}`);
  return lines.slice(start, end + 1).join('\n');
}

// ===== 01 心智模型：整份数据契约 =====
export const contractsFull = contractsSource;

// ===== 02 状态与退出条件 =====
/** 手写循环的主体：一次模型调用 → 有 function_call 就继续，没有就是最终回答 */
export const openaiContinue = block(openaiLoopSource, '    async def _continue(');
/** 检查点落盘：先查秘密、再原子替换、权限 0600 */
export const checkpointSave = block(
  checkpointsSource,
  '    def save(self, state: RunState) -> None:',
);

// ===== 03 Skills 渐进式披露 =====
export const skillDoc = skillDocSource;
/** 扫描可信 Skill 根目录：只读 frontmatter 的 name / description，正文按需再读 */
export const skillDiscovery = block(
  skillsSource,
  'def _discover_skills(root: Path) -> dict[str, tuple[SkillSummary, Path]]:',
);

// ===== 04 MCP 工具发现与调用 =====
/** 六个工具的严格 JSON Schema 与 annotations */
export const mcpToolDefinitions = block(
  mcpServerSource,
  'def _tool_definitions(max_content_bytes: int) -> list[types.Tool]:',
);
/** 本地 stdio MCP → Responses function tools 的适配层 */
export const mcpListFunctionTools = block(
  mcpAdapterSource,
  '    async def list_function_tools(self) -> list[dict[str, Any]]:',
);

// ===== 05 Docker 信任边界 =====
export const dockerfile = dockerfileSource;
/** docker run 的全部隔离开关 */
export const sandboxArgv = block(
  sandboxSource,
  '    def build_argv(self, workspace: Path, skills_dir: Path) -> list[str]:',
);
/** 逐级 openat + O_NOFOLLOW：软链接无法把路径带出 /workspace */
export const workspaceDirFd = block(
  workspaceSource,
  '    def _open_directory_fd(self, parts: tuple[str, ...]) -> int:',
);
/** argv 必须是字符串数组且首元素在允许清单内，永不拼 shell 字符串 */
export const workspaceArgvCheck = block(
  workspaceSource,
  '    def _validate_argv(self, argv: Sequence[str]) -> list[str]:',
);

export const sandboxVariants: CodeVariant[] = [
  { lang: 'docker', label: '容器镜像', file: 'sandbox/Dockerfile', code: dockerfile },
  { lang: 'python', label: '启动参数', file: 'agent_core/sandbox.py', code: sandboxArgv },
  { lang: 'python', label: '路径校验', file: 'agent_core/workspace.py', code: workspaceDirFd },
  { lang: 'python', label: '命令校验', file: 'agent_core/workspace.py', code: workspaceArgvCheck },
];

// ===== 06 纯 OpenAI SDK 手写循环 =====
/** 解析 → 分类 → 暂停 → 执行 → 按原 call_id 回填的一整轮 */
export const openaiProcessCalls = block(openaiLoopSource, '    async def _process_calls(');
/** 没有框架帮忙时，参数校验要自己对着 strict schema 做 */
export const openaiValidateArguments = block(
  openaiLoopSource,
  '    def _validate_tool_arguments(',
);

// ===== 07 LangChain 高层 Agent =====
/** import 段本身就是证据：create_agent 的运行时跑在 LangGraph 上 */
export const langchainImports = excerpt(
  langchainLoopSource,
  'from langchain.agents import create_agent',
  'from langgraph.types import Command, interrupt',
);
/** 四个 middleware + create_agent + LangGraph checkpointer */
export const langchainCreateAgent = excerpt(
  langchainLoopSource,
  '        middleware = [',
  '        )',
);

// ===== 08 LangGraph 显式状态图 =====
/** 节点、条件边与 checkpointer 的显式装配 */
export const langgraphBuildGraph = block(langgraphLoopSource, '    async def build_graph(self) -> Any:');
/** interrupt() 之前不做任何副作用，恢复时从节点开头重放也安全 */
export const langgraphRequestApproval = block(
  langgraphLoopSource,
  '    async def _request_approval(self, state: GraphState) -> dict[str, Any]:',
);

// ===== 09 暂停、审批与恢复 =====
export const policyFull = policySource;
/** 三个实现共用的 CLI 语义：子命令 + --resume + --approve/--reject/--edit-json */
export const cliParser = block(cliSource, 'def build_parser() -> argparse.ArgumentParser:');
/** 恢复时校验 digest、重新校验被编辑的参数，再继续执行 */
export const openaiResume = block(openaiLoopSource, '    async def _resume_claimed(');

// ===== 10 三版对比：三个 entrypoint 的接线 =====
const entrypointRun = 'async def _run(args: argparse.Namespace) -> RunOutcome:';

export const orchestrationVariants: CodeVariant[] = [
  {
    lang: 'python',
    label: 'OpenAI SDK',
    file: 'pure_openai.py',
    code: block(pureOpenaiSource, entrypointRun),
  },
  {
    lang: 'python',
    label: 'LangChain',
    file: 'langchain_agent.py',
    code: block(langchainAgentSource, entrypointRun),
  },
  {
    lang: 'python',
    label: 'LangGraph',
    file: 'langgraph_agent.py',
    code: block(langgraphAgentSource, entrypointRun),
  },
];
