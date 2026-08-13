import { env } from "@/env";
import { supabase } from "@/auth/supabase";
import { ApiError } from "./client";

export type IngestKind = "audio" | "image" | "document" | "url";

export interface Ingested {
  kind: IngestKind;
  source: string;
  text: string;
}

/** Multipart POST — no content-type header, the browser sets the boundary. */
async function upload(path: string, body: FormData): Promise<Response> {
  const headers = new Headers();
  const { data } = await supabase.auth.getSession();
  if (data.session) headers.set("authorization", `Bearer ${data.session.access_token}`);

  const response = await fetch(`${env.apiUrl}${path}`, { method: "POST", headers, body });
  if (!response.ok) {
    const message = await response
      .json()
      .then((body: { detail?: string; error?: string; message?: string }) =>
        body.detail ?? body.error ?? body.message ?? `upload failed (${response.status})`,
      )
      .catch(() => `upload failed (${response.status})`);
    throw new ApiError(
      response.status,
      message,
      response.headers.get("x-login-upsell") !== null,
    );
  }
  return response;
}

/**
 * Public speech-to-text (D7 — anonymous users get voice too). The transcript
 * comes back as text and is then sent as an ordinary chat message: there is no
 * separate voice path through the pipeline.
 */
export async function transcribe(recording: Blob): Promise<string> {
  const form = new FormData();
  form.append("file", recording, "recording.webm");
  const response = await upload("/api/transcribe", form);
  const { text } = (await response.json()) as { text: string };
  return text;
}

/**
 * Pro submission ingestion: voice, flyer photo, PDF/DOCX and links all reduce
 * to text server-side. The caller appends that text to the conversation, where
 * the single extraction path merges it with everything said so far.
 */
export async function ingestFile(file: File): Promise<Ingested> {
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await upload("/api/push/ingest", form);
  return (await response.json()) as Ingested;
}

export async function ingestUrl(url: string): Promise<Ingested> {
  const form = new FormData();
  form.append("url", url);
  const response = await upload("/api/push/ingest", form);
  return (await response.json()) as Ingested;
}
