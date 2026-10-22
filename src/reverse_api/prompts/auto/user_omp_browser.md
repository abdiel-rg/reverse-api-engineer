<mission>
{prompt}
</mission>

{requested_start_url_block}

<output_directory>
{scripts_dir}
</output_directory>

## Browser capture and code generation

Use only OMP's JavaScript `eval` tool and its global `browser` facade for browser capture, honoring OMP's configured browser route. Do not use the RAE Playwright MCP. Open a fresh named tab without an `app` or `app.target` option so OMP selects the browser and no existing tab is adopted. Respect OMP's configured project approval policy; do not attempt to change approval settings or bypass an approval.

Capture traffic into this exact HAR file: `{har_path}`. {starting_url_instruction} If no starting URL is supplied, derive the target from the mission's named site or service; replace the `tab.goto` placeholder with that concrete HTTP(S) URL. Do not choose an unrelated host or invent a target. If the mission does not identify a safe target clearly, stop and report the blocker. Complete the requested mission interactions while recording; do not stop HAR immediately after the initial page load unless that fulfills the mission. Do not follow links or navigate to other hosts unless the mission requires it. If the requested action requires credentials or approval that are unavailable, stop and report the exact blocker.

Use `content: "text"` to retain textual response bodies needed to infer API schemas; do not capture binary bodies. Text responses may contain private or sensitive data, so treat the local HAR as sensitive. Do not echo response data or copy credentials, cookies, tokens, session data, or personal data into generated files, logs, or summaries.

Follow this sequence in one JavaScript eval cell, adapting only the tab name and mission-specific interactions:

```javascript
let tab;
let recording = false;
try {{
  tab = await browser.open({{
    name: "rae-{run_id}",
    url: "about:blank",
    timeout: 120,
    {headed_option}
  }});
  await tab.harStart({{ content: "text" }});
  recording = true;
  await tab.goto({requested_url_json});
  // Perform the mission-requested interactions here while HAR recording remains active.
  const savedHarPath = await tab.harStop({{ path: {har_path_json} }});
  recording = false;
  console.log(`Saved HAR: ${{savedHarPath}}`);
}} finally {{
  if (tab) {{
    if (recording) {{
      try {{
        await tab.harStop({{ path: {har_path_json} }});
      }} catch {{}}
    }}
    try {{
      await tab.close();
    }} catch {{}}
  }}
}}
```

Start HAR recording before navigating. When a supplied or unambiguous starting URL exists, verify that the saved HAR contains a request to its exact host before generating the client. Otherwise, verify that the HAR contains a valid request to the target selected from the mission. If the browser API reports that it cannot start or an approval is denied, report the exact failure; do not fall back to another browser or claim capture success.

Generate the requested client and supporting files in `{scripts_dir}`. Test the client against the captured API, then summarize the APIs found and whether execution succeeded.
