// AEGIS-Ω Console — neural field backdrop.
// A slow synaptic mesh: drifting nodes connected by proximity edges, rendered
// behind the glass panels. Pure SVG + requestAnimationFrame, GPU-cheap.
// This is the "neural" half of neural glassmorphism — the living substrate the
// frosted glass refracts.

import { useEffect, useRef } from 'react'
import { T } from './consoleTokens.js'

interface Node { x: number; y: number; vx: number; vy: number }

const NODE_COUNT = 34
const LINK_DIST = 150

export function NeuralField() {
  const ref = useRef<SVGSVGElement | null>(null)

  useEffect(() => {
    const svg = ref.current
    if (!svg) return
    const ns = 'http://www.w3.org/2000/svg'
    let w = svg.clientWidth || 1200
    let h = svg.clientHeight || 800

    const nodes: Node[] = Array.from({ length: NODE_COUNT }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.18, vy: (Math.random() - 0.5) * 0.18,
    }))

    // Presence: the cursor is a live node the mesh reaches toward.
    // This is what makes it feel like it knows you're there.
    const cursor = { x: -999, y: -999, active: false }
    const REACH = 220
    function onMove(e: PointerEvent) {
      const rect = svg!.getBoundingClientRect()
      cursor.x = e.clientX - rect.left; cursor.y = e.clientY - rect.top; cursor.active = true
    }
    function onLeave() { cursor.active = false }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerleave', onLeave)

    const linkGroup = document.createElementNS(ns, 'g')
    const nodeGroup = document.createElementNS(ns, 'g')
    svg.appendChild(linkGroup)
    svg.appendChild(nodeGroup)

    const dots = nodes.map(() => {
      const c = document.createElementNS(ns, 'circle')
      c.setAttribute('r', '1.6')
      c.setAttribute('fill', T.indigo)
      c.setAttribute('fill-opacity', '0.5')
      nodeGroup.appendChild(c)
      return c
    })

    let raf = 0
    function frame() {
      while (linkGroup.firstChild) linkGroup.removeChild(linkGroup.firstChild)
      for (let i = 0; i < nodes.length; i += 1) {
        const n = nodes[i]!
        // gentle attraction toward the cursor when it's near — the mesh leans in
        if (cursor.active) {
          const dx = cursor.x - n.x, dy = cursor.y - n.y
          const d = Math.hypot(dx, dy)
          if (d < REACH && d > 1) {
            const pull = (1 - d / REACH) * 0.04
            n.vx += (dx / d) * pull; n.vy += (dy / d) * pull
          }
        }
        n.vx = Math.max(-0.6, Math.min(0.6, n.vx * 0.99))
        n.vy = Math.max(-0.6, Math.min(0.6, n.vy * 0.99))
        n.x += n.vx; n.y += n.vy
        if (n.x < 0 || n.x > w) n.vx *= -1
        if (n.y < 0 || n.y > h) n.vy *= -1
        dots[i]!.setAttribute('cx', n.x.toFixed(1))
        dots[i]!.setAttribute('cy', n.y.toFixed(1))
      }
      // synapses fire from cursor to nearby nodes — visible "it sees you"
      if (cursor.active) {
        for (let i = 0; i < nodes.length; i += 1) {
          const n = nodes[i]!
          const d = Math.hypot(cursor.x - n.x, cursor.y - n.y)
          if (d < REACH) {
            const line = document.createElementNS(ns, 'line')
            line.setAttribute('x1', cursor.x.toFixed(1)); line.setAttribute('y1', cursor.y.toFixed(1))
            line.setAttribute('x2', n.x.toFixed(1)); line.setAttribute('y2', n.y.toFixed(1))
            line.setAttribute('stroke', T.phi)
            line.setAttribute('stroke-opacity', (0.22 * (1 - d / REACH)).toFixed(3))
            line.setAttribute('stroke-width', '0.7')
            linkGroup.appendChild(line)
          }
        }
      }
      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const a = nodes[i]!, b = nodes[j]!
          const dx = a.x - b.x, dy = a.y - b.y
          const d = Math.hypot(dx, dy)
          if (d < LINK_DIST) {
            const line = document.createElementNS(ns, 'line')
            line.setAttribute('x1', a.x.toFixed(1)); line.setAttribute('y1', a.y.toFixed(1))
            line.setAttribute('x2', b.x.toFixed(1)); line.setAttribute('y2', b.y.toFixed(1))
            line.setAttribute('stroke', T.indigo)
            line.setAttribute('stroke-opacity', (0.12 * (1 - d / LINK_DIST)).toFixed(3))
            line.setAttribute('stroke-width', '0.6')
            linkGroup.appendChild(line)
          }
        }
      }
      raf = requestAnimationFrame(frame)
    }
    frame()

    function onResize() { w = svg!.clientWidth || w; h = svg!.clientHeight || h }
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerleave', onLeave)
      svg.removeChild(linkGroup); svg.removeChild(nodeGroup)
    }
  }, [])

  return (
    <svg ref={ref} aria-hidden="true" style={{
      position: 'fixed', inset: 0, width: '100%', height: '100%',
      zIndex: 0, pointerEvents: 'none',
    }} />
  )
}

// Static gradient glow blobs — the colored light the glass refracts.
export function GlowField() {
  const blob = (top: string, left: string, color: string, size: number): import('react').CSSProperties => ({
    position: 'fixed', top, left, width: size, height: size, borderRadius: '50%',
    background: `radial-gradient(circle, ${color}22 0%, transparent 70%)`,
    filter: 'blur(40px)', zIndex: 0, pointerEvents: 'none',
  })
  return (
    <>
      <div style={blob('-8%', '-6%', T.indigo, 520)} />
      <div style={blob('40%', '70%', T.phi, 480)} />
      <div style={blob('78%', '12%', T.green, 420)} />
    </>
  )
}
