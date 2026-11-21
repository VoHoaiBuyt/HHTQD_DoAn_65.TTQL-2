"""Chụp giao diện Streamlit bằng Chrome headless qua DevTools protocol.

Cần một Streamlit server đang chạy (mặc định http://localhost:8501, đổi bằng
tham số đầu tiên). Ảnh được ghi vào `reports/ui/` cho báo cáo. Đây là công cụ
kiểm tra cục bộ, không thuộc pipeline mô hình.

    python scripts/capture_ui_screenshots.py
    python scripts/capture_ui_screenshots.py http://localhost:8517
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
WIDTH = 1440

TAB_DATA = "Dữ liệu đầu vào"
TAB_PLAN = "Lộ trình đề xuất"
TAB_SIM = "Mô phỏng chiến lược"
TAB_RISK = "Rủi ro & Học phần"


def _read_targets() -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=1) as response:
        return json.load(response)


async def _wait_for_target() -> str:
    for _ in range(100):
        try:
            for target in await asyncio.to_thread(_read_targets):
                if target.get("type") == "page":
                    return target["webSocketDebuggerUrl"]
        except (OSError, ValueError):
            pass
        await asyncio.sleep(0.2)
    raise RuntimeError("Chrome DevTools target không sẵn sàng")


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        f"--remote-debugging-port={DEBUG_PORT}", f"--user-data-dir={tempfile.mkdtemp(prefix='dss-chrome-')}",
        f"--window-size={WIDTH},1000", "about:blank",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        async with websockets.connect(await _wait_for_target(), max_size=120_000_000) as websocket:
            counter = itertools.count(1)

            async def send(method: str, params: dict | None = None) -> dict:
                message_id = next(counter)
                await websocket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
                while True:
                    reply = json.loads(await websocket.recv())
                    if reply.get("id") == message_id:
                        if "error" in reply:
                            raise RuntimeError(reply["error"])
                        return reply.get("result", {})

            async def evaluate(expression: str) -> object:
                result = await send("Runtime.evaluate",
                                    {"expression": expression, "returnByValue": True, "awaitPromise": True})
                return result.get("result", {}).get("value")

            async def viewport(height: int) -> None:
                await send("Emulation.setDeviceMetricsOverride",
                           {"width": WIDTH, "height": height, "deviceScaleFactor": 1, "mobile": False})

            async def wait_for(js_condition: str, timeout: float = 30.0) -> None:
                for _ in range(int(timeout / 0.25)):
                    if await evaluate(f"!!({js_condition})"):
                        return
                    await asyncio.sleep(0.25)
                raise RuntimeError(f"Hết thời gian chờ: {js_condition}")

            async def wait_idle() -> None:
                """Chờ Streamlit chạy xong (không còn biểu tượng 'Running')."""
                await asyncio.sleep(0.8)
                await wait_for("!document.querySelector('[data-testid=stStatusWidget]')", timeout=60)
                await asyncio.sleep(1.2)

            async def click(js_element: str) -> None:
                """Bấm bằng sự kiện chuột thật để widget React nhận được."""
                await viewport(1000)
                point = await evaluate(
                    f"(() => {{ const e = {js_element}; if (!e) return null; e.scrollIntoView({{block: 'center'}});"
                    "const b = e.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })()"
                )
                if not point:
                    raise RuntimeError(f"Không tìm thấy phần tử: {js_element}")
                for kind in ("mousePressed", "mouseReleased"):
                    await send("Input.dispatchMouseEvent",
                               {"type": kind, "x": point[0], "y": point[1], "button": "left", "clickCount": 1})

            def by_text(selector: str, text: str) -> str:
                return (f"[...document.querySelectorAll({json.dumps(selector)})]"
                        f".find(n => n.innerText.trim().includes({json.dumps(text)}))")

            async def open_tab(name: str) -> None:
                await click(by_text("[role=tab]", name))
                await wait_idle()

            async def expand(text: str) -> None:
                await click(by_text("[data-testid=stExpander] summary", text))
                await asyncio.sleep(1.5)

            async def choose_persona(student_id: str) -> None:
                await click("document.querySelector('[data-testid=stSelectbox] input')")
                await asyncio.sleep(0.6)
                await send("Input.insertText", {"text": student_id})
                await asyncio.sleep(0.6)
                for kind in ("keyDown", "keyUp"):
                    await send("Input.dispatchKeyEvent",
                               {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                # Xác nhận tiêu đề tổng quan đã đổi sang đúng mã trước khi chụp.
                await wait_for(f"document.body.innerText.includes('👤 {student_id}')", timeout=60)
                await wait_idle()

            async def shot(name: str) -> None:
                await evaluate("window.scrollTo(0, 0); document.querySelector('[data-testid=stMain]')?.scrollTo(0, 0)")
                height = await evaluate(
                    "Math.min(4200, Math.max(...[...document.querySelectorAll('*')].map(e => e.scrollHeight)))"
                )
                await viewport(int(height or 1200))
                await asyncio.sleep(2.0)
                result = await send("Page.captureScreenshot", {"format": "png"})
                path = OUTPUT_DIR / name
                path.write_bytes(base64.b64decode(result["data"]))
                print(f"wrote {path}")

            await send("Page.enable")
            await viewport(1000)
            await send("Page.navigate", {"url": APP_URL})
            await wait_for("document.querySelectorAll('[role=tab]').length >= 4", timeout=60)
            await wait_idle()

            # 01 — Dữ liệu đầu vào (hồ sơ mẫu được phân tích tự động)
            await choose_persona("S002")
            await open_tab(TAB_DATA)
            await shot("01_nhap_ho_so.png")

            # 02–03 — Rủi ro & học phần
            await open_tab(TAB_RISK)
            await shot("02_danh_gia_tong_quan.png")
            await choose_persona("S005")
            await open_tab(TAB_RISK)
            await click(by_text("[data-testid=stRadioOption]", "Bị chặn"))
            await wait_idle()
            await shot("03_danh_gia_shap.png")

            # 04–05 — Lộ trình đề xuất
            await choose_persona("S002")
            await open_tab(TAB_PLAN)
            await shot("04_lo_trinh_so_sanh.png")
            await expand("Tùy chỉnh tham số")
            await expand("Mô hình tối ưu")
            await shot("05_lo_trinh_chi_tiet.png")

            # 06–07 — Mô phỏng chiến lược
            await open_tab(TAB_SIM)
            await shot("06_mo_phong_tong_quan.png")
            await expand("có ý nghĩa thống kê")
            await expand("theo từng sinh viên")
            await shot("07_mo_phong_theo_sinh_vien.png")

            # 08 — Năm kịch bản sinh viên
            for student_id in ("S001", "S002", "S003", "S005", "S008"):
                await choose_persona(student_id)
                await open_tab(TAB_RISK)
                await shot(f"08_danh_gia_{student_id}.png")

            # 09 — S003: mọi phương án best_effort, cảnh báo đỏ
            await choose_persona("S003")
            await open_tab(TAB_PLAN)
            await wait_for("document.body.innerText.includes('KHÔNG phải phương án an toàn')")
            await shot("09_s003_best_effort.png")
    finally:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=10)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        APP_URL = sys.argv[1]
    asyncio.run(main())
