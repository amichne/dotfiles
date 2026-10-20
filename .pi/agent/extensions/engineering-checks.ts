import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { homedir } from "node:os";
import { join } from "node:path";

// Native event adapter only: no tools, prompts, routing, or automatic continuation.
export default function engineeringChecks(pi: ExtensionAPI) {
  const run = async (phase: string, ctx: ExtensionContext) => {
    let report: Record<string, unknown>;
    try {
      const result = await pi.exec(join(homedir(), ".local/bin/agent-check"), [phase,
        "--repo", ctx.cwd, "--session", ctx.sessionManager.getSessionId()], { timeout: 110000 });
      const parsed: unknown = JSON.parse(result.stdout);
      if (!parsed || typeof parsed !== "object" || !("status" in parsed) || result.code !== 0) {
        report = { status: "failed", failure: "check-failed", ...(parsed && typeof parsed === "object" ? parsed : {}) };
        report.status = "failed";
      } else report = parsed as Record<string, unknown>;
    } catch { report = { status: "failed", failure: "check-unavailable" }; }
    const failed = report.status === "failed";
    pi.appendEntry("engineering-check", { phase, ...report });
    ctx.ui.setStatus("engineering-check", `checks: ${failed ? "failed" : report.status}`);
    if (failed) ctx.ui.notify(`Engineering checks failed; ${report.receipt ?? report.failure ?? "inspect agent-check"}`, "error");
  };
  pi.on("session_start", async (_event, ctx) => { await run("begin", ctx); });
  pi.on("turn_end", async (_event, ctx) => { await run("turn", ctx); });
  pi.on("agent_before_settle", async (_event, ctx) => { await run("handoff", ctx); });
}
