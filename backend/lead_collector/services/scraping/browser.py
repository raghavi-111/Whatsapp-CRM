import asyncio
import sys
from threading import Lock
from contextlib import contextmanager


_playwright_start_lock = Lock()


class BrowserStartupError(Exception):
    """Raised when Playwright or Chromium cannot be started."""


def _start_playwright(sync_playwright):
    """Start Playwright with subprocess support under Daphne on Windows."""
    if sys.platform != 'win32':
        return sync_playwright().start()

    # Daphne installs WindowsSelectorEventLoopPolicy while loading Django, but
    # SelectorEventLoop cannot launch Playwright's driver subprocess. Restrict
    # the policy swap to Playwright loop creation and restore it immediately.
    with _playwright_start_lock:
        previous_policy = asyncio.get_event_loop_policy()
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            return sync_playwright().start()
        finally:
            asyncio.set_event_loop_policy(previous_policy)


@contextmanager
def browser_page(*, headless=True, timeout=15000):
    """Yield one isolated page and close every browser resource on exit."""
    manager = browser = context = page = None
    try:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserStartupError('Playwright or Chromium is not installed.') from exc
        manager = _start_playwright(sync_playwright)
        browser = manager.chromium.launch(headless=headless)
        context = browser.new_context(locale='en-US')
        page = context.new_page()
        page.set_default_timeout(timeout)
        page.set_default_navigation_timeout(timeout)
        yield page
    except BrowserStartupError:
        raise
    except Exception as exc:
        if browser is None:
            raise BrowserStartupError('Chromium could not be started.') from exc
        raise
    finally:
        for resource in (page, context, browser):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
        if manager is not None:
            try:
                manager.stop()
            except Exception:
                pass
