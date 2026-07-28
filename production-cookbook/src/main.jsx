import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Circle,
  ClipboardCheck,
  Clock3,
  Factory,
  Filter,
  LayoutDashboard,
  Menu,
  MoreVertical,
  Package,
  Plus,
  Search,
  Settings,
  ShoppingCart,
  Truck,
  X,
} from "lucide-react";
import "./styles.css";

const navigation = [
  ["Overview", LayoutDashboard],
  ["Production", Factory],
  ["Recipes", BookOpen],
  ["Inventory", Package],
  ["Purchasing", ShoppingCart],
  ["Orders", ClipboardCheck],
  ["Quality", CheckCircle2],
  ["Reports", BarChart3],
];

const batches = [
  { number: "BB250520-01", product: "Sourdough loaf", time: "06:00 – 08:00", progress: 100, team: "Bake Team A", status: "Completed" },
  { number: "BB250520-02", product: "Chocolate cake", time: "08:30 – 10:30", progress: 62, team: "Bake Team B", status: "In progress" },
  { number: "BB250520-03", product: "Vanilla cupcakes", time: "10:45 – 12:15", progress: 0, team: "Bake Team A", status: "Planned" },
  { number: "BB250520-04", product: "Cold brew coffee", time: "12:30 – 14:30", progress: 0, team: "Beverage Team", status: "Planned" },
  { number: "BB250520-05", product: "Lemon tart", time: "14:45 – 16:15", progress: 0, team: "Pastry Team", status: "Planned" },
  { number: "BB250520-06", product: "Almond croissant", time: "16:30 – 18:00", progress: 0, team: "Bake Team B", status: "Planned" },
];

const stock = [
  ["Bread flour", "120 kg", "200 kg"],
  ["Unsalted butter", "3.2 kg", "10 kg"],
  ["Eggs", "48 pcs", "120 pcs"],
  ["Cocoa powder", "1.1 kg", "2 kg"],
  ["Almonds", "2.5 kg", "5 kg"],
];

const orders = [
  ["ORD-10234", "Café Centrale", "May 20"],
  ["ORD-10228", "Market Deli", "May 20"],
  ["ORD-10230", "Green Leaf Co.", "May 21"],
  ["ORD-10218", "Hotel Europa", "May 21"],
  ["ORD-10212", "Daily Bites", "May 22"],
];

const yieldPoints = [93, 96, 92, 95.5, 90.5, 94.5, 97];

function Sidebar({ open, onClose, active, setActive }) {
  return (
    <>
      {open && <button className="scrim" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
        <div className="brand"><span className="brand-mark">B</span>Batchbook</div>
        <nav aria-label="Primary">
          {navigation.map(([label, Icon]) => (
            <button
              className={`nav-item ${active === label ? "nav-item--active" : ""}`}
              key={label}
              onClick={() => { setActive(label); onClose(); }}
            >
              <Icon size={19} strokeWidth={1.8} /> {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="nav-item"><Settings size={19} /> Settings</button>
          <div className="profile">
            <span className="avatar">M</span>
            <span><strong>Mila</strong><small>Admin</small></span>
            <ChevronDown size={16} />
          </div>
        </div>
      </aside>
    </>
  );
}

function Metric({ icon: Icon, label, value, note, tone }) {
  return (
    <article className="metric">
      <span className="metric-icon"><Icon size={22} /></span>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small className={tone || ""}>{note}</small>
      </div>
    </article>
  );
}

function Status({ value }) {
  const variant = value.toLowerCase().replace(" ", "-");
  return <span className={`status status--${variant}`}>{value === "Completed" ? <CheckCircle2 size={15} /> : value === "Planned" ? <Clock3 size={15} /> : <Circle size={15} />} {value}</span>;
}

function ProductionTable({ query }) {
  const visible = useMemo(() => batches.filter((batch) => `${batch.number} ${batch.product} ${batch.team}`.toLowerCase().includes(query.toLowerCase())), [query]);
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Batch #</th><th>Product</th><th>Time</th><th>Progress</th><th>Team</th><th>Status</th><th /></tr></thead>
        <tbody>
          {visible.map((batch) => (
            <tr key={batch.number}>
              <td className="mono">{batch.number}</td><td className="product-name">{batch.product}</td><td>{batch.time}</td>
              <td><div className="progress-cell"><span>{batch.progress}%</span><i><b style={{ width: `${batch.progress}%` }} /></i></div></td>
              <td>{batch.team}</td><td><Status value={batch.status} /></td>
              <td><button className="icon-button" aria-label={`Actions for ${batch.number}`}><MoreVertical size={18} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!visible.length && <div className="empty">No batches match “{query}”.</div>}
    </div>
  );
}

function YieldChart() {
  const coords = yieldPoints.map((value, index) => `${54 + index * 99},${148 - (value - 88) * 9.5}`).join(" ");
  return (
    <div className="chart" aria-label="Weekly yield chart">
      <svg viewBox="0 0 700 190" role="img">
        {[88, 92, 96, 100].map((value, index) => <g key={value}><line x1="54" x2="665" y1={148 - index * 38} y2={148 - index * 38} /><text x="4" y={153 - index * 38}>{value}%</text></g>)}
        <line className="target" x1="54" x2="665" y1="110" y2="110" />
        <polyline points={coords} />
        {yieldPoints.map((value, index) => <circle key={index} cx={54 + index * 99} cy={148 - (value - 88) * 9.5} r="4" />)}
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => <text className="day" key={day} x={42 + index * 99} y="181">{day}</text>)}
      </svg>
    </div>
  );
}

function App() {
  const [navOpen, setNavOpen] = useState(false);
  const [active, setActive] = useState("Overview");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");

  const notify = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2800);
  };

  return (
    <div className="app">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} active={active} setActive={(next) => { setActive(next); if (next !== "Overview") notify(`${next} workspace is ready for API integration.`); }} />
      <main>
        <header className="topbar">
          <div className="heading">
            <button className="menu-button" onClick={() => setNavOpen(true)} aria-label="Open navigation"><Menu /></button>
            <div><h1>{active === "Overview" ? "Good morning, Mila" : active}</h1><p>Here’s what’s happening in production today.</p></div>
          </div>
          <div className="top-actions">
            <label className="date-control"><CalendarDays size={17} /><span>May 20, 2025</span><ChevronDown size={15} /></label>
            <label className="global-search"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search batches, products, orders…" /></label>
            <button className="primary" onClick={() => notify("New batch draft created.")}><Plus size={18} /> New batch <ChevronDown size={15} /></button>
          </div>
        </header>

        <section className="metrics" aria-label="Daily production metrics">
          <Metric icon={CalendarDays} label="Today’s batches" value="12" note="2 in progress · 10 planned" />
          <Metric icon={Package} label="Units planned" value="8,540" note="↑ 12.4% vs yesterday" tone="positive" />
          <Metric icon={BarChart3} label="Yield efficiency" value="93.6%" note="↑ 1.6 pp above target" tone="positive" />
          <Metric icon={ClipboardCheck} label="Open orders" value="18" note="6 urgent" tone="critical" />
        </section>

        <section className="dashboard-grid">
          <article className="panel production-panel">
            <div className="panel-header">
              <h2>Today’s production</h2>
              <div className="panel-tools">
                <button className="secondary"><Filter size={16} /> Filter</button>
                <label className="panel-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search schedule…" />{query && <button onClick={() => setQuery("")} aria-label="Clear search"><X size={15} /></button>}</label>
              </div>
            </div>
            <ProductionTable query={query} />
            <button className="text-link" onClick={() => notify("Full production schedule opened.")}>View full production schedule →</button>
          </article>

          <article className="panel stock-panel">
            <div className="panel-header"><h2>Low stock</h2><button className="text-link">View all</button></div>
            <div className="compact-table"><div className="compact-head"><span>Material</span><span>On hand</span><span>Min. level</span></div>
              {stock.map(([name, onHand, minimum], index) => <button key={name} onClick={() => notify(`${name} added to purchase draft.`)}><span>{name}</span><span className={index === 3 ? "critical" : "warning"}>{onHand}</span><span>{minimum}</span></button>)}
            </div>
          </article>

          <article className="panel orders-panel">
            <div className="panel-header"><h2>Urgent orders</h2><button className="text-link">View all</button></div>
            <div className="compact-table orders"><div className="compact-head"><span>Order #</span><span>Customer</span><span>Due</span></div>
              {orders.map(([number, customer, due], index) => <button key={number} onClick={() => notify(`${number} selected.`)}><span className="mono">{number}</span><span>{customer}</span><span className={index < 2 ? "critical" : index < 4 ? "warning" : ""}>{due}</span></button>)}
            </div>
          </article>

          <article className="panel yield-panel">
            <div className="panel-header"><div><h2>Weekly yield</h2><p>Actual output compared with the 92% target</p></div><button className="secondary">This week <ChevronDown size={15} /></button></div>
            <YieldChart />
          </article>

          <article className="panel purchasing-panel">
            <div className="panel-header"><h2>Quick purchasing</h2></div>
            {[
              [ShoppingCart, "Create purchase order", "Add items and send to supplier", "New PO"],
              [ClipboardCheck, "Reorder from templates", "Use recent approved orders", "Reorder"],
              [Package, "Import suggestions", "AI suggestions based on usage", "Review"],
              [Truck, "Track deliveries", "Check incoming orders and status", "Open"],
            ].map(([Icon, title, description, action]) => (
              <div className="purchase-action" key={title}><span className="purchase-icon"><Icon size={19} /></span><div><strong>{title}</strong><small>{description}</small></div><button onClick={() => notify(`${title} opened.`)}>{action}</button></div>
            ))}
          </article>
        </section>
        <footer><span>All times local&nbsp;&nbsp; • &nbsp;&nbsp;Currency: BAM</span><span>Last updated: 08:32</span></footer>
      </main>
      {notice && <div className="toast" role="status"><CheckCircle2 size={18} />{notice}</div>}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
