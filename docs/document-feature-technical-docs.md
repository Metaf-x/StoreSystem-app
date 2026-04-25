# Техническая документация: документы поставщика и PDF-документы заказа

## Обзор реализации

Фича распределена между тремя частями системы:

- `products_service` хранит документы поставщиков и их метаданные;
- `orders_service` генерирует PDF-документы заказа и отгрузки;
- `auth_service` отдает UI-страницы и JavaScript для загрузки/скачивания.

Основные файлы:

- [products_service/app/routes.py](/Users/metaf/Dev/git/StoreSystem-app/products_service/app/routes.py)
- [products_service/app/models.py](/Users/metaf/Dev/git/StoreSystem-app/products_service/app/models.py)
- [products_service/app/schemas.py](/Users/metaf/Dev/git/StoreSystem-app/products_service/app/schemas.py)
- [orders_service/app/routes.py](/Users/metaf/Dev/git/StoreSystem-app/orders_service/app/routes.py)
- [auth_service/static/js/suppliers.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/suppliers.js)
- [auth_service/static/js/shipments.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/shipments.js)
- [auth_service/static/js/admin_orders.js](/Users/metaf/Dev/git/StoreSystem-app/auth_service/static/js/admin_orders.js)

## Хранение документов поставщика

Метаданные хранятся в таблице `supplier_documents`.

Поля:

- `document_id` - UUID документа;
- `supplier_id` - UUID поставщика;
- `document_type` - тип документа;
- `original_filename` - исходное имя файла;
- `stored_filename` - имя файла на диске;
- `content_type` - MIME type из upload-запроса;
- `file_size` - размер файла в байтах;
- `uploaded_by` - ID пользователя, загрузившего документ;
- `created_at` - дата загрузки;
- `description` - необязательное описание.

Файлы хранятся на диске:

```text
products_service/uploads/supplier_documents/<supplier_id>/<stored_filename>
```

В контейнере путь монтируется как:

```yaml
./products_service/uploads:/app/uploads
```

Монтирование добавлено в:

- `docker-compose.yml`;
- `docker-compose-with-elk.yml`.

## API документов поставщика

### Загрузка документа

```http
POST /suppliers/{supplier_id}/documents
Content-Type: multipart/form-data
Authorization: Bearer <access_token>
```

Поля формы:

- `file` - файл;
- `document_type` - один из `contract`, `certificate`, `requisites`, `price_list`, `other`;
- `description` - необязательное описание.

Доступ: только superadmin.

Успешный ответ: JSON с метаданными документа.

### Список документов

```http
GET /suppliers/{supplier_id}/documents
Authorization: Bearer <access_token>
```

Доступ: любой авторизованный пользователь.

Ответ: массив документов поставщика, отсортированный по `created_at desc`.

### Скачивание документа

```http
GET /suppliers/{supplier_id}/documents/{document_id}/download
Authorization: Bearer <access_token>
```

Доступ: любой авторизованный пользователь.

Ответ: `FileResponse` с исходным именем файла в download metadata.

### Удаление документа

```http
DELETE /suppliers/{supplier_id}/documents/{document_id}
Authorization: Bearer <access_token>
```

Доступ: только superadmin.

При удалении удаляется файл на диске и запись метаданных в БД.

## Валидация документов поставщика

- Максимальный размер upload: 10 MB.
- Тип документа проверяется по allowlist.
- Файл сохраняется под UUID-именем.
- Исходное имя файла не используется как путь сохранения.
- При превышении лимита размера частично записанный файл удаляется.
- Если файл отсутствует на диске при скачивании, API возвращает `404`.

## Удаление поставщика

Удаление поставщика дополнительно проверяет наличие документов.

Если документы существуют, API возвращает ошибку:

```text
Cannot delete supplier: there are documents linked to this supplier.
```

Это сделано для первой версии, чтобы не удалять файлы каскадно и не терять документооборот.

## PDF-документы заказа

PDF-документы реализованы в `orders_service` отдельным REST router рядом с существующим GraphQL API.

Зависимость:

```text
reportlab==4.2.5
```

Она добавлена в `orders_service/requirements.txt`.

### Счет

```http
GET /orders/{order_id}/documents/invoice.pdf
Authorization: Bearer <access_token>
```

### Отгрузочный документ

```http
GET /orders/{order_id}/documents/shipment.pdf
Authorization: Bearer <access_token>
```

Ответ:

```http
Content-Type: application/pdf
Content-Disposition: attachment; filename="<kind>-<order_id>.pdf"
```

Где `<kind>`:

- `invoice`;
- `shipment`.

## Авторизация PDF-документов

Порядок проверки:

1. Проверяется Bearer token.
2. Загружается заказ по `order_id`.
3. Если `order.user_id` совпадает с текущим пользователем, скачивание разрешается.
4. Если заказ чужой, выполняется проверка superadmin.
5. Если пользователь не superadmin, возвращается `403`.

## Состав PDF

PDF строится на лету через `reportlab` и не сохраняется.

Документ содержит:

- заголовок `Invoice` или `Shipment Document`;
- `Order ID`;
- `User ID`;
- `Status`;
- `Created at`;
- таблицу позиций заказа:
  - `Product ID`;
  - `Warehouse ID`;
  - `Quantity`;
  - `Price`;
  - `Total`;
- итоговую сумму `Grand total`.

## UI

### Поставщики

В `suppliers.html` добавлена модалка документов поставщика.

В `suppliers.js` добавлено:

- проверка роли через `/check-superadmin`;
- открытие модалки документов;
- загрузка списка документов;
- upload через `FormData`;
- скачивание через `fetch` и blob;
- удаление документа для superadmin;
- скрытие формы загрузки для пользователей без superadmin.

### Мои отгрузки

В `shipments.js` для каждого заказа добавлены кнопки:

- "Скачать счет";
- "Скачать отгрузочный документ".

Скачивание идет через `fetch` с `Authorization`, затем blob сохраняется как PDF.

### Заказы

В `admin_orders.js` для каждого заказа добавлены те же кнопки скачивания PDF.

Экран уже доступен только superadmin, но API все равно выполняет серверную проверку прав.

## Проверка после изменений

После изменения зависимостей нужно пересобрать минимум `orders_service`:

```bash
docker compose build orders_service
docker compose up -d orders_service
```

Для применения volume и backend/UI изменений рекомендуется пересобрать и поднять:

```bash
docker compose build products_service orders_service auth_service
docker compose up -d products_service orders_service auth_service
```

Минимальные проверки:

```bash
docker compose config --quiet
docker compose -f docker-compose-with-elk.yml config --quiet
```

Проверки API:

- загрузить документ поставщика от superadmin;
- получить список документов от обычного пользователя;
- скачать документ поставщика;
- убедиться, что обычный пользователь не может удалить документ;
- скачать `invoice.pdf` по своему заказу;
- проверить `403` при скачивании чужого заказа;
- скачать PDF чужого заказа от superadmin.

