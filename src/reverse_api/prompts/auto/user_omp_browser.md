<mission>
{prompt}
</mission>

{requested_start_url_block}

<output_directory>
{scripts_dir}
</output_directory>

## Browser capture and code generation

Use only OMP's JavaScript `eval` tool and its global `browser` facade for browser capture, honoring OMP's configured browser route. Do not use the RAE Playwright MCP. Open a fresh named tab without an `app` or `app.target` option so OMP selects the browser and no existing tab is adopted. Respect OMP's configured project approval policy; do not attempt to change approval settings or bypass an approval. For page structure use `await tab.observe()` or `await tab.ariaSnapshot()`; the OMP facade has no `tab.snapshot()` method.

Capture bounded, already-received API responses into this exact HAR file: `{har_path}`. {starting_url_instruction} If no starting URL is supplied, derive the target from the mission's named site or service; replace the `tab.goto` placeholder with that concrete HTTP(S) URL. Do not choose an unrelated host or invent a target. If the mission does not identify a safe target clearly, stop and report the blocker. Complete only authorized read-only mission interactions. Do not follow links or navigate to other hosts unless the mission requires it. If credentials or approval unavailable, stop and report the blocker.

Response bodies may include private data. Keep them in memory only; never print, log, or persist unredacted response data, URLs/query values, headers, cookies, tokens, session data, or feed/personal data.

Use two separate JavaScript Eval calls. Do not retain a JavaScript `tab` handle between calls; look up the named tab afresh in call 2.

### Eval call 1: open, navigate, inspect

```javascript
const tab = await browser.open({{
  name: "rae-{run_id}",
  url: "about:blank",
  timeout: 120,
  persist: true,
  {headed_option}
  {allowed_domains_option}
}});
await tab.goto({requested_url_json});
// Perform only mission-authorized read-only inspection; do not click or submit.
```

### Eval call 2: harvest completed GET JSON responses and write a redacted HAR

```javascript
const tabName = "rae-{run_id}";
const openTabs = await browser.tabs();
if (!openTabs.some(({{ name }}) => name === tabName)) throw new Error("Capture tab is not open.");
const tab = browser.tab(tabName);
const requestedDomains = {allowed_domains_json};
// When no explicit domain was resolved, anchor capture to the actual target opened in call 1.
const targetUrl = new URL(tab.url());
if (!["http:", "https:"].includes(targetUrl.protocol)) throw new Error("Capture target is not HTTP(S).");
const allowedDomains = requestedDomains.length ? requestedDomains : [targetUrl.hostname];
const isAllowedHost = host => allowedDomains.some(domain =>
  domain.startsWith("*.") ? host.endsWith(`.${{domain.slice(2)}}`) : host === domain
);
const requestOptions = {{ type: ["fetch", "xhr", "document"], method: "GET", status: "2xx", limit: 50 }};
const isJsonGet = r =>
  r.method === "GET" &&
  Number(r.status) >= 200 && Number(r.status) < 300 &&
  Number.isFinite(Number(r.sizes?.responseBody)) &&
  Number(r.sizes.responseBody) > 0 && Number(r.sizes.responseBody) <= 1024 * 1024 &&
  Object.entries(r.responseHeaders || {{}}).some(([k, v]) =>
    k.toLowerCase() === "content-type" && /(?:application\/json|\+json)/i.test(v)
  );
let candidates = (await tab.requests(requestOptions))
  .filter(r => isAllowedHost(new URL(r.url).hostname) && isJsonGet(r))
  .slice(0, 3);
for (let attempt = 0; !candidates.length && attempt < 3; attempt++) {{
  // At most three viewport scrolls may trigger lazy-loaded read-only API requests; never click.
  await tab.wheel(0, 600);
  await new Promise(resolve => setTimeout(resolve, 5000));
  candidates = (await tab.requests(requestOptions))
    .filter(r => isAllowedHost(new URL(r.url).hostname) && isJsonGet(r))
    .slice(0, 3);
}}
const idLikeParents = new Set(["in", "pub", "people", "feed-member", "feed-member-id", "users", "user", "profiles", "profile", "members", "member", "entities", "entity"]);
const staticPathSegments = new Set(["company", "companies", "school", "schools", "jobs", "groups", "events", "feed", "pulse", "learning"]);
const redactPath = pathname => pathname.split("/").map((segment, index, parts) => {{
  const parent = parts[index - 1]?.toLowerCase();
  return /^(?:\d+|urn:|[A-Fa-f0-9]{{12,}}|[A-Za-z0-9_-]{{24,}})/.test(segment) ||
    (idLikeParents.has(parent) && !staticPathSegments.has(segment.toLowerCase())) ? ":id" : segment;
}}).join("/");
if (redactPath("/in/alice") !== "/in/:id" || redactPath("/users/alice") !== "/users/:id") {{
  throw new Error("Synthetic short-profile-slug redaction check failed.");
}}
const dynamicKeyParents = new Set(["user", "users", "profile", "profiles", "member", "members", "entity", "entities", "record", "records", "byid", "bykey", "byusername", "byuser", "byprofile", "byentity", "byrecord"]);
const stableSchemaKeys = new Set([
  "id", "type", "name", "title", "description", "url", "href", "text", "content", "body",
  "status", "createdAt", "updatedAt", "firstName", "lastName", "username", "email", "count",
  "total", "items", "results", "data", "attributes", "relationships", "metadata", "links",
  "next", "previous", "page", "limit", "offset", "value", "label", "key", "code", "slug",
  "kind", "role", "company", "companyName", "location", "author", "user", "users", "profile",
  "profiles", "member", "members", "image", "avatar", "date", "timestamp", "startDate", "endDate"
]);
const redact = (value, parentKey = "") => {{
  if (value === null) return null;
  if (Array.isArray(value)) return value.length ? [redact(value[0])] : [];
  if (typeof value === "string") return "<string>";
  if (typeof value === "number") return 0;
  if (typeof value === "boolean") return false;
  if (typeof value === "object") {{
    const out = {{}};
    let index = 0;
    for (const [key, child] of Object.entries(value).slice(0, 100)) {{
      const safeKey = !dynamicKeyParents.has(parentKey.toLowerCase()) && stableSchemaKeys.has(key)
        ? key : `field_${{index}}`;
      out[safeKey] = redact(child, key);
      index++;
    }}
    return out;
  }}
  return null;
}};
const sample = {{ data: {{ alice: {{ id: 1 }} }}, users: {{ bob: {{ id: 2 }} }} }};
const expected = {{ data: {{ field_0: {{ id: 0 }} }}, users: {{ field_0: {{ id: 0 }} }} }};
if (JSON.stringify(redact(sample)) !== JSON.stringify(expected)) {{
  throw new Error("Synthetic short user-key redaction check failed.");
}}
const statusReasons = {{ 200: "OK", 201: "Created", 202: "Accepted", 204: "No Content", 301: "Moved Permanently", 302: "Found", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable" }};
const entries = [];
for (const record of candidates) {{
  // This loads only a response already received by the browser; never replay a request.
  const detail = await tab.request(record.id);
  if (!isJsonGet(record) || typeof detail.body !== "string" ||
      new TextEncoder().encode(detail.body).byteLength > 1024 * 1024 ||
      !/json/i.test(detail.contentType || "")) continue;
  let parsed;
  try {{ parsed = JSON.parse(detail.body); }} catch {{ continue; }}
  const source = new URL(record.url);
  const path = redactPath(source.pathname);
  const safeUrl = new URL(`${{source.protocol}}//${{source.host}}${{path}}`);
  for (const key of source.searchParams.keys()) {{
    if (/^[A-Za-z][A-Za-z0-9_-]{{0,63}}$/.test(key)) safeUrl.searchParams.set(key, "<redacted>");
  }}
  const body = JSON.stringify(redact(parsed));
  const bodySize = new TextEncoder().encode(body).byteLength;
  const statusText = typeof detail.statusText === "string" ? detail.statusText :
    typeof record.statusText === "string" ? record.statusText : statusReasons[Number(record.status)] ?? "";
  entries.push({{
    startedDateTime: new Date(record.ts).toISOString(),
    time: record.durationMs || 0,
    request: {{ method: "GET", url: safeUrl.toString(), httpVersion: "HTTP/1.1", headers: [], queryString: [...safeUrl.searchParams.keys()].map(name => ({{ name, value: "<redacted>" }})), cookies: [], headersSize: -1, bodySize: 0 }},
    response: {{ status: record.status, statusText, httpVersion: "HTTP/1.1", headers: [], cookies: [], content: {{ size: bodySize, mimeType: detail.contentType, text: body }}, redirectURL: "", headersSize: -1, bodySize }},
    cache: {{}},
    timings: {{ send: 0, wait: record.durationMs || 0, receive: 0 }}
  }});
}}
if (!entries.length) throw new Error("No completed GET JSON response body was available to sanitize.");
const har = {{ log: {{ version: "1.2", creator: {{ name: "RAE OMP capture", version: "1" }}, entries }} }};
await Bun.write({har_path_json}, JSON.stringify(har));
console.log({{ entryCount: entries.length, allowedHostPresent: entries.some(e => isAllowedHost(new URL(e.request.url).hostname)) }});
await tab.close();
```

Select only completed 2xx GET `fetch`/`xhr` responses or JSON documents, and cap retrieval at three bodies and 1 MiB each. Never inspect or replay POST requests. Before writing, keep only JSON structure and stable schema property names; replace every scalar with a type placeholder and represent arrays with at most one redacted exemplar. Replace ID-like path segments, preserve safe query parameter names but replace all values, and omit all request/response header and cookie values. Do not store unredacted body, path IDs, query values, or personal data anywhere.

Verify the written HAR has a request to the requested host or a host in `requestedDomains` before generation. `tab.request` runs in the logged-in browser context; generated external clients do not inherit those browser cookies. Never copy session credentials into a client. Generate the complete client when a schema-bearing HAR is available; missing authentication is not a reason to skip client generation. Use the existing language-specific runtime-auth/session conventions. If auth cannot be inferred because captured headers were redacted, document it as unverified and accept user-managed runtime authentication without guessing its format. Run syntax/structural checks; skip authenticated API calls unless safe runtime credentials are already configured, and report that limitation. Do not claim authenticated execution without user-managed runtime credentials. Do not create a placeholder client; stop only if the HAR has no usable endpoint schema.
