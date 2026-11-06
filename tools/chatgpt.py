from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from cloro_api import answer_text, ask


class CloroChatGPTTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        output = ask(self.runtime.credentials.get("api_key"), "chatgpt", tool_parameters)
        yield self.create_text_message(answer_text(output))
        yield self.create_json_message(output)
