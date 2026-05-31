from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import websockets


SMOKE_MARKDOWN = """# Smoke Paper

Abstract
This is a frontend completion-action smoke test.

1 Introduction
The manuscript is intentionally short.
"""


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test Workbench frontend flows through Chrome CDP.")
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--cdp-url", required=True)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--flow", choices=("review", "preset", "command", "upload", "cancel", "retry", "filter", "desktop"), default="review")
    parser.add_argument("--expect", choices=("success", "failure"), default="success")
    args = parser.parse_args()

    async with BrowserSession(args.cdp_url, f"{args.frontend_url.rstrip('/')}/#workbench") as browser:
        if args.flow == "desktop":
            await smoke_desktop_path(browser)
            await browser.capture_screenshot(Path(args.screenshot))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "flow": args.flow,
                        "frontend_url": args.frontend_url,
                        "screenshot": args.screenshot,
                        "hash": await browser.eval("window.location.hash"),
                        "viewport": {"width": 1440, "height": 900},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if args.flow == "filter":
            await smoke_filter_path(browser)
            await browser.capture_screenshot(Path(args.screenshot))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "flow": args.flow,
                        "frontend_url": args.frontend_url,
                        "screenshot": args.screenshot,
                        "hash": await browser.eval("window.location.hash"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if args.flow == "retry":
            await smoke_retry_path(browser)
            await browser.capture_screenshot(Path(args.screenshot))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "flow": args.flow,
                        "frontend_url": args.frontend_url,
                        "screenshot": args.screenshot,
                        "hash": await browser.eval("window.location.hash"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if args.flow == "cancel":
            await smoke_cancel_path(browser)
            await browser.capture_screenshot(Path(args.screenshot))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "flow": args.flow,
                        "frontend_url": args.frontend_url,
                        "screenshot": args.screenshot,
                        "hash": await browser.eval("window.location.hash"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if args.flow == "upload":
            await smoke_upload_path(browser)
            await browser.capture_screenshot(Path(args.screenshot))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "flow": args.flow,
                        "frontend_url": args.frontend_url,
                        "screenshot": args.screenshot,
                        "hash": await browser.eval("window.location.hash"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if args.flow == "command":
            await smoke_command_path(browser)
            await browser.capture_screenshot(Path(args.screenshot))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "flow": args.flow,
                        "frontend_url": args.frontend_url,
                        "screenshot": args.screenshot,
                        "hash": await browser.eval("window.location.hash"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if args.flow == "preset":
            await smoke_preset_path(browser)
            await browser.capture_screenshot(Path(args.screenshot))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "flow": args.flow,
                        "frontend_url": args.frontend_url,
                        "screenshot": args.screenshot,
                        "hash": await browser.eval("window.location.hash"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        await browser.wait_for_text("Begin Review")
        set_file = await browser.eval(
            """
            (() => {
              const input = document.querySelector('input[type=file]');
              const transfer = new DataTransfer();
              transfer.items.add(new File(
                [__SMOKE_MARKDOWN__],
                'codex_completion_actions_smoke.md',
                { type: 'text/markdown' }
              ));
              input.files = transfer.files;
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
              return document.body.innerText.includes('codex_completion_actions_smoke.md');
            })()
            """.replace("__SMOKE_MARKDOWN__", json.dumps(SMOKE_MARKDOWN)),
        )
        if not set_file:
            raise RuntimeError("frontend did not show the selected smoke file")

        await browser.wait_for_expression(
            """
            (() => {
              const button = [...document.querySelectorAll('button')]
                .find((item) => item.textContent.includes('Begin Review'));
              return Boolean(button && !button.disabled);
            })()
            """,
            label="Begin Review to become clickable",
            timeout_seconds=30,
        )

        await browser.eval(
            """
            [...document.querySelectorAll('button')]
              .find((item) => item.textContent.includes('Begin Review'))
              .click()
            """
        )
        if args.expect == "success":
            await smoke_success_path(browser)
        else:
            await smoke_failure_path(browser)

        await browser.capture_screenshot(Path(args.screenshot))

        result = {
            "status": "ok",
            "flow": args.flow,
            "expect": args.expect,
            "frontend_url": args.frontend_url,
            "screenshot": args.screenshot,
            "hash": await browser.eval("window.location.hash"),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


async def smoke_success_path(browser: "BrowserSession") -> None:
    await browser.wait_for_text("Open report", timeout_seconds=120)
    await browser.wait_for_text("Download final_report.md", timeout_seconds=10)
    await browser.wait_for_text("REVIEW THEATER", timeout_seconds=30)
    await browser.wait_for_expression(
        "document.querySelector('.review-theater-stats')?.innerText.toLowerCase().includes('elapsed') && document.querySelector('.review-theater-stats')?.innerText.toLowerCase().includes('next')",
        label="home review theater progress stats",
        timeout_seconds=30,
    )
    await browser.wait_for_expression(
        "document.querySelector('.review-theater-card')?.innerText.includes('Report Renderer')",
        label="home review theater renderer node",
        timeout_seconds=30,
    )

    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.includes('Open report'))
          .click()
        """
    )
    await browser.wait_for_expression(
        "window.location.hash.startsWith('#report=')",
        label="Open report to navigate to report detail",
        timeout_seconds=30,
    )
    await browser.wait_for_text("Review report.", timeout_seconds=30)
    await browser.wait_for_text("REVIEW THEATER", timeout_seconds=30)
    await browser.wait_for_expression(
        "document.querySelector('.review-theater-stats')?.innerText.toLowerCase().includes('elapsed') && document.querySelector('.review-theater-stats')?.innerText.toLowerCase().includes('done')",
        label="detail review theater progress stats",
        timeout_seconds=30,
    )
    await browser.wait_for_expression(
        "document.querySelector('.review-theater-card')?.innerText.includes('Report Renderer')",
        label="detail review theater renderer node",
        timeout_seconds=30,
    )
    await browser.wait_for_text("final_report.md", timeout_seconds=60)
    await browser.wait_for_text("LLM CALLS", timeout_seconds=30)
    await browser.wait_for_text("LLM TIMELINE", timeout_seconds=30)


async def smoke_desktop_path(browser: "BrowserSession") -> None:
    await browser.command(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1440,
            "height": 900,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await browser.wait_for_text("Submit a manuscript for review.", timeout_seconds=30)
    await browser.wait_for_text("The panel awaits.", timeout_seconds=30)
    await browser.wait_for_expression(
        """
        (() => {
          const hero = document.querySelector('.hero');
          const rail = document.querySelector('.rail');
          const page = document.querySelector('.workbench-page');
          const navButtons = document.querySelectorAll('nav button');
          if (!hero || !rail || !page || navButtons.length < 5) return false;
          const heroBox = hero.getBoundingClientRect();
          const railBox = rail.getBoundingClientRect();
          const pageColumns = getComputedStyle(page).gridTemplateColumns;
          const bodyText = document.body.innerText.toLowerCase();
          return window.innerWidth >= 1200
            && heroBox.width >= 850
            && railBox.width >= 300
            && railBox.left > heroBox.left
            && pageColumns.includes('px')
            && bodyText.includes('manuscript intake')
            && bodyText.includes('reviewer 1');
        })()
        """,
        label="desktop workbench layout",
        timeout_seconds=30,
    )


async def smoke_failure_path(browser: "BrowserSession") -> None:
    await browser.wait_for_text("REVIEW FAILED", timeout_seconds=120, allow_failure_text=True)
    await browser.wait_for_text("REVIEW THEATER", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_expression(
        """
        (() => {
          const theater = document.querySelector('.review-theater-card');
          if (!theater) return false;
          const text = theater.innerText;
          return text.includes('Content Checker') && !text.includes('Reviewer · R1');
        })()
        """,
        label="failed home theater stops at failed node",
        timeout_seconds=30,
    )
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.trim() === 'Runs')
          .click()
        """
    )
    await browser.wait_for_text("FAILED", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_expression(
        """
        (() => {
          const button = [...document.querySelectorAll('.report-actions button')]
            .find((item) => item.textContent.includes('Preview') && !item.disabled);
          if (!button) return false;
          button.click();
          return true;
        })()
        """,
        label="failed job preview button",
        timeout_seconds=30,
    )
    await browser.wait_for_expression(
        "document.body.innerText.toLowerCase().includes('partial_report.md')",
        label="partial_report.md preview",
        timeout_seconds=30,
    )
    await browser.wait_for_text("Partial Review Report", timeout_seconds=30, allow_failure_text=True)
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.includes('Open full'))
          .click()
        """
    )
    await browser.wait_for_expression(
        "window.location.hash.startsWith('#report=')",
        label="Open full to navigate to failed report detail",
        timeout_seconds=30,
    )
    await browser.wait_for_text("PARTIAL MARKDOWN", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_text("REVIEW THEATER", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_expression(
        """
        (() => {
          const theater = document.querySelector('.review-theater-card');
          if (!theater) return false;
          const text = theater.innerText;
          return text.includes('Content Checker') && !text.includes('Reviewer · R1');
        })()
        """,
        label="failed detail theater stops at failed node",
        timeout_seconds=30,
    )
    await browser.wait_for_expression(
        "document.body.innerText.toLowerCase().includes('partial_report.md')",
        label="partial_report.md detail",
        timeout_seconds=30,
    )
    await browser.wait_for_text("DIAGNOSTICS", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_text("LLM CALLS", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_text("LLM TIMELINE", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_text("content_check · error · sf/deepseek-v4-flash", timeout_seconds=30, allow_failure_text=True)
    await browser.wait_for_text("ConfigurationError", timeout_seconds=30, allow_failure_text=True)


async def smoke_preset_path(browser: "BrowserSession") -> None:
    await browser.wait_for_text("Save preset", timeout_seconds=30)
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.includes('Quick Review'))
          .click()
        """
    )
    await browser.wait_for_text("Quick Review · CS · AAAI", timeout_seconds=10)
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.includes('Save preset'))
          .click()
        """
    )
    await browser.wait_for_text("Saved Quick Review · CS · AAAI", timeout_seconds=30)
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.trim() === 'Settings')
          .click()
        """
    )
    await browser.wait_for_text("SAVED PRESETS", timeout_seconds=30)
    await browser.wait_for_text("LLM ROUTING", timeout_seconds=30)
    await browser.wait_for_text("sf/deepseek-v4-pro", timeout_seconds=30)
    await browser.wait_for_text("Quick Review · CS · AAAI", timeout_seconds=30)
    await browser.eval(
        """
        [...document.querySelectorAll('.preset-row button')]
          .find((item) => item.textContent.trim() === 'Use')
          .click()
        """
    )
    await browser.wait_for_expression(
        "window.location.hash === '#workbench'",
        label="Use preset to return to Workbench",
        timeout_seconds=30,
    )
    await browser.wait_for_text("Using Quick Review · CS · AAAI", timeout_seconds=30)


async def smoke_command_path(browser: "BrowserSession") -> None:
    await browser.command(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1440,
            "height": 1000,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await browser.wait_for_text("Begin Review", timeout_seconds=30)
    await browser.eval("document.querySelector('.cmd-button').click()")
    await browser.wait_for_text("Command Palette", timeout_seconds=10)
    await browser.wait_for_text("本地产物与 Markdown 报告", timeout_seconds=10)
    await browser.eval(
        """
        [...document.querySelectorAll('.command-item')]
          .find((item) => item.textContent.includes('Library'))
          .click()
        """
    )
    await browser.wait_for_expression(
        "window.location.hash === '#library'",
        label="Library command to navigate",
        timeout_seconds=30,
    )
    await browser.wait_for_text("ARTIFACT LIBRARY", timeout_seconds=30)
    await browser.eval(
        """
        window.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'k',
          metaKey: true,
          bubbles: true
        }))
        """
    )
    await browser.wait_for_text("Command Palette", timeout_seconds=10)
    await browser.eval(
        """
        window.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'Escape',
          bubbles: true
        }))
        """
    )
    await browser.wait_for_expression(
        "!document.body.innerText.includes('Command Palette')",
        label="Escape to close command palette",
        timeout_seconds=10,
    )


async def smoke_upload_path(browser: "BrowserSession") -> None:
    await browser.command(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1440,
            "height": 1000,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await browser.wait_for_text("Begin Review", timeout_seconds=30)
    await browser.eval(
        """
        (() => {
          const drop = document.querySelector('.ms-drop');
          const transfer = new DataTransfer();
          transfer.items.add(new File(
            [__SMOKE_MARKDOWN__],
            'codex_drag_upload_smoke.md',
            { type: 'text/markdown' }
          ));
          drop.dispatchEvent(new DragEvent('dragenter', {
            bubbles: true,
            cancelable: true,
            dataTransfer: transfer
          }));
        })()
        """.replace("__SMOKE_MARKDOWN__", json.dumps(SMOKE_MARKDOWN)),
    )
    await browser.wait_for_expression(
        "document.querySelector('.ms-drop').classList.contains('drag-over')",
        label="drag upload highlight",
        timeout_seconds=10,
    )
    await browser.eval(
        """
        (() => {
          const drop = document.querySelector('.ms-drop');
          const transfer = new DataTransfer();
          transfer.items.add(new File(
            [__SMOKE_MARKDOWN__],
            'codex_drag_upload_smoke.md',
            { type: 'text/markdown' }
          ));
          drop.dispatchEvent(new DragEvent('drop', {
            bubbles: true,
            cancelable: true,
            dataTransfer: transfer
          }));
        })()
        """.replace("__SMOKE_MARKDOWN__", json.dumps(SMOKE_MARKDOWN)),
    )
    await browser.wait_for_text("codex_drag_upload_smoke.md", timeout_seconds=10)
    await browser.wait_for_expression(
        """
        (() => {
          const drop = document.querySelector('.ms-drop');
          const button = [...document.querySelectorAll('button')]
            .find((item) => item.textContent.includes('Begin Review'));
          return drop.classList.contains('has-file')
            && !drop.classList.contains('drag-over')
            && Boolean(button && !button.disabled);
        })()
        """,
        label="dropped upload to stage file",
        timeout_seconds=10,
    )


async def smoke_cancel_path(browser: "BrowserSession") -> None:
    await browser.command(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1440,
            "height": 1000,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await browser.wait_for_text("Begin Review", timeout_seconds=30)
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.trim() === 'Runs')
          .click()
        """
    )
    await browser.wait_for_text("RUN HISTORY", timeout_seconds=30)
    await browser.wait_for_text("codex_cancel_smoke.md", timeout_seconds=30)
    await browser.wait_for_text("QUEUED", timeout_seconds=30)
    await browser.eval(
        """
        (() => {
          const row = [...document.querySelectorAll('.run-row')]
            .find((item) => item.textContent.includes('codex_cancel_smoke.md'));
          row.querySelector('.report-link.danger').click();
        })()
        """
    )
    await browser.wait_for_text("CANCELED", timeout_seconds=30)
    await browser.wait_for_expression(
        """
        (() => {
          const row = [...document.querySelectorAll('.run-row')]
            .find((item) => item.textContent.includes('codex_cancel_smoke.md'));
          const cancelButton = row?.querySelector('.report-link.danger');
          return Boolean(row && row.textContent.includes('CANCELED') && !cancelButton);
        })()
        """,
        label="cancel action to update queued row",
        timeout_seconds=30,
    )
    await browser.eval(
        """
        (() => {
          const row = [...document.querySelectorAll('.run-row')]
            .find((item) => item.textContent.includes('codex_cancel_smoke.md') && item.textContent.includes('CANCELED'));
          [...row.querySelectorAll('button')]
            .find((item) => item.textContent.includes('Inspect'))
            .click();
        })()
        """
    )
    await browser.wait_for_expression(
        "window.location.hash.startsWith('#report=')",
        label="Open canceled job detail",
        timeout_seconds=30,
    )
    await browser.wait_for_text("REVIEW THEATER", timeout_seconds=30)
    await browser.wait_for_text("Run canceled", timeout_seconds=30)
    await browser.wait_for_text("Run canceled before graph node events.", timeout_seconds=30)


async def smoke_retry_path(browser: "BrowserSession") -> None:
    await browser.command(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1440,
            "height": 1000,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await browser.wait_for_text("Begin Review", timeout_seconds=30)
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.trim() === 'Runs')
          .click()
        """
    )
    await browser.wait_for_text("RUN HISTORY", timeout_seconds=30)
    await browser.wait_for_text("codex_retry_smoke.md", timeout_seconds=30)
    await browser.wait_for_text("CANCELED", timeout_seconds=30)
    await browser.eval(
        """
        (() => {
          const row = [...document.querySelectorAll('.run-row')]
            .find((item) => item.textContent.includes('codex_retry_smoke.md') && item.textContent.includes('CANCELED'));
          [...row.querySelectorAll('button')]
            .find((item) => item.textContent.includes('Retry'))
            .click();
        })()
        """
    )
    await browser.wait_for_expression(
        """
        (() => {
          const rows = [...document.querySelectorAll('.run-row')]
            .filter((item) => item.textContent.includes('codex_retry_smoke.md'));
          return rows.length >= 2
            && rows.some((item) => item.textContent.includes('CANCELED'))
            && rows.some((item) => item.textContent.includes('QUEUED') || item.textContent.includes('RUNNING') || item.textContent.includes('SUCCEEDED'));
        })()
        """,
        label="retry action to create a new run row",
        timeout_seconds=60,
    )
    await browser.eval(
        """
        (() => {
          const row = [...document.querySelectorAll('.run-row')]
            .find((item) => item.textContent.includes('codex_retry_smoke.md') && !item.textContent.includes('CANCELED'));
          [...row.querySelectorAll('button')]
            .find((item) => item.textContent.includes('Open') || item.textContent.includes('Inspect'))
            .click();
        })()
        """
    )
    await browser.wait_for_expression(
        "window.location.hash.startsWith('#report=')",
        label="Open retried job detail",
        timeout_seconds=30,
    )
    await browser.wait_for_text("REVIEW THEATER", timeout_seconds=30)


async def smoke_filter_path(browser: "BrowserSession") -> None:
    await browser.command(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1440,
            "height": 1000,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await browser.wait_for_text("Begin Review", timeout_seconds=30)
    await browser.eval(
        """
        [...document.querySelectorAll('button')]
          .find((item) => item.textContent.trim() === 'Runs')
          .click()
        """
    )
    await browser.wait_for_text("RUN HISTORY", timeout_seconds=30)
    await browser.wait_for_text("codex_filter_active.md", timeout_seconds=30)
    await browser.wait_for_text("codex_filter_extra.md", timeout_seconds=30)
    await browser.wait_for_text("codex_filter_canceled.md", timeout_seconds=30)
    await browser.wait_for_expression(
        """
        [...document.querySelectorAll('.run-row')]
          .some((row) => row.textContent.includes('codex_filter_active.md') && row.querySelector('.run-progress-cell'))
        """,
        label="run row progress summary",
        timeout_seconds=30,
    )
    await browser.eval(
        """
        [...document.querySelectorAll('.run-status-filter button')]
          .find((item) => item.textContent.trim() === 'Canceled')
          .click()
        """
    )
    await browser.wait_for_expression(
        """
        document.body.innerText.includes('codex_filter_canceled.md')
          && !document.body.innerText.includes('codex_filter_active.md')
          && !document.body.innerText.includes('codex_filter_extra.md')
        """,
        label="Canceled filter to hide active rows",
        timeout_seconds=30,
    )
    await browser.eval(
        """
        [...document.querySelectorAll('.run-status-filter button')]
          .find((item) => item.textContent.trim() === 'Active')
          .click()
        """
    )
    await browser.wait_for_expression(
        """
        document.body.innerText.includes('codex_filter_active.md')
          && document.body.innerText.includes('codex_filter_extra.md')
          && !document.body.innerText.includes('codex_filter_canceled.md')
        """,
        label="Active filter to hide canceled rows",
        timeout_seconds=30,
    )
    await browser.eval(
        """
        (() => {
          const input = document.querySelector('.run-search input');
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(input, 'active');
          input.dispatchEvent(new Event('input', { bubbles: true }));
        })()
        """
    )
    await browser.wait_for_expression(
        """
        document.body.innerText.includes('codex_filter_active.md')
          && !document.body.innerText.includes('codex_filter_extra.md')
          && !document.body.innerText.includes('codex_filter_canceled.md')
        """,
        label="Search query to narrow active rows",
        timeout_seconds=30,
    )


class BrowserSession:
    def __init__(self, cdp_url: str, target_url: str) -> None:
        self.cdp_url = cdp_url.rstrip("/")
        self.target_url = target_url
        self._next_id = 0
        self._ws = None

    async def __aenter__(self) -> "BrowserSession":
        request = Request(f"{self.cdp_url}/json/new?{quote(self.target_url, safe=':/#?=&')}", method="PUT")
        with urlopen(request, timeout=10) as response:
            target = json.loads(response.read().decode("utf-8"))
        self._ws = await websockets.connect(target["webSocketDebuggerUrl"], max_size=20_000_000)
        await self.command("Page.enable")
        await self.command("Runtime.enable")
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def command(self, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if self._ws is None:
            raise RuntimeError("browser session is not open")
        self._next_id += 1
        message_id = self._next_id
        await self._ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(await self._ws.recv())
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result", {})

    async def eval(self, expression: str) -> object:
        result = await self.command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        value = result.get("result", {})
        if isinstance(value, dict):
            return value.get("value")
        return None

    async def wait_for_text(self, text: str, timeout_seconds: int = 60, *, allow_failure_text: bool = False) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            body_text = await self.eval("document.body.innerText")
            if isinstance(body_text, str) and text in body_text:
                return
            if not allow_failure_text and isinstance(body_text, str) and "Review failed" in body_text:
                raise RuntimeError("review job failed during frontend smoke")
            await asyncio.sleep(1)
        raise TimeoutError(f"timed out waiting for text: {text}")

    async def wait_for_expression(self, expression: str, *, label: str, timeout_seconds: int = 30) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            value = await self.eval(expression)
            if value:
                return
            await asyncio.sleep(0.5)
        raise TimeoutError(f"timed out waiting for {label}")

    async def capture_screenshot(self, path: Path) -> None:
        result = await self.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(str(result["data"])))


if __name__ == "__main__":
    asyncio.run(main())
