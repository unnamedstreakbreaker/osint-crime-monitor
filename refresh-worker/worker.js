// Cloudflare Worker: the "Refresh now" button calls this, and it starts the
// GitHub Actions workflow. The GitHub token stays here, never in the web page.
//
// Settings (Worker → Settings → Variables and Secrets):
//   GITHUB_TOKEN   (Secret)  fine-grained token: only this repo, "Actions: Read and write"
//   REPO           (Text)    unnamedstreakbreaker/osint-crime-monitor
//   WORKFLOW       (Text)    hourly.yml
//   ALLOWED_ORIGIN (Text)    https://unnamedstreakbreaker.github.io
//   COOLDOWN_MIN   (Text)    5   (minimum minutes between refreshes)

export default {
  async fetch(req, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Content-Type": "application/json",
    };
    const reply = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: cors });

    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST") return reply({ message: "Use POST" }, 405);
    const origin = req.headers.get("Origin") || "";
    if (env.ALLOWED_ORIGIN && origin !== env.ALLOWED_ORIGIN) return reply({ message: "Not allowed" }, 403);

    const api = `https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}`;
    const gh = {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "osint-refresh-worker",
    };

    // Don't start a new run if one is already going or one started very recently.
    const runs = await (await fetch(`${api}/runs?per_page=1`, { headers: gh })).json();
    const last = runs.workflow_runs && runs.workflow_runs[0];
    if (last && last.status !== "completed") {
      return reply({ status: "running", message: "An update is already running. This page reloads when it finishes." });
    }
    const cooldown = (+env.COOLDOWN_MIN || 5) * 60000;
    if (last && Date.now() - Date.parse(last.created_at) < cooldown) {
      return reply({ status: "recent", message: "News was refreshed a moment ago. Try again in a few minutes." });
    }

    const r = await fetch(`${api}/dispatches`, {
      method: "POST", headers: gh, body: JSON.stringify({ ref: "main" }),
    });
    if (r.status === 204) {
      return reply({ status: "started", message: "Fetching the latest news (about 2–3 minutes). This page reloads by itself." });
    }
    return reply({ status: "error", message: `GitHub refused the refresh (${r.status}).` }, 502);
  },
};
