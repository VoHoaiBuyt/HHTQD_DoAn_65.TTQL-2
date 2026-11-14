"""Capture the Streamlit UI with headless Chrome over the DevTools protocol.

Requires a running Streamlit server (default http://localhost:8501, override
with the first argument). Writes
screenshots to `reports/ui/` for the Word/markdown report. This is a local
verification helper, not part of the model pipeline.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "ui"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
APP_URL = "http://localhost:8501"
DEBUG_PORT = 9333


def _read_targets() -> list[dict]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=1
    ) as response:
        return json.load(response)


async def _wait_for_target() -> str:
    for _ in range(100):
        try:
            targets = await asyncio.to_thread(_read_targets)
            for target in targets:
                if target.get("type") == "page":
                    return target["webSocketDebuggerUrl"]
        except (OSError, ValueError):
            pass
        await asyncio.sleep(0.2)
    raise RuntimeError("Chrome DevTools target không sẵn sàng")


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profile_dir = tempfile.mkdtemp(prefix="dss-chrome-")
    process = await asyncio.create_subprocess_exec(
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={profile_dir}",
        "--window-size=1440,1200",
        "about:blank",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        websocket_url = await _wait_for_target()
        async with websockets.connect(
            websocket_url, max_size=80_000_000
        ) as websocket:
            counter = itertools.count(1)

            async def send(method: str, params: dict | None = None) -> dict:
                message_id = next(counter)
                await websocket.send(
                    json.dumps(
                        {"id": message_id, "method": method, "params": params or {}}
                    )
                )
                while True:
                    reply = json.loads(await websocket.recv())
                    if reply.get("id") == message_id:
                        if "error" in reply:
                            raise RuntimeError(reply["error"])
                        return reply.get("result", {})

            async def evaluate(expression: str) -> object:
                result = await send(
                    "Runtime.evaluate",
                    {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": True,
                    },
                )
                return result.get("result", {}).get("value")

            async def shot(name: str) -> None:
                result = await send("Page.captureScreenshot", {"format": "png"})
                path = OUTPUT_DIR / name
                path.write_bytes(base64.b64decode(result["data"]))
                print(f"wrote {path}")

            await send("Page.enable")
            await send("Runtime.enable")
            await send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": 1440,
                    "height": 1200,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            await send("Page.navigate", {"url": APP_URL})
            for _ in range(80):
                ready = await evaluate(
                    "document.querySelectorAll('[role=\"tab\"]').length"
                )
                if ready and int(ready) >= 4:
                    break
                await asyncio.sleep(0.25)
            await asyncio.sleep(1.0)

            async def click_text(selector: str, text: str) -> bool:
                expression = f"""
                (() => {{
                    const nodes = [...document.querySelectorAll({json.dumps(selector)})];
                    const target = nodes.find(n => n.innerText.trim().includes({json.dumps(text)}));
                    if (!target) return false;
                    target.click();
                    return true;
                }})()
                """
                return bool(await evaluate(expression))

            async def scroll_main(position: int) -> None:
                await evaluate(
                    "(() => { const m = document.querySelector('main.stMain');"
                    f"if (m) m.scrollTop = {position}; return true; }})()"
                )
                await asyncio.sleep(0.4)

            async def click_cdp(
                selector: str, text: str | None = None
            ) -> bool:
                expression = f"""
                (() => {{
                    const nodes = [...document.querySelectorAll({json.dumps(selector)})];
                    const target = {json.dumps(text)} === null
                        ? nodes[0]
                        : nodes.find(n => n.innerText.trim() === {json.dumps(text)});
                    if (!target) return null;
                    target.scrollIntoView({{block: "center", inline: "center"}});
                    const rect = target.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return null;
                    return {{x: rect.x + rect.width / 2, y: rect.y + rect.height / 2}};
                }})()
                """
                point = await evaluate(expression)
                if not point:
                    return False
                x, y = point["x"], point["y"]
                base = {"x": x, "y": y, "button": "left", "clickCount": 1}
                await send("Input.dispatchMouseEvent", {"type": "mouseMoved", **base})
                await send("Input.dispatchMouseEvent", {"type": "mousePressed", **base})
                await send("Input.dispatchMouseEvent", {"type": "mouseReleased", **base})
                await asyncio.sleep(0.2)
                return True

            async def combobox_value() -> str:
                expression = """
                (() => {{
                    const node = document.querySelector('[role="combobox"]');
                    if (!node) return "";
                    if (node.tagName === "INPUT") return (node.value || "").trim();
                    const input = node.querySelector("input");
                    return ((node.innerText || "").trim() || (input ? input.value : ""));
                }})()
                """
                return str(await evaluate(expression) or "")

            async def select_persona(label: str) -> bool:
                for _ in range(4):
                    if (await combobox_value()) == label:
                        return True
                    if not await click_cdp('[role="combobox"]'):
                        await asyncio.sleep(0.5)
                        continue
                    await asyncio.sleep(0.6)
                    if not await click_cdp('[role="option"]', label):
                        await send(
                            "Input.dispatchKeyEvent",
                            {"type": "keyDown", "key": "Escape", "code": "Escape"},
                        )
                        await send(
                            "Input.dispatchKeyEvent",
                            {"type": "keyUp", "key": "Escape", "code": "Escape"},
                        )
                        await asyncio.sleep(0.4)
                        continue
                    for _ in range(20):
                        await asyncio.sleep(0.25)
                        if (await combobox_value()) == label:
                            await asyncio.sleep(0.8)
                            return True
                return False

            await shot("01_nhap_ho_so.png")

            await click_text("button", "Đánh giá")
            await asyncio.sleep(2.5)
            await click_text('[role="tab"]', "Đánh giá")
            await asyncio.sleep(1.0)
            await scroll_main(0)
            await shot("02_danh_gia_tong_quan.png")
            await scroll_main(1400)
            await shot("03_danh_gia_shap.png")

            await click_text('[role="tab"]', "Lộ trình")
            await asyncio.sleep(0.8)
            await click_text("button", "Lập & so sánh lộ trình")
            await asyncio.sleep(2.5)
            await scroll_main(300)
            await shot("04_lo_trinh_so_sanh.png")
            await scroll_main(1500)
            await shot("05_lo_trinh_chi_tiet.png")

            await click_text('[role="tab"]', "Mô phỏng")
            await asyncio.sleep(1.0)
            await scroll_main(0)
            await shot("06_mo_phong_tong_quan.png")
            await scroll_main(900)
            await shot("07_mo_phong_theo_sinh_vien.png")

            async def wait_for_persona(label: str, timeout: int = 60) -> bool:
                expression = """
                (() => {
                    const node = document.querySelector('main.stMain');
                    return node ? node.innerText : "";
                })()
                """
                for _ in range(timeout * 4):
                    if f"Mã: {label}" in str(await evaluate(expression) or ""):
                        return True
                    await asyncio.sleep(0.25)
                return False

            for persona in ["S001", "S002", "S003", "S005", "S008"]:
                await click_text('[role="tab"]', "Nhập hồ sơ")
                await asyncio.sleep(0.5)
                selected = await select_persona(persona)
                await click_text("button", "Đánh giá")
                await asyncio.sleep(1.0)
                await click_text('[role="tab"]', "Đánh giá")
                fresh = await wait_for_persona(persona)
                await scroll_main(0)
                await shot(f"08_danh_gia_{persona}.png")
                if not (selected and fresh):
                    print(f"warning: stale capture for {persona}")

            await click_text('[role="tab"]', "Nhập hồ sơ")
            await asyncio.sleep(0.5)
            if not await select_persona("S003"):
                print("warning: could not select S003 for best-effort")
            await click_text("button", "Đánh giá")
            await asyncio.sleep(2.0)
            await click_text('[role="tab"]', "Lộ trình")
            await asyncio.sleep(0.8)
            await click_text("button", "Lập & so sánh lộ trình")
            await asyncio.sleep(2.5)
            await scroll_main(1600)
            await shot("09_s003_best_effort.png")
    finally:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=10)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        APP_URL = sys.argv[1]
    asyncio.run(main())
