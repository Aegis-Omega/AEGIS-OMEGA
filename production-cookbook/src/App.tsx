import { useMemo, useState } from 'react'
import { Activity, Bell, Boxes, CalendarDays, ChevronDown, ChevronRight, ClipboardCheck, CookingPot, FileBarChart, HelpCircle, LayoutDashboard, Menu, PackageOpen, Plus, Search, Settings, ShoppingCart, Sparkles, Truck, Users, Wheat, X } from 'lucide-react'

const nav = [
  ['Overview', LayoutDashboard], ['Production', CookingPot], ['Recipes', ClipboardCheck],
  ['Products', PackageOpen], ['Materials', Wheat], ['Inventory', Boxes],
  ['Orders', ShoppingCart], ['Purchasing', Truck], ['Suppliers', Users], ['Reports', FileBarChart],
] as const

const batches = [
  { product: 'Country Sourdough', id: 'B-2407-018', time: '07:30', qty: '48 loaves', state: 'In progress', tone: 'blue', progress: 68 },
  { product: 'Almond Croissants', id: 'B-2407-019', time: '09:00', qty: '72 pieces', state: 'Materials ready', tone: 'green', progress: 30 },
  { product: 'Summer Berry Tart', id: 'B-2407-020', time: '11:30', qty: '24 pieces', state: 'Planned', tone: 'gray', progress: 0 },
  { product: 'Focaccia Classica', id: 'B-2407-021', time: '14:00', qty: '36 trays', state: 'Planned', tone: 'gray', progress: 0 },
]

const stock = [
  { name: 'Cultured butter', meta: 'MAT-0018 · Chilled', left: '6.2 kg', min: '10 kg', pct: 35 },
  { name: 'Almond flour', meta: 'MAT-0031 · Dry store', left: '3.8 kg', min: '8 kg', pct: 25 },
  { name: 'Berry mix', meta: 'MAT-0044 · Frozen', left: '4.1 kg', min: '6 kg', pct: 45 },
]

function Metric({ label, value, note, good }: { label: string; value: string; note: string; good?: boolean }) {
  return <article className="metric"><div className="metric-label">{label}<HelpCircle size={14}/></div><strong>{value}</strong><p className={good ? 'good' : ''}>{good ? '↗ ' : ''}{note}</p></article>
}

export function App() {
  const [active, setActive] = useState('Overview')
  const [query, setQuery] = useState('')
  const [menu, setMenu] = useState(false)
  const [toast, setToast] = useState('')
  const filtered = useMemo(() => batches.filter(b => `${b.product} ${b.id}`.toLowerCase().includes(query.toLowerCase())), [query])
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2400) }

  return <div className="shell">
    <aside className={menu ? 'sidebar open' : 'sidebar'}>
      <button className="close" onClick={() => setMenu(false)} aria-label="Close menu"><X/></button>
      <div className="brand"><span><Wheat size={20}/></span><b>batchbook</b></div>
      <nav>{nav.map(([name, Icon]) => <button key={name} className={active === name ? 'active' : ''} onClick={() => { setActive(name); setMenu(false) }}><Icon size={18}/>{name}</button>)}</nav>
      <div className="workspace"><div className="avatar">MB</div><div><b>Maison Bloom</b><small>Sarajevo · BAM</small></div><ChevronDown size={15}/></div>
      <div className="side-bottom"><button><Settings size={18}/>Settings</button><button><HelpCircle size={18}/>Help & support</button></div>
    </aside>
    <main>
      <header><button className="menu" onClick={() => setMenu(true)} aria-label="Open menu"><Menu/></button><div className="search"><Search size={18}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search products, batches, orders…"/><kbd>⌘ K</kbd></div><button className="icon-btn" aria-label="Notifications"><Bell size={19}/><i/></button><div className="today"><CalendarDays size={18}/><span>Mon, 28 July</span></div></header>
      <div className="content">
        <section className="welcome"><div><p>MONDAY, 28 JULY</p><h1>Good morning, Amira.</h1><span>Here’s what’s happening across your production floor.</span></div><button className="primary" onClick={() => notify('New batch draft created')}><Plus size={18}/>New production batch</button></section>
        <section className="metrics"><Metric label="Today’s production" value="180 units" note="12% vs. last Monday" good/><Metric label="Batches completed" value="3 / 7" note="4 remaining today"/><Metric label="Orders due" value="12" note="3 require attention"/><Metric label="Waste this week" value="2.4%" note="0.8% below target" good/></section>
        <section className="grid-main">
          <article className="card schedule"><div className="card-head"><div><h2>Today’s production</h2><p>7 batches · 4 remaining</p></div><button onClick={() => setActive('Production')}>View schedule <ChevronRight size={16}/></button></div>
            <div className="batch-list">{filtered.length ? filtered.map((b, i) => <div className="batch" key={b.id}><div className="time">{b.time}<span className={b.tone}/></div><div className="batch-info"><div><b>{b.product}</b><small>{b.id} · {b.qty}</small></div><div className={`badge ${b.tone}`}>{b.state}</div><div className="bar"><i style={{width: `${b.progress}%`}}/></div><button aria-label={`Open ${b.product}`}><ChevronRight/></button></div></div>) : <div className="empty">No production batches match “{query}”.</div>}</div>
          </article>
          <article className="card stock"><div className="card-head"><div><h2>Low stock</h2><p>3 materials need attention</p></div><button onClick={() => setActive('Inventory')}>Inventory <ChevronRight size={16}/></button></div>{stock.map(s => <div className="stock-row" key={s.name}><div className="stock-icon"><Wheat size={18}/></div><div className="stock-name"><b>{s.name}</b><small>{s.meta}</small></div><div className="stock-qty"><b>{s.left}</b><small>of {s.min}</small></div><div className="stockbar"><i style={{width: `${s.pct}%`}}/></div></div>)}<button className="restock" onClick={() => notify('Purchase order draft started')}><Plus size={16}/>Create purchase order</button></article>
        </section>
        <section className="lower">
          <article className="card orders"><div className="card-head"><div><h2>Orders requiring attention</h2><p>Due in the next 48 hours</p></div><button>View all orders <ChevronRight size={16}/></button></div><div className="order"><span className="order-icon"><ShoppingCart/></span><div><b>Atelier Hotel</b><small>ORD-1084 · 4 line items</small></div><div><b>Today, 16:00</b><small>Local delivery</small></div><span className="badge amber">Awaiting production</span></div><div className="order"><span className="order-icon"><ShoppingCart/></span><div><b>Café Nomad</b><small>ORD-1087 · 2 line items</small></div><div><b>Tomorrow, 08:30</b><small>Pickup</small></div><span className="badge blue">In production</span></div></article>
          <article className="insight"><Sparkles size={20}/><div><span>WEEKLY INSIGHT</span><h3>Your croissant yield improved by 4.6%</h3><p>That’s approximately <b>18 more sellable pieces</b> from the same ingredients.</p><button>View production report <ChevronRight size={15}/></button></div></article>
        </section>
      </div>
    </main>
    {toast && <div className="toast"><Activity size={17}/>{toast}</div>}
  </div>
}
