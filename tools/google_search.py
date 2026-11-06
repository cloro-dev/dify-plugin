from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from cloro_api import google_text, search_google


class CloroGoogleSearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        output = search_google(self.runtime.credentials.get("api_key"), tool_parameters)
        yield self.create_text_message(google_text(output))
        yield self.create_json_message(output)
