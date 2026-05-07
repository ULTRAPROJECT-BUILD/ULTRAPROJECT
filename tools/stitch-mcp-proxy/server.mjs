import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");

function parseDotEnv(contents) {
  const env = {};
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

function loadRepoEnv() {
  if (process.env.STITCH_PROXY_SKIP_REPO_ENV === "1") {
    return {};
  }
  const envPath = path.join(repoRoot, ".env");
  if (!fs.existsSync(envPath)) return {};
  return parseDotEnv(fs.readFileSync(envPath, "utf8"));
}

const repoEnv = loadRepoEnv();
const apiKey = process.env.STITCH_API_KEY || repoEnv.STITCH_API_KEY || "";

if (!apiKey.trim()) {
  console.error(
    [
      "Stitch MCP proxy requires STITCH_API_KEY.",
      "Add STITCH_API_KEY=<your-key> to the platform repo .env",
      "or export it in the shell before starting Claude.",
    ].join("\n"),
  );
  process.exit(1);
}

const { StitchProxy } = await import("@google/stitch-sdk");
const { StdioServerTransport } = await import("@modelcontextprotocol/sdk/server/stdio.js");

const proxy = new StitchProxy({ apiKey: apiKey.trim() });
const transport = new StdioServerTransport();

process.on("SIGINT", async () => {
  try {
    await proxy.close?.();
  } finally {
    process.exit(0);
  }
});

process.on("SIGTERM", async () => {
  try {
    await proxy.close?.();
  } finally {
    process.exit(0);
  }
});

await proxy.start(transport);
