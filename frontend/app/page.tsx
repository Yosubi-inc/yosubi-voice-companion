"use client";

import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import "./styles.css";
import { transition, type State } from "../lib/conversation";
import { cancelSpeech, speakReply } from "../lib/speak";
import { RealtimeSTT } from "../lib/realtime";
import { Waveform } from "./waveform";
import { detectLanguage, BackendAgent, BackendSTT, type ChatMessage, type TranscriptionSession } from "../lib/voice";

export default function Home() {
  const [state, setState] = useState<State>({ phase: "idle", language: "en" });
  const stateRef = useRef(state);
  const [input, setInput] = useState("");
  const [error, setError] = useState(false);
  const [transcript, setTranscript] = useState<{ role: "user" | "assistant" | "confirmation"; text: string }[]>([]);
  const [micError, setMicError] = useState(false);
  const [partial, setPartial] = useState("");
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
    cancelSpeech();
    setPartial("");
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
    cancelSpeech();
    session.current?.stop();
    if (recorder.current?.state !== "inactive") recorder.current?.stop();
    stream.current?.getTracks().forEach(track => track.stop());
  }, []);
  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
    fetch("/health").catch(() => {});
  }, []);
  const onFinal = async (text: string) => {
    if (!text.trim() || stateRef.current.phase === "idle") return;
    const turn = ++generation.current;
    cancelSpeech();
    const language = detectLanguage(text, stateRef.current.language);
    setPartial("");
    flushSync(() => update(transition(stateRef.current, { type: "transcript", language })));
    messages.current.push({ role: "user", content: text });
    setTranscript(previous => [...previous, { role: "user", text }]);
    try {
      const result = await agent.current.complete([...messages.current], language);
      if (turn !== generation.current) return;
      const spoken = [result.text, result.actionConfirmation].filter(Boolean).join(" ");
      messages.current.push({ role: "assistant", content: spoken });
      setTranscript(previous => [...previous, { role: "assistant", text: result.text }, ...(result.actionConfirmation ? [{ role: "confirmation" as const, text: result.actionConfirmation }] : [])]);
      update(transition(stateRef.current, { type: "reply" }));
      await speakReply(spoken, result.language);
      if (turn === generation.current) update(transition(stateRef.current, { type: "finished" }));
    } catch {
      if (turn === generation.current) { setError(true); update({ phase: "listening", language }); }
    }
  };
  const start = async () => {
    const turn = ++generation.current;
    setError(false);
    setMicError(false);
    setPartial("");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (turn !== generation.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      let live = false;
      try {
        const realtime = new RealtimeSTT({ language: () => stateRef.current.language, stream: () => stream.current, onPartial: setPartial });
        const realtimeSession = realtime.start(onFinal);
        await Promise.race([realtimeSession.ready, new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 2500))]);
        if (turn !== generation.current) { realtimeSession.stop(); media.getTracks().forEach(track => track.stop()); return; }
        session.current = realtimeSession;
        live = true;
      } catch { /* chunked fallback below */ }
      if (!live) {
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
      }
      update(transition(stateRef.current, { type: "start" }));
    } catch { stop(); setMicError(true); }
  };
  const es = state.language === "es";
  const status = state.phase === "idle" ? (es ? "Detenido" : "Stopped") : state.phase === "thinking" ? (es ? "Pensando" : "Thinking") : state.phase === "speaking" ? (es ? "Hablando" : "Speaking") : (es ? "Escuchando" : "Listening");
  return <main className="app">
    <header>

      <h1>Sparks</h1>
      <p className="tagline">{es ? "tu compañero comunitario" : "your community companion"}</p>
    </header>
    <section className="voice-panel" aria-label={es ? "Controles de voz" : "Voice controls"}>
      <div className="indicators">
        <p role="status"><span className={`status-dot ${state.phase}`} aria-hidden="true" />{status}</p>
        <p aria-label={es ? "Idioma" : "Language"}>{es ? "Idioma: ES" : "Language: EN"}</p>
        {partial !== "" && <p aria-live="polite" className="partial">{partial}</p>}
        <Waveform active={state.phase === "listening" || state.phase === "speaking"} color={state.phase === "speaking" ? "blue" : "green"} />
      </div>
      <button className={`voice-button ${state.phase === "idle" ? "talk" : "stop"}`} type="button" onClick={() => state.phase === "idle" ? void start() : stop()}>{state.phase === "idle" ? <><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="11" rx="3" fill="currentColor" /><path d="M5 11a7 7 0 0 0 14 0" fill="none" stroke="currentColor" strokeWidth="2" /><line x1="12" y1="18" x2="12" y2="22" stroke="currentColor" strokeWidth="2" /></svg><span>{es ? "Hablar" : "Talk"}</span></> : <><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" /></svg><span>{es ? "Alto" : "Stop"}</span></>}</button>
      {micError && <div className="error" role="alert"><p>{es ? "No se pudo usar el micrófono. Comprueba el permiso e inténtalo de nuevo." : "Could not use the microphone. Check its permission and try again."}</p><button type="button" onClick={() => void start()}>{es ? "Intentar de nuevo" : "Try again"}</button></div>}
      {error && <p className="error" role="alert">{es ? "No se pudo procesar la respuesta. Inténtalo de nuevo." : "Could not process the reply. Please try again."}</p>}

      <form onSubmit={event => { event.preventDefault(); session.current?.submit(input); setInput(""); }}>
        <label htmlFor="transcript">{es ? "Escribe aquí" : "Type here"}</label>
        <div className="input-row"><input id="transcript" value={input} onChange={event => setInput(event.target.value)} disabled={state.phase === "idle"} /><button type="submit" disabled={state.phase === "idle" || !input.trim()}>{es ? "Enviar" : "Send"}</button></div>
      </form>
    </section>
    <section className="conversation" aria-label={es ? "Conversación" : "Conversation"}>
      <h2>{es ? "Conversación" : "Conversation"}</h2>
      {transcript.length === 0 ? <p>{es ? "Tu conversación aparecerá aquí." : "Your conversation will appear here."}</p> : <ol aria-live="polite">{transcript.map((line, index) => <li key={index} className={line.role}><strong>{line.role === "user" ? (es ? "Tú" : "You") : line.role === "confirmation" ? (es ? "Confirmación" : "Confirmation") : "Sparks"}</strong><p>{line.text}</p></li>)}</ol>}
    </section>
  </main>;
}
