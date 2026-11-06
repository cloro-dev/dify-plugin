from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from cloro_api import CloroError, get_credits


class CloroProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        # GET /v1/credits costs no credits. It fails when the key is not valid.
        try:
            get_credits(credentials.get("api_key"))
        except CloroError as error:
            raise ToolProviderCredentialValidationError(str(error)) from None
