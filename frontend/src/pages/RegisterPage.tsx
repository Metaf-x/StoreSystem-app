import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../state/AuthContext";

export function RegisterPage() {
  const { register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setFieldErrors({});
    setSuccess(false);

    const validationErrors = validateRegisterForm(name, email, password);
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      return;
    }

    setSubmitting(true);
    try {
      await register(name, email, password);
      setSuccess(true);
      setName("");
      setEmail("");
      setPassword("");
    } catch {
      setError("Некорректный формат email или email уже зарегистрирован.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container auth-page d-flex justify-content-center align-items-center">
      <div className="col-md-4">
        <h2 className="text-center mb-4">Регистрация</h2>
        <form className="mt-3" onSubmit={onSubmit} noValidate>
          <div className="mb-3">
            <label htmlFor="username" className="form-label">
              Имя пользователя
            </label>
            <input
              type="text"
              className={`form-control${fieldErrors.name ? " is-invalid" : ""}`}
              id="username"
              placeholder="Имя пользователя"
              required
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setFieldErrors((current) => ({ ...current, name: "" }));
              }}
            />
            {fieldErrors.name && <div className="invalid-feedback">{fieldErrors.name}</div>}
          </div>
          <div className="mb-3">
            <label htmlFor="email" className="form-label">
              Email
            </label>
            <input
              type="email"
              className={`form-control${fieldErrors.email ? " is-invalid" : ""}`}
              id="email"
              placeholder="Email"
              required
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setFieldErrors((current) => ({ ...current, email: "" }));
              }}
            />
            {fieldErrors.email && <div className="invalid-feedback">{fieldErrors.email}</div>}
          </div>
          <div className="mb-3">
            <label htmlFor="password" className="form-label">
              Пароль
            </label>
            <input
              type="password"
              className={`form-control${fieldErrors.password ? " is-invalid" : ""}`}
              id="password"
              placeholder="Пароль"
              required
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setFieldErrors((current) => ({ ...current, password: "" }));
              }}
            />
            {fieldErrors.password && <div className="invalid-feedback">{fieldErrors.password}</div>}
          </div>
          <button type="submit" className="btn btn-primary w-100" disabled={submitting}>
            {submitting ? "Регистрация..." : "Зарегистрироваться"}
          </button>
        </form>
        {success && <div className="text-center mt-3 text-success">Регистрация прошла успешно!</div>}
        {error && <div className="text-center mt-3 text-danger">{error}</div>}
        <div className="text-center mt-3">
          <p>
            Есть аккаунт? <Link to="/login">Войти</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

function validateRegisterForm(name: string, email: string, password: string) {
  const errors: Record<string, string> = {};
  const trimmedName = name.trim();
  const trimmedEmail = email.trim();

  if (!trimmedName) {
    errors.name = "Имя пользователя обязательно для заполнения.";
  } else if (!/^(?!\s).{3,50}$/.test(name)) {
    errors.name = "Имя должно содержать от 3 до 50 символов и не начинаться с пробела.";
  }

  if (!trimmedEmail) {
    errors.email = "Email обязателен для заполнения.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
    errors.email = "Введите корректный email.";
  }

  if (!password) {
    errors.password = "Пароль обязателен для заполнения.";
  } else if (password.length < 8 || password.length > 50 || /^\s/.test(password) || !password.trim()) {
    errors.password = "Пароль должен быть от 8 до 50 символов и не начинаться с пробела.";
  }

  return errors;
}
