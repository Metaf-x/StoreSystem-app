# Техническая документация: ролевая модель `customer`, `operator`, `admin`

## Обзор реализации

Ролевая модель реализована как одно поле `role` в пользователе `auth_service`.

Поддерживаемые значения:

```text
customer
operator
admin
```

Проверка доступа строится на иерархии:

```text
customer < operator < admin
```

Основные зоны реализации:

- `auth_service` хранит роль, отдает user context и управляет ролями;
- `products_service`, `orders_service`, `chat_service` получают роль через `auth_service`;
- frontend получает роль через `GET /me` и скрывает недоступные элементы интерфейса.

Основные файлы:

- [auth_service/app/models.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/models.py)
- [auth_service/app/database.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/database.py)
- [auth_service/app/routes.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/app/routes.py)
- [auth_service/main.py](/Users/metaf/Dev/git/StoreSystem-app/auth_service/main.py)
- [products_service/app/auth.py](/Users/metaf/Dev/git/StoreSystem-app/products_service/app/auth.py)
- [orders_service/app/auth.py](/Users/metaf/Dev/git/StoreSystem-app/orders_service/app/auth.py)
- [chat_service/app/auth.py](/Users/metaf/Dev/git/StoreSystem-app/chat_service/app/auth.py)
- [auth_service/static/js/check_superadmin.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/check_superadmin.js)

## Модель данных

В `auth_service.app.models.User` добавлено поле:

```python
role = Column(String, default="customer", nullable=False, index=True)
```

Поле `is_superadmin` оставлено как legacy migration source. Бизнес-логика должна использовать `role`, а не `is_superadmin`.

## Миграция

Миграция выполняется при старте `auth_service` в `database.init_db()`.

Порядок:

1. `models.Base.metadata.create_all(...)` создает отсутствующие таблицы.
2. `migrate_user_roles()` проверяет наличие таблицы `users`.
3. Если колонки `role` нет, выполняется:

```sql
ALTER TABLE users ADD COLUMN role VARCHAR NOT NULL DEFAULT 'customer'
```

4. Если есть legacy-колонка `is_superadmin`, данные переносятся:

```sql
UPDATE users
SET role = CASE WHEN is_superadmin THEN 'admin' ELSE 'customer' END
WHERE role IS NULL OR role = 'customer'
```

5. Невалидные роли нормализуются в `customer`.
6. Seed-пользователь получает роль `admin`.

## Auth service

### Ролевые константы

В auth routes используется порядок:

```python
ROLE_ORDER = {"customer": 0, "operator": 1, "admin": 2}
```

Проверка минимальной роли:

- `require_operator` разрешает `operator` и `admin`;
- `require_admin` разрешает только `admin`.

### `POST /verify-token`

Endpoint проверяет access token и наличие пользователя в БД.

Ответ при успехе:

```json
{
  "valid": true,
  "user_id": "uuid",
  "role": "operator"
}
```

Этот endpoint является единым контрактом межсервисной авторизации.

### `GET /me`

Endpoint используется frontend-ом для получения текущей роли.

Ответ:

```json
{
  "id": "uuid",
  "name": "User Name",
  "email": "user@example.com",
  "role": "admin"
}
```

### `PUT /users/{user_id}/role`

Endpoint обновляет роль пользователя.

Требования:

- доступ только `admin`;
- тело запроса валидируется схемой `UserRoleUpdate`;
- роль должна быть одной из `customer`, `operator`, `admin`;
- если пользователь уже имеет указанную роль, endpoint возвращает `200 OK` без записи в БД;
- если пользователь является последним `admin`, его нельзя понизить.

### Список пользователей

`GET /users`:

- для `admin` возвращает полный список с фильтрацией по `customer|operator|admin`;
- для не-admin возвращает только текущего пользователя.

## Межсервисная авторизация

Каждый сервис локально декодирует JWT, чтобы проверить базовую корректность токена, затем вызывает:

```http
POST http://auth_service:8000/verify-token
```

После ответа сервис получает:

```json
{
  "user_id": "uuid",
  "role": "customer|operator|admin"
}
```

В каждом auth-client используется одинаковый порядок ролей:

```python
ROLE_ORDER = {"customer": 0, "operator": 1, "admin": 2}
```

Параметр `minimum_role` определяет минимальный уровень доступа.

## Products service

Read-only endpoint-ы остаются доступными любому авторизованному пользователю:

- список продуктов;
- просмотр продукта;
- поиск продуктов;
- список поставщиков;
- просмотр поставщика;
- поиск поставщиков;
- список складов;
- просмотр склада;
- просмотр товаров на складе;
- список и скачивание документов поставщика.

Операционные endpoint-ы требуют `minimum_role="operator"`:

- загрузка изображения продукта;
- создание, изменение и удаление продукта;
- изменение доступности продукта;
- создание, изменение и удаление поставщика;
- загрузка и удаление документа поставщика;
- создание, изменение и удаление склада;
- добавление, изменение и удаление товара на складе.

## Orders service

`customer`:

- создает свои заказы;
- смотрит свои заказы;
- скачивает PDF только по своим заказам;
- может отменять свой заказ по существующим бизнес-правилам.

`operator` и `admin`:

- смотрят все заказы через GraphQL `listAllOrders`;
- получают доступ к чужому заказу;
- скачивают PDF по любому заказу;
- обновляют операционный статус заказа.

REST PDF endpoint-ы используют проверку:

1. Если заказ принадлежит текущему пользователю, доступ разрешается.
2. Иначе требуется `minimum_role="operator"`.

## Chat service

`customer`:

- видит свои чаты;
- читает сообщения только в чатах, где является участником;
- отправляет сообщения только в свои чаты;
- не может создавать чаты и добавлять участников.

`operator` и `admin`:

- создают чаты;
- добавляют участников;
- читают чат через `GET /chats/{chat_id}` даже без участия в нем.

## Frontend

Ролевое состояние хранится в JS на странице:

```javascript
window.currentUserRole
window.isOperator
window.isAdmin
```

Файл [auth_service/static/js/check_superadmin.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/check_superadmin.js) сохранен по старому пути, но теперь работает как role state module.

Он:

- вызывает `GET /me`;
- обновляет глобальное состояние роли;
- скрывает/показывает элементы меню;
- рассылает событие `role-status-changed`.

Событие:

```javascript
new CustomEvent("role-status-changed", {
  detail: { role, isOperator, isAdmin }
})
```

### Видимость UI

- `#user-list-item` виден только `admin`.
- `#pending-approval-item` виден `operator` и `admin`.
- `#adminOrdersBtn` виден `operator` и `admin`.
- `.btn-add-participants` видны `operator` и `admin`.
- Элементы с `data-role-min="operator"` видны `operator` и `admin`.
- Элементы с `data-role-min="admin"` видны только `admin`.

## Защита HTML-страниц

Некоторые HTML-страницы дополнительно защищены на сервере через refresh cookie:

- `/user-list` требует `admin`;
- `/pending-approval` требует `operator`;
- `/admin_orders` требует `operator`.

Это нужно, чтобы пользователь не мог открыть operator/admin страницу прямым URL, даже если пункт меню скрыт.

## Удаленные старые контракты

Код больше не должен обращаться к:

- `/check-superadmin`;
- `/verify-token-with-admin`;
- `/users/promote/{user_id}`;
- `is_superadmin` в ответах API;
- `isSuperAdmin` на фронтенде.

Если старые клиенты еще существуют, они должны быть переведены на:

- `GET /me` для UI;
- `POST /verify-token` для межсервисной проверки;
- `PUT /users/{user_id}/role` для назначения роли.

## Проверка

В рамках реализации выполнены проверки:

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-pycache /tmp/storesystem-roles-venv/bin/python -m unittest tests/test_seed_superadmin.py tests/test_auth_tokens.py
```

Результат:

```text
OK (skipped=1)
```

Также выполнена компиляция Python-модулей:

```bash
PYTHONPYCACHEPREFIX=/tmp/codex-pycache /tmp/storesystem-roles-venv/bin/python -m compileall auth_service products_service orders_service chat_service tests
```

И проверка синтаксиса измененных JS-файлов через:

```bash
node --check <file>
```

## Известные ограничения

- `is_superadmin` остается в модели только как legacy migration source.
- Роли фиксированы в коде, отдельной таблицы `roles` нет.
- Access token не содержит role claim; роль всегда берется из `auth_service`.
- Для запуска полного приложения нужны рабочие Kafka/PostgreSQL контейнеры и зависимости каждого сервиса.
