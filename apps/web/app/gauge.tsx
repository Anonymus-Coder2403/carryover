const CX = 130;
const CY = 140;
const TICK_COUNT = 21;

function zoneColor(fraction: number) {
  if (fraction < 0.4) return "var(--line)";
  if (fraction < 0.6) return "var(--brass)";
  return "var(--rust)";
}

function toRad(fraction: number) {
  return ((180 - fraction * 180) * Math.PI) / 180;
}

export function Gauge() {
  const ticks = Array.from({ length: TICK_COUNT }, (_, i) => {
    const fraction = i / (TICK_COUNT - 1);
    const major = i % 4 === 0;
    const angle = toRad(fraction);
    const inner = 98;
    const outer = major ? 118 : 108;
    return {
      key: i,
      x1: CX + inner * Math.cos(angle),
      y1: CY - inner * Math.sin(angle),
      x2: CX + outer * Math.cos(angle),
      y2: CY - outer * Math.sin(angle),
      color: zoneColor(fraction),
      width: major ? 2.5 : 1.25,
    };
  });

  const needleAngle = toRad(0.52);
  const needleX = CX + 84 * Math.cos(needleAngle);
  const needleY = CY - 84 * Math.sin(needleAngle);

  return (
    <svg
      viewBox="0 0 260 160"
      className="w-full max-w-xs"
      role="img"
      aria-label="Context health meter: healthy below 40 percent, degrading between 40 and 60, hand off above 60. Shown mid degrading."
    >
      {ticks.map((t) => (
        <line
          key={t.key}
          x1={t.x1}
          y1={t.y1}
          x2={t.x2}
          y2={t.y2}
          stroke={t.color}
          strokeWidth={t.width}
          strokeLinecap="round"
        />
      ))}
      <line x1={CX} y1={CY} x2={needleX} y2={needleY} stroke="var(--ink)" strokeWidth={2.5} strokeLinecap="round" />
      <circle cx={CX} cy={CY} r={5} fill="var(--ink)" />
      <text x={12} y={CY + 22} fontFamily="var(--font-data)" fontSize="11" fill="var(--ink)" opacity={0.55}>
        Healthy
      </text>
      <text x={CX - 26} y={16} fontFamily="var(--font-data)" fontSize="11" fill="var(--ink)" opacity={0.55}>
        Degrading
      </text>
      <text x={205} y={CY + 22} fontFamily="var(--font-data)" fontSize="11" fill="var(--ink)" opacity={0.55}>
        Hand off
      </text>
    </svg>
  );
}
