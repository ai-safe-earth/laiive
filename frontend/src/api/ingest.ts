import { apiFetch } from "./client";

export type IngestKind = "audio" | "image" | "document";

export interface Ingested {
  kind: IngestKind;
  source: string;
  text: string;
}

/**
 * Public speech-to-text (D7 — anonymous users get voice too). The transcript
 * comes back as text and is then sent as an ordinary chat message: there is no
 * separate voice path through the pipeline.
 */
export async function transcribe(recording: Blob): Promise<string> {
  const form = new FormData();
  form.append("file", recording, "recording.webm");
  const response = await apiFetch("/api/transcribe", { method: "POST", body: form });
  const { text } = (await response.json()) as { text: string };
  return text;
}

/**
 * Pro submission ingestion: voice, flyer photo and PDF/DOCX all reduce
 * to text server-side. The caller appends that text to the conversation, where
 * the single extraction path merges it with everything said so far.
 */
export async function ingestFile(file: File): Promise<Ingested> {
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await apiFetch("/api/push/ingest", { method: "POST", body: form });
  return (await response.json()) as Ingested;
}
