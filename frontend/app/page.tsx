"use client";

import { useEffect, useRef, useState } from "react";
import { transition, type State } from "../lib/conversation";
import { detectLanguage, FakeAgent, FakeSTT, type ChatMessage, type TranscriptionSession } from "../lib/voice";

export default function Home() {
  const [state, setState] = useState<State>({ phase: "idle", language: "en" });
  const stateRef = useRef(state);
  const [input, setInput] = useState("");
  const [error, setError] = useState(false);
  const [reply, setReply] = useState("");
  const stt = useRef(new FakeSTT());
  const agent = useRef(new FakeAgent());
  const session = useRef<TranscriptionSession | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const messages = useRef<ChatMessage[]>([]);
  const generation = useRef(0);
  const update = (next: State) => { stateRef.current = next; setState(next); };
  const stop = () => {
    generation.current++;
    window.speechSynthesis.cancel();
    session.current?.stop(); session.current = null;
    if (recorder.current?.state !== "inactive") recorder.current?.stop();
    recorder.current = null;
    stream.current?.getTracks().forEach(track => track.stop()); stream.current = null;
    update(transition(stateRef.current, { type: "stop" }));
  };
  useEffect(() => () => {
    generation.current++;
    window.speechSynthesis.cancel();
    session.current?.stop();
    if (recorder.current?.state !== "inactive") recorder.current?.stop();
    stream.current?.getTracks().forEach(track => track.stop());
  }, []);
  const onFinal = async (text: string) => {
    if (!text.trim() || stateRef.current.phase === "idle") return;
    const turn = ++generation.current;
    window.speechSynthesis.cancel();
    const language = detectLanguage(text, stateRef.current.language);
    update(transition(stateRef.current, { type: "transcript", language }));
    messages.current.push({ role: "user", content: text });
    try {
      const result = await agent.current.complete([...messages.current], language);
      if (turn !== generation.current) return;
      const spoken = [result.text, result.actionConfirmation].filter(Boolean).join(" ");
      messages.current.push({ role: "assistant", content: spoken });
      setReply(spoken);
      const utterance = new SpeechSynthesisUtterance(spoken);
      utterance.lang = result.language === "es" ? "es-ES" : "en-US";
      utterance.onend = utterance.onerror = () => {
        if (turn === generation.current) update(transition(stateRef.current, { type: "finished" }));
      };
      update(transition(stateRef.current, { type: "reply" }));
      window.speechSynthesis.speak(utterance);
    } catch {
      if (turn === generation.current) { setError(true); update({ phase: "listening", language }); }
    }
  };
  const start = async () => {
    const turn = ++generation.current;
    setError(false);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (turn !== generation.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      session.current = stt.current.start(onFinal);
      recorder.current = new MediaRecorder(media);
      recorder.current.ondataavailable = event => { if (event.data.size) session.current?.pushAudio(event.data); };
      recorder.current.start(250);
      update(transition(stateRef.current, { type: "start" }));
    } catch { stop(); setError(true); }
  };
  const es = state.language === "es";
  return <main>
    <h1>Yosubi Voice Companion</h1>
    <p>{es ? "Demostración: el micrófono está activo, pero la transcripción es simulada. Escribe lo que dirías." : "Demo: the microphone is active, but transcription is simulated. Type what you would say."}</p>
    <button type="button" onClick={() => state.phase === "idle" ? void start() : stop()}>{state.phase === "idle" ? "Start talking / Empezar a hablar" : "Stop talking / Dejar de hablar"}</button>
    <p role="status">{state.phase === "idle" ? (es ? "Detenido" : "Stopped") : state.phase === "thinking" ? (es ? "Pensando" : "Thinking") : state.phase === "speaking" ? (es ? "Hablando" : "Speaking") : (es ? "Escuchando" : "Listening")}</p>
    {error && <p role="alert">{es ? "No se pudo usar el micrófono o procesar la respuesta. Inténtalo de nuevo." : "Could not use the microphone or process the reply. Please try again."}</p>}
    <form onSubmit={event => { event.preventDefault(); stt.current.submit(input); setInput(""); }}>
      <label htmlFor="transcript">{es ? "Transcripción simulada" : "Fake transcript"}</label>{" "}
      <input id="transcript" value={input} onChange={event => setInput(event.target.value)} disabled={state.phase === "idle"} />{" "}
      <button type="submit" disabled={state.phase === "idle" || !input.trim()}>{es ? "Enviar" : "Send"}</button>
    </form>
    {reply && <p>{reply}</p>}
  </main>;
}
