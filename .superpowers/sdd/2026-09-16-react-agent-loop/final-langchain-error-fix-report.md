# I4 LangChain MCP error handling final report

## Result

- Added one strict `decode_mcp_tool_result` helper in `mcp_adapter.py`; LangChain and LangGraph now decode the same exact `{"is_error": bool, "content": ...}` JSON envelope.
- The adapter still prefers MCP `structuredContent` and falls back to serialized MCP `content`, while preserving `isError` as `is_error`.
- LangChain now returns explicit `ToolMessage(status="error")` values for MCP `is_error=true` and malformed envelopes instead of treating their JSON strings as successful tool output.
- Read-only MCP error envelopes are controlled observations and are not retried. Transport/runtime exceptions remain eligible for the existing bounded read-only retry policy.
- Side-effect MCP error envelopes are never retried. Their ledger entry finishes as `failed`; when the terminal write cannot be confirmed durable, the model receives `side_effect_status_uncertain` with status `failed`.
- Malformed envelopes fail closed. A read-only call becomes `malformed_mcp_result`; a side-effect call follows the controlled uncertain/failed path and is not redispatched.
- Updated the chapter to distinguish returned MCP errors from retryable Python exceptions.

## TDD evidence

The new LangChain regression tests were run before implementation and failed for the intended reasons:

- read error envelope produced `ToolMessage.status == "success"`;
- write error envelope produced ledger status `executed`;
- malformed envelope produced `ToolMessage.status == "success"`;
- durability-uncertain error completion preserved `executed` instead of `failed`.

After the implementation, the four focused regressions passed.

Coverage added for:

- read `is_error=true` model observation and no retry;
- write `is_error=true` failed ledger status, explicit error observation, and no retry;
- failed ledger finish with uncertain durability;
- malformed read envelope fail-closed behavior.

## Verification

- Focused LangChain suite: `56 passed`.
- Focused MCP adapter/server and parity suites: `29 passed`.
- Focused LangGraph suite: `47 passed`.
- Combined final focused LangChain/MCP/LangGraph/parity run: `132 passed`.
- Full non-Docker suite: `386 passed, 3 deselected`.
- Astro build: `12 page(s) built`, exit 0.
- IDE diagnostics: no linter errors.
- `git diff --check`: passed.

## Residual concern

The decoder intentionally accepts only the current two-field adapter envelope. If the adapter contract later adds metadata, both consumers will fail closed until the decoder and tests are deliberately updated.

No credentials, certificates, or cryptographic algorithms were added or changed. The security rules were applied by keeping tool output untrusted, validating the envelope at the host boundary, and avoiding any secret-bearing test data.
