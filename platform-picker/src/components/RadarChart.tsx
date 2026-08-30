import type { PlatformRanking } from '../lib/matcher.js'

const CX = 110
const CY = 110
const MAX_R = 80
const GRID_STEPS = [2, 4, 6, 8, 10]

const PLATFORM_ORDER = ['TikTok', 'YouTube Shorts', 'Instagram Reels', 'Snapchat Spotlight']

const PLATFORM_COLORS: Record<string, string> = {
  'TikTok': '#EE1D52',
  'YouTube Shorts': '#FF0000',
  'Instagram Reels': '#E1306C',
  'Snapchat Spotlight': '#FACC15',
}

const PLATFORM_LABEL: Record<string, string> = {
  'TikTok': 'TikTok',
  'YouTube Shorts': 'YT Shorts',
  'Instagram Reels': 'Reels',
  'Snapchat Spotlight': 'Snapchat',
}

// 4 axes: top, right, bottom, left
const ANGLES = [
  -Math.PI / 2,
  0,
  Math.PI / 2,
  Math.PI,
]

const LABEL_OFFSET = 16

function pt(r: number, idx: number): [number, number] {
  return [CX + r * Math.cos(ANGLES[idx]!), CY + r * Math.sin(ANGLES[idx]!)]
}

function labelPos(idx: number): [number, number] {
  const [x, y] = pt(MAX_R + LABEL_OFFSET, idx)
  return [x!, y!]
}

interface RadarChartProps {
  rankings: PlatformRanking[]
}

export function RadarChart({ rankings }: RadarChartProps) {
  const scoreMap: Record<string, number> = {}
  for (const r of rankings) scoreMap[r.platform] = r.score

  const polygon = PLATFORM_ORDER.map((p, i) => {
    const score = scoreMap[p] ?? 0
    const [x, y] = pt((score / 10) * MAX_R, i)
    return `${x!},${y!}`
  }).join(' ')

  const VIEWBOX = 220

  return (
    <svg viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`} className="w-full max-w-xs mx-auto">
      {/* Grid rings */}
      {GRID_STEPS.map(step => {
        const r = (step / 10) * MAX_R
        const pts = PLATFORM_ORDER.map((_, i) => {
          const [x, y] = pt(r, i)
          return `${x!},${y!}`
        }).join(' ')
        return (
          <polygon
            key={step}
            points={pts}
            fill="none"
            stroke="#1C1C20"
            strokeWidth="1"
          />
        )
      })}

      {/* Axis lines */}
      {PLATFORM_ORDER.map((_, i) => {
        const [x, y] = pt(MAX_R, i)
        return (
          <line
            key={i}
            x1={CX} y1={CY}
            x2={x!} y2={y!}
            stroke="#1C1C20"
            strokeWidth="1"
          />
        )
      })}

      {/* Score polygon */}
      <polygon
        points={polygon}
        fill="#7C3AED"
        fillOpacity="0.25"
        stroke="#A78BFA"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />

      {/* Score dots */}
      {PLATFORM_ORDER.map((p, i) => {
        const score = scoreMap[p] ?? 0
        const [x, y] = pt((score / 10) * MAX_R, i)
        const color = PLATFORM_COLORS[p] ?? '#A78BFA'
        return (
          <circle
            key={p}
            cx={x!} cy={y!}
            r={4}
            fill={color}
            stroke="white"
            strokeWidth="1"
          />
        )
      })}

      {/* Axis labels */}
      {PLATFORM_ORDER.map((p, i) => {
        const [x, y] = labelPos(i)
        const color = PLATFORM_COLORS[p] ?? '#6B6B7A'
        const anchor = i === 0 || i === 2 ? 'middle' : i === 1 ? 'start' : 'end'
        return (
          <text
            key={p}
            x={x!} y={y!}
            fill={color}
            fontSize="8.5"
            fontFamily="Inter, system-ui, sans-serif"
            fontWeight="600"
            textAnchor={anchor}
            dominantBaseline="middle"
          >
            {PLATFORM_LABEL[p] ?? p}
          </text>
        )
      })}

      {/* Center dot */}
      <circle cx={CX} cy={CY} r={2} fill="#6B6B7A" />
    </svg>
  )
}
