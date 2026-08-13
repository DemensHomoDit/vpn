# Деплой на VPS

Один сервер (Ubuntu 22.04+) несёт всё: sing-box, FastAPI, бота, webapp.

## 1. Загрузка и установка

```bash
apt-get update && apt-get install -y git
git clone <ваш-репо> /root/vpn
cd /root/vpn

sudo bash server/install.sh            # sing-box + firewall (443/tcp)
sudo python3 server/gen-server-conf.py init
sudo systemctl enable --now sing-box

# проверить: публичный ключ и short_id в /etc/sing-box/meta.json
```

## 2. Бэкенд и бот

```bash
cd /root/vpn/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env
```

`.env`: BOT_TOKEN (от @BotFather), ADMIN_IDS (ваш tg_id), JWT_SECRET
(случайная строка), VPS_IP (IP сервера), USERS_SCRIPT/GEN_SCRIPT
(пути `/root/vpn/server/...`).

systemd-юниты:

```ini
# /etc/systemd/system/vpn-api.service
[Unit]
Description=VPN API
After=network.target

[Service]
WorkingDirectory=/root/vpn/backend
EnvironmentFile=/root/vpn/backend/.env
ExecStart=/root/vpn/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/vpn-bot.service
[Unit]
Description=VPN bot
After=network.target

[Service]
WorkingDirectory=/root/vpn/backend
EnvironmentFile=/root/vpn/backend/.env
ExecStart=/root/vpn/backend/.venv/bin/python -m app.bot
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now vpn-api vpn-bot
```

Бот ходит в `users.sh` через sudo — при запуске от root работает
напрямую. Если хотите непривилегированного пользователя:

```bash
echo "vpn ALL=(root) NOPASSWD: /root/vpn/server/users.sh" > /etc/sudoers.d/vpn
```

## 3. Проверка

1. Напишите боту `/start` — создастся пользователь.
2. «Купить подписку» → появится заявка → админ подтверждает кнопкой →
   пользователь получает дни.
3. «Мой конфиг» → QR / файл. Импортируйте в sing-box на телефоне,
   включите — западные сайты через VPN, российские напрямую.

## 4. Mini App

WebApp уже собран в `backend/webapp/dist` (пересборка: `cd webapp && npm i && npm run build`).
FastAPI отдаёт его на `/` и `/webapp`.

HTTPS нужен обязательно. Без домена — временно:

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
cloudflared tunnel --url http://localhost:8000
```

Появится URL вида `https://xxxx.trycloudflare.com`. С доменом
(~$3/год) — Caddy: `caddy reverse-proxy --from vpn.example.com --to :8000`.

Затем в @BotFather: Bot Settings → Menu Button → URL webapp.
`WEBAPP_URL` в `.env` → кнопка «Открыть Mini App» в боте.

## 5. Эксплуатация

- `/stats` — статистика (бот, админ)
- `/extend <tg_id> <дней>` — продлить
- `/revoke <tg_id>` — отозвать доступ
- Просрочка отключается автоматически (loop в боте, раз в час)
- Списки RU-правил у клиентов обновляются сами (rule sets, раз в сутки)

## Известные ограничения v1

- Платежи: ручное подтверждение админом (провайдер подключается через
  `backend/app/payments/`).
- IPv6 на клиенте не используется (`strategy: ipv4_only`).
- UUID хранится в SQLite бэкенда — сервер-бэкап БД не помешает
  (`data/vpn.db`).