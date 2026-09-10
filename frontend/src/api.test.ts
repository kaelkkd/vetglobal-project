import { afterEach, describe, expect, it, vi } from "vitest";

import { pollDocument, waitForTerminalDocument } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("document polling", () => {
  it("does not parse JSON from an empty 204 response", async () => {
    const json = vi.fn(() => {
      throw new Error("json must not be called");
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 204, ok: true, json }));

    const result = await pollDocument("http://api.test", 12, new AbortController().signal);

    expect(result).toBeNull();
    expect(json).not.toHaveBeenCalled();
  });

  it("continues after 204 and stops after the first terminal result", async () => {
    const terminal = {
      id: 12,
      pet_id: 1,
      filename: "record.txt",
      media_type: "text/plain",
      size_bytes: 8,
      created_at: "2026-09-10T12:00:00Z",
      job_id: 7,
      status: "DONE",
      summary: "Stable",
      error: null,
      completed_at: "2026-09-10T12:00:01Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ status: 204, ok: true })
      .mockResolvedValueOnce({ status: 200, ok: true, json: async () => terminal });
    vi.stubGlobal("fetch", fetchMock);

    const result = await waitForTerminalDocument(
      "http://api.test",
      12,
      new AbortController().signal,
    );

    expect(result).toEqual(terminal);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("cancels an obsolete long-poll request", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn((_url: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => {
          reject(new DOMException("Polling cancelled", "AbortError"));
        });
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const polling = waitForTerminalDocument("http://api.test", 12, controller.signal);
    controller.abort();

    await expect(polling).rejects.toMatchObject({ name: "AbortError" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
