# BC MCP Proxy for ChatGPT

ChatGPT **cannot send custom HTTP headers** on MCP connectors.  
BC MCP server **requires** `TenantId`, `EnvironmentName`, and `Company` headers.

This proxy bridges the gap:

```
ChatGPT  ──►  this proxy  ──►  mcp.businesscentral.dynamics.com
               (injects BC headers)
```

---

## Deploy on Railway (easiest)

1. **Push to GitHub** — create a repo, push these files
2. **Go to [railway.app](https://railway.app)** → New Project → Deploy from GitHub
3. **Add environment variables** in Railway dashboard:

   | Variable         | Value                                    |
   |------------------|------------------------------------------|
   | `BC_TENANT_ID`   | `b633019a-86c9-4c20-b2a5-6e56659fc085`   |
   | `BC_ENVIRONMENT` | `Production` (or your sandbox name)      |
   | `BC_COMPANY`     | `CRONUS USA, Inc.`                       |

4. **Railway auto-detects** Python + Procfile → deploys automatically
5. **Copy the public URL** Railway gives you, e.g. `https://bc-mcp-proxy-xyz.up.railway.app`

---

## Deploy on Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service → Connect repo
3. Set environment to **Python**, start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add the same environment variables
5. Copy the `.onrender.com` URL

---

## Connect to ChatGPT

1. Open ChatGPT → **Plugins** → click **+**
2. Name: `Business Central`
3. Connection: **Server URL**
4. URL: paste your proxy URL (e.g. `https://bc-mcp-proxy-xyz.up.railway.app`)
5. Auth: **OAuth** → enter your Entra ID **Client ID**
6. Save → start a new chat → enable the plugin → sign in with Microsoft
7. Test: *"Show me open sales orders"*

---

## Verify it's working

Hit the health endpoint in your browser:

```
https://your-proxy-url.up.railway.app/health
```

Should return:
```json
{
  "status": "ok",
  "target": "https://mcp.businesscentral.dynamics.com",
  "tenant": "b633019a...",
  "environment": "Production",
  "company": "CRONUS USA, Inc."
}
```

---

## How it works

- **All requests** from ChatGPT are forwarded to BC MCP server as-is
- The proxy **adds** `TenantId`, `EnvironmentName`, `Company` headers
- **OAuth/auth** passes through — ChatGPT authenticates with Entra ID directly
- **SSE streaming** is fully supported for MCP responses
- The proxy itself stores **no credentials** — tokens flow through in the Authorization header

---

## Important: Entra ID App Registration

Make sure your Entra ID app registration (the one you already have) includes
ChatGPT's redirect URI. If ChatGPT prompts you to sign in but fails,
check the redirect URI in Entra → App registrations → Authentication.
