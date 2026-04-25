import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  createProduct,
  deleteProduct,
  getProduct,
  listProducts,
  listSuppliers,
  searchProducts,
  updateProduct,
  uploadImage,
} from "../api/products";
import { PRODUCTS_API_URL } from "../config";
import { ApiError } from "../lib/http";
import { useAuth } from "../state/AuthContext";
import type { Product, ProductPayload, Supplier } from "../types";
import { Modal } from "../ui/Modal";

type ProductFormState = {
  productId?: string;
  name: string;
  description: string;
  category: string;
  price: string;
  stockQuantity: string;
  supplierId: string;
  imageFile: File | null;
  imageUrl: string | null;
  weight: string;
  dimensions: string;
  manufacturer: string;
};

type ProductFormErrors = Partial<Record<keyof ProductFormState, string>>;

const emptyProductForm: ProductFormState = {
  name: "",
  description: "",
  category: "",
  price: "",
  stockQuantity: "",
  supplierId: "",
  imageFile: null,
  imageUrl: null,
  weight: "",
  dimensions: "",
  manufacturer: "",
};

export function ProductsPage() {
  const { accessToken, authorizedFetch, canWriteProducts, refreshAccessToken } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [searchName, setSearchName] = useState("");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ type: "success" | "danger" | "info"; message: string } | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [form, setForm] = useState<ProductFormState>(emptyProductForm);
  const [formErrors, setFormErrors] = useState<ProductFormErrors>({});
  const [detailsProduct, setDetailsProduct] = useState<Product | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const showNotice = useCallback((message: string, type: "success" | "danger" | "info" = "success") => {
    setNotice({ message, type });
    window.setTimeout(() => setNotice(null), 3000);
  }, []);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    try {
      setProducts(await listProducts(authorizedFetch));
    } catch {
      showNotice("Ошибка загрузки продуктов", "danger");
    } finally {
      setLoading(false);
    }
  }, [authorizedFetch, showNotice]);

  const loadSuppliers = useCallback(async () => {
    try {
      setSuppliers(await listSuppliers(authorizedFetch));
    } catch {
      showNotice("Ошибка загрузки поставщиков", "danger");
    }
  }, [authorizedFetch, showNotice]);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  const openCreateModal = async () => {
    setForm(emptyProductForm);
    setFormErrors({});
    setFormMode("create");
    await loadSuppliers();
  };

  const openEditModal = async (productId: string) => {
    try {
      const product = await getProduct(authorizedFetch, productId);
      setForm(productToForm(product));
      setFormErrors({});
      setFormMode("edit");
      await loadSuppliers();
    } catch {
      showNotice("Ошибка загрузки продукта", "danger");
    }
  };

  const openDetails = async (productId: string) => {
    try {
      setDetailsProduct(await getProduct(authorizedFetch, productId));
    } catch {
      showNotice("Ошибка загрузки продукта", "danger");
    }
  };

  const onSearch = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      const nextProducts = searchName.trim()
        ? await searchProducts(authorizedFetch, searchName.trim())
        : await listProducts(authorizedFetch);
      setProducts(nextProducts);
      if (nextProducts.length === 0) {
        showNotice("Продукты не найдены", "info");
      }
    } catch {
      showNotice("Ошибка поиска продукта", "danger");
    } finally {
      setLoading(false);
    }
  };

  const onDelete = async (productId: string) => {
    if (!window.confirm("Вы уверены, что хотите удалить продукт?")) {
      return;
    }
    try {
      await deleteProduct(authorizedFetch, productId);
      await loadProducts();
      showNotice("Продукт удален");
    } catch (error) {
      showNotice(error instanceof ApiError ? error.message : "Ошибка удаления продукта", "danger");
    }
  };

  const onSubmitProduct = async (event: FormEvent) => {
    event.preventDefault();
    const validationErrors = validateProductForm(form);
    if (Object.keys(validationErrors).length > 0) {
      setFormErrors(validationErrors);
      showNotice("Проверьте ошибки в форме", "danger");
      return;
    }

    setSubmitting(true);
    try {
      const token = accessToken || (await refreshAccessToken());
      if (!token) {
        throw new ApiError("Unauthorized", 401);
      }

      let imageUrl = form.imageUrl;
      if (form.imageFile) {
        imageUrl = (await uploadImage(token, form.imageFile)).imageUrl;
      }

      const payload = formToPayload(form, imageUrl);
      if (formMode === "edit" && form.productId) {
        await updateProduct(authorizedFetch, form.productId, payload);
        showNotice("Продукт успешно обновлен");
      } else {
        await createProduct(authorizedFetch, payload);
        showNotice("Продукт успешно добавлен");
      }
      setFormMode(null);
      setForm(emptyProductForm);
      await loadProducts();
    } catch (error) {
      showNotice(error instanceof ApiError ? error.message : "Ошибка сохранения продукта", "danger");
    } finally {
      setSubmitting(false);
    }
  };

  const supplierNameById = useMemo(
    () => new Map(suppliers.map((supplier) => [supplier.supplier_id, supplier.name])),
    [suppliers],
  );

  return (
    <>
      <h2 className="text-center my-4">Управление продуктами</h2>
      {notice && <div className={`app-notification alert alert-${notice.type}`}>{notice.message}</div>}

      {canWriteProducts && (
        <div className="text-end mb-3">
          <button className="btn btn-primary mb-3" type="button" onClick={openCreateModal}>
            Добавить новый продукт
          </button>
        </div>
      )}

      <form className="input-group mb-4" onSubmit={onSearch}>
        <input
          type="text"
          className="form-control"
          placeholder="Введите название для поиска"
          value={searchName}
          onChange={(event) => setSearchName(event.target.value)}
        />
        <button className="btn btn-outline-secondary" type="submit">
          Найти
        </button>
      </form>

      <div className="card shadow-sm">
        <div className="card-body">
          <h5 className="card-title mb-3">Список продуктов</h5>
          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status" />
            </div>
          ) : (
            <div className="table-responsive">
              <table className="table align-middle">
                <thead className="table-light">
                  <tr>
                    <th scope="col">ID</th>
                    <th scope="col">Название</th>
                    <th scope="col">Описание</th>
                    <th scope="col">Категория</th>
                    <th scope="col">Цена</th>
                    <th scope="col" className="text-center">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {products.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center text-muted py-4">
                        Продукты не найдены
                      </td>
                    </tr>
                  ) : (
                    products.map((product) => (
                      <tr key={product.product_id}>
                        <td className="product-id-cell">{product.product_id}</td>
                        <td>
                          <button className="btn btn-link p-0" type="button" onClick={() => openDetails(product.product_id)}>
                            {product.name}
                          </button>
                        </td>
                        <td>{product.description || ""}</td>
                        <td>{product.category || ""}</td>
                        <td>{product.price} руб</td>
                        <td className="text-center">
                          {canWriteProducts && (
                            <>
                              <button
                                className="btn btn-sm btn-outline-warning mt-2 me-2"
                                type="button"
                                onClick={() => openEditModal(product.product_id)}
                              >
                                Редактировать
                              </button>
                              <button
                                className="btn btn-sm btn-outline-danger mt-2"
                                type="button"
                                onClick={() => onDelete(product.product_id)}
                              >
                                Удалить
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {formMode && (
        <Modal
          title={formMode === "create" ? "Добавить новый продукт" : "Редактировать продукт"}
          onClose={() => setFormMode(null)}
        >
          <ProductForm
            form={form}
            errors={formErrors}
            suppliers={suppliers}
            submitting={submitting}
            mode={formMode}
            onChange={(nextForm, changedField) => {
              setForm(nextForm);
              if (changedField) {
                setFormErrors((current) => ({ ...current, [changedField]: undefined }));
              }
            }}
            onSubmit={onSubmitProduct}
          />
        </Modal>
      )}

      {detailsProduct && (
        <Modal title={detailsProduct.name} onClose={() => setDetailsProduct(null)}>
          <ProductDetails product={detailsProduct} supplierName={supplierNameById.get(detailsProduct.supplier_id)} />
        </Modal>
      )}
    </>
  );
}

function ProductForm({
  form,
  errors,
  suppliers,
  submitting,
  mode,
  onChange,
  onSubmit,
}: {
  form: ProductFormState;
  errors: ProductFormErrors;
  suppliers: Supplier[];
  submitting: boolean;
  mode: "create" | "edit";
  onChange: (form: ProductFormState, changedField?: keyof ProductFormState) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const setField = (field: keyof ProductFormState, value: string | File | null) => {
    onChange({ ...form, [field]: value }, field);
  };

  return (
    <form onSubmit={onSubmit} noValidate>
      <TextInput
        label="Название продукта (обязательно)"
        value={form.name}
        error={errors.name}
        onChange={(value) => setField("name", value)}
        required
      />
      <TextInput
        label="Описание"
        value={form.description}
        error={errors.description}
        onChange={(value) => setField("description", value)}
      />
      <TextInput
        label="Категория"
        value={form.category}
        error={errors.category}
        onChange={(value) => setField("category", value)}
      />
      <TextInput
        label="Цена (руб)(обязательно)"
        value={form.price}
        error={errors.price}
        onChange={(value) => setField("price", value.replace(",", "."))}
        required
      />
      <TextInput
        type="number"
        label="Количество продукта (обязательно)"
        value={form.stockQuantity}
        error={errors.stockQuantity}
        onChange={(value) => setField("stockQuantity", value)}
        required
      />
      <div className="mb-3">
        <label className="form-label" htmlFor="supplier-id">
          Поставщик (обязательно)
        </label>
        <select
          className={`form-control${errors.supplierId ? " is-invalid" : ""}`}
          id="supplier-id"
          required
          value={form.supplierId}
          onChange={(event) => setField("supplierId", event.target.value)}
        >
          <option value="" disabled>
            Выберите поставщика
          </option>
          {suppliers.map((supplier) => (
            <option key={supplier.supplier_id} value={supplier.supplier_id}>
              {supplier.name}
            </option>
          ))}
        </select>
        {errors.supplierId && <div className="invalid-feedback">{errors.supplierId}</div>}
      </div>
      <div className="mb-3">
        <label className="form-label" htmlFor="image-url">
          Изображение продукта
        </label>
        <input
          type="file"
          className={`form-control${errors.imageFile ? " is-invalid" : ""}`}
          id="image-url"
          accept=".png,.jpeg,.jpg"
          onChange={(event) => setField("imageFile", event.target.files?.[0] || null)}
        />
        {errors.imageFile && <div className="invalid-feedback">{errors.imageFile}</div>}
        {mode === "edit" && form.imageUrl && <div className="form-text">Текущее изображение будет сохранено, если не выбрать новый файл.</div>}
      </div>
      <TextInput
        type="number"
        step="0.01"
        label="Вес партии продукта (кг)"
        value={form.weight}
        error={errors.weight}
        onChange={(value) => setField("weight", value.replace(",", "."))}
      />
      <TextInput
        label="Габариты продукта (1х1х1 метра)"
        value={form.dimensions}
        error={errors.dimensions}
        onChange={(value) => setField("dimensions", value)}
      />
      <TextInput
        label="Производитель"
        value={form.manufacturer}
        error={errors.manufacturer}
        onChange={(value) => setField("manufacturer", value)}
      />
      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? "Сохранение..." : mode === "create" ? "Создать продукт" : "Сохранить изменения"}
      </button>
    </form>
  );
}

function TextInput({
  label,
  value,
  error,
  onChange,
  required,
  type = "text",
  step,
}: {
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  step?: string;
}) {
  const id = label.toLowerCase().replace(/[^a-zа-я0-9]+/gi, "-");
  return (
    <div className="mb-3">
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      <input
        type={type}
        step={step}
        className={`form-control${error ? " is-invalid" : ""}`}
        id={id}
        required={required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {error && <div className="invalid-feedback">{error}</div>}
    </div>
  );
}

function ProductDetails({ product, supplierName }: { product: Product; supplierName?: string }) {
  const imageSrc = product.image_url?.startsWith("http") ? product.image_url : `${PRODUCTS_API_URL}${product.image_url || ""}`;
  return (
    <>
      {product.image_url && <img className="product-image-preview mb-3" src={imageSrc} alt={product.name} />}
      <p>
        <strong>Описание:</strong> {product.description || "Нет описания"}
      </p>
      <p>
        <strong>Категория:</strong> {product.category || "Нет категории"}
      </p>
      <p>
        <strong>Цена:</strong> {product.price} руб
      </p>
      <p>
        <strong>Количество на складе:</strong> {product.stock_quantity}
      </p>
      <p>
        <strong>Поставщик:</strong> {supplierName || product.supplier_id}
      </p>
      <p>
        <strong>Вес:</strong> {product.weight || "Нет данных"} кг
      </p>
      <p>
        <strong>Габариты:</strong> {product.dimensions || "Нет данных"}
      </p>
      <p>
        <strong>Производитель:</strong> {product.manufacturer || "Нет данных"}
      </p>
    </>
  );
}

function productToForm(product: Product): ProductFormState {
  return {
    productId: product.product_id,
    name: product.name,
    description: product.description || "",
    category: product.category || "",
    price: String(product.price),
    stockQuantity: String(product.stock_quantity),
    supplierId: product.supplier_id,
    imageFile: null,
    imageUrl: product.image_url,
    weight: product.weight ? String(product.weight) : "",
    dimensions: product.dimensions || "",
    manufacturer: product.manufacturer || "",
  };
}

function formToPayload(form: ProductFormState, imageUrl: string | null): ProductPayload {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    category: form.category.trim() || null,
    price: form.price.trim(),
    stock_quantity: Number.parseInt(form.stockQuantity, 10),
    supplier_id: form.supplierId,
    image_url: imageUrl,
    weight: form.weight.trim() || null,
    dimensions: form.dimensions.trim() || null,
    manufacturer: form.manufacturer.trim() || null,
  };
}

function validateProductForm(form: ProductFormState) {
  const errors: ProductFormErrors = {};
  const name = form.name.trim();
  if (!/^[а-яА-Яa-zA-Z0-9\s]{3,100}$/.test(name)) {
    errors.name = name ? "Название должно быть от 3 до 100 символов, только буквы, цифры и пробелы." : "Название продукта обязательно для заполнения.";
  }
  if (form.description.trim().length > 500) {
    errors.description = "Описание не должно превышать 500 символов.";
  }
  const category = form.category.trim();
  if (category && (category.length > 50 || !/^[а-яА-Яa-zA-Z0-9]+$/.test(category))) {
    errors.category = "Категория должна быть до 50 символов, только буквы и цифры.";
  }
  const price = form.price.trim().replace(",", ".");
  if (!price || Number.isNaN(Number(price)) || Number(price) <= 0 || Number(price) > 9999999.99) {
    errors.price = price ? "Цена должна быть положительным числом, максимум 9999999.99." : "Цена обязательна для заполнения.";
  }
  if (!/^\d+$/.test(form.stockQuantity) || Number.parseInt(form.stockQuantity, 10) < 0) {
    errors.stockQuantity = form.stockQuantity ? "Количество должно быть целым числом, не меньше 0." : "Количество обязательно для заполнения.";
  }
  if (!form.supplierId) {
    errors.supplierId = "Необходимо выбрать поставщика.";
  }
  if (form.imageFile && !/\.(png|jpeg|jpg)$/i.test(form.imageFile.name)) {
    errors.imageFile = "Формат изображения должен быть .png, .jpeg или .jpg.";
  }
  const weight = form.weight.trim().replace(",", ".");
  if (weight && (!/^\d{1,8}\.\d{2}$/.test(weight) || Number(weight) <= 0)) {
    errors.weight = "Вес должен быть положительным числом с двумя знаками после запятой.";
  }
  const dimensions = form.dimensions.trim();
  if (dimensions && (dimensions.length > 100 || !/^\d+x\d+x\d+$/.test(dimensions))) {
    errors.dimensions = 'Габариты должны быть в формате "1x2x3" и содержать не более 100 символов.';
  }
  const manufacturer = form.manufacturer.trim();
  if (manufacturer && !/^[а-яА-Яa-zA-Z0-9]{1,100}$/.test(manufacturer)) {
    errors.manufacturer = "Производитель может содержать только буквы и цифры, максимум 100 символов.";
  }
  return errors;
}
