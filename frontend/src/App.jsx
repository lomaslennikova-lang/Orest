import { useEffect, useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const currencyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
});

const dateFormatter = new Intl.DateTimeFormat("uk-UA", {
  dateStyle: "medium",
  timeStyle: "short",
});

const statusLabels = {
  checking: "перевірка",
  loading: "завантаження",
  ready: "готово",
  error: "помилка",
  login: "вхід",
};

const typeLabels = {
  income: "Дохід",
  expense: "Витрата",
};

function formatCurrency(value) {
  return currencyFormatter.format(Number(value || 0));
}

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return dateFormatter.format(new Date(value));
}

function getDateKey(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getTransactionSummary(transactions) {
  return transactions.reduce(
    (summary, transaction) => {
      const amount = Number(transaction.amount || 0);

      if (transaction.type === "income") {
        summary.total_income += amount;
      } else {
        summary.total_expense += amount;
      }

      summary.balance = summary.total_income - summary.total_expense;
      return summary;
    },
    {
      total_income: 0,
      total_expense: 0,
      balance: 0,
    },
  );
}

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [credentials, setCredentials] = useState({
    username: "admin",
    password: "",
  });
  const [transactions, setTransactions] = useState([]);
  const [filters, setFilters] = useState({
    dateFrom: "",
    dateTo: "",
    type: "",
    user: "",
  });
  const [status, setStatus] = useState("checking");
  const [error, setError] = useState("");

  const userOptions = useMemo(() => {
    return [...new Set(transactions.map((transaction) => transaction.user))].sort(
      (firstUser, secondUser) => firstUser.localeCompare(secondUser, "uk"),
    );
  }, [transactions]);

  const filteredTransactions = useMemo(() => {
    return transactions.filter((transaction) => {
      const transactionDate = getDateKey(transaction.created_at);
      const matchesDateFrom =
        !filters.dateFrom || (transactionDate && transactionDate >= filters.dateFrom);
      const matchesDateTo =
        !filters.dateTo || (transactionDate && transactionDate <= filters.dateTo);
      const matchesType = !filters.type || transaction.type === filters.type;
      const matchesUser = !filters.user || transaction.user === filters.user;

      return matchesDateFrom && matchesDateTo && matchesType && matchesUser;
    });
  }, [filters, transactions]);

  const summary = useMemo(
    () => getTransactionSummary(filteredTransactions),
    [filteredTransactions],
  );

  async function loadDashboard() {
    try {
      setStatus("loading");

      const response = await fetch(`${API_BASE_URL}/api/transactions`, {
        credentials: "include",
      });

      if (response.status === 401) {
        setCurrentUser(null);
        setStatus("login");
        return;
      }

      if (!response.ok) {
        throw new Error("Не вдалося завантажити дані API.");
      }

      const transactionsData = await response.json();

      setTransactions(transactionsData);
      setStatus("ready");
      setError("");
    } catch (loadError) {
      setStatus("error");
      setError(loadError.message);
    }
  }

  useEffect(() => {
    async function checkSession() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/me`, {
          credentials: "include",
        });

        if (response.status === 401) {
          setStatus("login");
          return;
        }

        if (!response.ok) {
          throw new Error("Не вдалося перевірити сесію.");
        }

        const user = await response.json();
        setCurrentUser(user);
        setError("");
        await loadDashboard();
      } catch (loadError) {
        setStatus("error");
        setError(loadError.message);
      }
    }

    checkSession();
  }, []);

  async function handleLogin(event) {
    event.preventDefault();

    try {
      setStatus("checking");
      setError("");

      const response = await fetch(`${API_BASE_URL}/api/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(credentials),
      });

      if (response.status === 401) {
        throw new Error("Невірний логін або пароль.");
      }

      if (!response.ok) {
        throw new Error("Вхід тимчасово недоступний.");
      }

      const user = await response.json();
      setCurrentUser(user);
      setCredentials((previousCredentials) => ({
        ...previousCredentials,
        password: "",
      }));
      await loadDashboard();
    } catch (loginError) {
      setStatus("login");
      setError(loginError.message);
    }
  }

  async function handleLogout() {
    await fetch(`${API_BASE_URL}/api/logout`, {
      method: "POST",
      credentials: "include",
    });
    setCurrentUser(null);
    setStatus("login");
  }

  function updateFilter(name, value) {
    setFilters((previousFilters) => ({
      ...previousFilters,
      [name]: value,
    }));
  }

  function resetFilters() {
    setFilters({
      dateFrom: "",
      dateTo: "",
      type: "",
      user: "",
    });
  }

  if (status === "login" || (!currentUser && status !== "checking" && status !== "error")) {
    return (
      <main className="login-shell">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="brand login-brand">
            <div className="brand-mark">O</div>
            <div>
              <div className="brand-name">Orest</div>
              <div className="brand-subtitle">Адмінка</div>
            </div>
          </div>
          <div>
            <h1>Вхід</h1>
            <p>Увійдіть як адміністратор, щоб переглянути дані.</p>
          </div>
          {error ? <div className="notice">{error}</div> : null}
          <label>
            Логін
            <input
              autoComplete="username"
              value={credentials.username}
              onChange={(event) =>
                setCredentials({
                  ...credentials,
                  username: event.target.value,
                })
              }
            />
          </label>
          <label>
            Пароль
            <input
              autoComplete="current-password"
              type="password"
              value={credentials.password}
              onChange={(event) =>
                setCredentials({
                  ...credentials,
                  password: event.target.value,
                })
              }
            />
          </label>
          <button className="primary-button" type="submit">
            Увійти
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">O</div>
          <div>
            <div className="brand-name">Orest</div>
            <div className="brand-subtitle">Адмінка</div>
          </div>
        </div>

        <nav className="nav" aria-label="Розділи адмінки">
          <a className="active" href="/">
            Фінансовий стан
          </a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Фінансовий стан</h1>
            <p>Дані станом на поточний момент</p>
          </div>
          <div className="topbar-actions">
            <span className={`pill ${status}`}>
              {statusLabels[status] || status}
            </span>
            <button className="ghost-button" type="button" onClick={handleLogout}>
              Вийти
            </button>
          </div>
        </header>

        {status === "error" ? <div className="notice">{error}</div> : null}

        <section className="metrics" aria-label="Загальні дані">
          <article className="metric income">
            <span>Доходи</span>
            <strong>{formatCurrency(summary.total_income)}</strong>
          </article>
          <article className="metric expense">
            <span>Витрати</span>
            <strong>{formatCurrency(summary.total_expense)}</strong>
          </article>
          <article className="metric balance">
            <span>Баланс</span>
            <strong>{formatCurrency(summary.balance)}</strong>
          </article>
        </section>

        <section className="content-grid">
          <article className="panel filters-panel">
            <div className="panel-header">
              <h2>Фільтри</h2>
              <button className="ghost-button" type="button" onClick={resetFilters}>
                Скинути
              </button>
            </div>
            <div className="filter-grid">
              <label>
                Дата з
                <input
                  max={filters.dateTo || undefined}
                  type="date"
                  value={filters.dateFrom}
                  onChange={(event) => updateFilter("dateFrom", event.target.value)}
                />
              </label>
              <label>
                Дата по
                <input
                  min={filters.dateFrom || undefined}
                  type="date"
                  value={filters.dateTo}
                  onChange={(event) => updateFilter("dateTo", event.target.value)}
                />
              </label>
              <label>
                Тип
                <select
                  value={filters.type}
                  onChange={(event) => updateFilter("type", event.target.value)}
                >
                  <option value="">Усі типи</option>
                  <option value="income">Дохід</option>
                  <option value="expense">Витрата</option>
                </select>
              </label>
              <label>
                Користувач
                <select
                  value={filters.user}
                  onChange={(event) => updateFilter("user", event.target.value)}
                >
                  <option value="">Усі користувачі</option>
                  {userOptions.map((user) => (
                    <option key={user} value={user}>
                      {user}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </article>

          <article className="panel table-panel">
            <div className="panel-header">
              <h2>Transactions</h2>
              <span>{filteredTransactions.length} записів</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th className="amount-cell">Сума</th>
                    <th>Категорія</th>
                    <th>Тип</th>
                    <th>Користувач</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTransactions.map((transaction) => (
                    <tr key={transaction.id}>
                      <td>{formatDate(transaction.created_at)}</td>
                      <td className="amount-cell">
                        {formatCurrency(transaction.amount)}
                      </td>
                      <td>{transaction.category}</td>
                      <td>
                        <span className={`tag ${transaction.type}`}>
                          {typeLabels[transaction.type] || transaction.type}
                        </span>
                      </td>
                      <td>{transaction.user}</td>
                    </tr>
                  ))}
                  {!filteredTransactions.length ? (
                    <tr>
                      <td className="empty-row" colSpan="5">
                        Немає транзакцій за вибраними фільтрами
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}

export default App;
