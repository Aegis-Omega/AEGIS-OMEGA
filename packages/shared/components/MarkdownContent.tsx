import type { ReactNode } from 'react'

function renderInline(text: string): ReactNode {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]*\]\([^)]*\))/g)
  if (tokens.length === 1) return text
  return (
    <>
      {tokens.map((t, i) => {
        if (t.startsWith('**') && t.endsWith('**') && t.length > 4)
          return <strong key={i} style={{ color: '#ECEAE3', fontWeight: 600 }}>{t.slice(2, -2)}</strong>
        if (t.startsWith('`') && t.endsWith('`') && t.length > 2)
          return (
            <code key={i} style={{
              background: '#1A1A1E', padding: '0.1em 0.4em', borderRadius: '4px',
              fontFamily: 'monospace', fontSize: '0.85em', color: '#C8A96E',
              border: '1px solid #2A2A2E',
            }}>
              {t.slice(1, -1)}
            </code>
          )
        const m = t.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
        if (m)
          return <a key={i} href={m[2]} target="_blank" rel="noopener noreferrer" style={{ color: '#60A5FA', textDecoration: 'underline' }}>{m[1]}</a>
        return t || null
      })}
    </>
  )
}

export function MarkdownContent({ content }: { content: string }) {
  const nodes: ReactNode[] = []
  const lines = content.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) { codeLines.push(lines[i]); i++ }
      i++
      nodes.push(
        <div key={nodes.length} style={{ margin: '8px 0', borderRadius: '8px', overflow: 'hidden', border: '1px solid #1E1E22' }}>
          {lang && (
            <div style={{ background: '#0C0C0E', padding: '5px 14px', borderBottom: '1px solid #1E1E22', fontFamily: 'monospace', fontSize: '11px', color: '#6B6B7A' }}>
              {lang}
            </div>
          )}
          <pre style={{ background: '#0A0A0C', padding: '12px 14px', overflow: 'auto', margin: 0 }}>
            <code style={{ fontFamily: '"Fira Code","Cascadia Code","JetBrains Mono",monospace', fontSize: '12px', color: '#ECEAE3', whiteSpace: 'pre' }}>
              {codeLines.join('\n')}
            </code>
          </pre>
        </div>
      )
      continue
    }

    if (/^---+$/.test(line) || /^===+$/.test(line)) {
      nodes.push(<hr key={nodes.length} style={{ border: 'none', borderTop: '1px solid #1E1E22', margin: '10px 0' }} />)
      i++; continue
    }

    const h3m = line.match(/^### (.+)/); if (h3m) { nodes.push(<h3 key={nodes.length} style={{ color: '#ECEAE3', fontWeight: 600, fontSize: '0.9em', margin: '12px 0 3px' }}>{renderInline(h3m[1])}</h3>); i++; continue }
    const h2m = line.match(/^## (.+)/);  if (h2m) { nodes.push(<h2 key={nodes.length} style={{ color: '#ECEAE3', fontWeight: 600, fontSize: '1em',   margin: '14px 0 4px' }}>{renderInline(h2m[1])}</h2>); i++; continue }
    const h1m = line.match(/^# (.+)/);   if (h1m) { nodes.push(<h1 key={nodes.length} style={{ color: '#ECEAE3', fontWeight: 700, fontSize: '1.1em', margin: '14px 0 5px' }}>{renderInline(h1m[1])}</h1>); i++; continue }

    if (/^[-*+] /.test(line)) {
      const items: ReactNode[] = []
      while (i < lines.length && /^[-*+] /.test(lines[i])) {
        items.push(<li key={items.length} style={{ margin: '2px 0' }}>{renderInline(lines[i].replace(/^[-*+] /, ''))}</li>)
        i++
      }
      nodes.push(<ul key={nodes.length} style={{ margin: '6px 0', paddingLeft: '18px', listStyleType: 'disc' }}>{items}</ul>)
      continue
    }

    if (/^\d+\. /.test(line)) {
      const items: ReactNode[] = []
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(<li key={items.length} style={{ margin: '2px 0' }}>{renderInline(lines[i].replace(/^\d+\. /, ''))}</li>)
        i++
      }
      nodes.push(<ol key={nodes.length} style={{ margin: '6px 0', paddingLeft: '18px' }}>{items}</ol>)
      continue
    }

    if (line.trim() === '') { i++; continue }

    const paraLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].startsWith('#') &&
      !lines[i].startsWith('```') &&
      !/^[-*+] /.test(lines[i]) &&
      !/^\d+\. /.test(lines[i]) &&
      !/^---+$/.test(lines[i])
    ) { paraLines.push(lines[i]); i++ }
    if (paraLines.length > 0)
      nodes.push(<p key={nodes.length} style={{ margin: '3px 0 6px', lineHeight: '1.65' }}>{renderInline(paraLines.join(' '))}</p>)
  }

  return <>{nodes}</>
}
