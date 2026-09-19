#!/usr/bin/env python3
"""静态守卫 Sidebar 的 bfcache 与短页面约束。"""

from pathlib import Path

SOURCE = Path("src/components/Sidebar.astro").read_text(encoding="utf-8")

assert "pagehide" not in SOURCE, "pagehide cleanup breaks bfcache-restored listeners"
assert (
    "documentBottom > window.innerHeight + 1" in SOURCE
), "bottom activation must require a genuinely scrollable document"
assert "requestAnimationFrame(updateActive)" in SOURCE
assert "if (frame === null)" in SOURCE

print("Sidebar static guards passed")
