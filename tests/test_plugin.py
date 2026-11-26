import ast
from pathlib import Path

import pytest
import requests
import yaml
from conftest import ROOT, load_fixture
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

import cloro_api
from cloro_api import CloroError, answer_sources
from provider.cloro import CloroProvider
from tools.aimode import CloroAIModeTool
from tools.bing_aimode import CloroBingAIModeTool
from tools.bing_search import CloroBingSearchTool
from tools.chatgpt import CloroChatGPTTool
from tools.gemini import CloroGeminiTool
from tools.google_search import CloroGoogleSearchTool

KEY = "test-key-not-real"


def run(tool_cls, params: dict) -> tuple[str, dict]:
    messages = list(tool_cls.from_credentials({"api_key": KEY}).invoke(params))
    assert [m.type.value for m in messages] == ["text", "json"]
    return messages[0].message.text, messages[1].message.json_object


# Provider


def test_credentials_check_calls_free_credits_endpoint(http):
    http.reply(200, load_fixture("credits.json"))
    CloroProvider()._validate_credentials({"api_key": KEY})
    call = http.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://api.cloro.dev/v1/credits"
    assert call["headers"]["Authorization"] == f"Bearer {KEY}"
    assert call["json"] is None
    assert call["timeout"] == 30


def test_credentials_check_rejects_bad_key_without_showing_it(http):
    http.reply(401, load_fixture("badkey.json"))
    with pytest.raises(ToolProviderCredentialValidationError) as error:
        CloroProvider()._validate_credentials({"api_key": KEY})
    assert "401" in str(error.value)
    assert "INVALID_API_KEY_FORMAT" in str(error.value)
    assert KEY not in str(error.value)


def test_credentials_check_needs_a_key(http):
    with pytest.raises(ToolProviderCredentialValidationError):
        CloroProvider()._validate_credentials({"api_key": "  "})
    assert http.calls == []


def test_network_error_has_a_clear_message(http):
    http.raise_error(requests.ConnectionError(f"failed with {KEY}"))
    with pytest.raises(ToolProviderCredentialValidationError) as error:
        CloroProvider()._validate_credentials({"api_key": KEY})
    assert "api.cloro.dev" in str(error.value)
    assert KEY not in str(error.value)


# Answer tools


@pytest.mark.parametrize(
    ("tool_cls", "engine"),
    [
        (CloroChatGPTTool, "chatgpt"),
        (CloroAIModeTool, "aimode"),
        (CloroGeminiTool, "gemini"),
        (CloroBingAIModeTool, "bing/aimode"),
    ],
)
def test_answer_tools_return_text_and_sources(http, tool_cls, engine):
    fixture = load_fixture(f"{engine.replace('/', '_')}.json")
    http.reply(200, fixture)
    text, data = run(tool_cls, {"prompt": " best rank tracker ", "country": "gb"})

    call = http.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == f"https://api.cloro.dev/v1/monitor/{engine}"
    assert call["json"] == {"prompt": "best rank tracker", "country": "GB", "include": {"markdown": True}}
    assert call["timeout"] == 290

    result = fixture["result"]
    assert data["prompt"] == "best rank tracker"
    assert data["country"] == "GB"
    assert data["text"] == result["text"]
    assert data["markdown"] == result["markdown"]
    assert [s["url"] for s in data["sources"]] == [s["url"] for s in result["sources"]]
    assert data["sources"][0] == {
        "position": result["sources"][0]["position"],
        "title": result["sources"][0]["label"],
        "url": result["sources"][0]["url"],
    }
    assert text.startswith(result["markdown"])
    assert "Sources:" in text
    assert result["sources"][0]["url"] in text


def test_country_defaults_to_us(http):
    http.reply(200, load_fixture("gemini.json"))
    run(CloroGeminiTool, {"prompt": "hello"})
    assert http.calls[0]["json"]["country"] == "US"


@pytest.mark.parametrize("country", ["USA", "1A", "U"])
def test_bad_country_is_rejected_before_the_request(http, country):
    with pytest.raises(CloroError, match="two-letter"):
        run(CloroChatGPTTool, {"prompt": "hello", "country": country})
    assert http.calls == []


def test_empty_prompt_is_rejected_before_the_request(http):
    with pytest.raises(CloroError, match="Prompt is required"):
        run(CloroAIModeTool, {"prompt": "   "})
    assert http.calls == []


def test_answer_without_sources(http):
    http.reply(200, {"success": True, "result": {"text": "Answer", "sources": [], "citationPills": [], "model": None}})
    text, data = run(CloroChatGPTTool, {"prompt": "hello"})
    assert text == "Answer"
    assert data["sources"] == []
    assert data["markdown"] == ""


def test_insufficient_credits_error(http):
    http.reply(403, {"success": False, "error": {"code": "INSUFFICIENT_CREDITS", "message": "Not enough credits"}})
    with pytest.raises(CloroError, match=r"cloro error 403 \(INSUFFICIENT_CREDITS\): Not enough credits"):
        run(CloroChatGPTTool, {"prompt": "hello"})


def test_error_without_json_body(http):
    http.reply(429, ValueError("not JSON"))
    with pytest.raises(CloroError, match="cloro error 429: Too many requests"):
        run(CloroGeminiTool, {"prompt": "hello"})


def test_response_without_success_is_an_error(http):
    http.reply(200, {"success": False})
    with pytest.raises(CloroError, match="without a result"):
        run(CloroGeminiTool, {"prompt": "hello"})


def test_timeout_has_a_clear_message(http):
    http.raise_error(requests.Timeout())
    with pytest.raises(CloroError, match="did not answer in time"):
        run(CloroChatGPTTool, {"prompt": "hello"})


# Google Search


def test_google_search_with_ai_overview(http):
    fixture = load_fixture("google.json")
    http.reply(200, fixture)
    text, data = run(CloroGoogleSearchTool, {"query": "best rank tracker", "include_ai_overview": True})

    call = http.calls[0]
    assert call["url"] == "https://api.cloro.dev/v1/monitor/google"
    assert call["json"] == {"query": "best rank tracker", "country": "US", "include": {"aioverview": True}}
    assert call["timeout"] == 120

    # The fixture has 3 normal results, 1 with an empty link and 1 with a /goto link.
    assert [r["position"] for r in data["organic_results"]] == [1, 2, 3]
    assert all("google.com/goto" not in r["link"] for r in data["organic_results"])
    overview = fixture["result"]["aioverview"]
    assert data["ai_overview"]["text"] == overview["text"]
    assert [s["url"] for s in data["ai_overview"]["sources"]] == [s["url"] for s in overview["sources"]]
    assert text.startswith("AI Overview:")
    assert "AI Overview sources:" in text
    assert "Search results:" in text
    assert fixture["result"]["organicResults"][0]["link"] in text


def test_google_search_without_ai_overview(http):
    http.reply(200, load_fixture("google-noaio.json"))
    text, data = run(CloroGoogleSearchTool, {"query": "best rank tracker", "country": "de"})
    assert http.calls[0]["json"] == {"query": "best rank tracker", "country": "DE"}
    assert "ai_overview" not in data
    assert len(data["organic_results"]) == 2
    assert text.startswith("Search results:")


def test_google_search_when_google_shows_no_ai_overview(http):
    http.reply(200, load_fixture("google-noaio.json"))
    text, data = run(CloroGoogleSearchTool, {"query": "q", "include_ai_overview": True})
    assert data["ai_overview"] == {"text": "", "sources": []}
    assert "(Google showed no AI Overview.)" in text


def test_google_search_needs_a_query(http):
    with pytest.raises(CloroError, match="Query is required"):
        run(CloroGoogleSearchTool, {"query": ""})
    assert http.calls == []


# Bing Search


def test_bing_search_with_ai_overview(http):
    fixture = load_fixture("bing.json")
    http.reply(200, fixture)
    text, data = run(
        CloroBingSearchTool, {"query": " best rank tracker ", "country": "gb", "include_ai_overview": True}
    )

    call = http.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.cloro.dev/v1/monitor/bing"
    assert call["json"] == {"query": "best rank tracker", "country": "GB", "include": {"aioverview": True}}
    assert call["timeout"] == 120

    # The fixture has 2 normal results and 1 with an empty link.
    assert data["query"] == "best rank tracker"
    assert data["country"] == "GB"
    assert [r["position"] for r in data["organic_results"]] == [1, 2]
    overview = fixture["result"]["aioverview"]
    assert data["ai_overview"]["text"] == overview["text"]
    assert [s["url"] for s in data["ai_overview"]["sources"]] == [s["url"] for s in overview["sources"]]
    assert text.startswith("AI Overview:")
    assert "AI Overview sources:" in text
    assert fixture["result"]["organicResults"][0]["link"] in text


def test_bing_search_without_ai_overview(http):
    http.reply(200, load_fixture("bing-noaio.json"))
    text, data = run(CloroBingSearchTool, {"query": "best rank tracker"})
    assert http.calls[0]["json"] == {"query": "best rank tracker", "country": "US"}
    assert "ai_overview" not in data
    assert len(data["organic_results"]) == 2
    assert text.startswith("Search results:")


def test_bing_search_when_bing_shows_no_ai_overview(http):
    http.reply(200, load_fixture("bing-noaio.json"))
    text, data = run(CloroBingSearchTool, {"query": "q", "include_ai_overview": True})
    assert data["ai_overview"] == {"text": "", "sources": []}
    assert "(Bing showed no AI Overview.)" in text


def test_bing_search_needs_a_query(http):
    with pytest.raises(CloroError, match="Query is required"):
        run(CloroBingSearchTool, {"query": "  "})
    assert http.calls == []


# Ads


@pytest.mark.parametrize("tool_cls", [CloroGoogleSearchTool, CloroBingSearchTool])
def test_search_returns_the_ads(http, tool_cls):
    fixture = load_fixture("bing-noaio.json")
    fixture["result"]["ads"] = [
        {
            "position": 1,
            "blockPosition": "top",
            "type": "RESULT",
            "title": "Rank tracker sale",
            "url": "https://shop.example/rank",
            "page": 1,
            "domain": "shop.example",
            "description": "Track ranks.",
        },
        {
            "position": 1,
            "blockPosition": "rhs",
            "type": "SHOPPING_CARD",
            "title": "SEO book",
            "url": "https://www.google.com/goto?url=x",
            "price": {"value": 29, "currency": "$", "raw": "$29.00"},
            "store": "Shop",
        },
        {},
    ]
    http.reply(200, fixture)
    text, data = run(tool_cls, {"query": "best rank tracker"})
    assert http.calls[0]["json"] == {"query": "best rank tracker", "country": "US"}
    assert data["ads"] == [
        {
            "position": 1,
            "block_position": "top",
            "type": "RESULT",
            "title": "Rank tracker sale",
            "link": "https://shop.example/rank",
            "description": "Track ranks.",
        },
        {
            "position": 1,
            "block_position": "rhs",
            "type": "SHOPPING_CARD",
            "title": "SEO book",
            "price": "$29.00",
            "store": "Shop",
        },
        {},
    ]
    assert len(data["organic_results"]) == 2
    assert "Ads:\n- [RESULT top 1] Rank tracker sale: https://shop.example/rank\n   Track ranks." in text
    assert "- [SHOPPING_CARD rhs 1] SEO book\n   $29.00 | Shop" in text


def test_search_without_ads(http):
    http.reply(200, load_fixture("bing-noaio.json"))
    text, data = run(CloroBingSearchTool, {"query": "q"})
    assert data["ads"] == []
    assert "Ads:" not in text


# Plugin files


def test_plugin_registers_provider_and_tools():
    from dify_plugin import DifyPluginEnv
    from dify_plugin.core.plugin_registration import PluginRegistration

    registration = PluginRegistration(DifyPluginEnv())
    assert registration.get_tool_provider_cls("cloro").__name__ == "CloroProvider"
    expected = {
        "google_search": "CloroGoogleSearchTool",
        "bing_search": "CloroBingSearchTool",
        "chatgpt": "CloroChatGPTTool",
        "aimode": "CloroAIModeTool",
        "gemini": "CloroGeminiTool",
        "bing_aimode": "CloroBingAIModeTool",
    }
    for name, class_name in expected.items():
        assert registration.get_tool_cls("cloro", name).__name__ == class_name


def test_each_tool_file_has_one_tool_class():
    for path in Path(ROOT, "tools").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        assert len(classes) == 1, path.name


def test_manifest_and_tool_files_agree():
    manifest = yaml.safe_load(Path(ROOT, "manifest.yaml").read_text(encoding="utf-8"))
    provider = yaml.safe_load(Path(ROOT, "provider/cloro.yaml").read_text(encoding="utf-8"))
    # meta.version is the version of the manifest format, not of the plugin.
    assert manifest["meta"]["version"] == "0.0.1"
    assert cloro_api.USER_AGENT == f"cloro-dify-plugin/{manifest['version']}"
    assert manifest["author"] == provider["identity"]["author"] == "cloro-dev"
    assert manifest["network"]["domains"] == ["api.cloro.dev"]
    assert Path(ROOT, "_assets", manifest["icon"]).is_file()
    for tool_file in provider["tools"]:
        tool = yaml.safe_load(Path(ROOT, tool_file).read_text(encoding="utf-8"))
        assert tool["identity"]["author"] == "cloro-dev"
        assert Path(ROOT, tool["extra"]["python"]["source"]).is_file()


def test_no_promoted_engines_outside_scope():
    # Only ChatGPT, Google AI Mode, Gemini, Bing AI Mode, Google Search and Bing Search are in this plugin.
    # "Copilot Search in Bing" is the other name of Bing AI Mode, so it is allowed.
    names = ("perplexity", "copilot", "grok")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".venv" in path.parts or ".git" in path.parts or path.suffix == ".pyc":
            continue
        if path.suffix in {".py", ".yaml", ".md", ".txt"} and path.name != "test_plugin.py":
            text = path.read_text(encoding="utf-8").lower().replace("copilot search in bing", "")
            assert not any(n in text for n in names), path


def test_google_search_and_shopping_links_are_not_sources():
    sources = answer_sources(
        {
            "sources": [
                {"position": 1, "label": "AWS", "url": "https://aws.amazon.com/what-is/rag/"},
                {"position": 2, "label": "Product", "url": "https://www.google.com/search?q=product&ibp=oshop"},
            ]
        }
    )
    assert [s["url"] for s in sources] == ["https://aws.amazon.com/what-is/rag/"]
