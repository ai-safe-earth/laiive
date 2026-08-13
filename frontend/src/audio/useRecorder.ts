import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Microphone capture for the chat composers. Returns the recording as a Blob —
 * transcription happens server-side (`/api/transcribe` for everyone,
 * `/api/push/ingest` inside the pro flow).
 */
export function useRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const release = useCallback(() => {
    recorder.current?.stream.getTracks().forEach((track) => track.stop());
    recorder.current = null;
    chunks.current = [];
    setIsRecording(false);
  }, []);

  // A recording still running when the page unmounts would keep the mic light
  // on until the tab closes.
  useEffect(() => release, [release]);

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const media = new MediaRecorder(stream);
    chunks.current = [];
    media.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.current.push(event.data);
    };
    media.start();
    recorder.current = media;
    setIsRecording(true);
  }, []);

  const stop = useCallback(async (): Promise<Blob> => {
    const media = recorder.current;
    if (!media) throw new Error("not recording");

    const recording = await new Promise<Blob>((resolve) => {
      media.onstop = () => resolve(new Blob(chunks.current, { type: "audio/webm" }));
      media.stop();
    });

    release();
    return recording;
  }, [release]);

  return { isRecording, start, stop };
}
