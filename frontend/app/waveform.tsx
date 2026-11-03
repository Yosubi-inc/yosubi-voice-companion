"use client";
import { useEffect, useRef } from "react";

import { getMicAnalyser } from "../lib/realtime";
import { getSpeechAnalyser } from "../lib/speak";

export function Waveform({ active, color }: { active: boolean; color: "green" | "blue" }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    let frame = 0;
    const data = new Uint8Array(128);
    const draw = () => {
      frame = requestAnimationFrame(draw);
      const analyser = color === "blue" ? getSpeechAnalyser() : getMicAnalyser();
      const width = canvas.width;
      const height = canvas.height;
      context.clearRect(0, 0, width, height);
      context.fillStyle = color === "blue" ? "#005a9c" : "#1b8a5a";
      if (!active || !analyser) {
        context.fillRect(0, height / 2 - 1, width, 2);
        return;
      }
      analyser.getByteTimeDomainData(data);
      const bars = 48;
      const gap = width / bars;
      for (let i = 0; i < bars; i++) {
        const v = data[Math.floor((i * data.length) / bars)] / 128 - 1;
        const h = Math.max(2, Math.abs(v) * height);
        context.fillRect(i * gap + 1, (height - h) / 2, gap - 2, h);
      }
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [active, color]);
  return <canvas ref={ref} width={600} height={72} className="waveform" aria-hidden="true" />;
}
