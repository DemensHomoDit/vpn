import { useCallback, useEffect, useState } from "react";
import WebApp from "@twa-dev/sdk";
import QRCode from "qrcode";
import * as api from "./api";

type View = "home" | "config" | "buy" | "help" | "admin";

const PLAN_META: Record<string, { label: string; badge?: string }> = {
  month: { label: "1 месяц" },
  "3months": { label: "3 месяца", badge: "популярный" },
  year: { label: "12 месяцев", badge: "выгодно" },
};

const fmtDate = (ts: number) =>
  new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(new Date(ts * 1000));

/* ---------- SF-style line icons ---------- */

type IconName =
  | "home" | "qr" | "bag" | "help" | "shield" | "chev" | "check" | "x"
  | "copy" | "refresh" | "link" | "external" | "arrow";

function Icon({ name, ...rest }: { name: IconName } & React.SVGProps<SVGSVGElement>) {
  const p = {
    viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
    strokeWidth: 1.9, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
    ...rest,
  };
  switch (name) {
    case "home":
      return <svg {...p}><path d="M3.5 10.2 12 3.5l8.5 6.7" /><path d="M5.5 9v11.5h13V9" /><path d="M9.8 20.5v-6h4.4v6" /></svg>;
    case "qr":
      return <svg {...p}><rect x="4" y="4" width="6.5" height="6.5" rx="1.4" /><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.4" /><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.4" /><path d="M13.5 13.5h3v3M20 17.5v3h-3.5" /></svg>;
    case "bag":
      return <svg {...p}><path d="M5.8 8.2h12.4l-1.1 12a1.6 1.6 0 0 1-1.6 1.4H8.5a1.6 1.6 0 0 1-1.6-1.4l-1.1-12Z" /><path d="M9 8.2V7a3 3 0 0 1 6 0v1.2" /></svg>;
    case "help":
      return <svg {...p}><circle cx="12" cy="12" r="8.6" /><path d="M9.6 9.4a2.5 2.5 0 0 1 4.9.6c0 1.7-2.4 2-2.4 3.5" /><path d="M12 17.1v.1" /></svg>;
    case "shield":
      return <svg {...p}><path d="M12 3.2 19 6v5.6c0 4.4-2.9 7.4-7 9.2-4.1-1.8-7-4.8-7-9.2V6l7-2.8Z" /><path d="m9 11.6 2.1 2.1 3.9-4.2" /></svg>;
    case "chev":
      return <svg {...p} strokeWidth={2.4}><path d="m9 5.5 6.5 6.5L9 18.5" /></svg>;
    case "check":
      return <svg {...p} strokeWidth={2.4}><path d="m5 12.6 4.4 4.4L19 7" /></svg>;
    case "x":
      return <svg {...p} strokeWidth={2.4}><path d="M6.5 6.5l11 11M17.5 6.5l-11 11" /></svg>;
    case "copy":
      return <svg {...p}><rect x="8.5" y="8.5" width="11" height="11" rx="2.4" /><path d="M15 5.5H6.9A2.4 2.4 0 0 0 4.5 7.9V16" /></svg>;
    case "refresh":
      return <svg {...p}><path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" /><path d="M19.8 3.8v3.4h-3.4" /></svg>;
    case "link":
      return <svg {...p}><path d="M10.2 13.8a3.6 3.6 0 0 0 5.1 0l3-3a3.6 3.6 0 0 0-5.1-5.1l-1.2 1.2" /><path d="M13.8 10.2a3.6 3.6 0 0 0-5.1 0l-3 3a3.6 3.6 0 0 0 5.1 5.1l1.2-1.2" /></svg>;
    case "external":
      return <svg {...p}><path d="M13.5 5.5h5v5" /><path d="M18.5 5.5 11 13" /><path d="M17 13.8v3.9a1.8 1.8 0 0 1-1.8 1.8H6.3a1.8 1.8 0 0 1-1.8-1.8V8.8A1.8 1.8 0 0 1 6.3 7h3.9" /></svg>;
    case "arrow":
      return <svg {...p} strokeWidth={2.2}><path d="M4.5 12h14" /><path d="m13 6.5 5.5 5.5-5.5 5.5" /></svg>;
  }
}

/* ---------- shared pieces ---------- */

function Group({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <section>
      {label && <div className="sl">{label}</div>}
      <div className="group">{children}</div>
    </section>
  );
}

function Row({ icon, tint, children, onClick }: {
  icon: IconName; tint: string; children?: React.ReactNode; onClick?: () => void;
}) {
  return (
    <button className="group-row ri" onClick={onClick}>
      <span className="rb" style={{ background: tint }}><Icon name={icon} /></span>
      {children}
      <span className="chev"><Icon name="chev" /></span>
    </button>
  );
}

function Spinner() {
  return <div className="spin" aria-label="Загрузка" />;
}

/* ---------- app ---------- */

export default function App() {
  const [view, setView] = useState<View>("home");
  const [me, setMe] = useState<any>(null);
  const [admin, setAdmin] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const initData = WebApp.initData;
    if (!initData) {
      setError("Откройте приложение через кнопку «📱 Личный кабинет» в боте.");
      return;
    }
    api
      .auth(initData)
      .then((d) => {
        setAdmin(d.admin);
        return api.me();
      })
      .then(setMe)
      .catch(() => setError("Не удалось авторизоваться. Закройте приложение и откройте его заново из бота."));
  }, []);

  const go = (v: View) => {
    setError("");
    setView(v);
  };

  return (
    <div className="app">
      {error && <div className="error">{error}</div>}

      <main>
        {view === "home" && <Home me={me} go={go} />}
        {view === "config" && <Config />}
        {view === "buy" && <Buy me={me} go={go} />}
        {view === "help" && <Help />}
        {view === "admin" && admin && <Admin />}
      </main>

      <nav className="tabs">
        <button className={`tab ${view === "home" ? "active" : ""}`} onClick={() => go("home")}>
          <Icon name="home" />Главная
        </button>
        <button className={`tab ${view === "config" ? "active" : ""}`} onClick={() => go("config")}>
          <Icon name="qr" />Конфиг
        </button>
        <button className={`tab ${view === "buy" ? "active" : ""}`} onClick={() => go("buy")}>
          <Icon name="bag" />Тарифы
        </button>
        <button className={`tab ${view === "help" ? "active" : ""}`} onClick={() => go("help")}>
          <Icon name="help" />Помощь
        </button>
        {admin && (
          <button className={`tab ${view === "admin" ? "active" : ""}`} onClick={() => go("admin")}>
            <Icon name="shield" />Админ
          </button>
        )}
      </nav>
    </div>
  );
}

/* ---------- home ---------- */

function Home({ me, go }: { me: any; go: (v: View) => void }) {
  if (!me) return <Spinner />;
  const active = !!me.active;
  return (
    <div className="stack">
      <div className={`hero ${active ? "" : "off"}`}>
        <div className="hero-brand">
          <span>VPN</span>
          <span className="pill">
            <span className="dot" />
            {active ? "Активна" : "Не активна"}
          </span>
        </div>
        <div className="hero-num">
          {me.days_left}
          <span>{me.days_left === 1 ? "день" : me.days_left < 5 ? "дня" : "дней"} осталось</span>
        </div>
        <div className="hero-foot">
          <span>{me.expires_at ? `до ${fmtDate(me.expires_at)}` : "подписка не оформлена"}</span>
          <span>VLESS · Reality</span>
        </div>
      </div>

      {!active && (
        <button className="btn btn-primary" onClick={() => go("buy")}>
          <Icon name="bag" />Оформить подписку
        </button>
      )}

      <Group>
        <Row icon="qr" tint="var(--accent)" onClick={() => go("config")}>
          Мой конфиг
        </Row>
        <Row icon="bag" tint="var(--green)" onClick={() => go("buy")}>
          Тарифы и оплата
        </Row>
        <Row icon="help" tint="var(--orange)" onClick={() => go("help")}>
          Инструкция
        </Row>
      </Group>

      <p className="foot">
        Сервер: {me.server?.ip}:{me.server?.port} · {me.server?.sni}. Российские сайты идут напрямую,
        остальные — через VPN.
      </p>
    </div>
  );
}

/* ---------- config ---------- */

function Config() {
  const [cfg, setCfg] = useState<any>(null);
  const [qr, setQr] = useState("");
  const [copied, setCopied] = useState<"" | "uri" | "sub">("");
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    api.getConfig().then((c) => {
      setCfg(c);
      QRCode.toDataURL(c.config_uri, { width: 240, margin: 0 }).then(setQr);
    }).catch(() => setErr("Не удалось загрузить конфиг. Попробуйте позже."));
  }, []);

  useEffect(load, [load]);

  const copy = (key: "uri" | "sub", text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(""), 1600);
  };

  const regen = () => {
    if (!window.confirm("Перевыпустить ключи? Текущий конфиг перестанет работать.")) return;
    setErr("");
    api.regenerate().then(load).catch(() => setErr("Не удалось перевыпустить."));
  };

  if (err && !cfg) return <div className="error">{err}</div>;
  if (!cfg) return <Spinner />;

  return (
    <div className="stack">
      <div className="lt">Конфиг</div>

      <div className="qrwrap">
        {qr && <img src={qr} alt="QR-код конфига" className="qr" />}
        <button className="btn btn-primary" onClick={() => copy("uri", cfg.config_uri)}>
          <Icon name={copied === "uri" ? "check" : "copy"} />
          {copied === "uri" ? "Скопировано" : "Скопировать vless://"}
        </button>
        {cfg.subscribe_url && (
          <button className="btn btn-tinted" onClick={() => copy("sub", cfg.subscribe_url)}>
            <Icon name={copied === "sub" ? "check" : "link"} />
            {copied === "sub" ? "Скопировано" : "Скопировать подписку"}
          </button>
        )}
        <button className="btn btn-plain" onClick={regen}>
          <Icon name="refresh" />Перевыпустить ключи
        </button>
      </div>

      <Group label="Как подключиться в Happ">
        <a className="group-row ri" href="https://github.com/Happ-proxy" target="_blank" rel="noreferrer">
          <span className="rb" style={{ background: "var(--indigo)" }}><Icon name="external" /></span>
          Скачать Happ
          <span className="row-val small">Android · iOS · Desktop</span>
          <span className="chev"><Icon name="chev" /></span>
        </a>
        <div className="group-row">
          <p className="small muted" style={{ lineHeight: 1.5 }}>
            Happ → «+» → вставить ссылку или отсканировать QR. Подписка обновляет конфиг сама.
            Старые профили удалите — они недействительны.
          </p>
        </div>
      </Group>
    </div>
  );
}

/* ---------- buy ---------- */

function Buy({ me, go }: { me: any; go: (v: View) => void }) {
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState("");

  if (!me) return <Spinner />;

  if (result)
    return (
      <div className="stack">
        <div className="lt">Тарифы</div>
        <div className="result-card">
          <span className="result-ico"><Icon name="check" /></span>
          <div className="result-title">Заявка №{result.payment_id} создана</div>
          <p className="result-text">{result.instructions}</p>
          <button className="btn btn-tinted" style={{ marginTop: 6 }} onClick={() => go("home")}>
            <Icon name="arrow" />На главную
          </button>
        </div>
      </div>
    );

  const pay = (key: string) => {
    if (busy) return;
    setBusy(key);
    api.pay(key).then(setResult).catch(() => setBusy("")).finally(() => setBusy(""));
  };

  return (
    <div className="stack">
      <div className="lt">Тарифы</div>
      <Group label="Подписка">
        {Object.entries(me.plans).map(([key, p]: [string, any]) => (
          <button key={key} className="group-row ri plan-row" onClick={() => pay(key)}>
            <span className="row-main">
              <span className="plan-name">
                {PLAN_META[key]?.label}
                {PLAN_META[key]?.badge && <span className="capsule">{PLAN_META[key]?.badge}</span>}
              </span>
              <span className="plan-sub">{p.days} дней</span>
            </span>
            <span className="plan-price">{p.price} ₽</span>
            <span className="chev"><Icon name="chev" /></span>
          </button>
        ))}
      </Group>
      <p className="foot">Оплата подтверждается администратором вручную — после подтверждения дни
        добавляются автоматически.</p>
    </div>
  );
}

/* ---------- help ---------- */

function Help() {
  const [text, setText] = useState("");
  useEffect(() => {
    api.instructions().then((d) => setText(d.text)).catch(() => setText("Инструкция временно недоступна."));
  }, []);
  return (
    <div className="stack">
      <div className="lt">Инструкция</div>
      <div className="group"><p className="help-text">{text || "…"}</p></div>
    </div>
  );
}

/* ---------- admin ---------- */

function Admin() {
  const [tab, setTab] = useState<"overview" | "payments" | "extend">("overview");
  const [stats, setStats] = useState<any>(null);
  const [payments, setPayments] = useState<any[]>([]);
  const [tgId, setTgId] = useState("");
  const [days, setDays] = useState("30");
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    api.adminStats().then(setStats).catch(() => {});
    api.adminPayments().then((d) => setPayments(d.payments)).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const decide = (id: number, approve: boolean) => {
    api.adminPay(id, approve).then(load).catch(() => {});
  };

  const extend = () => {
    setMsg("");
    api.adminExtend(Number(tgId), Number(days))
      .then(() => setMsg("Продлено ✓"))
      .catch(() => setMsg("Не удалось продлить"));
  };

  if (!stats) return <Spinner />;

  const pending = payments.filter((p) => p.status === "pending");
  const history = payments.filter((p) => p.status !== "pending").slice(0, 8);

  return (
    <div className="stack">
      <div className="lt">Админ</div>

      <div className="seg" role="tablist">
        <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>Обзор</button>
        <button className={tab === "payments" ? "active" : ""} onClick={() => setTab("payments")}>
          Заявки{pending.length ? ` · ${pending.length}` : ""}
        </button>
        <button className={tab === "extend" ? "active" : ""} onClick={() => setTab("extend")}>Продление</button>
      </div>

      {tab === "overview" && (
        <>
          <div className="tiles">
            <div className="tile"><b>{stats.users}</b><span>пользователей</span></div>
            <div className="tile"><b>{stats.active}</b><span>активных</span></div>
            <div className="tile"><b>{stats.revenue} ₽</b><span>доход · {stats.paid_count}</span></div>
          </div>
          <Group label="Последние заявки">
            {history.length === 0 && <div className="empty">Пока нет заявок</div>}
            {history.map((p) => (
              <div className="group-row" key={p.id}>
                <span className="pay-main">
                  <span className="pay-title">№{p.id} · {p.amount} ₽</span>
                  <span className="pay-sub">@{p.username || p.tg_id} · {p.status}</span>
                </span>
              </div>
            ))}
          </Group>
        </>
      )}

      {tab === "payments" && (
        <Group label={pending.length ? "Ожидают подтверждения" : "Заявки"}>
          {pending.length === 0 && <div className="empty">Новых заявок нет</div>}
          {pending.map((p) => (
            <div className="group-row" key={p.id}>
              <span className="pay-main">
                <span className="pay-title">№{p.id} · {p.amount} ₽</span>
                <span className="pay-sub">@{p.username || p.tg_id}</span>
              </span>
              <button className="act ok" aria-label="Подтвердить" onClick={() => decide(p.id, true)}>
                <Icon name="check" />
              </button>
              <button className="act no" aria-label="Отклонить" onClick={() => decide(p.id, false)}>
                <Icon name="x" />
              </button>
            </div>
          ))}
        </Group>
      )}

      {tab === "extend" && (
        <Group label="Продлить подписку вручную">
          <div className="group-row" style={{ display: "block", padding: "14px 16px" }}>
            <div className="field-row">
              <input className="field" placeholder="tg_id" inputMode="numeric" value={tgId} onChange={(e) => setTgId(e.target.value)} />
              <input className="field" placeholder="дней" inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value)} />
            </div>
            <button className="btn btn-primary" onClick={extend}>
              <Icon name="arrow" />Продлить
            </button>
            {msg && <div className="ok-note" style={{ marginTop: 10, justifyContent: "center" }}>
              <Icon name="check" />{msg}
            </div>}
          </div>
        </Group>
      )}
    </div>
  );
}
