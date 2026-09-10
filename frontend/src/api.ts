export type Pet = {
  id: number;
  name: string;
  owner_name: string;
  created_at: string;
};

export type DocumentAccepted = {
  document_id: number;
  job_id: number;
  status: "ENQUEUED";
};

export type DocumentResult = {
  id: number;
  pet_id: number;
  filename: string;
  media_type: string;
  size_bytes: number;
  created_at: string;
  job_id: number;
  status: "ENQUEUED" | "DONE" | "FAILED";
  summary: string | null;
  error: string | null;
  completed_at: string | null;
};

type ErrorBody = { code?: string; message?: string; detail?: unknown };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ConnectionError extends Error {
  constructor() {
    super("The API could not be reached after several attempts.");
    this.name = "ConnectionError";
  }
}

async function responseError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {};
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    // A proxy or server may return a non-JSON error page.
  }
  return new ApiError(body.message ?? `Request failed with status ${response.status}.`, response.status);
}

export async function createPet(
  apiBaseUrl: string,
  input: { name: string; owner_name: string },
): Promise<Pet> {
  const response = await fetch(`${apiBaseUrl}/pets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as Pet;
}

export async function uploadDocument(
  apiBaseUrl: string,
  petId: number,
  file: File,
  idempotencyKey: string,
): Promise<DocumentAccepted> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${apiBaseUrl}/pets/${petId}/documents`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body,
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as DocumentAccepted;
}

export async function pollDocument(
  apiBaseUrl: string,
  documentId: number,
  signal: AbortSignal,
): Promise<DocumentResult | null> {
  const response = await fetch(
    `${apiBaseUrl}/documents/${documentId}/poll?after_job_id=0`,
    { signal },
  );
  if (response.status === 204) return null;
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as DocumentResult;
}

function abortableDelay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Polling cancelled", "AbortError"));
      },
      { once: true },
    );
  });
}

export async function waitForTerminalDocument(
  apiBaseUrl: string,
  documentId: number,
  signal: AbortSignal,
  onRetry?: (attempt: number) => void,
): Promise<DocumentResult> {
  let failures = 0;
  while (!signal.aborted) {
    try {
      const document = await pollDocument(apiBaseUrl, documentId, signal);
      failures = 0;
      if (document?.status === "DONE" || document?.status === "FAILED") return document;
    } catch (error) {
      if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
        throw error;
      }
      if (error instanceof ApiError && error.status < 500) throw error;
      failures += 1;
      if (failures > 4) throw new ConnectionError();
      onRetry?.(failures);
      await abortableDelay(Math.min(500 * 2 ** (failures - 1), 4_000), signal);
    }
  }
  throw new DOMException("Polling cancelled", "AbortError");
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}
