# VPN-сервис в стиле VPSUS

Свой VPN-сервис: российские сервисы работают напрямую (реальный RU-IP,
без предупреждений «у вас VPN»), западные — через VPS в Европе.
Управление — Telegram-бот + Mini App (ЛК, оплата, инструкции, админка).

## Протокол

**VLESS + Reality (Xray через панель Marzban)** — трафик маскируется под
обычный HTTPS к реальному сайту (`dl.google.com`), устойчив к DPI и
активному зондированию, нет серверного сертификата и открытых признаков
VPN.

Маршрутизация — на клиенте: домены и IP РФ идут напрямую (правила в
клиентских приложениях), всё остальное — через VPS.

Пользователи = записи панели Marzban (REST API): регистрация, продление
и отзыв доступа делаются бэкендом через API, лимиты и сроки считает
Marzban.

## Структура

```
server/     скрипты для VPS: установка Marzban в Docker, автообновление из Git
backend/    FastAPI + aiogram-бот, БД, платежный слой, клиент Marzban API
webapp/     React Mini App (Telegram WebApp)
```

## Клиенты

| Платформа | Приложение |
|---|---|
| Windows/macOS | Hiddify / Nekoray / v2rayN |
| Android | v2rayNG / NekoBox |
| iOS | Streisand / FoXray |

Выдача конфига: QR-код или `vless://` ссылка + подписочная ссылка Marzban
(подписка обновляет конфиг автоматически).

## Быстрый старт (VPS, Ubuntu 22.04+)

```bash
# 1. Marzban: Docker, контейнер, sudo-админ, Reality-ключи
sudo bash server/install.sh vpnadmin 'пароль'
# → настроить инбаунд VLESS-REALITY на 443 (см. вывод скрипта и DEPLOY.md)

# 2. бэкенд и бот
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # BOT_TOKEN, ADMIN_IDS, JWT_SECRET, MARZBAN_*, REALITY_*
systemd юниты vpn-api (порт 8081) и vpn-bot — см. DEPLOY.md

# 3. webapp: собрать dist в backend/webapp/dist
cd webapp && npm ci && npm run build
```

Подробный деплой: [DEPLOY.md](DEPLOY.md).

## Mini App без домена

WebApp в Telegram открывается только по HTTPS. Без домена — временный
Cloudflare Tunnel к `127.0.0.1:8081` (адрес меняется при перезапуске);
домен (~$3/год) — правильный путь: постоянный URL и HTTPS-подписки.

## Платежи

Слой `backend/app/payments/` — абстракция `PaymentProvider`.
Сейчас включён `manual` (подтверждение админом). Провайдер
(ЮKassa / CryptoBot / Stars) подключается реализацией интерфейса,
см. `payments/manual.py`.

## Безопасность

- Бот/API обращаются к Marzban по локальному REST (`MARZBAN_URL=http://127.0.0.1:8000`);
  порт 8000 открыт ради подписок — для постоянного HTTPS нужен домен.
- Секреты только в `backend/.env` на сервере; автообновление из Git не
  перезаписывает его и останавливается при локальных изменениях.
