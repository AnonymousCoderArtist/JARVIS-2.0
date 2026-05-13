import { useState, useRef, useCallback } from "react";
import { Mic, Square, Loader2 } from "lucide-react";

interface VoiceInputProps {
  onTranscript: (text: string) => void;
}

export function VoiceInput({ onTranscript }: VoiceInputProps) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunks.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.current.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunks.current, { type: "audio/webm" });
        if (blob.size > 0) {
          setTranscribing(true);
          try {
            const formData = new FormData();
            formData.append("audio", blob, "recording.webm");
            const res = await fetch("/api/voice/transcribe", { method: "POST", body: formData });
            const data = await res.json();
            if (data.text) onTranscript(data.text);
          } catch { }
          setTranscribing(false);
        }
      };
      recorder.start();
      mediaRecorder.current = recorder;
      setRecording(true);
    } catch { }
  }, [onTranscript]);

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop();
      setRecording(false);
    }
  }, []);

  return (
    <button
      type="button"
      onClick={recording ? stopRecording : startRecording}
      disabled={transcribing}
      className="flex h-8 w-8 items-center justify-center rounded-lg transition-all disabled:opacity-40"
      style={{
        color: recording ? "rgba(255, 80, 80, 0.9)" : "rgba(100, 140, 220, 0.5)",
        background: recording ? "rgba(255, 80, 80, 0.15)" : "transparent",
      }}
    >
      {transcribing ? <Loader2 className="h-4 w-4 animate-spin" /> : recording ? <Square className="h-3.5 w-3.5" /> : <Mic className="h-4 w-4" />}
    </button>
  );
}
