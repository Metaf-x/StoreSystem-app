# Техническая документация: авторизация и JWT-сессия

## Обзор реализации

Авторизация реализована в `auth_service` и используется UI, `products_service`, `orders_service` и `chat_service`.

Схема:

```text
POST /login -> access JWT в JSON + refresh JWT в HttpOnly cookie
POST /refresh-token -> новый access JWT по refresh cookie
Authorization: Bearer <access JWT> -> защищенные API
```

Основные файлы:

- [auth_service/app/auth.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/auth.py)
- [auth_service/app/routes.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/routes.py)
- [auth_service/app/schemas.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/schemas.py)
- [auth_service/app/models.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/models.py)
- [auth_service/main.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/main.py)
- [auth_service/static/js/auth.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/auth.js)
- [auth_service/static/js/form_login.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/form_login.js)
- [products_service/app/auth.py](/Users/metaf/Dev/git/StoreSystem-app/products_service/app/auth.py)
- [orders_service/app/auth.py](/Users/metaf/Dev/git/StoreSystem-app/orders_service/app/auth.py)
- [chat_service/app/auth.py](/Users/metaf/Dev/git/StoreSystem-app/chat_service/app/auth.py)
- [chat_service/app/websocket.py](/Users/metaf/Dev/git/StoreSystem-app/chat_service/app/websocket.py)

## Модель данных

Refresh-сессии хранятся в таблице `tokens`.

Поля:

- `user_id` - primary key, один refresh token на пользователя;
- `access_token` - последний выданный access token, хранится для совместимости;
- `refresh_token` - текущий refresh token пользователя;
- `created_at` - время создания пары токенов;
- `expires_at` - срок действия последнего access token;
- `refresh_expires_at` - срок действия refresh token.

Так как `user_id` является primary key, новый login того же пользователя перезаписывает предыдущую refresh-сессию.

## Создание токенов

`auth.create_tokens(data, db)` принимает `data["sub"]` как user id.

Access JWT payload:

```json
{
  "sub": "user-uuid",
  "token_type": "access",
  "exp": 1710000000
}
```

Refresh JWT payload:

```json
{
  "sub": "user-uuid",
  "token_type": "refresh",
  "exp": 1710000000
}
```

Подпись:

```text
HS256 SECRET_KEY
```

`create_tokens()` делает PostgreSQL upsert в `tokens` по `user_id`.

## `POST /login`

Endpoint: [auth_service/app/routes.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/routes.py)

Request:

```json
{
  "email": "user@example.com",
  "password": "password",
  "remember_me": true
}
```

Успешный response body:

```json
{
  "user_id": "uuid",
  "message": "User successfully logged in",
  "access_token": "jwt",
  "token_type": "bearer"
}
```

Response header:

```http
Set-Cookie: refresh_token=<jwt>; HttpOnly; SameSite=Lax; Path=/
```

Если `remember_me=true`, cookie получает `Max-Age` на 7 дней. Если `remember_me=false`, cookie является session cookie.

## `POST /refresh-token`

Endpoint читает cookie:

```text
refresh_token
```

Алгоритм:

1. Если cookie нет, вернуть `{ "user_id": null, "access_token": null }`.
2. Декодировать refresh JWT.
3. Проверить `token_type=refresh`.
4. Проверить `sub`.
5. Найти строку в `tokens` по `user_id`, `refresh_token`, `refresh_expires_at > now`.
6. Выпустить новый access JWT.
7. Обновить `tokens.access_token` и `tokens.expires_at`.
8. Вернуть `user_id` и `access_token`.

Невалидный refresh token не выбрасывает 401 наружу для login page. Endpoint возвращает `200` с пустыми полями.

## Access token verification

`auth.verify_token(token)` выполняет stateless JWT-проверку:

- декодирует JWT через `SECRET_KEY`;
- проверяет `exp`;
- проверяет `token_type`;
- проверяет наличие `sub`;
- возвращает JWT payload.

Функция не проверяет таблицу `tokens`. Это значит:

- access token продолжает работать до `exp`, даже если пользователь нажал logout;
- refresh token не принимается как access token;
- старые access tokens без `token_type` временно принимаются.

## `/verify-token`

Endpoint находится в [auth_service/main.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/main.py).

Назначение:

- проверить access token;
- найти пользователя в БД;
- вернуть актуальную роль.

Request:

```json
{
  "token": "access-jwt"
}
```

Success:

```json
{
  "valid": true,
  "user_id": "uuid",
  "role": "customer"
}
```

Failure:

```json
{
  "valid": false,
  "error": "Invalid token"
}
```

## `/me`

Endpoint требует Bearer access token.

Response:

```json
{
  "id": "uuid",
  "name": "User Name",
  "email": "user@example.com",
  "role": "operator"
}
```

Frontend использует `/me` для актуализации роли и видимости UI.

## Межсервисная авторизация

`products_service`, `orders_service` и `chat_service` используют одинаковую схему:

1. Получить Bearer token из входящего запроса.
2. Локально декодировать JWT через общий `SECRET_KEY`.
3. Проверить `token_type=access` и `sub`.
4. Вызвать `auth_service /verify-token`.
5. Получить свежую роль пользователя.
6. Сравнить роль с `minimum_role`.

Иерархия ролей:

```python
ROLE_ORDER = {"customer": 0, "operator": 1, "admin": 2}
```

`require_admin=True` в старом коде мапится на `minimum_role="operator"` для обратной совместимости старых вызовов.

## Frontend auth state

Файл [auth_service/static/js/auth.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/auth.js) содержит:

- `cachedAccessToken`;
- `cachedUserId`;
- `refreshTokenPromise`;
- `getTokenFromDatabase()`;
- `getNewAccessToken()`;
- `logoutUser()`.

`getTokenFromDatabase()`:

1. Проверяет access token в памяти.
2. Если token валиден, возвращает его.
3. Если token отсутствует или истек, вызывает `/refresh-token`.
4. Если refresh вернул access token, кладет его в память.
5. Если refresh не вернул access token, редиректит на `/login`.

`form_login.js` на login page:

- при загрузке вызывает `/refresh-token`;
- если получен access token, редиректит на `/products`;
- если token не получен, оставляет пользователя на форме логина.

## Role state frontend

Файл [auth_service/static/js/check_superadmin.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/check_superadmin.js) оставлен под старым именем, но работает как role state module.

Он:

- получает access token через `getTokenFromDatabase()`;
- вызывает `/me`;
- выставляет `window.currentUserRole`, `window.isOperator`, `window.isAdmin`;
- обновляет видимость элементов;
- рассылает событие `role-status-changed`;
- обновляет роль по таймеру, при focus и `visibilitychange`.

## HTML page protection

Часть HTML-страниц защищается на сервере через refresh cookie:

- `/pending-approval` требует `operator`;
- `/admin_orders` требует `operator`;
- `/user-list` требует `admin`.

Проверка идет по refresh token row и текущей роли пользователя в БД.

## WebSocket auth

Chat frontend открывает WebSocket с access token в query parameter:

```text
/ws/{chat_id}/{user_id}?token=<access-jwt>
```

`chat_service`:

- проверяет наличие token;
- валидирует access JWT;
- сравнивает `token.sub` с `user_id` из URL;
- затем проверяет участие пользователя в чате.

## Прогрев UI-сессии в автотестах

Для Selenide/JUnit5:

1. API-клиент вызывает `/login`.
2. Извлекает `refresh_token` из response cookies.
3. Selenium добавляет cookie `refresh_token` в браузер.
4. Тест открывает `/login` или `/products`.
5. UI получает access token через `/refresh-token`.

Пример:

```java
open(baseUrl);

WebDriverRunner.getWebDriver().manage().deleteCookieNamed("refresh_token");
WebDriverRunner.getWebDriver().manage().addCookie(
    new Cookie.Builder("refresh_token", refreshToken)
        .path("/")
        .isHttpOnly(true)
        .isSecure(false)
        .build()
);

open(baseUrl + "/products");
```

Cookie нужно ставить на тот же host/port, где открыт UI.

## OpenAPI

FastAPI генерирует схемы ответов из `schemas.py`.

Особенность: кастомный `/openapi.json` добавляет Bearer security ко всем paths. Из-за этого Swagger UI может показывать `/login`, `/register` и `/refresh-token` как защищенные, хотя фактически они не требуют `Authorization` header.

Это ограничение документации, а не runtime-поведения.

## Известные ограничения

- Сейчас хранится одна refresh-сессия на пользователя.
- Logout не отзывает уже выданный access token мгновенно.
- Refresh token rotation не реализован: при refresh обновляется access token, но не refresh token.
- Используется симметричный `HS256`; все сервисы с локальной JWT-проверкой должны знать общий `SECRET_KEY`.
- В production cookie должна ставиться с `Secure=true`.
