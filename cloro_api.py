"""Calls to the cloro API and conversion of its responses to tool output.

The provider and the four tools share this module. A tool file must hold
only one Tool subclass, so the shared code is here and not in tools/.
"""

from typing import Any

import requests

API_BASE = "https://api.cloro.dev"
USER_AGENT = "cloro-dify-plugin/0.0.1"

# Seconds to wait for cloro. A sync AI answer can take some minutes, so the
# answer timeout is near the plugin limit (MAX_REQUEST_TIMEOUT in main.py).
CREDENTIALS_TIMEOUT = 30
SEARCH_TIMEOUT = 120
ANSWER_TIMEOUT = 290

DEFAULT_COUNTRY = "US"
MAX_INPUT_LENGTH = 10000

STATUS_MESSAGES = {
    401: "The API key is not valid.",
    403: "Not enough credits.",
    429: "Too many requests at the same time. Try again soon.",
}


class CloroError(Exception):
    """An error message that is safe to show to the user and to the model."""


def _api_key(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CloroError("A cloro API key is required.")
    return value.strip()


def _error_message(response: requests.Response) -> str:
    """Make a message from {"error": {"code", "message"}}. The key is never in it."""
    code, message = "", ""
    try:
        error = response.json().get("error") or {}
        code = str(error.get("code") or "")
        message = str(error.get("message") or "")
    except (ValueError, AttributeError):
        pass
    if not message:
        message = STATUS_MESSAGES.get(response.status_code, "The request failed.")
    label = f"cloro error {response.status_code}" + (f" ({code})" if code else "")
    return f"{label}: {message[:500]}"


def _request(method: str, path: str, api_key: Any, body: dict | None, timeout: int) -> Any:
    key = _api_key(api_key)
    try:
        response = requests.request(
            method,
            API_BASE + path,
            headers={"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT},
            json=body,
            timeout=timeout,
        )
    except requests.Timeout:
        raise CloroError("cloro did not answer in time. Try again.") from None
    except requests.RequestException:
        raise CloroError("Could not connect to api.cloro.dev. Check the network.") from None
    if response.status_code >= 400:
        raise CloroError(_error_message(response))
    try:
        return response.json()
    except ValueError:
        raise CloroError("cloro sent a response that is not JSON.") from None


def get_credits(api_key: Any) -> dict:
    """GET /v1/credits. It costs no credits, so it is the credential check."""
    return _request("GET", "/v1/credits", api_key, None, CREDENTIALS_TIMEOUT)


def monitor(api_key: Any, engine: str, body: dict, timeout: int) -> dict:
    """POST /v1/monitor/<engine> (sync) and return the "result" object."""
    data = _request("POST", f"/v1/monitor/{engine}", api_key, body, timeout)
    if not isinstance(data, dict) or not data.get("success") or not isinstance(data.get("result"), dict):
        raise CloroError("cloro sent a response without a result.")
    return data["result"]


# Tool inputs


def required_text(params: dict, name: str, label: str) -> str:
    value = params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise CloroError(f"{label} is required.")
    value = value.strip()
    if len(value) > MAX_INPUT_LENGTH:
        raise CloroError(f"{label} can have a maximum of {MAX_INPUT_LENGTH} characters.")
    return value


def country_code(params: dict) -> str:
    """Two-letter ISO 3166-1 country code, in upper case. The default is US."""
    value = params.get("country")
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_COUNTRY
    if not isinstance(value, str) or len(value.strip()) != 2 or not value.strip().isalpha():
        raise CloroError("Country must be a two-letter country code, for example US, GB or DE.")
    return value.strip().upper()


# Tool output


def _usable_url(url: Any) -> bool:
    """False for an empty link, a Google /goto redirect or a Google search or shopping page."""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False
    path = url.split("?", 1)[0]
    return "google.com/goto" not in path and "google.com/search" not in path


def answer_sources(result: dict) -> list[dict]:
    """The sources of an AI answer. All sources count as cited."""
    sources = []
    for item in result.get("sources") or []:
        if not isinstance(item, dict) or not _usable_url(item.get("url")):
            continue
        sources.append(
            {
                "position": item.get("position"),
                "title": item.get("label") or "",
                "url": item["url"],
            }
        )
    return sources


def answer_output(result: dict) -> dict:
    """Output of the ChatGPT, AI Mode and Gemini tools."""
    return {
        "text": result.get("text") or "",
        "markdown": result.get("markdown") or "",
        "sources": answer_sources(result),
    }


def google_output(result: dict) -> dict:
    """Output of the Google Search tool."""
    organic = []
    for item in result.get("organicResults") or []:
        if not isinstance(item, dict) or not _usable_url(item.get("link")):
            continue
        organic.append(
            {
                "position": item.get("position"),
                "title": item.get("title") or "",
                "link": item["link"],
                "snippet": item.get("snippet") or "",
            }
        )
    output: dict[str, Any] = {"organic_results": organic}
    overview = result.get("aioverview")
    if isinstance(overview, dict):
        output["ai_overview"] = {
            "text": overview.get("text") or "",
            "sources": answer_sources(overview),
        }
    return output


def ask(api_key: Any, engine: str, params: dict) -> dict:
    """Send a prompt to chatgpt, aimode or gemini. Return the tool's JSON output."""
    prompt = required_text(params, "prompt", "Prompt")
    country = country_code(params)
    body = {"prompt": prompt, "country": country, "include": {"markdown": True}}
    result = monitor(api_key, engine, body, ANSWER_TIMEOUT)
    return {"prompt": prompt, "country": country, **answer_output(result)}


def search_google(api_key: Any, params: dict) -> dict:
    """Run a Google search. Return the tool's JSON output."""
    query = required_text(params, "query", "Query")
    country = country_code(params)
    with_overview = params.get("include_ai_overview") is True
    body: dict[str, Any] = {"query": query, "country": country}
    if with_overview:
        body["include"] = {"aioverview": True}
    output = google_output(monitor(api_key, "google", body, SEARCH_TIMEOUT))
    if with_overview and "ai_overview" not in output:
        output["ai_overview"] = {"text": "", "sources": []}
    return {"query": query, "country": country, **output}


def _source_lines(sources: list[dict]) -> list[str]:
    return [f"{index}. {s['title'] or s['url']}: {s['url']}" for index, s in enumerate(sources, 1)]


def answer_text(output: dict) -> str:
    """Plain text for an agent: the answer, then the numbered sources."""
    lines = [output["markdown"] or output["text"] or "(The answer is empty.)"]
    if output["sources"]:
        lines += ["", "Sources:"] + _source_lines(output["sources"])
    return "\n".join(lines)


def google_text(output: dict) -> str:
    """Plain text for an agent: the AI Overview (if any), then the results."""
    lines: list[str] = []
    overview = output.get("ai_overview")
    if overview is not None:
        lines += ["AI Overview:", overview["text"] or "(Google showed no AI Overview.)"]
        if overview["sources"]:
            lines += ["", "AI Overview sources:"] + _source_lines(overview["sources"])
        lines.append("")
    lines.append("Search results:")
    if not output["organic_results"]:
        lines.append("(No results.)")
    for item in output["organic_results"]:
        lines.append(f"{item['position']}. {item['title']}: {item['link']}")
        if item["snippet"]:
            lines.append(f"   {item['snippet']}")
    return "\n".join(lines)
