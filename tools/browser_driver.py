import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA = r"D:\AccessReaper-v2\tools\chrome_profile"

class BrowserDriver:
    def __init__(self, headless=True):
        self.headless = headless
        self.proc = None
        self.ws = None
        self.cmd_id = 0
        self.console_logs = []
        self.console_errors = []
        self._pending_commands = {}
        self._listener_task = None

    async def start(self):
        os.makedirs(USER_DATA, exist_ok=True)
        cmd = [
            CHROME_PATH,
            "--headless=new" if self.headless else "",
            "--remote-debugging-port=9222",
            f"--user-data-dir={USER_DATA}",
            "--disable-extensions",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank"
        ]
        cmd = [c for c in cmd if c]
        self.proc = subprocess.Popen(cmd)

        tabs = []
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=1) as resp:
                    all_targets = json.loads(resp.read().decode())
                    tabs = [t for t in all_targets if t.get("type") == "page"]
                    if tabs and "webSocketDebuggerUrl" in tabs[0]:
                        break
            except Exception:
                await asyncio.sleep(0.3)

        if not tabs:
            raise RuntimeError("Could not connect to Chrome debugging port.")

        ws_url = tabs[0]["webSocketDebuggerUrl"]
        self.ws = await websockets.connect(ws_url, max_size=25 * 1024 * 1024)
        self._listener_task = asyncio.create_task(self._listen())

        await self.send("Page.enable")
        await self.send("Runtime.enable")
        await self.send("DOM.enable")

    async def _listen(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._pending_commands:
                    future = self._pending_commands.pop(msg_id)
                    if not future.done():
                        future.set_result(msg)
                elif "method" in msg:
                    method = msg["method"]
                    params = msg.get("params", {})
                    if method == "Runtime.consoleAPICalled":
                        log_type = params.get("type", "log")
                        args = [str(a.get("value", a.get("description", ""))) for a in params.get("args", [])]
                        log_text = " ".join(args)
                        self.console_logs.append((log_type, log_text))
                        if log_type in ("error", "warning") and "DevTools" not in log_text:
                            self.console_errors.append(f"[{log_type.upper()}] {log_text}")
                    elif method == "Runtime.exceptionThrown":
                        details = params.get("exceptionDetails", {})
                        text = details.get("text", "") + " " + str(details.get("exception", {}).get("description", ""))
                        self.console_errors.append(f"[EXCEPTION] {text}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            pass

    async def send(self, method: str, params: dict = None) -> dict:
        self.cmd_id += 1
        cid = self.cmd_id
        future = asyncio.get_event_loop().create_future()
        self._pending_commands[cid] = future
        payload = {"id": cid, "method": method}
        if params:
            payload["params"] = params
        await self.ws.send(json.dumps(payload))
        return await future

    async def navigate(self, url: str, wait_seconds: float = 1.5):
        self.console_errors.clear()
        self.console_logs.clear()
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(wait_seconds)

    async def evaluate(self, expression: str):
        resp = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        result = resp.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(f"JS evaluation error: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    async def click(self, selector: str, wait_seconds: float = 0.5):
        expr = f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) throw new Error("Element not found: " + {json.dumps(selector)});
            el.scrollIntoView({{block: 'center'}});
            el.click();
            return true;
        }})()
        """
        await self.evaluate(expr)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    async def set_viewport(self, width: int, height: int, is_mobile: bool = False):
        await self.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": is_mobile
        })

    async def screenshot(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        resp = await self.send("Page.captureScreenshot", {"format": "png"})
        data = resp["result"]["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        print(f"  [SCREENSHOT] Saved {path}")

    async def close(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self.ws:
            await self.ws.close()
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
