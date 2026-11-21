from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from cloro_api import search, search_text


class CloroGoogleSearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        output = search(self.runtime.credentials.get("api_key"), "google", tool_parameters)
        yield self.create_text_message(search_text(output, "Google"))
        yield self.create_json_message(output)
