# 🚀 Binance Cloud Grid Bot (Northflank Deployment Guide)

Этот микросервис специально подготовлен для **автономной круглосуточной работы 24/7 в облаке Northflank.com**.

## Особенности микро-бота:
1. **Потребление**: ~35 МБ RAM (работает на бесплатном тарифе Northflank).
2. **Нулевые зависимости**: стандартная библиотека Python (собирается в Docker за 5 секунд).
3. **Безопасность для $50**:
   - Размер лота: по умолчанию **$10** (`ORDER_AMOUNT_USDT=10.0`).
   - Сетка: **3 уровня вниз** с шагом 0.40% (`GRID_STEP_BPS=40.0`).
   - Тейк-профит: **+0.60%** (`GRID_PROFIT_BPS=60.0`).
   - Переключатель тестовой / боевой торговли: `USE_TESTNET=true`.

---

## 🛠️ Как развернуть на Northflank за 3 минуты:

### Шаг 1: Зарегистрируйтесь на Northflank.com
1. Перейдите на [https://northflank.com](https://northflank.com) и войдите через свой GitHub-аккаунт.

### Шаг 2: Создайте проект (Project)
1. Нажмите **«Create Project»** (назовите, например: `binance-grid-bot`).
2. Выберите регион (рекомендуется **Frankfurt, Europe** — самый близкий к серверам Binance).

### Шаг 3: Создайте сервис (Deployment Service)
1. Внутри проекта нажмите **«Create Service»** $\rightarrow$ выберите **«Deployment Service»**.
2. В блоке **Deployment Source** выберите:
   - **Repository**: ваш репозиторий `Asset1312/kase-pilot`
   - **Branch**: `main`
3. В блоке **Build Configuration**:
   - **Build Type**: `Dockerfile`
   - **Context Path**: `/deploy/northflank-grid-bot`
   - **Dockerfile Path**: `/deploy/northflank-grid-bot/Dockerfile`
4. В блоке **Plan**:
   - Выберите бесплатный план **Micro** (0.1 CPU, 128 MB RAM).

### Шаг 4: Переменные окружения (Environment Variables)
В разделе **Environment Variables** добавьте:

| Переменная | Значение для Testnet | Значение для Live ($50) |
| :--- | :--- | :--- |
| `BINANCE_API_KEY` | *Ваш ключ с testnet.binance.vision* | *Боевой ключ с Binance* |
| `BINANCE_SECRET_KEY` | *Ваш секрет с testnet.binance.vision* | *Боевой секрет с Binance* |
| `USE_TESTNET` | `true` | `false` |
| `SYMBOL` | `SOLUSDT` (или `DOGEUSDT`, `XRPUSDT`) | `SOLUSDT` |
| `ORDER_AMOUNT_USDT` | `10.0` | `10.0` |
| `TELEGRAM_BOT_TOKEN` | *(опционально)* | *(токен вашего телеграм-бота)* |
| `TELEGRAM_CHAT_ID` | *(опционально)* | *(ваш ID чата)* |

5. Нажмите **«Deploy Service»**!

---

## 📱 Результат
- Бот запустится в облаке за 10 секунд.
- Во вкладке **Logs** в Northflank вы будете в реальном времени видеть установку лимитных ордеров, фиксацию профита и начисление USDT.
- Компьютер можно выключать — бот торгует автономно 24/7!
