from pathlib import Path

from coursesmith.use_cases.shared.ports.prompts_port import PromptsPort


class PromptsAdapter(PromptsPort):
    def __init__(self, base_path: Path):
        self._base_path = base_path

    def get_prompt(self, name: str, version: int) -> str:
        prompt_file = self._base_path / name / f"v{version}.prompt.txt"
        return prompt_file.read_text(encoding="utf-8")
