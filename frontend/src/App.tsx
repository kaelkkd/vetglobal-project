import { useEffect, useRef, useState } from "react";
import type { ReactNode, SubmitEvent } from "react";

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

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

type WorkflowState = "idle" | "uploading" | "pending" | "done" | "failed" | "connection";
type Theme = "light" | "dark";

const COPY = {
  en: {
    documentOperations: "Document operations",
    localAssessment: "Local assessment",
    workflow: "Document workflow",
    title: "Clinical summary intake",
    introduction: "Create a pet record, upload a TXT or PDF, and follow its processing state.",
    mode: "Mode",
    simulation: "Simulation",
    sequence: "Sequence",
    sequenceValue: "Record / Document / Result",
    petRecord: "Pet record",
    petDescription: "Start a new single-pet workspace.",
    petName: "Pet name",
    ownerName: "Owner name",
    creating: "Creating…",
    createAnotherPet: "Create another pet",
    createPet: "Create pet",
    currentRecord: "Current record",
    owner: "Owner",
    document: "Document",
    documentDescription: "Attach the source material for this record.",
    fileRequirements: "Accepted file requirements",
    maximum: "Maximum 5 MiB",
    selectDocument: "Select document",
    selectedDocument: "Selected document",
    format: "Format",
    size: "Size",
    uploadingButton: "Uploading…",
    processingButton: "Processing…",
    uploadDocument: "Upload document",
    statusLabel: "Status",
    summaryResult: "Summary result",
    readyTitle: "Ready for a document",
    readyDetail: "Complete both intake steps to start the simulated workflow.",
    processingSequence: "Processing sequence",
    acceptedStep: "Document accepted",
    queuedStep: "Job queued",
    deliveredStep: "Result delivered",
    uploadingTitle: "Uploading securely",
    uploadingDetail: "The document and its job are being saved together.",
    pendingTitle: "Awaiting worker result",
    pendingDetail: (attempt: number) => attempt ? `Connection retry ${attempt} of 4…` : "Long polling is active. Complete the job with the CLI simulator.",
    summaryComplete: "Summary complete",
    processingFailed: "Processing failed",
    connectionInterrupted: "Connection interrupted",
    persistedJob: "The job is still persisted. Reconnect without uploading it again.",
    retryStatus: "Retry status check",
    safeRetry: "Submit the document again. Its idempotency key makes the retry safe.",
    receipt: "Acceptance receipt",
    file: "File",
    job: "Job",
    switchLanguage: "Mudar para português brasileiro",
    switchTheme: (theme: Theme) => theme === "light" ? "Enable dark mode" : "Enable light mode",
    themeAction: (theme: Theme) => theme === "light" ? "Dark mode" : "Light mode",
    status: { idle: "Not started", uploading: "Uploading", pending: "Pending", done: "Complete", failed: "Failed", connection: "Offline" },
  },
  "pt-BR": {
    documentOperations: "Operações de documentos",
    localAssessment: "Ambiente local",
    workflow: "Fluxo de documentos",
    title: "Entrada de resumo clínico",
    introduction: "Crie o cadastro do pet, envie um TXT ou PDF e acompanhe o processamento.",
    mode: "Modo",
    simulation: "Simulação",
    sequence: "Sequência",
    sequenceValue: "Cadastro / Documento / Resultado",
    petRecord: "Cadastro do pet",
    petDescription: "Inicie um novo espaço de trabalho para um único pet.",
    petName: "Nome do pet",
    ownerName: "Nome do tutor",
    creating: "Criando…",
    createAnotherPet: "Cadastrar outro pet",
    createPet: "Cadastrar pet",
    currentRecord: "Cadastro atual",
    owner: "Tutor",
    document: "Documento",
    documentDescription: "Anexe o material de origem deste cadastro.",
    fileRequirements: "Requisitos de arquivo aceitos",
    maximum: "Máximo de 5 MiB",
    selectDocument: "Selecionar documento",
    selectedDocument: "Documento selecionado",
    format: "Formato",
    size: "Tamanho",
    uploadingButton: "Enviando…",
    processingButton: "Processando…",
    uploadDocument: "Enviar documento",
    statusLabel: "Status",
    summaryResult: "Resultado do resumo",
    readyTitle: "Pronto para receber um documento",
    readyDetail: "Conclua as duas etapas de entrada para iniciar o fluxo simulado.",
    processingSequence: "Sequência de processamento",
    acceptedStep: "Documento aceito",
    queuedStep: "Tarefa na fila",
    deliveredStep: "Resultado entregue",
    uploadingTitle: "Envio seguro em andamento",
    uploadingDetail: "O documento e sua tarefa estão sendo salvos juntos.",
    pendingTitle: "Aguardando o resultado",
    pendingDetail: (attempt: number) => attempt ? `Tentativa de reconexão ${attempt} de 4…` : "A consulta está ativa. Conclua a tarefa com o simulador pela linha de comando.",
    summaryComplete: "Resumo concluído",
    processingFailed: "Falha no processamento",
    connectionInterrupted: "Conexão interrompida",
    persistedJob: "A tarefa continua salva. Reconecte sem enviar o documento novamente.",
    retryStatus: "Tentar consultar novamente",
    safeRetry: "Envie o documento novamente. A chave de idempotência torna a tentativa segura.",
    receipt: "Comprovante de aceite",
    file: "Arquivo",
    job: "Tarefa",
    switchLanguage: "Switch to English",
    switchTheme: (theme: Theme) => theme === "light" ? "Ativar modo escuro" : "Ativar modo claro",
    themeAction: (theme: Theme) => theme === "light" ? "Modo escuro" : "Modo claro",
    status: { idle: "Não iniciado", uploading: "Enviando", pending: "Pendente", done: "Concluído", failed: "Falhou", connection: "Sem conexão" },
  },
} as const;

type Locale = keyof typeof COPY;

function App() {
  const [locale, setLocale] = useState<Locale>(() => localStorage.getItem("vetglobal-locale") === "pt-BR" ? "pt-BR" : "en");
  const [theme, setTheme] = useState<Theme>(() => {
    const savedTheme = localStorage.getItem("vetglobal-theme");
    if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
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
  const copy = COPY[locale];

  useEffect(() => () => pollingController.current?.abort(), []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = locale === "pt-BR" ? "Área de trabalho VetGlobal" : "VetGlobal Workspace";
    localStorage.setItem("vetglobal-locale", locale);
  }, [locale]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("vetglobal-theme", theme);
  }, [theme]);

  async function startPolling(documentId: number) {
    pollingController.current?.abort();
    const controller = new AbortController();
    pollingController.current = controller;
    setWorkflow("pending");
    setRetryAttempt(0);
    try {
      const document = await waitForTerminalDocument(API_BASE_URL, documentId, controller.signal, setRetryAttempt);
      setResult(document);
      setWorkflow(document.status === "DONE" ? "done" : "failed");
    } catch (error) {
      if (controller.signal.aborted) return;
      setUploadError(errorMessage(error));
      setWorkflow(error instanceof ConnectionError ? "connection" : "failed");
    }
  }

  async function handlePetSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedForm = event.currentTarget;
    const form = new FormData(submittedForm);
    setPetBusy(true);
    setPetError("");
    try {
      const created = await createPet(API_BASE_URL, { name: String(form.get("name") ?? ""), owner_name: String(form.get("ownerName") ?? "") });
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

  async function handleUpload(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pet || !selectedFile) return;
    pollingController.current?.abort();
    setWorkflow("uploading");
    setUploadError("");
    setAccepted(null);
    setResult(null);
    try {
      const receipt = await uploadDocument(API_BASE_URL, pet.id, selectedFile, uploadKey.current);
      setAccepted(receipt);
      await startPolling(receipt.document_id);
    } catch (error) {
      setUploadError(errorMessage(error));
      const connectionFailure = !(error instanceof ApiError) || error.status >= 500 || error instanceof ConnectionError;
      setWorkflow(connectionFailure ? "connection" : "failed");
    }
  }

  const busy = workflow === "uploading" || workflow === "pending";

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main" aria-label={`VetGlobal — ${copy.localAssessment}`}>
          <span className="brand-mark" aria-hidden="true">V</span>
          <span className="brand-name">VetGlobal</span>
        </a>
        <div className="topbar-context">
          <div className="environment">
            <span>{copy.documentOperations}</span><span aria-hidden="true">/</span><strong>{copy.localAssessment}</strong>
          </div>
          <div className="interface-controls">
            <button className="utility-button" type="button" onClick={() => setLocale(locale === "en" ? "pt-BR" : "en")} aria-label={copy.switchLanguage} title={copy.switchLanguage}>
              {locale === "en" ? "PT-BR" : "EN"}
            </button>
            <button className="utility-button theme-button" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={copy.switchTheme(theme)} title={copy.switchTheme(theme)}>
              <span aria-hidden="true">{theme === "light" ? "◐" : "◑"}</span>{copy.themeAction(theme)}
            </button>
          </div>
        </div>
      </header>

      <main id="main" className="workspace">
        <div className="page-heading">
          <div className="heading-copy">
            <p className="eyebrow">{copy.workflow}</p><h1>{copy.title}</h1><p>{copy.introduction}</p>
          </div>
          <dl className="workflow-context" aria-label={copy.workflow}>
            <div><dt>{copy.mode}</dt><dd>{copy.simulation}</dd></div>
            <div><dt>{copy.sequence}</dt><dd>{copy.sequenceValue}</dd></div>
          </dl>
        </div>

        <div className="workflow-grid">
          <section className="panel intake-panel" aria-labelledby="pet-heading">
            <div className="step-heading">
              <span className="step-number">01</span><div><h2 id="pet-heading">{copy.petRecord}</h2><p>{copy.petDescription}</p></div>
            </div>
            <form onSubmit={handlePetSubmit} className="form-stack">
              <label>{copy.petName}<input name="name" maxLength={120} required placeholder="Hank" /></label>
              <label>{copy.ownerName}<input name="ownerName" maxLength={200} required placeholder="John Bergeson" /></label>
              {petError && <p className="form-error" role="alert">{petError}</p>}
              <button type="submit" disabled={petBusy}>{petBusy ? copy.creating : pet ? copy.createAnotherPet : copy.createPet}</button>
            </form>

            {pet && (
              <div className="record-card" aria-live="polite">
                <span className="record-initial" aria-hidden="true">{pet.name.charAt(0).toUpperCase()}</span>
                <div className="record-identity"><span className="record-label">{copy.currentRecord}</span><strong>{pet.name}</strong><span>{copy.owner}: {pet.owner_name}</span></div>
                <code>Pet #{pet.id}</code>
              </div>
            )}

            <div className="step-divider" />
            <div className="step-heading">
              <span className="step-number">02</span><div><h2 id="upload-heading">{copy.document}</h2><p>{copy.documentDescription}</p></div>
            </div>
            <form onSubmit={handleUpload} className="form-stack" aria-labelledby="upload-heading">
              <div id="file-requirements" className="file-requirements" aria-label={copy.fileRequirements}><span>TXT</span><span>PDF</span><span>{copy.maximum}</span></div>
              <label className="file-control">
                {copy.selectDocument}
                <input type="file" accept=".txt,.pdf,text/plain,application/pdf" aria-describedby="file-requirements" disabled={!pet || busy} required onChange={(event) => { setSelectedFile(event.target.files?.[0] ?? null); uploadKey.current = crypto.randomUUID(); }} />
              </label>
              {selectedFile && (
                <div className="file-summary" aria-live="polite">
                  <div><span>{copy.selectedDocument}</span><strong title={selectedFile.name}>{selectedFile.name}</strong></div>
                  <dl><div><dt>{copy.format}</dt><dd>{fileExtension(selectedFile)}</dd></div><div><dt>{copy.size}</dt><dd>{formatFileSize(selectedFile.size)}</dd></div></dl>
                </div>
              )}
              <button type="submit" disabled={!pet || !selectedFile || busy}>{workflow === "uploading" ? copy.uploadingButton : workflow === "pending" ? copy.processingButton : copy.uploadDocument}</button>
            </form>
          </section>

          <section className="panel status-panel" aria-labelledby="status-heading">
            <div className="status-header">
              <div><p className="eyebrow">{copy.statusLabel}</p><h2 id="status-heading">{copy.summaryResult}</h2></div>
              <StatusBadge state={workflow} labels={copy.status} />
            </div>
            <div className="status-content" aria-live="polite">
              {workflow === "idle" && (
                <EmptyState title={copy.readyTitle} detail={copy.readyDetail}>
                  <ol className="workflow-preview" aria-label={copy.processingSequence}><li><span>01</span>{copy.acceptedStep}</li><li><span>02</span>{copy.queuedStep}</li><li><span>03</span>{copy.deliveredStep}</li></ol>
                </EmptyState>
              )}
              {workflow === "uploading" && <EmptyState title={copy.uploadingTitle} detail={copy.uploadingDetail} active />}
              {workflow === "pending" && <EmptyState title={copy.pendingTitle} detail={copy.pendingDetail(retryAttempt)} active />}
              {workflow === "done" && result && (
                <div className="result-block success"><p className="result-kicker">{copy.summaryComplete}</p><blockquote>{result.summary}</blockquote><DocumentMeta result={result} labels={copy} /></div>
              )}
              {workflow === "failed" && (
                <div className="result-block failure" role="alert"><p className="result-kicker">{copy.processingFailed}</p><h3>{result?.error ?? uploadError}</h3>{result && <DocumentMeta result={result} labels={copy} />}</div>
              )}
              {workflow === "connection" && (
                <div className="result-block failure" role="alert">
                  <p className="result-kicker">{copy.connectionInterrupted}</p><h3>{uploadError}</h3>
                  {accepted ? <><p>{copy.persistedJob}</p><button type="button" onClick={() => void startPolling(accepted.document_id)}>{copy.retryStatus}</button></> : <p>{copy.safeRetry}</p>}
                </div>
              )}
            </div>
            {accepted && <footer className="receipt"><span>{copy.receipt}</span><code>{copy.document} #{accepted.document_id}</code><code>{copy.job} #{accepted.job_id}</code></footer>}
          </section>
        </div>
      </main>
    </div>
  );
}

function StatusBadge({ state, labels }: { state: WorkflowState; labels: Readonly<Record<WorkflowState, string>> }) {
  return <span className={`status-badge status-${state}`}>{labels[state]}</span>;
}

function EmptyState({ title, detail, active = false, children }: { title: string; detail: string; active?: boolean; children?: ReactNode }) {
  return <div className="empty-state"><span className={active ? "pulse active" : "pulse"} aria-hidden="true" /><h3>{title}</h3><p>{detail}</p>{children}</div>;
}

function fileExtension(file: File) {
  const extension = file.name.split(".").pop();
  return extension ? extension.toUpperCase() : "FILE";
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(bytes < 1024 * 100 ? 1 : 0)} KiB`;
}

function DocumentMeta({ result, labels }: { result: DocumentResult; labels: { file: string; size: string; job: string } }) {
  return <dl className="document-meta"><div><dt>{labels.file}</dt><dd>{result.filename}</dd></div><div><dt>{labels.size}</dt><dd>{Math.max(1, Math.round(result.size_bytes / 1024))} KiB</dd></div><div><dt>{labels.job}</dt><dd>#{result.job_id}</dd></div></dl>;
}

export default App;
