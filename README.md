# cloro for Dify

cloro is the API for AI answers. This plugin adds six tools from [cloro](https://cloro.dev?utm_source=dify-plugins&utm_medium=byok) to Dify agents, chatflows and workflows:

- **ChatGPT Answer**: the answer that ChatGPT gives to a prompt, with the sources that it cites.
- **Google AI Mode Answer**: the answer that Google AI Mode gives to a prompt, with its sources.
- **Gemini Answer**: the answer that Gemini gives to a prompt, with its sources.
- **Bing AI Mode Answer**: the answer that Bing AI Mode gives to a prompt, with its sources.
- **Google Search**: the Google organic results and ads for a query. As an option, the tool also gets the Google AI Overview text and its sources.
- **Bing Search**: the Bing organic results and ads for a query. As an option, the tool also gets the text of the Bing AI Overview (the AI summary at the top of the results page) and its sources.

Each tool sends the request from the country that you select. Use the tools to see what AI assistants, Google and Bing tell people about a topic, a brand or a product, and which pages they cite.

Source: https://github.com/cloro-dev/dify-plugin
Contact: info@cloro.dev

## Setup

1. Install **cloro** from the Dify Marketplace.
2. Create a cloro account and an API key at https://dashboard.cloro.dev/api-keys?utm_source=dify-plugins&utm_medium=byok. The free plan has 500 credits a month.
3. In Dify, open **Tools**, select **cloro**, click **Authorize** and paste the API key. The plugin checks the key with `GET /v1/credits`, which costs no credits.
4. Add the tools that you need to an agent, a chatflow or a workflow.

## Usage

| Tool | Inputs | Credits per call |
| --- | --- | --- |
| ChatGPT Answer | Prompt, Country | 7 |
| Google AI Mode Answer | Prompt, Country | 6 |
| Gemini Answer | Prompt, Country | 6 |
| Bing AI Mode Answer | Prompt, Country | 6 |
| Google Search | Query, Country, Include AI Overview | 5, or 7 with the AI Overview |
| Bing Search | Query, Country, Include AI Overview | 5, or 7 with the AI Overview |

- **Prompt** of the Bing AI Mode tool and **Query** of the Bing Search tool can have a maximum of 3,500 characters after URL encoding, and fewer for non-Latin scripts. cloro rejects a longer text with error 400.
- **Country** is a two-letter country code, for example `US`, `GB` or `DE`. The default is `US`. The Bing tools do not support `CN`, `KR` and `RU`.
- **Include AI Overview** is a setting of the Google Search and Bing Search tools. Google and Bing do not show an AI Overview for all queries. When there is no AI Overview, the AI Overview text is empty.

The credit counts are for the synchronous API, which these tools use. Source: [cloro pricing by provider](https://cloro.dev/docs/guides/providers?utm_source=dify-plugins&utm_medium=byok).

### Output

Each tool returns two messages:

- **text**: the answer (Markdown) or the search results, then a numbered list of sources. Agents read this message.
- **json**: the same data as fields, for workflow variables.

JSON of the answer tools:

```json
{
  "prompt": "best project management tools",
  "country": "US",
  "text": "Plain text of the answer",
  "markdown": "Markdown of the answer",
  "sources": [{"position": 1, "title": "Page title", "url": "https://example.com/page"}]
}
```

JSON of Google Search and Bing Search:

```json
{
  "query": "best project management tools",
  "country": "US",
  "organic_results": [{"position": 1, "title": "Page title", "link": "https://example.com/page", "snippet": "Text from the page"}],
  "ads": [{"position": 1, "block_position": "rhs", "type": "SHOPPING_CARD", "title": "Product title", "link": "https://example.com/product", "price": "$12.57", "store": "Example"}],
  "ai_overview": {"text": "Text of the AI Overview", "sources": [{"position": 1, "title": "Page title", "url": "https://example.com/page"}]}
}
```

`ai_overview` is in the output only when **Include AI Overview** is on. `ads` has the text ads (`RESULT`) and the shopping cards (`SHOPPING_CARD`) on the page. An ad has only the fields that the page shows, and `description` is one of them. `ads` is empty when the page has no ads. The ads cost no extra credits. The tools do not return results whose link is empty or is a Google redirect (`google.com/goto`) link.

### Errors

The tool stops with the error message from cloro. Examples: `cloro error 401 (INVALID_API_KEY_FORMAT)` for a key that is not valid, `cloro error 403 (INSUFFICIENT_CREDITS)` when the account has no credits, and `cloro error 429` when too many requests run at the same time.

## Connection requirements

The plugin connects only to `https://api.cloro.dev` on port 443. The Dify plugin daemon must be able to make outbound HTTPS requests to this host. The API key goes only in the `Authorization: Bearer` header.

Timeouts: 30 seconds for the key check, 120 seconds for Google Search and Bing Search, and 290 seconds for the answer tools.

## Privacy

See [PRIVACY.md](PRIVACY.md).

## Development

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests
dify plugin package .
```

The tests replace all HTTP calls with stubs. They do not use an API key or credits.
