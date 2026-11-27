import { useMemo } from "react";
import { normalizeVolumeKeyframes, volumeAtTime, type VolumeKeyframe } from "../lib/audioAutomation";

type Props = {
  keyframes: VolumeKeyframe[];
  duration: number;
  playhead: number;
  fallbackVolume: number;
  onChange: (points: VolumeKeyframe[]) => void;
};

const WIDTH = 560;
const HEIGHT = 150;
const PAD_X = 24;
const PAD_Y = 16;

export function AudioAutomationCurve({ keyframes, duration, playhead, fallbackVolume, onChange }: Props) {
  const safeDuration = Math.max(0.1, duration);
  const points = useMemo(() => normalizeVolumeKeyframes(keyframes, safeDuration), [keyframes, safeDuration]);
  const x = (time: number) => PAD_X + (time / safeDuration) * (WIDTH - PAD_X * 2);
  const y = (gain: number) => HEIGHT - PAD_Y - (gain / 2) * (HEIGHT - PAD_Y * 2);
  const curve = points.length
    ? points.map((point) => `${x(point.time)},${y(point.volume)}`).join(" ")
    : `${PAD_X},${y(fallbackVolume)} ${WIDTH - PAD_X},${y(fallbackVolume)}`;
  const currentGain = volumeAtTime(points, Math.min(safeDuration, Math.max(0, playhead)), fallbackVolume);

  const updatePoint = (index: number, patch: Partial<VolumeKeyframe>) => {
    const next = points.map((point, pointIndex) => pointIndex === index ? { ...point, ...patch } : point);
    onChange(normalizeVolumeKeyframes(next, safeDuration));
  };

  return <section className="audio-automation-curve" aria-label="Volume automation curve editor">
    <div className="audio-automation-heading"><strong>Automation curve</strong><span>Playhead gain: {currentGain.toFixed(2)}×</span></div>
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Volume gain curve from zero to two times">
      {[0, 0.5, 1, 1.5, 2].map((gain) => <g key={gain}>
        <line x1={PAD_X} x2={WIDTH - PAD_X} y1={y(gain)} y2={y(gain)} className="automation-grid"/>
        <text x="3" y={y(gain) + 4} className="automation-axis-label">{gain.toFixed(1)}×</text>
      </g>)}
      <line x1={x(Math.min(safeDuration, Math.max(0, playhead)))} x2={x(Math.min(safeDuration, Math.max(0, playhead)))} y1={PAD_Y} y2={HEIGHT - PAD_Y} className="automation-playhead"/>
      <polyline points={curve} fill="none" className="automation-line"/>
      {points.map((point, index) => <circle key={`${point.time}-${index}`} cx={x(point.time)} cy={y(point.volume)} r="6" className="automation-point"/>) }
    </svg>
    <div className="audio-automation-controls">
      {points.map((point, index) => <div className="automation-point-control" key={`${point.time}-${index}`}>
        <strong>Point {index + 1}</strong>
        <label>Time {point.time.toFixed(2)}s
          <input aria-label={`Point ${index + 1} time`} type="range" min="0" max={safeDuration} step="0.01" value={point.time}
            onChange={(event) => updatePoint(index, { time: Number(event.target.value) })}/>
        </label>
        <label>Gain {point.volume.toFixed(2)}×
          <input aria-label={`Point ${index + 1} gain`} type="range" min="0" max="2" step="0.01" value={point.volume}
            onChange={(event) => updatePoint(index, { volume: Number(event.target.value) })}/>
        </label>
        <button type="button" onClick={() => onChange(points.filter((_, pointIndex) => pointIndex !== index))}>Remove</button>
      </div>)}
      {!points.length && <small>No automation points yet. Add a point at the playhead to start shaping the volume.</small>}
    </div>
  </section>;
}
