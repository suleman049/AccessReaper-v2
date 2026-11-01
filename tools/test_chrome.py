import json
import subprocess
import time
import urllib.request
import asyncio
import websockets
import base64

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA = r"D:\AccessReaper-v2\tools\chrome_profile"

async def test_chrome():
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={USER_DATA}",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank"
    ]
    proc = subprocess.Popen(cmd)
    try:
        # Wait for debugging port
        for _ in range(20):
            try:
                with urllib.request.urlopen("http://localhost:9222/json", timeout=1) as resp:
                    tabs = json.loads(resp.read().decode())
                    if tabs:
                        break
            except Exception:
                time.sleep(0.3)
        
        print("Connected to Chrome! Available tabs:", len(tabs))
        ws_url = tabs[0]["webSocketDebuggerUrl"]
        
        async with websockets.connect(ws_url) as ws:
            # 1. Enable Page and Runtime
            await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            await ws.recv()
            await ws.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
            await ws.recv()
            
            # 2. Navigate to AccessReaper v2
            print("Navigating to http://127.0.0.1:8100/#settings ...")
            await ws.send(json.dumps({
                "id": 3,
                "method": "Page.navigate",
                "params": {"url": "http://127.0.0.1:8100/#settings"}
            }))
            await ws.recv()
            
            # Wait 2 seconds for app to render
            await asyncio.sleep(2)
            
            # 3. Check document title and elements
            await ws.send(json.dumps({
                "id": 4,
                "method": "Runtime.evaluate",
                "params": {"expression": "document.title"}
            }))
            resp = json.loads(await ws.recv())
            title = resp["result"]["result"]["value"]
            print("Page title:", title)
            
            # Check cards
            check_script = """
            ({
                riskCard: Boolean(document.querySelector('#risk-rules-settings-card')),
                scheduleCard: Boolean(document.querySelector('#schedule-settings-card')),
                usersNav: Boolean(document.querySelector('a[href="#users"]')),
                h1: document.querySelector('h1')?.textContent
            })
            """
            await ws.send(json.dumps({
                "id": 5,
                "method": "Runtime.evaluate",
                "params": {"expression": check_script, "returnByValue": True}
            }))
            resp = json.loads(await ws.recv())
            res = resp["result"]["result"]["value"]
            print("DOM check:", res)
            
            # 4. Take screenshot
            await ws.send(json.dumps({
                "id": 6,
                "method": "Page.captureScreenshot",
                "params": {"format": "png"}
            }))
            resp = json.loads(await ws.recv())
            img_b64 = resp["result"]["data"]
            with open(r"D:\AccessReaper-v2\docs\verification\test_settings.png", "wb") as f:
                f.write(base64.b64decode(img_b64))
            print("Screenshot saved to docs/verification/test_settings.png!")
            
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(test_chrome())
