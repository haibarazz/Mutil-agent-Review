from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx

from src.core.models import ParsedPaper
from src.infra.parsers.shared import DocumentParseError, build_parsed_paper

# 我们都mineru 解析
class MinerUStandardPDFParser:
    name = "mineru-standard"

    def __init__(
        self,
        *,
        token: str,
        base_url: str = "https://mineru.net",
        model_version: str = "vlm",
        timeout_sec: int = 300,
        poll_interval_sec: float = 3.0,
        request_timeout_sec: float = 30.0,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.model_version = model_version
        self.timeout_sec = timeout_sec
        self.poll_interval_sec = poll_interval_sec
        self.request_timeout_sec = request_timeout_sec

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def parse(self, path: Path) -> ParsedPaper:
        path = path.expanduser().resolve()
        if not self.is_configured:
            raise DocumentParseError("MINERU_API_TOKEN is not configured")
        if not path.exists():
            raise DocumentParseError(f"file does not exist: {path}")
        if path.suffix.lower() != ".pdf":
            raise DocumentParseError(f"MinerU only supports PDF files: {path.suffix}")

        batch = self._post_json(
            f"{self.base_url}/api/v4/file-urls/batch",
            payload={
                "files": [{"name": path.name}],
                "model_version": self.model_version,
            },
        )
        data = batch.get("data") or {}
        batch_id = data.get("batch_id")
        upload_urls = data.get("file_urls") or []
        if not batch_id or not upload_urls:
            raise DocumentParseError("MinerU did not return an upload URL")

        self._put_file(upload_urls[0], path)
        result = self._poll_batch_result(str(batch_id))
        full_zip_url = result.get("full_zip_url")
        if not full_zip_url:
            raise DocumentParseError("MinerU did not return full_zip_url")

        archive = self._get_bytes(str(full_zip_url), headers={})
        markdown = _extract_full_markdown_from_zip(archive)
        return build_parsed_paper(path, markdown, [markdown])

    def _poll_batch_result(self, batch_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout_sec
        url = f"{self.base_url}/api/v4/extract-results/batch/{batch_id}"
        while time.time() < deadline:
            payload = self._get_json(url, headers=self._headers())
            extract_result = payload.get("data", {}).get("extract_result") or []
            result = extract_result[0] if extract_result else {}
            state = result.get("state")
            if state == "done":
                return result
            if state == "failed":
                raise DocumentParseError(result.get("err_msg") or "MinerU parse failed")
            time.sleep(self.poll_interval_sec)
        raise DocumentParseError("MinerU parse timed out")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", url, headers=self._headers(), data=json.dumps(payload).encode("utf-8"))

    def _get_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        return self._request_json("GET", url, headers=headers)

    def _get_bytes(self, url: str, headers: dict[str, str]) -> bytes:
        return self._request_bytes("GET", url, headers=headers)

    def _put_file(self, url: str, path: Path) -> None:
        self._request_bytes("PUT", url, headers={"Content-Type": ""}, data=path.read_bytes())

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: bytes | None = None,
    ) -> dict[str, Any]:
        response = self._request_bytes(method, url, headers=headers, data=data)
        try:
            return json.loads(response.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise DocumentParseError(f"MinerU returned invalid JSON from {url}") from exc

    def _request_bytes(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: bytes | None = None,
    ) -> bytes:
        try:
            with httpx.Client(timeout=self.request_timeout_sec, follow_redirects=True) as client:
                response = client.request(method, url, headers=headers, content=data)
                response.raise_for_status()
                return response.content
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            message = body or exc.response.reason_phrase
            raise DocumentParseError(f"MinerU HTTP {exc.response.status_code}: {message}") from exc
        except Exception as exc:
            raise DocumentParseError(f"MinerU request failed: {exc}") from exc


def _extract_full_markdown_from_zip(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in archive.namelist():
            if name.endswith("full.md"):
                return archive.read(name).decode("utf-8")
    raise DocumentParseError("MinerU archive missing full.md")
