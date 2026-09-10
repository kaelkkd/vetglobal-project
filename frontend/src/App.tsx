import { FormEvent, useEffect, useRef, useState } from "react";

import {
  ApiError,
  ConnectionError,
  createPet,
  DocumentAccepted,
  DocumentResult,
  errorMessage,
  Pet,
  uploadDocument,
  waitForTerminalDocument,
} from "./api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

type WorkflowState = "idle" | "uploading" | "pending" | "done" | "failed" | "connection";

function App() {
  const [pet, setPet] = useState<Pet | null>(null);
  const [petBusy, setPetBusy] = useState(false);
  const [petError, setPetError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [workflow, setWorkflow] = useState<WorkflowState>("idle");
  const [accepted, setAccepted] = useState<DocumentAccepted | null>(null);
  const [result, setResult] = useState<DocumentResult | null>(null);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const pollingController = useRef<AbortController | null>(null);
  const uploadKey = useRef(crypto.randomUUID());

  useEffect(() => () => pollingController.current?.abort(), []);

  async function startPolling(documentId: number) {
    pollingController.current?.abort();
    const controller = new AbortController();
    pollingController.current = controller;
    setWorkflow("pending");
    setRetryAttempt(0);
    try {
      const document = await waitForTerminalDocument(
        API_BASE_URL,
        documentId,
        controller.signal,
        setRetryAttempt,
      );
      setResult(document);
      setWorkflow(document.status === "DONE" ? "done" : "failed");
    } catch (error) {
      if (controller.signal.aborted) return;
      setUploadError(errorMessage(error));
      setWorkflow(error instanceof ConnectionError ? "connection" : "failed");
    }
  }

  async function handlePetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedForm = event.currentTarget;
    const form = new FormData(submittedForm);
    setPetBusy(true);
    setPetError("");
    try {
      const created = await createPet(API_BASE_URL, {
        name: String(form.get("name") ?? ""),
        owner_name: String(form.get("ownerName") ?? ""),
      });
      pollingController.current?.abort();
      setPet(created);
      setAccepted(null);
      setResult(null);
      setSelectedFile(null);
      uploadKey.current = crypto.randomUUID();
      setWorkflow("idle");
      submittedForm.reset();
    } catch (error) {
      setPetError(errorMessage(error));
    } finally {
      setPetBusy(false);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pet || !selectedFile) return;
    pollingController.current?.abort();
    setWorkflow("uploading");
    setUploadError("");
    setResult(null);
    try {
      const receipt = await uploadDocument(
        API_BASE_URL,
        pet.id,
        selectedFile,
        uploadKey.current,
      );
      setAccepted(receipt);
      await startPolling(receipt.document_id);
    } catch (error) {
      setUploadError(errorMessage(error));
      const connectionFailure =
        !(error instanceof ApiError) || error.status >= 500 || error instanceof ConnectionError;
      setWorkflow(connectionFailure ? "connection" : "failed");
    }
  }

  const busy = workflow === "uploading" || workflow === "pending";

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main" aria-label="VetGlobal workspace home">
          <span className="brand-mark" aria-hidden="true">V</span>
          <span>VetGlobal</span>
        </a>
        <span className="environment">Local assessment workspace</span>
      </header>

      <main id="main" className="workspace">
        <div className="page-heading">
          <p className="eyebrow">Document workflow</p>
          <h1>Clinical summary intake</h1>
          <p>Create a pet record, upload a TXT or PDF, and follow its processing state.</p>
        </div>

        <div className="workflow-grid">
          <section className="panel intake-panel" aria-labelledby="pet-heading">
            <div className="step-heading">
              <span className="step-number">01</span>
              <div>
                <h2 id="pet-heading">Pet record</h2>
                <p>Start a new single-pet workspace.</p>
              </div>
            </div>

            <form onSubmit={handlePetSubmit} className="form-stack">
              <label>
                Pet name
                <input name="name" maxLength={120} required placeholder="Hank" />
              </label>
              <label>
                Owner name
                <input name="ownerName" maxLength={200} required placeholder="John Bergeson" />
              </label>
              {petError && <p className="form-error" role="alert">{petError}</p>}
              <button type="submit" disabled={petBusy}>
                {petBusy ? "Creating…" : pet ? "Create another pet" : "Create pet"}
              </button>
            </form>

            {pet && (
              <div className="record-card" aria-live="polite">
                <span className="record-label">Current record</span>
                <strong>{pet.name}</strong>
                <span>{pet.owner_name}</span>
                <code>Pet #{pet.id}</code>
              </div>
            )}

            <div className="step-divider" />

            <div className="step-heading">
              <span className="step-number">02</span>
              <div>
                <h2 id="upload-heading">Document</h2>
                <p>TXT or PDF, up to 5 MiB.</p>
              </div>
            </div>
            <form onSubmit={handleUpload} className="form-stack" aria-labelledby="upload-heading">
              <label className="file-control">
                Select document
                <input
                  type="file"
                  accept=".txt,.pdf,text/plain,application/pdf"
                  disabled={!pet || busy}
                  required
                  onChange={(event) => {
                    setSelectedFile(event.target.files?.[0] ?? null);
                    uploadKey.current = crypto.randomUUID();
                  }}
                />
              </label>
              <button type="submit" disabled={!pet || !selectedFile || busy}>
                {workflow === "uploading" ? "Uploading…" : workflow === "pending" ? "Processing…" : "Upload document"}
              </button>
            </form>
          </section>

          <section className="panel status-panel" aria-labelledby="status-heading">
            <div className="status-header">
              <div>
                <p className="eyebrow">Live status</p>
                <h2 id="status-heading">Summary result</h2>
              </div>
              <StatusBadge state={workflow} />
            </div>

            <div className="status-content" aria-live="polite">
              {workflow === "idle" && (
                <EmptyState title="Ready for a document" detail="Complete both steps to begin the simulated workflow." />
              )}
              {workflow === "uploading" && (
                <EmptyState title="Uploading securely" detail="The document and its job are being saved together." active />
              )}
              {workflow === "pending" && (
                <EmptyState
                  title="Awaiting worker result"
                  detail={retryAttempt ? `Connection retry ${retryAttempt} of 4…` : "Long polling is active. Complete the job with the CLI simulator."}
                  active
                />
              )}
              {workflow === "done" && result && (
                <div className="result-block success">
                  <p className="result-kicker">Summary complete</p>
                  <blockquote>{result.summary}</blockquote>
                  <DocumentMeta result={result} />
                </div>
              )}
              {workflow === "failed" && (
                <div className="result-block failure" role="alert">
                  <p className="result-kicker">Processing failed</p>
                  <h3>{result?.error ?? uploadError}</h3>
                  {result && <DocumentMeta result={result} />}
                </div>
              )}
              {workflow === "connection" && (
                <div className="result-block failure" role="alert">
                  <p className="result-kicker">Connection interrupted</p>
                  <h3>{uploadError}</h3>
                  {accepted ? (
                    <>
                      <p>The job is still persisted. Reconnect without uploading it again.</p>
                      <button type="button" onClick={() => void startPolling(accepted.document_id)}>
                        Retry status check
                      </button>
                    </>
                  ) : (
                    <p>Submit the document again. Its idempotency key makes the retry safe.</p>
                  )}
                </div>
              )}
            </div>

            {accepted && (
              <footer className="receipt">
                <span>Acceptance receipt</span>
                <code>Document #{accepted.document_id}</code>
                <code>Job #{accepted.job_id}</code>
              </footer>
            )}
          </section>
        </div>

        <aside className="notice">
          <strong>Simulation note</strong>
          <span>No clinical AI runs in this demo. Use the backend worker simulator to return a canned success or failure.</span>
        </aside>
      </main>
    </div>
  );
}

function StatusBadge({ state }: { state: WorkflowState }) {
  const labels: Record<WorkflowState, string> = {
    idle: "Not started",
    uploading: "Uploading",
    pending: "Pending",
    done: "Complete",
    failed: "Failed",
    connection: "Offline",
  };
  return <span className={`status-badge status-${state}`}>{labels[state]}</span>;
}

function EmptyState({ title, detail, active = false }: { title: string; detail: string; active?: boolean }) {
  return (
    <div className="empty-state">
      <span className={active ? "pulse active" : "pulse"} aria-hidden="true" />
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

function DocumentMeta({ result }: { result: DocumentResult }) {
  return (
    <dl className="document-meta">
      <div><dt>File</dt><dd>{result.filename}</dd></div>
      <div><dt>Size</dt><dd>{Math.max(1, Math.round(result.size_bytes / 1024))} KiB</dd></div>
      <div><dt>Job</dt><dd>#{result.job_id}</dd></div>
    </dl>
  );
}

export default App;
