---
name: web-browsing
description: Web browsing, fetching, searching, and file downloading capabilities
---

# Web Browsing & Internet Access

## Overview
This skill provides guidance on how to use web browsing capabilities within the Hermes Agent environment to access, search, and interact with internet resources.

## Core Capabilities

### 1. Web Fetching (web_fetch)
Use the `web_fetch` tool to retrieve content from URLs.

**Steps:**
1. Identify the URL to fetch
2. Call `web_fetch(url="<URL>")` 
3. Parse and extract relevant content from the response
4. Handle errors (timeouts, 404, etc.)

### 2. Web Search (web_search)
Use the `web_search` tool to search the internet.

**Steps:**
1. Formulate a search query
2. Call `web_search(query="<query>", num_results=N)`
3. Review results and follow up on relevant links
4. Fetch full content from promising results

### 3. File Downloads
Use `terminal` to download files from the internet.

**Steps:**
1. Identify the download URL
2. Use `curl` or `wget` in terminal:
   ```
   curl -L -o <output_file> <URL>
   # or
   wget -O <output_file> <URL>
   ```
3. Verify the downloaded file

## Common Pitfalls
- Some websites block automated requests
- Rate limits may apply
- Some sites require JavaScript rendering — static fetch gets HTML only
- Always verify downloaded files for security

## Verification
- Confirm web fetch returned expected content
- Verify downloaded files exist and are non-empty
- Check search results relevance