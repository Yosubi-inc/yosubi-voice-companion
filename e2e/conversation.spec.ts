import { expect, test } from "@playwright/test";
import { transition, type State } from "../frontend/lib/conversation";

test("conversation state transitions and ignores stale events", () => {
  let state: State = { phase: "idle", language: "en" };
  expect(transition(state, { type: "transcript", language: "es" })).toEqual(state);
  state = transition(state, { type: "start" });
  expect(state.phase).toBe("listening");
  state = transition(state, { type: "transcript", language: "es" });
  expect(state).toEqual({ phase: "thinking", language: "es" });
  state = transition(state, { type: "reply" });
  expect(state.phase).toBe("speaking");
  state = transition(state, { type: "transcript", language: "en" });
  expect(state).toEqual({ phase: "thinking", language: "en" });
  expect(transition(state, { type: "finished" })).toEqual(state);
  state = transition(state, { type: "reply" });
  state = transition(state, { type: "finished" });
  expect(state.phase).toBe("listening");
  state = transition(state, { type: "stop" });
  expect(transition(state, { type: "reply" })).toEqual(state);
});
