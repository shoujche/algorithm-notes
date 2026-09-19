#!/usr/bin/env python3
"""用 Chrome DevTools Protocol 验证 A01 侧栏 section 高亮。"""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.request
from typing import Any

import websockets

SECTION_IDS = [
    "mental-model",
    "state",
    "skills",
    "mcp",
    "sandbox",
    "openai-sdk",
    "langchain",
    "langgraph",
    "hitl",
    "comparison",
]


class CDP:
    def __init__(self, websocket: Any) -> None:
        self.websocket = websocket
        self.sequence = 0
        self.console_errors: list[str] = []

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.sequence += 1
        request_id = self.sequence
        await self.websocket.send(
            json.dumps({"id": request_id, "method": method, "params": params or {}})
        )
        while True:
            message = json.loads(await self.websocket.recv())
            event = message.get("method")
            event_params = message.get("params", {})
            if event == "Runtime.exceptionThrown":
                self.console_errors.append("Runtime.exceptionThrown")
            elif (
                event == "Runtime.consoleAPICalled"
                and event_params.get("type") in {"error", "assert"}
            ):
                self.console_errors.append(f"console.{event_params['type']}")
            elif (
                event == "Log.entryAdded"
                and event_params.get("entry", {}).get("level") == "error"
            ):
                self.console_errors.append(event_params["entry"].get("text", "Log error"))
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    async def evaluate(self, expression: str) -> Any:
        result = await self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")


def page_websocket_url(cdp_url: str) -> str:
    with urllib.request.urlopen(f"{cdp_url}/json/list", timeout=3) as response:
        targets = json.load(response)
    return next(target["webSocketDebuggerUrl"] for target in targets if target["type"] == "page")


async def wait_for_active(cdp: CDP, expected: str) -> str | None:
    observed: str | None = None
    for _ in range(40):
        observed = await cdp.evaluate(
            "document.querySelector('aside a[data-nav].active')?.dataset.nav ?? null"
        )
        if observed == expected:
            return observed
        await asyncio.sleep(0.1)
    return observed


async def verify(cdp_url: str, page_url: str) -> None:
    async with websockets.connect(page_websocket_url(cdp_url), max_size=16_000_000) as websocket:
        cdp = CDP(websocket)
        await cdp.call("Page.enable")
        await cdp.call("Runtime.enable")
        await cdp.call("Log.enable")
        await cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 1440,
                "height": 1000,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )
        await cdp.call("Page.navigate", {"url": page_url})
        await asyncio.sleep(0.5)

        anchors = await cdp.evaluate(
            "[...document.querySelectorAll('aside a[data-nav]')].map(link => link.dataset.nav)"
        )
        assert anchors == SECTION_IDS, f"anchor mismatch: {anchors}"

        observed: list[str | None] = []
        for section_id in SECTION_IDS:
            await cdp.evaluate(
                f"document.getElementById({json.dumps(section_id)}).scrollIntoView("
                "{block: 'start', behavior: 'instant'})"
            )
            observed.append(await wait_for_active(cdp, section_id))
        assert observed == SECTION_IDS, f"scroll active mismatch: {observed}"

        await cdp.evaluate("window.scrollTo({top: document.documentElement.scrollHeight})")
        bottom_active = await wait_for_active(cdp, "comparison")
        assert bottom_active == "comparison", f"bottom active mismatch: {bottom_active}"

        await cdp.evaluate(
            "document.querySelector('aside a[data-nav=\"skills\"]').focus()"
        )
        await cdp.call(
            "Input.dispatchKeyEvent",
            {
                "type": "keyDown",
                "key": "Enter",
                "code": "Enter",
                "windowsVirtualKeyCode": 13,
            },
        )
        await cdp.call(
            "Input.dispatchKeyEvent",
            {
                "type": "keyUp",
                "key": "Enter",
                "code": "Enter",
                "windowsVirtualKeyCode": 13,
            },
        )
        keyboard_active = await wait_for_active(cdp, "skills")
        location_hash = await cdp.evaluate("location.hash")
        assert location_hash == "#skills", f"keyboard hash mismatch: {location_hash}"
        assert keyboard_active == "skills", f"keyboard active mismatch: {keyboard_active}"

        await cdp.call("Page.navigate", {"url": "about:blank"})
        await asyncio.sleep(0.1)
        await cdp.call("Page.navigate", {"url": f"{page_url}#langgraph"})
        await cdp.evaluate("document.fonts.ready.then(() => true)")
        await asyncio.sleep(0.1)
        direct_hash_active = await wait_for_active(cdp, "langgraph")
        direct_hash = await cdp.evaluate("location.hash")
        assert direct_hash == "#langgraph", f"direct hash mismatch: {direct_hash}"
        assert direct_hash_active == "langgraph", (
            f"direct hash active mismatch: {direct_hash_active}"
        )

        await cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 2,
                "mobile": True,
            },
        )
        await cdp.evaluate(
            "document.getElementById('hitl').scrollIntoView("
            "{block: 'start', behavior: 'instant'})"
        )
        mobile_active = await wait_for_active(cdp, "hitl")
        overflow = await cdp.evaluate(
            "({scroll: document.documentElement.scrollWidth,"
            "client: document.documentElement.clientWidth,"
            "body: document.body.scrollWidth})"
        )
        assert mobile_active == "hitl", f"resize active mismatch: {mobile_active}"
        assert overflow["scroll"] <= overflow["client"], f"document overflow: {overflow}"
        assert overflow["body"] <= overflow["client"], f"body overflow: {overflow}"

        await cdp.call(
            "Emulation.setEmulatedMedia",
            {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]},
        )
        await asyncio.sleep(0.1)
        reduced_before = await cdp.evaluate(
            "({disabled: document.getElementById('agent-loop-play').disabled,"
            "hintHidden: document.getElementById('agent-loop-hint').hidden,"
            "count: document.getElementById('agent-loop-count').textContent})"
        )
        await asyncio.sleep(2)
        reduced_after = await cdp.evaluate(
            "document.getElementById('agent-loop-count').textContent"
        )
        assert reduced_before == {
            "disabled": True,
            "hintHidden": False,
            "count": "1 / 9",
        }, f"reduced-motion state mismatch: {reduced_before}"
        assert reduced_after == "1 / 9", f"reduced-motion autoplayed: {reduced_after}"
        assert not cdp.console_errors, f"console errors: {cdp.console_errors}"

        print(
            json.dumps(
                {
                    "anchors": anchors,
                    "scrollActive": observed,
                    "bottomActive": bottom_active,
                    "keyboard": {"hash": location_hash, "active": keyboard_active},
                    "directHash": {
                        "hash": direct_hash,
                        "active": direct_hash_active,
                    },
                    "mobile": {"active": mobile_active, "overflow": overflow},
                    "reducedMotion": {
                        "before": reduced_before,
                        "after": reduced_after,
                    },
                    "consoleErrors": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9223")
    parser.add_argument(
        "--page-url",
        default="http://127.0.0.1:4321/algorithm-notes/agent/react-agent-loop",
    )
    args = parser.parse_args()
    asyncio.run(verify(args.cdp_url, args.page_url))


if __name__ == "__main__":
    main()
