import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../state/AuthContext";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { canWriteProducts, logout, user } = useAuth();
  const navigate = useNavigate();

  const onLogout = async (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-light bg-light">
        <div className="container-fluid">
          <Link className="navbar-brand" to="/products">
            Личный кабинет
          </Link>
          <button
            className="navbar-toggler"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#navbarNav"
            aria-controls="navbarNav"
            aria-expanded="false"
            aria-label="Toggle navigation"
          >
            <span className="navbar-toggler-icon" />
          </button>
          <div className="collapse navbar-collapse" id="navbarNav">
            <ul className="navbar-nav me-auto">
              <li className="nav-item">
                <Link className="nav-link" to="/products">
                  Продукты
                </Link>
              </li>
              <li className="nav-item">
                <a className="nav-link" href="/suppliers">
                  Поставщики
                </a>
              </li>
              <li className="nav-item">
                <a className="nav-link" href="/warehouses">
                  Склады
                </a>
              </li>
              <li className="nav-item">
                <a className="nav-link" href="/orders">
                  Заказы
                </a>
              </li>
              <li className="nav-item">
                <a className="nav-link" href="/chat-ui">
                  Чаты
                </a>
              </li>
              {user?.role === "admin" && (
                <li className="nav-item">
                  <a className="nav-link" href="/user-list">
                    Список пользователей
                  </a>
                </li>
              )}
              {canWriteProducts && (
                <li className="nav-item">
                  <a className="nav-link" href="/pending-approval">
                    На согласование
                  </a>
                </li>
              )}
            </ul>
            <ul className="navbar-nav">
              <li className="nav-item">
                <a className="nav-link" href="/login" onClick={onLogout}>
                  Выйти
                </a>
              </li>
            </ul>
          </div>
        </div>
      </nav>
      <main className="container mt-5">{children}</main>
    </>
  );
}
