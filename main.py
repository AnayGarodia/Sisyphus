# browser_agent_extensive.py
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from typing import Optional, List

class BrowserAgent:
    def __init__(self, headless: bool = False):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    # ------------------- Core Actions -------------------
    def go_to(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded")

    def click(self, selector: str, strict: bool = True, index: int = 0, timeout: int = 5000):
        """Click an element. Handles multiple matches."""
        try:
            locator = self.page.locator(selector)
            if strict:
                locator = locator.nth(index)  # pick the first by default
            locator.click(timeout=timeout)
        except PlaywrightTimeoutError:
            print(f"[ERROR] Could not find element to click: {selector}")

    def fill(self, selector: str, text: str, strict: bool = True, index: int = 0, timeout: int = 5000):
        try:
            locator = self.page.locator(selector)
            if strict:
                locator = locator.nth(index)
            locator.fill(text, timeout=timeout)
        except PlaywrightTimeoutError:
            print(f"[ERROR] Could not find element to fill: {selector}")

    def read(self, selector: str, strict: bool = True, index: int = 0, timeout: int = 5000) -> Optional[str]:
        try:
            locator = self.page.locator(selector)
            if strict:
                locator = locator.nth(index)
            return locator.inner_text(timeout=timeout)
        except PlaywrightTimeoutError:
            print(f"[ERROR] Could not find element to read: {selector}")
            return None

    def scan(self) -> str:
        """Return the full page content."""
        return self.page.content()

    def screenshot(self, path: str = "screenshot.png"):
        self.page.screenshot(path=path)

    # ------------------- Advanced Actions -------------------
    def select_dropdown(self, selector: str, value: str):
        """Select a dropdown option by value."""
        try:
            self.page.select_option(selector, value)
        except PlaywrightTimeoutError:
            print(f"[ERROR] Could not find dropdown: {selector}")

    def hover(self, selector: str, timeout: int = 5000):
        """Hover over an element."""
        try:
            self.page.locator(selector).hover(timeout=timeout)
        except PlaywrightTimeoutError:
            print(f"[ERROR] Could not find element to hover: {selector}")

    def wait_for_text(self, selector: str, text: str, timeout: int = 5000) -> bool:
        """Wait for specific text to appear."""
        try:
            self.page.locator(selector).wait_for(state="visible", timeout=timeout)
            actual_text = self.page.locator(selector).inner_text()
            return text in actual_text
        except PlaywrightTimeoutError:
            print(f"[ERROR] Text '{text}' not found in selector: {selector}")
            return False

    # ------------------- Utility -------------------
    def help(self):
        print("""
Available commands:
- go_to(url)
- click(selector, strict=True, index=0)
- fill(selector, text, strict=True, index=0)
- read(selector, strict=True, index=0)
- scan()          # get full page content
- screenshot(path)
- select_dropdown(selector, value)
- hover(selector)
- wait_for_text(selector, text)
- close()
""")

    def close(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()


# ------------------- Example Usage -------------------
if __name__ == "__main__":
    agent = BrowserAgent(headless=False)

    agent.go_to("https://www.google.com")
    agent.fill("input[name='q']", "Playwright Python")  # fill search
    agent.click("input[name='btnK']", index=0)  # pick the first visible button

    agent.page.wait_for_timeout(2000)  # wait for results
    first_result = agent.read("h3", index=0)
    print("First result:", first_result)

    # Scan page and take a screenshot
    content = agent.scan()
    print("Page content length:", len(content))
    agent.screenshot("google_search.png")

    agent.close()
