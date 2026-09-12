import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.browser.playwright_manager import playwright_manager
from app.core.config import settings
from app.core.logging_config import logger


class ApplicationAssistant:
    """
    Assists users with filling application forms in the browser.

    COMPLIANCE:
    - Autofills only user-provided information (name, email, phone, etc.)
    - Takes a screenshot before any submission for user review
    - Never submits forms without explicit user approval
    - Does not bypass CAPTCHAs or anti-bot protections
    """

    @staticmethod
    async def open_application_page(url: str):
        """Open a job application URL in the Playwright browser."""
        page = await playwright_manager.new_page()
        if not page:
            logger.warning("Browser not available.")
            return None
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        logger.info(f"Opened application page: {url}")
        return page

    @staticmethod
    async def autofill_form(page, user_data: Dict[str, str]):
        """
        Attempt to autofill common form fields with user-provided data.
        Only fills fields that can be identified by standard attributes.
        """
        field_selectors = {
            "name": ['input[name*="name"]', 'input[id*="name"]', 'input[placeholder*="name" i]'],
            "email": ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]'],
            "phone": ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]'],
            "linkedin": ['input[name*="linkedin"]', 'input[id*="linkedin"]', 'input[placeholder*="linkedin" i]'],
            "github": ['input[name*="github"]', 'input[id*="github"]', 'input[placeholder*="github" i]'],
            "portfolio": ['input[name*="portfolio"]', 'input[name*="website"]', 'input[id*="portfolio"]'],
            "location": ['input[name*="location"]', 'input[name*="city"]', 'input[id*="location"]'],
        }

        filled_count = 0
        for field_key, selectors in field_selectors.items():
            value = user_data.get(field_key, "")
            if not value:
                continue
            for selector in selectors:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        await el.fill(value)
                        filled_count += 1
                        break
                except Exception:
                    continue

        logger.info(f"Autofilled {filled_count} form fields.")
        return filled_count

    @staticmethod
    async def take_review_screenshot(page, application_id: int) -> str:
        """Capture a screenshot of the application form for user review before submission."""
        os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"app_{application_id}_{timestamp}.png"
        filepath = os.path.join(settings.SCREENSHOTS_DIR, filename)
        await page.screenshot(path=filepath, full_page=True)
        logger.info(f"Screenshot saved: {filepath}")
        return filepath


application_assistant = ApplicationAssistant()
