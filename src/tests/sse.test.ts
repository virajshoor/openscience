import { describe, it, expect, vi, beforeEach } from "vitest";

const SSE_EVENTS = {
  token: (text: string) => `data: ${JSON.stringify({ event: "token", data: { text } })}\n\n`,
  tool_call: (d: unknown) => `data: ${JSON.stringify({ event: "tool_call", data: d })}\n\n`,
  tool_result: (id: string, name: string, result: unknown) =>
    `data: ${JSON.stringify({ event: "tool_result", data: { id, name, result } })}\n\n`,
  viewer: (d: unknown) => `data: ${JSON.stringify({ event: "viewer", data: d })}\n\n`,
  done: (runId: string) => `data: ${JSON.stringify({ event: "done", data: { run_id: runId } })}\n\n`,
  error: (msg: string) => `data: ${JSON.stringify({ event: "error", data: { message: msg } })}\n\n`,
};

function makeMockResponse(events: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const e of events) controller.enqueue(encoder.encode(e));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

describe("SSE streamChat", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it("parses token, tool_call, tool_result, viewer, and done events", async () => {
    const events = [
      SSE_EVENTS.token("Hello "),
      SSE_EVENTS.token("world"),
      SSE_EVENTS.tool_call({ id: "c1", name: "pdb_fetch", arguments: { pdb_id: "1CRN" } }),
      SSE_EVENTS.tool_result("c1", "pdb.fetch", { summary: "ok" }),
      SSE_EVENTS.viewer({ type: "protein", src: "runs/x/1CRN.pdb", label: "PDB 1CRN" }),
      SSE_EVENTS.done("run123"),
    ];

    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(makeMockResponse(events))));

    const { streamChat } = await import("../lib/api");

    const calls: Record<string, unknown[]> = {
      onToken: [],
      onToolCall: [],
      onToolResult: [],
      onViewer: [],
      onDone: [],
      onError: [],
    };

    await streamChat([], {
      onToken: (t) => calls.onToken.push(t),
      onToolCall: (c) => calls.onToolCall.push(c),
      onToolResult: (id, name, result) => calls.onToolResult.push({ id, name, result }),
      onViewer: (v) => calls.onViewer.push(v),
      onDone: (runId) => calls.onDone.push(runId),
      onError: (msg) => calls.onError.push(msg),
    });

    expect(calls.onToken).toEqual(["Hello ", "world"]);
    expect(calls.onToolCall).toHaveLength(1);
    expect((calls.onToolCall[0] as { name: string }).name).toBe("pdb_fetch");
    expect(calls.onToolResult).toHaveLength(1);
    expect((calls.onToolResult[0] as { name: string }).name).toBe("pdb.fetch");
    expect(calls.onViewer).toHaveLength(1);
    expect((calls.onViewer[0] as { type: string }).type).toBe("protein");
    expect(calls.onDone).toEqual(["run123"]);
    expect(calls.onError).toHaveLength(0);
  });

  it("calls onError for error events", async () => {
    const events = [SSE_EVENTS.error("something broke")];
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(makeMockResponse(events))));
    const { streamChat } = await import("../lib/api");

    let errorMsg = "";
    await streamChat([], {
      onToken: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onViewer: () => {},
      onDone: () => {},
      onError: (m) => { errorMsg = m; },
    });
    expect(errorMsg).toBe("something broke");
  });

  it("handles non-200 responses", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("", { status: 500 }))));
    const { streamChat } = await import("../lib/api");

    let errorMsg = "";
    await streamChat([], {
      onToken: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onViewer: () => {},
      onDone: () => {},
      onError: (m) => { errorMsg = m; },
    });
    expect(errorMsg).toContain("500");
  });
});

describe("sidecarConfig mapping", async () => {
  it("converts camelCase config to snake_case", async () => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(makeMockResponse([SSE_EVENTS.done("x")]))));
    const { streamChat } = await import("../lib/api");

    let sentBody: Record<string, unknown> = {};
    const fetchMock = vi.fn((url: string, opts: { body?: string }) => {
      sentBody = JSON.parse(opts.body || "{}");
      return Promise.resolve(makeMockResponse([SSE_EVENTS.done("x")]));
    });
    vi.stubGlobal("fetch", fetchMock);

    // Access the internal config via the store
    const { useSession } = await import("../stores/session");
    useSession.getState().setConfig({
      baseUrl: "http://test/v1",
      apiKey: "sk-test",
      model: "gpt-4",
      temperature: 0.5,
      useTools: false,
    });

    await streamChat([{ role: "user", content: "hi" }], {
      onToken: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onViewer: () => {},
      onDone: () => {},
      onError: () => {},
    });

    const cfg = sentBody.config as Record<string, unknown>;
    expect(cfg.base_url).toBe("http://test/v1");
    expect(cfg.api_key).toBe("sk-test");
    expect(cfg.model).toBe("gpt-4");
    expect(cfg.temperature).toBe(0.5);
    expect(cfg.use_tools).toBe(false);
  });
});