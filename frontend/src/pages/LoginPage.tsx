import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../state/AuthContext";

export function LoginPage() {
  const { login, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setError("");
    setFieldErrors({});
  }, [email, password]);

  if (status === "authenticated") {
    return <Navigate to="/products" replace />;
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const validationErrors = validateLoginForm(email, password);
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      return;
    }

    setSubmitting(true);
    try {
      await login(email, password, rememberMe);
      const from = (location.state as { from?: Location } | null)?.from?.pathname || "/products";
      navigate(from, { replace: true });
    } catch {
      setError("Неверный email или пароль.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container auth-page d-flex justify-content-center align-items-center">
      <div className="col-md-4">
        <h2 className="text-center mb-4">Вход</h2>
        <form className="mt-3" onSubmit={onSubmit} noValidate>
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
              onChange={(event) => setEmail(event.target.value)}
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
              onChange={(event) => setPassword(event.target.value)}
            />
            {fieldErrors.password && <div className="invalid-feedback">{fieldErrors.password}</div>}
          </div>
          <div className="form-check mb-3">
            <input
              className="form-check-input"
              type="checkbox"
              id="rememberMe"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
            />
            <label className="form-check-label" htmlFor="rememberMe">
              Запомнить меня
            </label>
          </div>
          <button type="submit" className="btn btn-primary w-100" disabled={submitting}>
            {submitting ? "Вход..." : "Войти"}
          </button>
        </form>
        {error && (
          <div className="mt-3 text-center text-danger" data-testid="login-error">
            {error}
          </div>
        )}
        <div className="text-center mt-3">
          <p>
            Нет аккаунта? <Link to="/register">Зарегистрируйтесь</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

function validateLoginForm(email: string, password: string) {
  const errors: Record<string, string> = {};
  const trimmedEmail = email.trim();

  if (!trimmedEmail) {
    errors.email = "Email обязателен для заполнения.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
    errors.email = "Введите корректный email.";
  }

  if (!password) {
    errors.password = "Пароль обязателен для заполнения.";
  }

  return errors;
}
