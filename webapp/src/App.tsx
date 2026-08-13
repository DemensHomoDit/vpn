import { useCallback, useEffect, useState } from "react";
import WebApp from "@twa-dev/sdk";
import QRCode from "qrcode";
import * as api from "./api";

type View = "home" | "config" | "buy" | "help" | "admin";

const PLAN_KEYS: Record<string, { label: string; badge?: string }> = {
  month: { label: "1 месяц" },
  "3months": { label: "3 месяца", badge: "популярный" },
  year: { label: "12 месяцев", badge: "выгодно" },
};

export default function App() {
  const [view, setView] = useState<View>("home");
  const [me, setMe] = useState<any>(null);
  const [admin, setAdmin] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .auth(WebApp.initData)
      .then((d) => {
        setAdmin(d.admin);
        return api.me();
      })
      .then(setMe)
      .catch((e) => setError(String(e)));
  }, []);

  const go = (v: View) => {
    setError("");
    setView(v);
  };

  return (
    <div className="app">
      <header className="top">
        <div className="logo">◉ VPN</div>
        <div className="user">{me?.name || "…"}</div>
      </header>

      {error && <div className="error">{error}</div>}

      <main>
        {view === "home" && <Home me={me} go={go} />}
        {view === "config" && <Config me={me} />}
        {view === "buy" && <Buy me={me} />}
        {view === "help" && <Help />}
        {view === "admin" && <Admin />}
      </main>

      <nav className="tabs">
        <button className={view === "home" ? "active" : ""} onClick={() => go("home")}>ЛК</button>
        <button className={view === "config" ? "active" : ""} onClick={() => go("config")}>Конфиг</button>
        <button className={view === "buy" ? "active" : ""} onClick={() => go("buy")}>Купить</button>
        <button className={view === "help" ? "active" : ""} onClick={() => go("help")}>Помощь</button>
        {admin && (
          <button className={view === "admin" ? "active" : ""} onClick={() => go("admin")}>Админ</button>
        )}
      </nav>
    </div>
  );
}

function Home({ me, go }: { me: any; go: (v: View) => void }) {
  if (!me) return <p className="muted">Загрузка…</p>;
  const active = me.active;
  return (
    <div className="stack">
      <div className={`status-card ${active ? "on" : "off"}`}>
        <div className="status-title">{active ? "Подписка активна" : "Нет активной подписки"}</div>
        <div className="days">{me.days_left} <span>дн. осталось</span></div>
        <div className="muted">Сервер: {me.server.ip}:{me.server.port}</div>
      </div>
      <div className="grid">
        <button className="card" onClick={() => go("config")}>🔗 Мой конфиг</button>
        <button className="card" onClick={() => go("buy")}>💳 Купить подписку</button>
        <button className="card" onClick={() => go("help")}>📖 Инструкция</button>
      </div>
    </div>
  );
}

function Config({ me }: { me: any }) {
  const [cfg, setCfg] = useState<any>(null);
  const [qr, setQr] = useState("");
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    api.getConfig().then((c) => {
      setCfg(c);
      QRCode.toDataURL(c.config_uri, { width: 240, margin: 1 }).then(setQr);
    }).catch((e) => setError2(String(e)));
  }, []);
  const setError2 = (s: string) => {};

  useEffect(() => {
    load();
  }, [load]);

  const copyUri = () => {
    navigator.clipboard.writeText(cfg.config_uri);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const download = () => {
    const blob = new Blob([cfg.config_json], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `config-${me.tg_id}.json`;
    a.click();
  };

  const regen = () => {
    if (!confirm("Перегенерировать конфиг? Старый перестанет работать.")) return;
    api.regenerate().then(() => load());
  };

  if (!cfg) return <p className="muted">Загрузка…</p>;
  return (
    <div className="stack">
      <div className="card center">
        {qr && <img src={qr} alt="QR" className="qr" />}
        <button className="btn" onClick={copyUri}>{copied ? "Скопировано ✓" : "Скопировать vless://"}</button>
        <button className="btn ghost" onClick={download}>Скачать файл .json</button>
        <button className="btn ghost" onClick={regen}>Перегенерировать</button>
        <p className="muted small">Android/iOS: QR в sing-box (SFA/SFI) или NekoBox/Streisand.<br />Windows: файл .json в sing-box GUI / Nekoray.</p>
      </div>
    </div>
  );
}

function Buy({ me }: { me: any }) {
  const [result, setResult] = useState<any>(null);
  if (!me) return <p className="muted">Загрузка…</p>;
  if (result)
    return (
      <div className="stack">
        <div className="card">
          <div className="ok">Заявка #{result.payment_id} создана</div>
          <p className="muted">{result.instructions}</p>
          <p className="muted small">Статус: {result.status}</p>
        </div>
      </div>
    );
  return (
    <div className="stack">
      {Object.entries(me.plans).map(([key, p]: [string, any]) => (
        <button key={key} className="plan" onClick={() => api.pay(key).then(setResult).catch((e) => alert(e))}>
          <div>
            <div className="plan-name">
              {PLAN_KEYS[key]?.label} {PLAN_KEYS[key]?.badge && <span className="badge">{PLAN_KEYS[key].badge}</span>}
            </div>
            <div className="muted">{p.days} дней</div>
          </div>
          <div className="price">{p.price} ₽</div>
        </button>
      ))}
    </div>
  );
}

function Help() {
  const [text, setText] = useState("Загрузка…");
  useEffect(() => {
    api.instructions().then((d) => setText(d.text)).catch(() => setText("Недоступно"));
  }, []);
  return (
    <div className="card">
      <pre className="help-text">{text}</pre>
    </div>
  );
}

function Admin() {
  const [stats, setStats] = useState<any>(null);
  const [payments, setPayments] = useState<any[]>([]);
  const [tgId, setTgId] = useState("");
  const [days, setDays] = useState("30");
  const [msg, setMsg] = useState("");

  const load = () => {
    api.adminStats().then(setStats);
    api.adminPayments().then((d) => setPayments(d.payments));
  };
  useEffect(load, []);

  const decide = (id: number, approve: boolean) => {
    api.adminPay(id, approve).then(load);
  };

  const extend = () => {
    api.adminExtend(Number(tgId), Number(days)).then(() => setMsg("Продлено ✓")).catch((e) => setMsg(String(e)));
  };

  if (!stats) return <p className="muted">Загрузка…</p>;
  return (
    <div className="stack">
      <div className="grid">
        <div className="card center"><b>{stats.users}</b><span className="muted">пользователей</span></div>
        <div className="card center"><b>{stats.active}</b><span className="muted">активных</span></div>
        <div className="card center"><b>{stats.revenue} ₽</b><span className="muted">доход ({stats.paid_count})</span></div>
      </div>

      <div className="card">
        <b>Продлить подписку</b>
        <div className="row">
          <input placeholder="tg_id" value={tgId} onChange={(e) => setTgId(e.target.value)} />
          <input placeholder="дней" value={days} onChange={(e) => setDays(e.target.value)} />
          <button className="btn" onClick={extend}>OK</button>
        </div>
        {msg && <div className="ok">{msg}</div>}
      </div>

      <div className="card">
        <b>Заявки на оплату</b>
        {payments.filter((p) => p.status === "pending").length === 0 && <p className="muted">Нет pending-заявок</p>}
        {payments.filter((p) => p.status === "pending").map((p) => (
          <div key={p.id} className="pay-row">
            <div>
              #{p.id} · {p.amount} ₽ · @{p.username || p.tg_id}
            </div>
            <div className="row">
              <button className="btn small ok-btn" onClick={() => decide(p.id, true)}>✓</button>
              <button className="btn small" onClick={() => decide(p.id, false)}>✗</button>
            </div>
          </div>
        ))}
        {payments.filter((p) => p.status !== "pending").length > 0 && (
          <>
            <div className="muted small" style={{ marginTop: 12 }}>История:</div>
            {payments.filter((p) => p.status !== "pending").slice(0, 5).map((p) => (
              <div key={p.id} className="pay-row muted small">
                #{p.id} · {p.amount} ₽ · {p.status} · @{p.username || p.tg_id}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}