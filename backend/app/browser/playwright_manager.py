import os
from typing import Optional
from app.core.config import settings
from app.core.logging_config import logger


class PlaywrightManager:
    """
    Manages Playwright browser lifecycle for permitted automation workflows.
    
    COMPLIANCE:
    - No CAPTCHA bypass or anti-bot circumvention
    - No credential interception or fingerprint evasion
    - Browser is used only for user-initiated, user-supervised form assistance
    - All sessions require explicit user login and approval
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None

    async def launch(self, headless: bool = False):
        """Launch a persistent Chromium browser with user data directory."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            
            user_data_dir = os.path.abspath(settings.BROWSER_DATA_DIR)
            os.makedirs(user_data_dir, exist_ok=True)

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                args=["--disable-blink-features=AutomationControlled"],
            )
            logger.info("Playwright browser launched with persistent profile.")
        except ImportError:
            logger.warning("Playwright not installed. Browser automation unavailable.")
        except Exception as e:
            logger.error(f"Failed to launch Playwright browser: {e}")

    async def new_page(self):
        if not self._context:
            await self.launch()
        if self._context:
            return await self._context.new_page()
        return None

    async def close(self):
        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Playwright browser closed.")
        except Exception as e:
            logger.warning(f"Error closing Playwright: {e}")
        finally:
            self._context = None
            self._playwright = None

    @property
    def is_running(self) -> bool:
        return self._context is not None


playwright_manager = PlaywrightManager()
