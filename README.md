# cloro for Dify

This plugin adds four tools from [cloro](https://cloro.dev?utm_source=dify-plugins&utm_medium=byok) to Dify agents, chatflows and workflows:

- **ChatGPT Answer**: the answer that ChatGPT gives to a prompt, with the sources that it cites.
- **Google AI Mode Answer**: the answer that Google AI Mode gives to a prompt, with its sources.
- **Gemini Answer**: the answer that Gemini gives to a prompt, with its sources.
- **Google Search**: the Google organic results for a query. As an option, the tool also gets the Google AI Overview text and its sources.

Each tool sends the request from the country that you select. Use the tools to see what AI assistants and Google tell people about a topic, a brand or a product, and which pages they cite.

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
| Google Search | Query, Country, Include AI Overview | 5, or 7 with the AI Overview |

- **Country** is a two-letter country code, for example `US`, `GB` or `DE`. The default is `US`.
- **Include AI Overview** is a setting of the Google Search tool. Google does not show an AI Overview for all queries. When there is no AI Overview, the AI Overview text is empty.

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

JSON of Google Search:

```json
{
  "query": "best project management tools",
  "country": "US",
  "organic_results": [{"position": 1, "title": "Page title", "link": "https://example.com/page", "snippet": "Text from the page"}],
  "ai_overview": {"text": "Text of the AI Overview", "sources": [{"position": 1, "title": "Page title", "url": "https://example.com/page"}]}
}
```

`ai_overview` is in the output only when **Include AI Overview** is on. The tools do not return results whose link is empty or is a Google redirect (`google.com/goto`) link.

### Errors

The tool stops with the error message from cloro. Examples: `cloro error 401 (INVALID_API_KEY_FORMAT)` for a key that is not valid, `cloro error 403 (INSUFFICIENT_CREDITS)` when the account has no credits, and `cloro error 429` when too many requests run at the same time.

## Connection requirements

The plugin connects only to `https://api.cloro.dev` on port 443. The Dify plugin daemon must be able to make outbound HTTPS requests to this host. The API key goes only in the `Authorization: Bearer` header.

Timeouts: 30 seconds for the key check, 120 seconds for Google Search and 290 seconds for the answer tools.

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
