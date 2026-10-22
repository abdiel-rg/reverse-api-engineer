<mission>
{prompt}
</mission>

<output_directory>
{scripts_dir}
</output_directory>

## Browser capture and code generation

Use only OMP's JavaScript `eval` tool and its global `browser` facade for browser capture. Do not use the RAE Playwright MCP or OMP's browser relay. Open a fresh tab with relay and Tern disabled so they do not take over. Respect OMP's configured project approval policy; do not attempt to change approval settings or bypass an approval.

Capture traffic into this exact HAR file: `{har_path}`. The HAR must include requests from the mission's explicitly requested site. Follow this sequence in one JavaScript eval cell, adapting only the tab name and requested URL:

```javascript
const tab = await browser.open({{
  name: "rae-{run_id}",
  url: "about:blank",
  app: {{ relay: false, tern: false }},
  timeout: 120,
  {headed_option}
}});
await tab.harStart({{ content: "none" }});
await tab.goto("<URL from the mission>");
const savedHarPath = await tab.harStop({{ path: {har_path_json} }});
console.log(`Saved HAR: ${{savedHarPath}}`);
await tab.close();
```

Start HAR recording before navigating to the requested site. Do not follow links or navigate to any other host unless the mission explicitly requires it. Inspect the saved HAR and verify that it contains a request to the target domain before generating the client. If the browser API reports that it cannot start or an approval is denied, report the exact failure; do not fall back to a different browser or claim capture success.

Generate the requested client and supporting files in `{scripts_dir}`. Test the client against the captured API, then summarize the APIs found and whether execution succeeded.
