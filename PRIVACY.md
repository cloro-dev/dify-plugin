# Privacy policy

This plugin sends the inputs of the tool that you run (the prompt or the search query, the country and the AI Overview setting) to the cloro API at `api.cloro.dev`. cloro uses these inputs to do the request. The API key goes only in the HTTPS `Authorization: Bearer` header to this host. The provider credential check sends the key to `GET /v1/credits`.

The plugin does not collect other user data. It does not write files, does not use a database and does not keep requests or responses after the tool run. It does not log API keys, inputs or responses. Error messages contain only the error text from cloro, not the API key. The tool output goes back to Dify, where the settings of your Dify application control history and logs.

cloro is the third party that receives the data. The cloro privacy policy tells how cloro processes, stores and keeps data: https://cloro.dev/privacy/?utm_source=dify-plugins&utm_medium=byok

Contact: info@cloro.dev
