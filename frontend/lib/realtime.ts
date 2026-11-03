import type { Language } from "./conversation";
import type { TranscriptionSession } from "./voice";

export function downsampleTo16k(input: Float32Array, fromRate: number): Int16Array {
  if (fromRate === 16000) {
    const out = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) out[i] = Math.max(-1, Math.min(1, input[i])) * 32767;
    return out;
  }
  const ratio = fromRate / 16000;
  const length = Math.floor(input.length / ratio);
  const out = new Int16Array(length);
  for (let i = 0; i < length; i++) {
    const position = i * ratio;
    const index = Math.floor(position);
    const fraction = position - index;
    const a = input[index] ?? 0;
    const b = input[index + 1] ?? a;
    out[i] = Math.max(-1, Math.min(1, a + (b - a) * fraction)) * 32767;
  }
  return out;
}

const WORKLET = `class Capture extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice(0));
    return true;
  }
}
registerProcessor("sparks-capture", Capture);`;

export function voiceStreamUrl(language: Language, token = process.env.NEXT_PUBLIC_DEMO_API_TOKEN || ""): string {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const protocol = base
    ? (new URL(base).protocol === "https:" ? "wss:" : "ws:")
    : (typeof location !== "undefined" && location.protocol === "https:" ? "wss:" : "ws:");
  const host = base ? new URL(base).host : typeof location !== "undefined" ? location.host : "127.0.0.1:8000";
  return `${protocol}//${host}/voice/stream?token=${encodeURIComponent(token)}&language=${language}`;
}

let micAnalyser: AnalyserNode | null = null;

export function getMicAnalyser(): AnalyserNode | null {
  return micAnalyser;
}

function setMicAnalyser(node: AnalyserNode | null): void {
  micAnalyser = node;
}

export function isDuplicateFinal(text: string, previous: string, elapsedMs: number, windowMs = 4000): boolean {
  if (elapsedMs >= windowMs) return false;
  const normalize = (value: string) => value.toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  const current = normalize(text);
  return current !== "" && current === normalize(previous);
}

export interface RealtimeOptions {
  language: () => Language;
  stream: () => MediaStream | null;
  onPartial?: (text: string) => void;
}

export class RealtimeSTT {
  constructor(private options: RealtimeOptions) {}

  start(onFinal: (text: string) => void): TranscriptionSession & { ready: Promise<void> } {
    let socket: WebSocket | null = null;
    let context: AudioContext | null = null;
    let lastFinal = "";
    let lastFinalAt = 0;
    let stopped = false;
    let settled = false;
    let resolveReady!: () => void;
    let rejectReady!: (reason?: unknown) => void;
    const ready = new Promise<void>((resolve, reject) => { resolveReady = resolve; rejectReady = reject; });
    const finish = (error?: unknown) => {
      if (settled) return;
      settled = true;
      if (error) rejectReady(error); else resolveReady();
    };

    const cleanup = () => {
      stopped = true;
      try { socket?.close(); } catch { /* closed */ }
      socket = null;
      if (context) void context.close().catch(() => {});
      context = null;
      setMicAnalyser(null);
    };

    const session: TranscriptionSession & { ready: Promise<void> } = {
      ready,
      pushAudio: () => {},
      submit: (text: string) => { if (!stopped) onFinal(text); },
      stop: () => {
        try { socket?.send(JSON.stringify({ type: "endStream" })); } catch { /* closed */ }
        cleanup();
        finish();
      },
    };

    (async () => {
      try {
        const media = this.options.stream();
        if (!media) throw new Error("no media");
        const language = this.options.language();
        const ws = new WebSocket(voiceStreamUrl(language));
        socket = ws;
        ws.binaryType = "arraybuffer";
        ws.onclose = event => { if (!settled) finish(new Error(`closed ${event.code}`)); };
        ws.onerror = () => { if (!settled) finish(new Error("socket")); };
        ws.onmessage = event => {
          if (typeof event.data !== "string") return;
          let message: { type?: string; transcript?: string };
          try { message = JSON.parse(event.data); } catch { return; }
          if (message.type === "ready") { finish(); return; }
          if (message.type === "transcript" && message.transcript) this.options.onPartial?.(message.transcript);
          if (message.type === "speechComplete" && message.transcript && !stopped) {
            const now = Date.now();
            if (!isDuplicateFinal(message.transcript, lastFinal, now - lastFinalAt)) {
              lastFinal = message.transcript;
              lastFinalAt = now;
              onFinal(message.transcript);
            }
          }
          if (message.type === "error") finish(new Error("upstream"));
        };
        await ready;
        if (stopped) return;
        const audio = new AudioContext({ latencyHint: "interactive" });
        context = audio;
        await audio.resume().catch(() => {});
        const analyser = audio.createAnalyser();
        analyser.fftSize = 256;
        setMicAnalyser(analyser);
        await audio.audioWorklet.addModule(URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" })));
        const source = audio.createMediaStreamSource(media);
        const node = new AudioWorkletNode(audio, "sparks-capture");
        node.port.onmessage = (event: MessageEvent<Float32Array>) => {
          if (stopped || ws.readyState !== WebSocket.OPEN) return;
          ws.send(downsampleTo16k(event.data, audio.sampleRate).buffer as ArrayBuffer);
        };
        source.connect(node);
        source.connect(analyser);
      } catch (error) {
        cleanup();
        finish(error);
      }
    })();

    return session;
  }
}
