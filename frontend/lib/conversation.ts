export type Language = "en" | "es";
export type Phase = "idle" | "listening" | "thinking" | "speaking";
export type State = { phase: Phase; language: Language };
export type Event =
  | { type: "start" }
  | { type: "stop" }
  | { type: "transcript"; language: Language }
  | { type: "reply" }
  | { type: "finished" };

export function transition(state: State, event: Event): State {
  switch (event.type) {
    case "start": return { ...state, phase: "listening" };
    case "stop": return { ...state, phase: "idle" };
    case "transcript": return state.phase === "idle" ? state : { phase: "thinking", language: event.language };
    case "reply": return state.phase === "thinking" ? { ...state, phase: "speaking" } : state;
    case "finished": return state.phase === "speaking" ? { ...state, phase: "listening" } : state;
  }
}
