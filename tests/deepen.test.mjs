import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import register from "../.pi/agent/extensions/deepen.ts";

const suppliedInstructions = "I want a deeper version of this task, not a bigger one. Before rewriting it: (1) say what a top professional in this field would do here that I'm not asking for; (2) name the rawest material they would start from instead of what has already been digested for me; (3) name the specific methods and tools they would use; (4) say what, other than you or me, would show the result is right. Then rewrite my prompt to ask for exactly that.";

async function waitForCall(fixture) {
  for (let count = 0; count < 100 && fixture.calls.length === 0; count++) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(fixture.calls.length, 1, "the request must reach the model adapter");
}

function fixture() {
  const commands = new Map();
  const events = new Map();
  const calls = [];
  const messages = [];
  const notices = [];
  const reply = {
    stopReason: "stop",
    content: [
      { type: "thinking", thinking: "Private reasoning" },
      { type: "text", text: "1. Professional practice\n2. Raw sources\n3. Methods\n4. Independent evidence\n\nRewritten prompt: Examine unused CSS without file changes." },
    ],
  };
  const pi = {
    registerCommand: (name, command) => commands.set(name, command),
    on: (name, handler) => events.set(name, handler),
    sendMessage: (message, options) => messages.push({ message, options }),
  };
  const ctx = {
    model: { provider: "fixture", id: "frontier" },
    signal: undefined,
    isIdle: () => true,
    ui: { notify: (text, level) => notices.push({ text, level }) },
    modelRegistry: {
      hasConfiguredAuth: () => true,
      complete: async (...args) => {
        calls.push(args);
        return reply;
      },
    },
  };
  register(pi);
  return {
    commands, events, calls, messages, notices, reply, ctx,
    run: async (prompt) => {
      const command = commands.get("deepen");
      assert.ok(command, "/deepen must register with Pi");
      await command.handler(prompt, ctx);
    },
  };
}

test("one completion preserves the supplied instruction and original prompt without task execution", async () => {
  const f = fixture();
  const original = "Inspect unused CSS.\nKeep files unchanged, including $HOME and `quoted` paths.";
  await f.run(original);
  assert.equal(f.calls.length, 1);
  const [model, context, options] = f.calls[0];
  assert.equal(model, f.ctx.model);
  assert.ok(context.systemPrompt.includes(suppliedInstructions));
  assert.equal(context.messages.length, 1);
  assert.equal(context.messages[0].role, "user");
  assert.equal(context.messages[0].content, original);
  assert.deepEqual(context.tools, []);
  assert.equal(options.reasoningEffort, "high");
  assert.equal(options.cacheRetention, "none");
  assert.equal(f.messages.length, 1);
  assert.equal(f.messages[0].message.content, f.reply.content[1].text);
  assert.equal(f.messages[0].message.display, true);
  assert.equal(f.messages[0].options.triggerTurn, false);
  assert.ok(!f.messages[0].message.content.includes("Private reasoning"));
});

test("empty input, an absent model, missing authentication, and an active turn make no model call", async () => {
  for (const scenario of ["empty", "model", "auth", "busy"]) {
    const f = fixture();
    if (scenario === "model") f.ctx.model = undefined;
    if (scenario === "auth") f.ctx.modelRegistry.hasConfiguredAuth = () => false;
    if (scenario === "busy") f.ctx.isIdle = () => false;
    await f.run(scenario === "empty" ? " \n\t " : "Original task");
    assert.equal(f.calls.length, 0, scenario);
    assert.equal(f.messages.length, 0, scenario);
    assert.ok(f.notices.some((notice) => notice.level === "warning"), scenario);
  }
});

test("incomplete, aborted, failed, tool-call, and empty responses never become a rewritten prompt", async () => {
  for (const stopReason of ["length", "aborted", "error", "toolUse", "pending", "deferred", "empty"]) {
    const f = fixture();
    if (stopReason === "empty") f.reply.content = [];
    else f.reply.stopReason = stopReason;
    await f.run("Original task");
    assert.equal(f.calls.length, 1, stopReason);
    assert.equal(f.messages.length, 0, stopReason);
    assert.ok(f.notices.some((notice) => notice.level === "error"), stopReason);
  }
});

test("a failed provider call stops without retries or secret-bearing error text", async () => {
  const f = fixture();
  f.ctx.modelRegistry.complete = async (...args) => {
    f.calls.push(args);
    throw new Error("secret-provider-response");
  };
  await f.run("Original task");
  assert.equal(f.calls.length, 1);
  assert.equal(f.messages.length, 0);
  assert.ok(f.notices.some((notice) => notice.level === "error"));
  assert.ok(!JSON.stringify(f.notices).includes("secret-provider-response"));
});

test("one coordinator rejects overlapping rewrites and permits the next invocation", async () => {
  const f = fixture();
  assert.ok(f.commands.has("deepen"), "/deepen must register with Pi");
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  f.ctx.modelRegistry.complete = async (...args) => {
    f.calls.push(args);
    return pending;
  };
  const first = f.run("First task");
  await waitForCall(f);
  await f.run("Second task");
  assert.equal(f.calls.length, 1);
  finish(f.reply);
  await first;
  await f.run("Third task");
  assert.equal(f.calls.length, 2);
});

test("session shutdown cancels the request and suppresses a late successful response", async () => {
  const f = fixture();
  assert.ok(f.commands.has("deepen"), "/deepen must register with Pi");
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  f.ctx.modelRegistry.complete = async (...args) => {
    f.calls.push(args);
    return pending;
  };
  const run = f.run("Original task");
  await waitForCall(f);
  const signal = f.calls[0][2].signal;
  await f.events.get("session_shutdown")();
  assert.equal(signal.aborted, true);
  finish(f.reply);
  await run;
  assert.equal(f.messages.length, 0);
});

test("the prompt policy is the user's supplied text", async () => {
  const policy = await readFile(new URL("../.pi/agent/deepen.md", import.meta.url), "utf8");
  assert.equal(policy.trim(), suppliedInstructions);
});
