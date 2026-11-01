import asyncio
import sys

sys.path.insert(0, r"D:\AccessReaper-v2")
from tools.browser_driver import BrowserDriver


async def main():
    d = BrowserDriver(headless=True)
    await d.start()
    await d.navigate("http://127.0.0.1:8100/#request", wait_seconds=1.5)
    r = await d.evaluate(
        """(async () => {
        document.querySelector('#pub-name-input').value = 'Ahmad Raza (Friend Demo)';
        document.querySelector('#pub-email-input').value = 'ahmad.raza@testmail.com';
        document.querySelector('#pub-github-input').value = 'ahmad-raza-demo';
        document.querySelector('#pub-repo-select').value = 'payhive-eng/core-api';
        document.querySelector('#pub-access-select').value = 'Write';
        document.querySelector('#pub-duration-select').value = '0.0167';
        document.querySelector('#pub-reason-input').value = 'Live testing collaboration request from friend for demo';

        const form = document.querySelector('#public-access-request-form');
        let errorLogged = null;
        window.addEventListener('error', e => { errorLogged = e.message; });

        // Submit form
        form.requestSubmit();

        // Wait a second
        await new Promise(r => setTimeout(r, 1200));

        return {
            cardHtml: document.querySelector('#public-request-card')?.innerHTML?.slice(0, 300),
            errorLogged,
            h3Text: document.querySelector('#public-request-card h3')?.textContent
        };
    })()"""
    )
    print("FORM SUBMIT RESULT:", r)
    await d.close()


if __name__ == "__main__":
    asyncio.run(main())
