import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.errors import ConfigurationError, ErrorContext
from src.core.models import OutputLanguage, ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.graphs.runtime import get_review_nodes
from src.infra.llm_diagnostics import record_llm_event
from src.services.review_jobs import ReviewJobStatus, build_job_runner


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_PROVIDER"] = "mock"
        get_review_nodes.cache_clear()

    def tearDown(self) -> None:
        get_review_nodes.cache_clear()

    def test_create_review_keeps_json_local_path_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text(
                "JSON API Paper\n\nAbstract\nA small paper for API testing.\n\n1 Introduction\nContent.",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"DATA_DIR": str(Path(tmp) / "data"), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                response = client.post(
                    "/api/reviews",
                    json={
                        "paper_path": str(paper),
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                )

                self.assertEqual(200, response.status_code, response.text)
                body = response.json()
                self.assertEqual("QUICK_REVIEW", body["request"]["review_mode"])
                self.assertEqual("AAAI", body["request"]["venue_code"])
                self.assertTrue(Path(body["artifact_dir"]).exists())

    def test_cors_origins_are_configurable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_CORS_ORIGINS": "https://frontend.example.com,http://localhost:3000",
                "LLM_PROVIDER": "mock",
            },
        ):
            client = TestClient(create_app())
            response = client.options(
                "/health",
                headers={
                    "Origin": "https://frontend.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("https://frontend.example.com", response.headers["access-control-allow-origin"])

    def test_config_exposes_frontend_contract(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            client = TestClient(create_app())
            response = client.get("/api/config")

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual([".pdf", ".md", ".tex"], body["supported_upload_extensions"])
        self.assertEqual(83_886_080, body["max_upload_bytes"])
        self.assertEqual("zh", body["default_output_language"])
        self.assertEqual("FULL_REVIEW", body["default_review_mode"])

    def test_llm_config_exposes_safe_router_summary(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "router",
                "LLM_XUNFEI_BASE_URL": "https://secret-xunfei.example/v1",
                "LLM_XUNFEI_API_KEY": "sk-secret-xunfei",
            },
        ):
            client = TestClient(create_app())
            response = client.get("/api/llm-config")

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("loaded", body["status"])
        self.assertEqual("router", body["mode"])
        self.assertEqual("xopqwen36v35b", body["default_model"])

        providers = {item["name"]: item for item in body["providers"]}
        self.assertIn("xunfeid", providers)
        self.assertEqual("LLM_XUNFEI_BASE_URL", providers["xunfeid"]["base_url_env"])
        self.assertEqual("LLM_XUNFEI_API_KEY", providers["xunfeid"]["api_key_env"])
        self.assertTrue(providers["xunfeid"]["base_url_configured"])
        self.assertTrue(providers["xunfeid"]["api_key_configured"])

        prompts = {item["name"]: item for item in body["prompts"]}
        self.assertEqual("xopqwen36v35b", prompts["reviewer1"]["model"])
        self.assertEqual("xunfeid", prompts["reviewer1"]["provider"])
        self.assertTrue(prompts["reviewer1"]["registered"])

        nodes = {item["name"]: item for item in body["nodes"]}
        self.assertEqual("xopqwen36v35b", nodes["reviewer1"]["primary_model"])
        self.assertEqual(3, nodes["reviewer1"]["max_attempts"])
        self.assertEqual(
            ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-ai/DeepSeek-V4-Pro", "zai-org/GLM-5.2"],
            nodes["reviewer1"]["fallback_models"],
        )

        self.assertNotIn("sk-secret-xunfei", response.text)
        self.assertNotIn("https://secret-xunfei.example/v1", response.text)

    def test_openapi_exposes_typed_frontend_contracts(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            client = TestClient(create_app())
            response = client.get("/openapi.json")

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        schemas = body["components"]["schemas"]
        for schema_name in [
            "AppConfigResponse",
            "ArxivFetchCreate",
            "FetchedPaperResponse",
            "LLMRuntimeConfigResponse",
            "ReviewJobResponse",
            "ReviewJobProgressResponse",
            "ReviewJobsResponse",
            "ReviewJobsSummaryResponse",
            "ReviewPresetResponse",
            "ReviewPresetsResponse",
            "ReviewReportResponse",
            "ReviewDiagnosticsResponse",
            "ReviewLLMCallsResponse",
            "ReviewUsageSummaryResponse",
            "LibraryResponse",
        ]:
            self.assertIn(schema_name, schemas)

        jobs_schema = body["paths"]["/api/jobs"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewJobsResponse", jobs_schema["$ref"])
        jobs_summary_schema = body["paths"]["/api/jobs/summary"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewJobsSummaryResponse", jobs_summary_schema["$ref"])
        arxiv_schema = body["paths"]["/api/paper-sources/arxiv"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/FetchedPaperResponse", arxiv_schema["$ref"])
        llm_config_schema = body["paths"]["/api/llm-config"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/LLMRuntimeConfigResponse", llm_config_schema["$ref"])
        presets_schema = body["paths"]["/api/presets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewPresetsResponse", presets_schema["$ref"])
        cancel_schema = body["paths"]["/api/jobs/{job_id}/cancel"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewJobResponse", cancel_schema["$ref"])
        retry_schema = body["paths"]["/api/jobs/{job_id}/retry"]["post"]["responses"]["202"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewJobResponse", retry_schema["$ref"])
        report_schema = body["paths"]["/api/jobs/{job_id}/report"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewReportResponse", report_schema["$ref"])
        diagnostics_schema = body["paths"]["/api/jobs/{job_id}/diagnostics"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewDiagnosticsResponse", diagnostics_schema["$ref"])
        llm_calls_schema = body["paths"]["/api/jobs/{job_id}/llm-calls"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewLLMCallsResponse", llm_calls_schema["$ref"])
        usage_schema = body["paths"]["/api/jobs/{job_id}/usage"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("#/components/schemas/ReviewUsageSummaryResponse", usage_schema["$ref"])

    def test_presets_are_saved_locally_and_listed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                create_response = client.post(
                    "/api/presets",
                    json={
                        "name": "AAAI quick Chinese",
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                )
                list_response = client.get("/api/presets")

                self.assertEqual(201, create_response.status_code, create_response.text)
                created = create_response.json()
                self.assertEqual("AAAI quick Chinese", created["name"])
                self.assertEqual("QUICK_REVIEW", created["review_mode"])
                self.assertTrue(created["preset_id"])

                self.assertEqual(200, list_response.status_code, list_response.text)
                body = list_response.json()
                self.assertEqual(1, body["count"])
                self.assertEqual(created["preset_id"], body["presets"][0]["preset_id"])

                presets_path = data_dir / "presets.json"
                self.assertTrue(presets_path.exists())
                self.assertIn("AAAI quick Chinese", presets_path.read_text(encoding="utf-8"))

    def test_fetch_arxiv_source_downloads_pdf_into_uploads(self) -> None:
        class FakePdfResponse:
            def __init__(self, content: bytes) -> None:
                self.content = content
                self.offset = 0
                self.headers = {"content-length": str(len(content))}

            def __enter__(self):
                return self

            def __exit__(self, *exc_info: object) -> None:
                return None

            def read(self, size: int = -1) -> bytes:
                if self.offset >= len(self.content):
                    return b""
                if size < 0:
                    size = len(self.content) - self.offset
                chunk = self.content[self.offset : self.offset + size]
                self.offset += len(chunk)
                return chunk

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            pdf_bytes = b"%PDF-1.4\n% fake arxiv paper\n"
            with (
                patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}),
                patch("src.services.paper_sources.urlopen", return_value=FakePdfResponse(pdf_bytes)) as opener,
            ):
                client = TestClient(create_app())
                response = client.post(
                    "/api/paper-sources/arxiv",
                    json={"arxiv_id": "https://arxiv.org/abs/2406.12345v2"},
                )

                self.assertEqual(200, response.status_code, response.text)
                body = response.json()
                paper_path = Path(body["paper_path"])
                self.assertEqual("2406.12345v2", body["arxiv_id"])
                self.assertEqual("https://arxiv.org/pdf/2406.12345v2.pdf", body["pdf_url"])
                self.assertEqual(data_dir / "uploads", paper_path.parent)
                self.assertEqual(".pdf", paper_path.suffix)
                self.assertEqual(len(pdf_bytes), body["size_bytes"])
                self.assertTrue(paper_path.exists())
                self.assertEqual(pdf_bytes, paper_path.read_bytes())
                request = opener.call_args.args[0]
                self.assertEqual("https://arxiv.org/pdf/2406.12345v2.pdf", request.full_url)

    def test_fetch_arxiv_source_rejects_invalid_id(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            client = TestClient(create_app())
            response = client.post("/api/paper-sources/arxiv", json={"arxiv_id": "not-a-paper"})
            foreign_response = client.post(
                "/api/paper-sources/arxiv",
                json={"arxiv_id": "https://example.com/abs/2406.12345"},
            )

        self.assertEqual(400, response.status_code)
        self.assertIn("invalid arXiv id", response.text)
        self.assertEqual(400, foreign_response.status_code)
        self.assertIn("only arxiv.org", foreign_response.text)

    def test_upload_rejects_unsupported_file_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                response = client.post(
                    "/api/jobs",
                    data={
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                    files={"paper": ("paper.docx", b"Unsupported file", "application/octet-stream")},
                )

        self.assertEqual(400, response.status_code)
        self.assertIn("unsupported file extension", response.text)

    def test_upload_rejects_file_above_configured_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(
                os.environ,
                {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock", "APP_MAX_UPLOAD_BYTES": "8"},
            ):
                client = TestClient(create_app())
                response = client.post(
                    "/api/jobs",
                    data={
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                    files={"paper": ("paper.md", b"123456789", "text/markdown")},
                )

        self.assertEqual(413, response.status_code)
        self.assertIn("file is too large", response.text)

    def test_create_review_accepts_browser_file_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                response = client.post(
                    "/api/reviews",
                    data={
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                    files={
                        "paper": (
                            "browser paper.md",
                            b"Browser Upload Paper\n\nAbstract\nA small uploaded paper.\n\n1 Introduction\nContent.",
                            "text/markdown",
                        )
                    },
                )

                self.assertEqual(200, response.status_code, response.text)
                body = response.json()
                saved_paper = Path(body["request"]["paper_path"])
                self.assertEqual(data_dir / "uploads", saved_paper.parent)
                self.assertEqual(".md", saved_paper.suffix)
                self.assertTrue(saved_paper.exists())
                self.assertEqual("QUICK_REVIEW", body["request"]["review_mode"])

    def test_create_job_accepts_browser_upload_and_exposes_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                create_response = client.post(
                    "/api/jobs",
                    data={
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                    files={
                        "paper": (
                            "job paper.md",
                            b"Job Upload Paper\n\nAbstract\nA small uploaded paper.\n\n1 Introduction\nContent.",
                            "text/markdown",
                        )
                    },
                )

                self.assertEqual(202, create_response.status_code, create_response.text)
                created = create_response.json()
                self.assertEqual("QUEUED", created["status"])
                self.assertEqual("AAAI", created["request"]["venue_code"])
                self.assertEqual(0, created["progress"]["percent"])
                self.assertEqual("doc_parse", created["progress"]["next_node"])

                status_response = client.get(f"/api/jobs/{created['job_id']}")
                self.assertEqual(200, status_response.status_code, status_response.text)
                status = status_response.json()
                self.assertEqual("SUCCEEDED", status["status"])
                self.assertTrue(status["run_id"])
                self.assertTrue(Path(status["artifact_dir"]).exists())
                self.assertEqual("QUICK_REVIEW", status["request"]["review_mode"])
                self.assertEqual("SUCCEEDED", status["nodes"]["doc_parse"]["status"])
                self.assertEqual("SUCCEEDED", status["nodes"]["final_artifact_render"]["status"])
                self.assertTrue(status["node_events"])
                self.assertEqual(100, status["progress"]["percent"])
                self.assertEqual(13, status["progress"]["total_nodes"])
                self.assertEqual(13, status["progress"]["completed_nodes"])
                self.assertIn("ae_decision", status["nodes"])
                self.assertIn("ae_report", status["nodes"])
                self.assertIn("ae_finalize", status["nodes"])
                self.assertNotIn("ae_final", status["nodes"])
                self.assertIsNone(status["progress"]["next_node"])
                self.assertIsInstance(status["progress"]["elapsed_ms"], (int, float))

    def test_single_agent_job_progress_and_artifacts_match_single_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                create_response = client.post(
                    "/api/jobs",
                    data={
                        "review_mode": "SINGLE_AGENT_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                    files={
                        "paper": (
                            "single-agent-job.md",
                            b"Single Agent Paper\n\nAbstract\nA small paper.\n\n1 Introduction\nContent.",
                            "text/markdown",
                        )
                    },
                )

                self.assertEqual(202, create_response.status_code, create_response.text)
                job_id = create_response.json()["job_id"]
                status_response = client.get(f"/api/jobs/{job_id}")
                artifacts_response = client.get(f"/api/jobs/{job_id}/artifacts")

        self.assertEqual(200, status_response.status_code, status_response.text)
        status = status_response.json()
        self.assertEqual("SUCCEEDED", status["status"])
        self.assertEqual("SINGLE_AGENT_REVIEW", status["request"]["review_mode"])
        self.assertEqual(6, status["progress"]["total_nodes"])
        self.assertEqual(6, status["progress"]["completed_nodes"])
        self.assertEqual(100, status["progress"]["percent"])
        self.assertIn("single_reviewer", status["nodes"])
        self.assertNotIn("reviewer1", status["nodes"])
        self.assertNotIn("ae_final", status["nodes"])

        self.assertEqual(200, artifacts_response.status_code, artifacts_response.text)
        artifact_names = {item["name"] for item in artifacts_response.json()["artifacts"]}
        self.assertIn("single_reviewer.json", artifact_names)
        self.assertIn("final_report.md", artifact_names)

    def test_completed_job_exposes_artifacts_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                create_response = client.post(
                    "/api/jobs",
                    data={
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                    files={
                        "paper": (
                            "artifact paper.md",
                            b"Artifact Paper\n\nAbstract\nA small uploaded paper.\n\n1 Introduction\nContent.",
                            "text/markdown",
                        )
                    },
                )

                job_id = create_response.json()["job_id"]
                artifacts_response = client.get(f"/api/jobs/{job_id}/artifacts")
                report_response = client.get(f"/api/jobs/{job_id}/report")
                diagnostics_response = client.get(f"/api/jobs/{job_id}/diagnostics")
                llm_calls_response = client.get(f"/api/jobs/{job_id}/llm-calls")
                usage_response = client.get(f"/api/jobs/{job_id}/usage")
                download_response = client.get(f"/api/jobs/{job_id}/artifacts/final_report.md")

        self.assertEqual(200, artifacts_response.status_code, artifacts_response.text)
        artifacts = artifacts_response.json()
        artifact_names = {item["name"] for item in artifacts["artifacts"]}
        self.assertIn("final_report.md", artifact_names)
        self.assertIn("usage_summary.json", artifact_names)

        self.assertEqual(200, report_response.status_code, report_response.text)
        report = report_response.json()
        self.assertEqual("final_report.md", report["name"])
        self.assertIn("审稿报告", report["content"])

        self.assertEqual(200, diagnostics_response.status_code, diagnostics_response.text)
        diagnostics = diagnostics_response.json()
        self.assertEqual(job_id, diagnostics["job_id"])
        self.assertEqual("succeeded", diagnostics["diagnostics"]["status"])
        self.assertEqual([], diagnostics["diagnostics"]["errors"])

        self.assertEqual(200, llm_calls_response.status_code, llm_calls_response.text)
        self.assertEqual(0, llm_calls_response.json()["count"])

        self.assertEqual(200, usage_response.status_code, usage_response.text)
        usage = usage_response.json()
        self.assertEqual(job_id, usage["job_id"])
        self.assertEqual("review_usage_summary_v1", usage["usage"]["schema"])
        self.assertEqual(0, usage["usage"]["total_calls"])

        self.assertEqual(200, download_response.status_code, download_response.text)
        self.assertIn("attachment", download_response.headers["content-disposition"])
        self.assertIn("审稿报告", download_response.text)

    def test_failed_job_exposes_partial_report(self) -> None:
        class FailingGraph:
            def invoke(self, initial_state):
                record_llm_event(
                    "error",
                    {
                        "kind": "json",
                        "prompt": "reviewer1",
                        "provider": "fake_provider",
                        "model": "fake_model",
                        "attempt": 1,
                        "elapsed_ms": 42,
                        "error_type": "ProviderTransientError",
                        "retryable": "true",
                    },
                )
                raise ConfigurationError(
                    "LLM model is not registered",
                    context=ErrorContext(node="reviewer1", prompt_name="reviewer1", model="missing-model"),
                )

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                with patch("src.services.review_service.main_graph", FailingGraph()):
                    create_response = client.post(
                        "/api/jobs",
                        json={
                            "paper_path": self._write_paper(tmp, "failed.md"),
                            "review_mode": "QUICK_REVIEW",
                            "output_language": "zh",
                            "venue_domain": "CS",
                            "venue_collection": "CCFA",
                            "venue_code": "AAAI",
                        },
                    )

                self.assertEqual(202, create_response.status_code, create_response.text)
                job_id = create_response.json()["job_id"]
                status_response = client.get(f"/api/jobs/{job_id}")
                artifacts_response = client.get(f"/api/jobs/{job_id}/artifacts")
                report_response = client.get(f"/api/jobs/{job_id}/report")
                diagnostics_response = client.get(f"/api/jobs/{job_id}/diagnostics")
                llm_calls_response = client.get(f"/api/jobs/{job_id}/llm-calls")
                usage_response = client.get(f"/api/jobs/{job_id}/usage")
                library_response = client.get("/api/library")

        self.assertEqual(200, status_response.status_code, status_response.text)
        status = status_response.json()
        self.assertEqual("FAILED", status["status"])
        self.assertTrue(status["run_id"])
        self.assertTrue(status["artifact_dir"])
        self.assertEqual("ConfigurationError", status["error"]["error_type"])

        self.assertEqual(200, artifacts_response.status_code, artifacts_response.text)
        artifact_names = {item["name"] for item in artifacts_response.json()["artifacts"]}
        self.assertIn("diagnostics.json", artifact_names)
        self.assertIn("llm_calls.jsonl", artifact_names)
        self.assertIn("usage_summary.json", artifact_names)
        self.assertIn("partial_report.md", artifact_names)

        self.assertEqual(200, report_response.status_code, report_response.text)
        report = report_response.json()
        self.assertEqual("partial_report.md", report["name"])
        self.assertIn("Partial Review Report", report["content"])
        self.assertIn("LLM model is not registered", report["content"])

        self.assertEqual(200, diagnostics_response.status_code, diagnostics_response.text)
        diagnostics = diagnostics_response.json()
        self.assertEqual(job_id, diagnostics["job_id"])
        self.assertEqual("failed", diagnostics["diagnostics"]["status"])
        self.assertEqual("ConfigurationError", diagnostics["diagnostics"]["errors"][0]["error_type"])
        self.assertEqual("reviewer1", diagnostics["diagnostics"]["errors"][0]["node"])

        self.assertEqual(200, llm_calls_response.status_code, llm_calls_response.text)
        llm_calls = llm_calls_response.json()
        self.assertEqual(job_id, llm_calls["job_id"])
        self.assertEqual(1, llm_calls["count"])
        self.assertEqual("error", llm_calls["events"][0]["event"])
        self.assertEqual("reviewer1", llm_calls["events"][0]["prompt"])
        self.assertEqual("ProviderTransientError", llm_calls["events"][0]["error_type"])

        self.assertEqual(200, usage_response.status_code, usage_response.text)
        usage = usage_response.json()
        self.assertEqual(job_id, usage["job_id"])
        self.assertEqual(1, usage["usage"]["error_calls"])
        self.assertEqual(1, usage["usage"]["retry_error_count"])

        self.assertEqual(200, library_response.status_code, library_response.text)
        library_artifacts = library_response.json()["artifacts"]
        partial_report = next(item for item in library_artifacts if item["name"] == "partial_report.md")
        self.assertEqual(job_id, partial_report["job_id"])
        self.assertEqual("FAILED", partial_report["job_status"])
        self.assertEqual(f"/api/jobs/{job_id}/artifacts/partial_report.md", partial_report["download_url"])

    def test_list_jobs_returns_local_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                first = client.post(
                    "/api/jobs",
                    json={
                        "paper_path": self._write_paper(tmp, "first.md"),
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                ).json()
                second = client.post(
                    "/api/jobs",
                    json={
                        "paper_path": self._write_paper(tmp, "second.md"),
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                ).json()

                response = client.get("/api/jobs")
                summary_response = client.get("/api/jobs/summary")

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        job_ids = [job["job_id"] for job in body["jobs"]]
        self.assertEqual(2, body["count"])
        self.assertIn(first["job_id"], job_ids)
        self.assertIn(second["job_id"], job_ids)
        self.assertEqual("SUCCEEDED", body["jobs"][0]["status"])

        self.assertEqual(200, summary_response.status_code, summary_response.text)
        summary = summary_response.json()
        self.assertEqual(2, summary["count"])
        self.assertEqual(0, summary["active_count"])
        self.assertEqual(2, summary["succeeded_count"])
        self.assertEqual(0, summary["failed_count"])
        self.assertEqual(0, summary["canceled_count"])
        self.assertTrue(summary["latest_job_id"])
        self.assertEqual("SUCCEEDED", summary["latest_status"])

    def test_list_jobs_can_filter_by_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                runner = build_job_runner()
                queued = runner.create_job(
                    ReviewRequest(
                        paper_path=self._write_paper(tmp, "queued.md"),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        output_language=OutputLanguage.ZH,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
                canceled = runner.create_job(
                    ReviewRequest(
                        paper_path=self._write_paper(tmp, "canceled.md"),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        output_language=OutputLanguage.ZH,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
                runner.cancel_job(canceled.job_id)
                client = TestClient(create_app())

                active_response = client.get("/api/jobs?status=ACTIVE")
                canceled_response = client.get("/api/jobs?status=CANCELED")
                query_response = client.get("/api/jobs?status=ACTIVE&q=queued")
                empty_query_response = client.get("/api/jobs?status=ACTIVE&q=canceled")
                invalid_response = client.get("/api/jobs?status=NOPE")

        self.assertEqual(200, active_response.status_code, active_response.text)
        active_jobs = active_response.json()["jobs"]
        self.assertEqual([queued.job_id], [job["job_id"] for job in active_jobs])

        self.assertEqual(200, canceled_response.status_code, canceled_response.text)
        canceled_jobs = canceled_response.json()["jobs"]
        self.assertEqual([canceled.job_id], [job["job_id"] for job in canceled_jobs])

        self.assertEqual(200, query_response.status_code, query_response.text)
        query_jobs = query_response.json()["jobs"]
        self.assertEqual([queued.job_id], [job["job_id"] for job in query_jobs])

        self.assertEqual(200, empty_query_response.status_code, empty_query_response.text)
        self.assertEqual([], empty_query_response.json()["jobs"])

        self.assertEqual(400, invalid_response.status_code)

    def test_cancel_queued_job_updates_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                runner = build_job_runner()
                job = runner.create_job(
                    ReviewRequest(
                        paper_path=self._write_paper(tmp, "cancel.md"),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        output_language=OutputLanguage.ZH,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
                client = TestClient(create_app())

                cancel_response = client.post(f"/api/jobs/{job.job_id}/cancel")
                status_response = client.get(f"/api/jobs/{job.job_id}")
                summary_response = client.get("/api/jobs/summary")

        self.assertEqual(200, cancel_response.status_code, cancel_response.text)
        canceled = cancel_response.json()
        self.assertEqual("CANCELED", canceled["status"])
        self.assertEqual("ReviewJobCanceled", canceled["error"]["error_type"])
        self.assertEqual(0, canceled["progress"]["percent"])
        self.assertEqual([], canceled["progress"]["active_nodes"])
        self.assertIsNone(canceled["progress"]["next_node"])

        self.assertEqual(200, status_response.status_code, status_response.text)
        canceled_status = status_response.json()
        self.assertEqual("CANCELED", canceled_status["status"])
        self.assertEqual([], canceled_status["progress"]["active_nodes"])
        self.assertIsNone(canceled_status["progress"]["next_node"])

        self.assertEqual(200, summary_response.status_code, summary_response.text)
        summary = summary_response.json()
        self.assertEqual(0, summary["active_count"])
        self.assertEqual(1, summary["canceled_count"])

    def test_terminal_job_progress_does_not_expose_stale_running_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                runner = build_job_runner()
                job = runner.create_job(
                    ReviewRequest(
                        paper_path=self._write_paper(tmp, "stale-running.md"),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        output_language=OutputLanguage.ZH,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
                runner.store.update(
                    job.job_id,
                    status=ReviewJobStatus.CANCELED,
                    nodes={"doc_parse": {"node": "doc_parse", "status": "RUNNING"}},
                )
                client = TestClient(create_app())
                response = client.get(f"/api/jobs/{job.job_id}")

        self.assertEqual(200, response.status_code, response.text)
        progress = response.json()["progress"]
        self.assertEqual([], progress["active_nodes"])
        self.assertIsNone(progress["next_node"])

    def test_cancel_finished_job_returns_409(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                runner = build_job_runner()
                job = runner.create_job(
                    ReviewRequest(
                        paper_path=self._write_paper(tmp, "finished.md"),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        output_language=OutputLanguage.ZH,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
                runner.store.update(job.job_id, status=ReviewJobStatus.SUCCEEDED, run_id="done")
                client = TestClient(create_app())
                response = client.post(f"/api/jobs/{job.job_id}/cancel")

        self.assertEqual(409, response.status_code)

    def test_retry_finished_job_creates_new_job_from_same_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                runner = build_job_runner()
                source = runner.create_job(
                    ReviewRequest(
                        paper_path=self._write_paper(tmp, "retry.md"),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        output_language=OutputLanguage.ZH,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
                runner.store.update(source.job_id, status=ReviewJobStatus.CANCELED)
                client = TestClient(create_app())

                retry_response = client.post(f"/api/jobs/{source.job_id}/retry")
                jobs_response = client.get("/api/jobs")

        self.assertEqual(202, retry_response.status_code, retry_response.text)
        retried = retry_response.json()
        self.assertNotEqual(source.job_id, retried["job_id"])
        self.assertEqual("QUEUED", retried["status"])
        self.assertEqual("retry.md", Path(retried["request"]["paper_path"]).name)
        self.assertEqual("QUICK_REVIEW", retried["request"]["review_mode"])

        self.assertEqual(200, jobs_response.status_code, jobs_response.text)
        statuses = {job["job_id"]: job["status"] for job in jobs_response.json()["jobs"]}
        self.assertEqual("CANCELED", statuses[source.job_id])
        self.assertIn(retried["job_id"], statuses)

    def test_retry_active_job_returns_409(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                runner = build_job_runner()
                job = runner.create_job(
                    ReviewRequest(
                        paper_path=self._write_paper(tmp, "active.md"),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        output_language=OutputLanguage.ZH,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
                client = TestClient(create_app())
                response = client.post(f"/api/jobs/{job.job_id}/retry")

        self.assertEqual(409, response.status_code)

    def test_library_lists_completed_job_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                created = client.post(
                    "/api/jobs",
                    json={
                        "paper_path": self._write_paper(tmp, "library.md"),
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                ).json()

                response = client.get("/api/library")

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertGreaterEqual(body["count"], 1)
        final_report = next(item for item in body["artifacts"] if item["name"] == "final_report.md")
        self.assertEqual(created["job_id"], final_report["job_id"])
        self.assertEqual("SUCCEEDED", final_report["job_status"])
        self.assertEqual("AAAI", final_report["venue_code"])
        self.assertEqual("CCFA", final_report["venue_collection"])
        self.assertEqual("QUICK_REVIEW", final_report["review_mode"])
        self.assertEqual(f"/api/jobs/{created['job_id']}/artifacts/final_report.md", final_report["download_url"])

    def test_library_lists_completed_review_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                created = client.post(
                    "/api/jobs",
                    json={
                        "paper_path": self._write_paper(tmp, "library-run.md"),
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                ).json()

                response = client.get("/api/library/runs")

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertGreaterEqual(body["artifact_count"], 1)
        run = body["runs"][0]
        self.assertEqual(created["job_id"], run["job_id"])
        self.assertEqual("AAAI", run["venue_code"])
        self.assertEqual("CCFA", run["venue_collection"])
        self.assertEqual("QUICK_REVIEW", run["review_mode"])
        self.assertEqual("final_report.md", run["primary_report_name"])
        self.assertEqual(f"/api/jobs/{created['job_id']}/artifacts/final_report.md", run["primary_report_download_url"])
        self.assertIn("artifacts", run)
        self.assertIn("final_report.md", {artifact["name"] for artifact in run["artifacts"]})

    def test_library_deletes_selected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                created = client.post(
                    "/api/jobs",
                    json={
                        "paper_path": self._write_paper(tmp, "delete-artifacts.md"),
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                ).json()
                job_id = created["job_id"]
                delete_response = client.request(
                    "DELETE",
                    "/api/library/artifacts",
                    json={
                        "artifacts": [
                            {"job_id": job_id, "name": "final_decision.json"},
                            {"job_id": job_id, "name": "content_check.json"},
                        ]
                    },
                )
                library_response = client.get("/api/library")
                download_response = client.get(f"/api/jobs/{job_id}/artifacts/final_decision.json")

        self.assertEqual(200, delete_response.status_code, delete_response.text)
        delete_body = delete_response.json()
        self.assertEqual(2, delete_body["deleted_count"])
        self.assertEqual(0, delete_body["error_count"])

        self.assertEqual(200, library_response.status_code, library_response.text)
        remaining_names = {item["name"] for item in library_response.json()["artifacts"]}
        self.assertNotIn("final_decision.json", remaining_names)
        self.assertNotIn("content_check.json", remaining_names)
        self.assertEqual(404, download_response.status_code)

    def test_library_deletes_selected_review_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            with patch.dict(os.environ, {"DATA_DIR": str(data_dir), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                created = client.post(
                    "/api/jobs",
                    json={
                        "paper_path": self._write_paper(tmp, "delete-run.md"),
                        "review_mode": "QUICK_REVIEW",
                        "output_language": "zh",
                        "venue_domain": "CS",
                        "venue_collection": "CCFA",
                        "venue_code": "AAAI",
                    },
                ).json()
                job_id = created["job_id"]
                completed = client.get(f"/api/jobs/{job_id}").json()
                artifact_dir = Path(completed["artifact_dir"])

                delete_response = client.request(
                    "DELETE",
                    "/api/library/runs",
                    json={"job_ids": [job_id]},
                )
                job_response = client.get(f"/api/jobs/{job_id}")
                library_response = client.get("/api/library/runs")

        self.assertEqual(200, delete_response.status_code, delete_response.text)
        delete_body = delete_response.json()
        self.assertEqual(1, delete_body["deleted_count"])
        self.assertEqual(0, delete_body["error_count"])
        self.assertGreaterEqual(delete_body["deleted"][0]["artifact_count"], 1)
        self.assertFalse(artifact_dir.exists())
        self.assertEqual(404, job_response.status_code)
        self.assertEqual(0, library_response.json()["count"])

    def test_get_missing_job_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"DATA_DIR": str(Path(tmp) / "data"), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                response = client.get("/api/jobs/missing")

        self.assertEqual(404, response.status_code)

    def _write_paper(self, directory: str, name: str) -> str:
        path = Path(directory) / name
        path.write_text(
            "History Paper\n\nAbstract\nA small paper for history testing.\n\n1 Introduction\nContent.",
            encoding="utf-8",
        )
        return str(path)

    def test_missing_job_report_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"DATA_DIR": str(Path(tmp) / "data"), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                response = client.get("/api/jobs/missing/report")

        self.assertEqual(404, response.status_code)

    def test_missing_job_diagnostics_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"DATA_DIR": str(Path(tmp) / "data"), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                response = client.get("/api/jobs/missing/diagnostics")

        self.assertEqual(404, response.status_code)

    def test_missing_job_usage_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"DATA_DIR": str(Path(tmp) / "data"), "LLM_PROVIDER": "mock"}):
                client = TestClient(create_app())
                response = client.get("/api/jobs/missing/usage")

        self.assertEqual(404, response.status_code)


if __name__ == "__main__":
    unittest.main()
