# VPN-сервис в стиле VPSUS

Свой VPN-сервис: российские сервисы работают напрямую (реальный RU-IP,
без предупреждений «у вас VPN»), западные — через VPS в Европе.
Управление — Telegram-бот + Mini App (ЛК, оплата, инструкции, админка).

## Протокол

**VLESS + Reality (sing-box)** — самый современный протокол для этого
сценария: трафик маскируется под обычный HTTPS к реальному сайту
(fallback), устойчив к DPI и активному зондированию, нет серверного
сертификата и открытых признаков VPN.

Маршрутизация — на клиенте, нативными правилами sing-box:
- домены РФ (rule set `Russia-domains` + `geosite-ru` от itdoginfo/allow-domains)
  и IP РФ (`Russia-ips`) → DIRECT (реальный IP пользователя);
- всё остальное → VPS;
- rule set'ы обновляются автоматически (раз в сутки), списки поддерживает
  сообщество, ничего не нужно вести руками.

Пользователи = UUID в Reality inbound; отзыв доступа = удаление UUID из
`users.json` + reload.

## Структура

```
server/     скрипты для VPS: установка sing-box, генерация ключей/конфига,
            управление пользователями, генерация клиентских конфигов
backend/    FastAPI + aiogram-бот, БД, платежный слой
webapp/     React Mini App (Telegram WebApp)
```

## Клиенты (все платформы, официальные приложения sing-box)

| Платформа | Приложение |
|---|---|
| Windows | sing-box GUI / Nekoray / v2rayN (sing-box core) |
| Android | sing-box (SFA) / NekoBox |
| iOS | sing-box (SFI) / Streisand |

Клиентский конфиг — JSON sing-box (полная маршрутизация) + `vless://` URI
(для простого импорта). Для Android/iOS QR-код URI.

## Быстрый старт (VPS, Ubuntu 22.04+)

```bash
# 1. на VPS
sudo bash server/install.sh
sudo python3 server/gen-server-conf.py init
sudo systemctl enable --now sing-box

# 2. создать клиента
sudo bash server/users.sh add <uuid>            # UUID сгенерирует бэкенд
python3 server/gen-client-conf.py <IP> 443 <uuid> <pubkey> <short_id> my-vpn out.json out.uri

# 3. бэкенд и бот
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # заполнить BOT_TOKEN, ADMIN_IDS, SECRET
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
.venv/bin/python -m app.bot

# 4. webapp: собрать и положить dist в backend/webapp/dist
cd webapp && npm i && npm run build
```

## Деплой Mini App без домена

WebApp в Telegram открывается только по HTTPS. Без домена — временно
Cloudflare Tunnel / ngrok / bore; домен (~$3/год) — правильный путь,
тогда FastAPI отдаёт webapp статикой на том же origin.

## Платежи

Слой `backend/app/payments/` — абстракция `PaymentProvider`.
Сейчас включён `manual` (подтверждение админом). Провайдер
(ЮKassa / CryptoBot / Stars) подключается реализацией интерфейса,
см. `payments/manual.py`.

## Безопасность

- Бэкенд и бот живут на VPS и работают через `sudo`-ограниченные команды
  (`users.sh add/del`), без прямого доступа к конфигу сервера.
- UUID пользователя генерируется бэкендом, в открытом виде нигде не хранится
  кроме БД бэкенда.