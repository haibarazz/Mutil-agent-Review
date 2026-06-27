import unittest

from src.core.prompts import PromptRepository
from src.infra.llm_router import load_llm_router_config
from src.infra.settings import load_settings


class PromptTests(unittest.TestCase):
    def test_loads_markdown_prompt(self) -> None:
        settings = load_settings()
        prompt = PromptRepository(settings.prompts_dir).load("ae_final")

        self.assertTrue((settings.prompts_dir / "ae_final.md").exists())
        self.assertIn("AE", prompt.system_prompt)
        self.assertIn("{{review1_result}}", prompt.user_prompt_template)

    def test_prompt_root_has_no_json_configs(self) -> None:
        settings = load_settings()

        self.assertEqual([], sorted(settings.prompts_dir.rglob("*.json")))

    def test_prompt_frontmatter_only_declares_name_and_model(self) -> None:
        settings = load_settings()
        forbidden_keys = {"temperature", "top_p", "max_completion_tokens", "thinking", "output"}

        for path in settings.prompts_dir.glob("*.md"):
            lines = path.read_text(encoding="utf-8").splitlines()
            frontmatter_end = lines[1:].index("---") + 1
            keys = {
                line.split(":", 1)[0].strip()
                for line in lines[1:frontmatter_end]
                if ":" in line
            }
            self.assertFalse(forbidden_keys & keys, path.name)

    def test_prompt_models_are_registered_in_llm_router_config(self) -> None:
        settings = load_settings()
        router_config = load_llm_router_config(settings.llm_config_path)
        prompts = PromptRepository(settings.prompts_dir)

        missing = []
        for path in settings.prompts_dir.glob("*.md"):
            prompt = prompts.load(path.stem)
            if prompt.model not in router_config.models:
                missing.append((prompt.name, prompt.model))

        self.assertEqual([], missing)

    def test_prompt_names_have_node_level_llm_policy(self) -> None:
        settings = load_settings()
        router_config = load_llm_router_config(settings.llm_config_path)
        prompts = PromptRepository(settings.prompts_dir)

        missing = []
        for path in settings.prompts_dir.glob("*.md"):
            prompt = prompts.load(path.stem)
            if prompt.name not in router_config.nodes:
                missing.append(prompt.name)

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
