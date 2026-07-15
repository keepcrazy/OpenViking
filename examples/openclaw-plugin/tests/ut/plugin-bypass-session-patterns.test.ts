import { afterEach, describe, expect, it, vi } from "vitest";

import contextEnginePlugin from "../../index.js";

type HookHandler = (event: unknown, ctx?: Record<string, unknown>) => unknown;

function okResponse(result: unknown): Response {
  return new Response(JSON.stringify({ status: "ok", result }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function setupPlugin(pluginConfig?: Record<string, unknown>) {
  const handlers = new Map<string, HookHandler>();
  const logger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  };
  const registerContextEngine = vi.fn();

  contextEnginePlugin.register({
    logger,
    on: (name, handler) => {
      handlers.set(name, handler as HookHandler);
    },
    pluginConfig: {
      mode: "remote",
      baseUrl: "http://127.0.0.1:1933",
      autoCapture: true,
      autoRecall: true,
      ...pluginConfig,
    },
    registerContextEngine,
    registerService: vi.fn(),
    registerTool: vi.fn(),
  } as any);

  return {
    handlers,
    logger,
    registerContextEngine,
  };
}

describe("plugin bypass session patterns", () => {
  it("bypasses context-engine assemble before any OV client work", async () => {
    const { registerContextEngine, logger } = setupPlugin({
      bypassSessionPatterns: ["agent:*:cron:**"],
    });

    const factory = registerContextEngine.mock.calls[0]?.[1] as (() => {
      assemble: (params: {
        sessionId: string;
        sessionKey?: string;
        prompt?: string;
        messages: Array<{ role: string; content: string }>;
      }) => Promise<{ messages: Array<{ role: string; content: string }> }>;
    }) | undefined;
    expect(factory).toBeTruthy();
    const engine = factory!();
    const liveMessages = [{ role: "user", content: "Alice: hi\nBob: hello" }];

    const result = await engine.assemble({
      sessionId: "runtime-session",
      sessionKey: "agent:main:cron:nightly:run:1",
      prompt: "Alice: hi\nBob: hello",
      messages: liveMessages,
    });

    expect(result.messages).toBe(liveMessages);
    expect(logger.warn).not.toHaveBeenCalledWith(
      expect.stringContaining("failed to get client"),
    );
  });

  it("bypasses before_reset without calling commitOVSession", async () => {
    const { handlers, registerContextEngine } = setupPlugin({
      bypassSessionPatterns: ["agent:*:cron:**"],
    });

    const factory = registerContextEngine.mock.calls[0]?.[1] as (() => { commitOVSession: ReturnType<typeof vi.fn> }) | undefined;
    expect(factory).toBeTruthy();
    const engine = factory!();
    engine.commitOVSession = vi.fn().mockResolvedValue(true);

    const hook = handlers.get("before_reset");
    expect(hook).toBeTruthy();

    await hook!(
      {},
      {
        sessionId: "runtime-session",
        sessionKey: "agent:main:cron:nightly:run:1",
      },
    );

    expect(engine.commitOVSession).not.toHaveBeenCalled();
  });
});

describe("plugin before_reset context-engine commit", () => {
  it("commits with senderId even before the registered context-engine factory is first used", async () => {
    const fetchMock = vi.fn(async () =>
      okResponse({
        status: "completed",
        archived: false,
        memories_extracted: {},
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { handlers, registerContextEngine, logger } = setupPlugin();

    expect(registerContextEngine).toHaveBeenCalledWith("openviking", expect.any(Function));
    const hook = handlers.get("before_reset");
    expect(hook).toBeTruthy();

    await hook!(
      {},
      {
        sessionId: "runtime-session",
        sessionKey: "agent:main:chat:runtime-session",
        senderId: "ou_reset_sender",
      },
    );

    const commitCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/api/v1/sessions/") && String(url).endsWith("/commit"),
    );
    expect(commitCall).toBeTruthy();
    const [, init] = commitCall as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("X-OpenViking-User")).toBe("ou_reset_sender");
    expect(logger.info).toHaveBeenCalledWith(
      expect.stringContaining("committed OV session on reset for session=runtime-session"),
    );
  });

  it("skips before_reset commit without senderId and does not use a default user", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { handlers, logger } = setupPlugin();

    const hook = handlers.get("before_reset");
    expect(hook).toBeTruthy();

    await hook!(
      {},
      {
        sessionId: "runtime-session",
        sessionKey: "agent:main:chat:runtime-session",
      },
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(logger.warn).toHaveBeenCalledWith(
      expect.stringContaining("senderId is unavailable"),
    );
  });
});
