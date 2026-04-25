# Технические требования: авторизация и JWT-сессия

## Назначение

Система должна поддерживать browser login для UI и Bearer JWT для API-запросов между frontend и микросервисами.

Цели:

- не хранить access token в постоянном браузерном хранилище;
- восстанавливать вход после reload через `HttpOnly` refresh cookie;
- проверять access JWT без обращения к таблице токенов;
- получать актуальную роль пользователя на каждом role-sensitive запросе;
- поддерживать API/UI автотесты через прогрев сессии refresh cookie.

## Термины

- `access_token` - короткоживущий JWT для API-запросов.
- `refresh_token` - долгоживущий JWT для получения нового access token.
- `refresh session` - запись в таблице `tokens`, которая делает refresh token отзывным.
- `role` - актуальная роль пользователя из таблицы `users`.

## Token requirements

### Access token

Access token должен:

- быть JWT, подписанным `HS256`;
- содержать `sub` с `user_id`;
- содержать `exp`;
- содержать `token_type=access`;
- жить 30 минут;
- использоваться в `Authorization: Bearer <access_token>`;
- проверяться stateless по подписи, `exp`, `sub` и `token_type`;
- не храниться в `localStorage`, `sessionStorage` или cookie.

Access token не должен:

- содержать роль пользователя как источник правды;
- использоваться для refresh;
- требовать наличия точной строки access token в таблице `tokens`.

### Refresh token

Refresh token должен:

- быть JWT, подписанным `HS256`;
- содержать `sub` с `user_id`;
- содержать `exp`;
- содержать `token_type=refresh`;
- жить до 7 дней;
- храниться в таблице `tokens`;
- передаваться браузеру через `Set-Cookie`;
- использоваться только endpoint-ом `/refresh-token`;
- отзываться через `/logout`.

Refresh token cookie должна иметь:

- name: `refresh_token`;
- `HttpOnly`;
- `SameSite=Lax`;
- `Path=/`;
- `Max-Age=7 days`, если включен `remember_me`;
- отсутствие `Max-Age`, если `remember_me=false`;
- `Secure=true` в production HTTPS окружении.

## Login requirements

`POST /login` должен:

- принимать `email`, `password`, `remember_me`;
- проверять пароль по password hash;
- создавать новую пару access/refresh токенов;
- сохранять refresh session в таблицу `tokens`;
- возвращать `access_token` и `user_id` в JSON;
- не возвращать `refresh_token` в JSON;
- устанавливать `refresh_token` через `Set-Cookie`.

Новый login того же пользователя должен перезаписывать refresh session пользователя.

## Refresh requirements

`POST /refresh-token` должен:

- читать `refresh_token` из cookie;
- проверять JWT подпись, `exp`, `sub`, `token_type`;
- проверять наличие refresh token в таблице `tokens`;
- проверять `refresh_expires_at`;
- возвращать новый `access_token` и `user_id`, если refresh token валиден;
- возвращать `200` с `user_id=null` и `access_token=null`, если cookie отсутствует или refresh token невалиден.

Endpoint не должен требовать Bearer access token.

## Logout requirements

`POST /logout` должен:

- читать `refresh_token` из cookie;
- удалить соответствующую запись из таблицы `tokens`;
- удалить cookie `refresh_token`;
- быть идемпотентным для клиента.

Logout должен отзывать refresh token. Уже выданный access token может оставаться валидным до истечения `exp`.

## Role freshness requirements

Роль пользователя должна быть актуальной на следующем role-sensitive запросе после изменения роли.

Для этого:

- access token не должен быть источником правды для роли;
- `/verify-token` должен возвращать роль из таблицы `users`;
- `/me` должен возвращать роль из таблицы `users`;
- resource services должны использовать `/verify-token`, когда проверяют `minimum_role`;
- frontend должен периодически обновлять role state через `/me`.

## UI requirements

Frontend должен:

- очищать старые `access_token` и `user_id` из `localStorage`;
- хранить access token только в памяти страницы;
- при отсутствии access token вызывать `/refresh-token`;
- отправлять API-запросы с `Authorization: Bearer <access_token>`;
- перенаправлять пользователя на `/login`, если refresh не вернул access token;
- на login page пробовать `/refresh-token` и перенаправлять на `/products`, если пользователь уже авторизован.

## API test requirements

Для прогретой UI-сессии автотест должен:

- выполнить `POST /login` через API;
- взять `refresh_token` из response cookies;
- добавить cookie `refresh_token` в браузер на origin UI;
- открыть `/login` или целевую страницу;
- дождаться, пока UI получит access token через `/refresh-token`.

Автотест не должен класть `access_token` в `localStorage`.

## WebSocket requirements

Chat WebSocket должен:

- принимать access token в query parameter `token`;
- проверять access JWT;
- сверять JWT `sub` с `user_id` из URL;
- закрывать соединение с policy violation, если token отсутствует или невалиден.

## Acceptance Criteria

- После успешного `/login` JSON содержит `access_token`, но не содержит `refresh_token`.
- После успешного `/login` response содержит cookie `refresh_token`.
- После reload UI получает новый access token через `/refresh-token`.
- При отсутствии refresh cookie `/refresh-token` возвращает `200` с пустыми токен-полями.
- Защищенные API-запросы используют Bearer access token.
- Refresh token не принимается как Bearer access token.
- Изменение роли пользователя видно на следующем `/me` или `/verify-token`.
- Logout удаляет refresh session и cookie.
- После logout refresh token больше не выдает новый access token.
- Новый login того же пользователя инвалидирует старый refresh token.
