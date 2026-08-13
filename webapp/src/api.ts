const BASE = "";

let token: string | null = null;

export function setToken(t: string | null) {
  token = t;
}

async function req(path: string, options: RequestInit = {}): Promise<any> {
  const headers: Record<string, string> = { ...(options.headers as any) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(BASE + path, { ...options, headers });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

export async function auth(initData: string) {
  const data = await req("/api/webapp/auth", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData }),
  });
  setToken(data.token);
  return data;
}

export const me = () => req("/api/me");
export const getConfig = () => req("/api/config");
export const regenerate = () => req("/api/config/regenerate", { method: "POST" });
export const pay = (plan: string) =>
  req("/api/pay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan }),
  });
export const instructions = () => req("/api/instructions");
export const adminStats = () => req("/api/admin/stats");
export const adminPayments = () => req("/api/admin/payments");
export const adminPay = (paymentId: number, approve: boolean) =>
  req("/api/admin/pay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payment_id: paymentId, approve }),
  });
export const adminExtend = (tgId: number, days: number) =>
  req("/api/admin/extend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tg_id: tgId, days }),
  });