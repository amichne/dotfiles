import assert from "node:assert/strict";
import test from "node:test";
import { askBatch, QuestionBatch } from "../.pi/agent/lib/questions.ts";

const config = { defaultTimeoutMs: 60_000 };
const question = (id, fields = {}) => ({ id, prompt: `Choose ${id}`, ...fields });
const tick = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

function parse(questions) {
  const result = QuestionBatch.parse({ questions }, config);
  assert.equal(result.kind, "accepted");
  return result.value;
}

function fixture() {
  let now = 0;
  const timers = new Set();
  const calls = [];
  const controller = new AbortController();
  const dialog = (kind, title, options, signal, timeoutMs) => new Promise((resolve, reject) => {
    calls.push({ kind, title, options, signal, timeoutMs, resolve, reject });
  });
  const host = {
    select: (title, options, signal, timeoutMs) => dialog("select", title, options, signal, timeoutMs),
    input: (title, signal, timeoutMs) => dialog("input", title, undefined, signal, timeoutMs),
  };
  const clock = {
    now: () => now,
    schedule: (callback, delay) => {
      const timer = { callback, at: now + delay };
      timers.add(timer);
      return () => timers.delete(timer);
    },
  };
  return {
    calls, controller, timers,
    run: questions => askBatch(parse(questions), host, clock, controller.signal),
    advance: async ms => {
      now += ms;
      for (const timer of [...timers]) if (timer.at <= now) timer.callback();
      await tick();
    },
  };
}

test("each displayed question gets a separate full deadline", async () => {
  const f = fixture();
  const pending = f.run([question("first", { timeoutMs: 50 }), question("second", { timeoutMs: 200 })]);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].timeoutMs, 50);
  await f.advance(40);
  f.calls[0].resolve("First answer");
  await tick();
  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[1].timeoutMs, 200);
  await f.advance(199);
  assert.equal(f.calls[1].signal.aborted, false);
  f.calls[1].resolve("Second answer");
  assert.deepEqual(await pending, [
    { id: "first", status: "answered", answer: { kind: "freeform", text: "First answer" } },
    { id: "second", status: "answered", answer: { kind: "freeform", text: "Second answer" } },
  ]);
  assert.equal(f.timers.size, 0);
});

test("timeouts preserve separate policies without a default answer", async () => {
  const f = fixture();
  const pending = f.run([
    question("blocked", { timeoutMs: 10 }),
    question("judgment", { timeoutMs: 20, onTimeout: "model_judgment" }),
    question("veto", { timeoutMs: 30, onTimeout: "insufficient_evidence" }),
  ]);
  await f.advance(10);
  assert.equal(f.calls.length, 2);
  await f.advance(20);
  assert.equal(f.calls.length, 3);
  await f.advance(30);
  assert.deepEqual(await pending, [
    { id: "blocked", status: "timed_out", next: "insufficient_evidence" },
    { id: "judgment", status: "timed_out", next: "model_judgment" },
    { id: "veto", status: "timed_out", next: "insufficient_evidence" },
  ]);
  assert.ok(f.calls.every(call => call.signal.aborted));
  assert.equal(f.timers.size, 0);
});

test("freeform input shares its question deadline with selection", async () => {
  const f = fixture();
  const pending = f.run([question("choice", { options: ["A", "B"], timeoutMs: 100 })]);
  await f.advance(75);
  f.calls[0].resolve("Type a response…");
  await tick();
  assert.equal(f.calls[1].timeoutMs, 25);
  await f.advance(25);
  assert.deepEqual(await pending, [{ id: "choice", status: "timed_out", next: "insufficient_evidence" }]);
});

test("the user selects an exact option or supplies freeform text", async () => {
  const f = fixture();
  const pending = f.run([question("choice", { options: ["A", "B"] }), question("custom", { options: ["C"] })]);
  f.calls[0].resolve("2. B");
  await tick();
  f.calls[1].resolve("Type a response…");
  await tick();
  f.calls[2].resolve(" My own choice ");
  assert.deepEqual(await pending, [
    { id: "choice", status: "answered", answer: { kind: "selection", text: "B" } },
    { id: "custom", status: "answered", answer: { kind: "freeform", text: "My own choice" } },
  ]);
});

test("cancellation preserves earlier answers and never grants permission to guess", async () => {
  const f = fixture();
  const pending = f.run([question("first"), question("cancel", { onTimeout: "model_judgment" }), question("last")]);
  f.calls[0].resolve("Keep me");
  await tick();
  f.calls[1].resolve(undefined);
  assert.deepEqual(await pending, [
    { id: "first", status: "answered", answer: { kind: "freeform", text: "Keep me" } },
    { id: "cancel", status: "cancelled" },
    { id: "last", status: "not_asked" },
  ]);
  assert.equal(f.calls.length, 2);
  assert.equal(f.timers.size, 0);
});

test("abort dismisses the dialog even when the host never resolves", async () => {
  const f = fixture();
  const pending = f.run([question("first", { onTimeout: "model_judgment" }), question("later")]);
  f.controller.abort();
  assert.deepEqual(await pending, [{ id: "first", status: "aborted" }, { id: "later", status: "not_asked" }]);
  assert.equal(f.calls[0].signal.aborted, true);
  assert.equal(f.timers.size, 0);
});

test("an already aborted call opens no dialog", async () => {
  const f = fixture();
  f.controller.abort();
  assert.deepEqual(await f.run([question("first")]), [{ id: "first", status: "aborted" }]);
  assert.equal(f.calls.length, 0);
});

test("late answers cannot settle a later question or a later round", async () => {
  const f = fixture();
  const first = f.run([question("same", { timeoutMs: 10 })]);
  await f.advance(10);
  const firstResult = await first;
  const second = f.run([question("same", { timeoutMs: 10 })]);
  f.calls[0].resolve("Late answer from the previous round");
  await tick();
  assert.equal(f.calls[1].signal.aborted, false);
  f.calls[1].resolve("Current answer");
  assert.deepEqual(await second, [{ id: "same", status: "answered", answer: { kind: "freeform", text: "Current answer" } }]);
  assert.deepEqual(firstResult, [{ id: "same", status: "timed_out", next: "insufficient_evidence" }]);
});

test("unknown choices, empty answers, and host failures never become answers", async () => {
  for (const scenario of ["unknown", "empty", "failure"]) {
    const f = fixture();
    const pending = f.run([question("first", { options: scenario === "unknown" ? ["A"] : undefined }), question("later")]);
    if (scenario === "failure") f.calls[0].reject(new Error("private-host-detail"));
    else f.calls[0].resolve(scenario === "unknown" ? "Not an offered option" : "  ");
    const result = await pending;
    assert.equal(result[0].status, scenario === "failure" ? "ui_error" : "invalid_answer");
    assert.equal(result[1].status, "not_asked");
    assert.ok(!JSON.stringify(result).includes("private-host-detail"));
    assert.equal(f.timers.size, 0);
  }
});

test("invalid batches and invalid settings reject before a dialog can open", () => {
  for (const questions of [[], Array.from({ length: 6 }, (_, i) => question(String(i))),
    [question("same"), question("same")], [question("  ")],
    [question("a", { options: ["same", " same "] })], [question("a", { options: [3] })],
    [question("a", { onTimeout: "guess_without_evidence" })], [question("a", { timeoutMs: 0 })],
    [question("a", { timeoutMs: 3_600_001 })], [question("a", { timeoutMs: 1.5 })],
    [question("a", { unexpected: true })]]) {
    assert.deepEqual(QuestionBatch.parse({ questions }, config), { kind: "rejected", reason: "invalid_request" });
  }
  for (const settings of [null, {}, { defaultTimeoutMs: -1 }, { defaultTimeoutMs: 1, extra: true }]) {
    assert.deepEqual(QuestionBatch.parse({ questions: [question("a")] }, settings), { kind: "rejected", reason: "invalid_config" });
  }
});

test("a real timer resolves a stalled host and cancels its signal", async () => {
  let dialogSignal;
  const host = {
    select: async () => { throw new Error("unexpected selection"); },
    input: (_title, signal) => { dialogSignal = signal; return new Promise(() => {}); },
  };
  const outcomes = await askBatch(parse([question("real", { timeoutMs: 10 })]), host, {
    now: () => performance.now(),
    schedule: (callback, delay) => { const timer = setTimeout(callback, delay); return () => clearTimeout(timer); },
  }, new AbortController().signal);
  assert.deepEqual(outcomes, [{ id: "real", status: "timed_out", next: "insufficient_evidence" }]);
  assert.equal(dialogSignal.aborted, true);
});
