# Connecting Claude Code to the Obsidian vault (MCP)

The Obsidian MCP plugin exposes the vault as a streamable-HTTP MCP server at
`http://127.0.0.1:27200/mcp`, protected by a bearer token. The repo's
[`.mcp.json`](../.mcp.json) registers that server for Claude Code, with the URL
and token read from environment variables so no secret is ever committed:

| Variable | Meaning | Default |
|---|---|---|
| `OBSIDIAN_MCP_URL` | MCP endpoint URL | `http://127.0.0.1:27200/mcp` |
| `OBSIDIAN_MCP_TOKEN` | Bearer token from the plugin settings | *(empty — requests will 401 until set)* |

## Local use (Claude Code on the same machine as Obsidian)

1. Keep Obsidian running with the MCP plugin enabled.
2. Export the token, then start Claude Code in this repo:

   ```bash
   export OBSIDIAN_MCP_TOKEN=<token from the plugin settings>
   claude
   ```

   Approve the project MCP server when prompted. The default URL already
   points at `127.0.0.1:27200`, so nothing else is needed.

3. To make the vault available in *every* local project (not just this repo),
   register it at user scope instead:

   ```bash
   claude mcp add --transport http --scope user mcp-tools-istefox \
     http://127.0.0.1:27200/mcp \
     --header "Authorization: Bearer <token>"
   ```

## Remote use (Claude Code on the web / cloud sessions)

Cloud sessions run in an isolated container and cannot reach `127.0.0.1` on
your machine. To use the vault remotely, expose the port through a tunnel:

```bash
# Cloudflare quick tunnel (no account needed; prints a public https URL)
cloudflared tunnel --url http://127.0.0.1:27200
# or: ngrok http 27200
```

Then, in the claude.ai environment settings for this repo, set:

- `OBSIDIAN_MCP_URL` = `https://<tunnel-host>/mcp`
- `OBSIDIAN_MCP_TOKEN` = the plugin token

New sessions will pick up the server from `.mcp.json`. Notes:

- The environment's network policy must allow the tunnel domain
  (e.g. `*.trycloudflare.com` or `*.ngrok-free.app`).
- The tunnel only works while your machine is awake and Obsidian is running.
- A tunnel makes the vault endpoint publicly reachable; the bearer token is
  the only thing protecting it. Prefer short-lived tunnels, and rotate the
  token in the plugin settings if it may have been exposed.

## Security

- **Never commit the token** — this repository is public. `.mcp.json` only
  references environment variables.
- Rotate the token from the Obsidian plugin settings if it has been pasted
  anywhere it shouldn't live long-term.
