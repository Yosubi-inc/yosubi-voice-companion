"use client";

import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import "./styles.css";
import { transition, type State } from "../lib/conversation";
import { detectLanguage, BackendAgent, BackendSTT, type ChatMessage, type TranscriptionSession } from "../lib/voice";

export default function Home() {
  const [state, setState] = useState<State>({ phase: "idle", language: "en" });
  const stateRef = useRef(state);
  const [input, setInput] = useState("");
  const [error, setError] = useState(false);
  const [transcript, setTranscript] = useState<{ role: "user" | "assistant" | "confirmation"; text: string }[]>([]);
  const [micError, setMicError] = useState(false);
  const stt = useRef(new BackendSTT(() => stateRef.current.language));
  const agent = useRef(new BackendAgent());
  const session = useRef<TranscriptionSession | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const messages = useRef<ChatMessage[]>([]);
  const recordingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const generation = useRef(0);
  const update = (next: State) => { stateRef.current = next; setState(next); };
  const stop = () => {
    generation.current++;
    if (recordingTimer.current) clearInterval(recordingTimer.current);
    recordingTimer.current = null;
    window.speechSynthesis.cancel();
    session.current?.stop(); session.current = null;
    if (recorder.current?.state !== "inactive") recorder.current?.stop();
    recorder.current = null;
    stream.current?.getTracks().forEach(track => track.stop()); stream.current = null;
    update(transition(stateRef.current, { type: "stop" }));
  };
  useEffect(() => () => {
    generation.current++;
    if (recordingTimer.current) clearInterval(recordingTimer.current);
    recordingTimer.current = null;
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
    flushSync(() => update(transition(stateRef.current, { type: "transcript", language })));
    messages.current.push({ role: "user", content: text });
    setTranscript(previous => [...previous, { role: "user", text }]);
    try {
      const result = await agent.current.complete([...messages.current], language);
      if (turn !== generation.current) return;
      const spoken = [result.text, result.actionConfirmation].filter(Boolean).join(" ");
      messages.current.push({ role: "assistant", content: spoken });
      setTranscript(previous => [...previous, { role: "assistant", text: result.text }, ...(result.actionConfirmation ? [{ role: "confirmation" as const, text: result.actionConfirmation }] : [])]);
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
    setMicError(false);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (turn !== generation.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      session.current = stt.current.start(onFinal);
      recorder.current = new MediaRecorder(media);
      recorder.current.ondataavailable = event => { if (event.data.size) session.current?.pushAudio(event.data); };
      recorder.current.onstop = () => {
        if (session.current && recorder.current && stream.current) recorder.current.start();
      };
      recorder.current.start();
      recordingTimer.current = setInterval(() => {
        if (recorder.current?.state === "recording" && stateRef.current.phase === "listening") recorder.current.stop();
      }, 4000);
      update(transition(stateRef.current, { type: "start" }));
    } catch { stop(); setMicError(true); }
  };
  const es = state.language === "es";
  const status = state.phase === "idle" ? (es ? "Detenido" : "Stopped") : state.phase === "thinking" ? (es ? "Pensando" : "Thinking") : state.phase === "speaking" ? (es ? "Hablando" : "Speaking") : (es ? "Escuchando" : "Listening");
  return <main className="app">
    <header>
      <p className="eyebrow">Yosubi</p>
      <h1>{es ? "Tu compañero de voz" : "Your voice companion"}</h1>
      <p>{es ? "Una conversación sencilla, a tu ritmo." : "A simple conversation, at your pace."}</p>
    </header>
    <section className="voice-panel" aria-label={es ? "Controles de voz" : "Voice controls"}>
      <div className="indicators">
        <p role="status"><span className={`status-dot ${state.phase}`} aria-hidden="true" />{status}</p>
        <p aria-label={es ? "Idioma" : "Language"}>{es ? "Idioma: ES" : "Language: EN"}</p>
      </div>
      <button className="voice-button" type="button" onClick={() => state.phase === "idle" ? void start() : stop()}>{state.phase === "idle" ? "Start talking / Empezar a hablar" : "Stop talking / Dejar de hablar"}</button>
      {micError && <div className="error" role="alert"><p>{es ? "No se pudo usar el micrófono. Comprueba el permiso e inténtalo de nuevo." : "Could not use the microphone. Check its permission and try again."}</p><button type="button" onClick={() => void start()}>{es ? "Intentar de nuevo" : "Try again"}</button></div>}
      {error && <p className="error" role="alert">{es ? "No se pudo procesar la respuesta. Inténtalo de nuevo." : "Could not process the reply. Please try again."}</p>}
      <p className="demo-note">{es ? "Habla o escribe lo que quieres decir. Si el servicio no está disponible, usa el texto de demostración." : "Speak or type what you want to say. If the service is unavailable, use the demo text."}</p>
      <form onSubmit={event => { event.preventDefault(); stt.current.submit(input); setInput(""); }}>
        <label htmlFor="transcript">{es ? "Transcripción simulada" : "Fake transcript"}</label>
        <div className="input-row"><input id="transcript" value={input} onChange={event => setInput(event.target.value)} disabled={state.phase === "idle"} /><button type="submit" disabled={state.phase === "idle" || !input.trim()}>{es ? "Enviar" : "Send"}</button></div>
      </form>
    </section>
    <section className="conversation" aria-label={es ? "Conversación" : "Conversation"}>
      <h2>{es ? "Conversación" : "Conversation"}</h2>
      {transcript.length === 0 ? <p>{es ? "Tu conversación aparecerá aquí." : "Your conversation will appear here."}</p> : <ol aria-live="polite">{transcript.map((line, index) => <li key={index} className={line.role}><strong>{line.role === "user" ? (es ? "Tú" : "You") : line.role === "confirmation" ? (es ? "Confirmación" : "Confirmation") : (es ? "Asistente" : "Assistant")}</strong><p>{line.text}</p></li>)}</ol>}
    </section>
  </main>;
}
