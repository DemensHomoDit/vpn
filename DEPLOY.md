# Деплой на VPS

Один сервер (Ubuntu 22.04+) несёт всё: Marzban (Xray, VLESS Reality),
FastAPI-бэкенд, Telegram-бота и Mini App.

Порты: 443/TCP — VLESS Reality; 8000/TCP — HTTP-панель и подписки
Marzban; API бэкенда слушает 127.0.0.1:8081 и наружу отдаётся только
через HTTPS-туннель.

## 1. Marzban

```bash
git clone <ваш-репо> /root/vpn
sudo bash /root/vpn/server/install.sh vpnadmin 'пароль'
```

Скрипт ставит Docker, поднимает контейнер Marzban, создаёт sudo-админа,
сохраняет X25519-ключи в `/root/marzban-x25519.txt`.

Приведите инбаунд к целевому виду (см. вывод скрипта): порт 443,
Reality с `dest`/`sni` = `dl.google.com:443`, fingerprint `chrome`,
flow `xtls-rprx-vision`, tag `VLESS-REALITY`, один shortId из ключей.
Затем `docker compose restart` в `/opt/marzban`.

## 2. Бэкенд и бот

```bash
cd /root/vpn/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
```

`.env`: BOT_TOKEN (от @BotFather), ADMIN_IDS (ваш tg_id), JWT_SECRET
(случайная строка), MARZBAN_USERNAME/MARZBAN_PASSWORD — админ из шага 1,
VPS_IP, REALITY_PBK/REALITY_SID — из `/root/marzban-x25519.txt` и
xray_config.json, MARZBAN_PUBLIC_URL = `http://<IP>:8000`
(адрес подписок для клиентов), WEBAPP_URL — HTTPS-адрес Mini App (шаг 4).

systemd-юниты:

```ini
# /etc/systemd/system/vpn-api.service
[Unit]
Description=VPN API
After=network.target

[Service]
WorkingDirectory=/root/vpn/backend
EnvironmentFile=/root/vpn/backend/.env
ExecStart=/root/vpn/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8081
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

Бот и API работают с Marzban через локальный REST (`MARZBAN_URL`),
дополнительных sudo-скриптов не нужно.

## 3. Проверка

1. Напишите боту `/start`.
2. «⚡ Подключить» → QR / ссылка vless:// / подписочная ссылка.
   Импортируйте в v2rayNG (Android) или Streisand (iPhone), включите VPN:
   зарубежные сайты через VPN, российские напрямую.
3. «Купить подписку» → заявка → админ подтверждает → дни продлеваются
   в Marzban автоматически.

## 4. Mini App (HTTPS)

WebApp собран в `backend/webapp/dist` (пересборка: `cd webapp && npm ci && npm run build`).
FastAPI отдаёт его на `/` и `/webapp`. Порт 8081 закрыт файрволом;
снаружи — только HTTPS-туннель.

Без домена (временный адрес меняется при перезапуске туннеля):

```ini
# /etc/systemd/system/vpn-tunnel.service
[Service]
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8081
Restart=always
RestartSec=5
```

```bash
systemctl restart vpn-tunnel
journalctl -u vpn-tunnel | grep trycloudflare   # новый URL → WEBAPP_URL в .env
systemctl restart vpn-bot
```

С доменом (~$3/год) — Caddy: `caddy reverse-proxy --from vpn.example.com --to :8081`,
тогда WEBAPP_URL постоянный, а домен же можно указать как
XRAY_SUBSCRIPTION_URL_PREFIX в Marzban для красивых ссылок подписок.

В @BotFather: Bot Settings → Menu Button → URL webapp.

## 5. Автоматическое обновление из Git

```bash
cd /root/vpn
sudo install -m 755 server/update.sh server/update.sh
sudo install -m 644 server/vpn-update.service /etc/systemd/system/
sudo install -m 644 server/vpn-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-update.timer
```

Таймер каждые 6 часов: `git pull --ff-only`, pip/npm-установка, сборка
Mini App, рестарт сервисов. При локальных изменениях на сервере апдейт
безопасно пропускается.

## 6. Эксплуатация

- `/stats` — статистика (бот, админ)
- `/extend <tg_id> <дней>` — продлить (в БД и Marzban)
- `/revoke <tg_id>` — отключить пользователя (status=disabled)
- Просрочка: Marzban сам отключает пользователя по expire; бот сбрасывает
  флаг в БД раз в час
- Конфиги пользователей — «Перевыпустить» в меню или Mini App

## Известные ограничения

- Платежи: ручное подтверждение админом (провайдер подключается через
  `backend/app/payments/`).
- Подписочные ссылки идут по HTTP (`http://IP:8000`) — пока нет домена.
  Клиенты принимают http-подписки, но HTTPS лучше: решается доменом.
- Ссылки пользователя привязаны к IP сервера — домен избавит и от этого.
