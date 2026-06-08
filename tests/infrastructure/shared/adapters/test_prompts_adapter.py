from coursesmith import RESOURCES_DIR
from coursesmith.infrastructure.shared.adapters.outbound.prompts_adapter import PromptsAdapter


def test_course_outline_v1_renders_topic():
    adapter = PromptsAdapter(base_path=RESOURCES_DIR)
    prompt = adapter.get_prompt("course_outline", 1)
    assert "{topic}" in prompt
