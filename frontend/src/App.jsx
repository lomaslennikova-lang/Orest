import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const currencyFormatter = new Intl.NumberFormat("uk-UA", {
  style: "currency",
  currency: "UAH",
});

const dateFormatter = new Intl.DateTimeFormat("uk-UA", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatCurrency(value) {
  return currencyFormatter.format(Number(value || 0));
}

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return dateFormatter.format(new Date(value));
}

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [credentials, setCredentials] = useState({
    username: "admin",
    password: "",
  });
  const [summary, setSummary] = useState({
    total_income: 0,
    total_expense: 0,
    balance: 0,
  });
  const [transactions, setTransactions] = useState([]);
  const [status, setStatus] = useState("checking");
  const [error, setError] = useState("");

  async function loadDashboard() {
    try {
      setStatus("loading");

      const [summaryResponse, transactionsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/summary`, { credentials: "include" }),
        fetch(`${API_BASE_URL}/api/transactions`, { credentials: "include" }),
      ]);

      if (summaryResponse.status === 401 || transactionsResponse.status === 401) {
        setCurrentUser(null);
        setStatus("login");
        return;
      }

      if (!summaryResponse.ok || !transactionsResponse.ok) {
        throw new Error("Не вдалося завантажити дані API.");
      }

      const [summaryData, transactionsData] = await Promise.all([
        summaryResponse.json(),
        transactionsResponse.json(),
      ]);

      setSummary(summaryData);
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
            <div className="brand-subtitle">Admin</div>
          </div>
        </div>

        <nav className="nav">
          <a className="active" href="/">
            Dashboard
          </a>
          <a href={`${API_BASE_URL}/api/summary`}>Summary API</a>
          <a href={`${API_BASE_URL}/api/transactions`}>Transactions API</a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Finance operations</h1>
            <p>Neon database</p>
          </div>
          <div className="topbar-actions">
            <span className={`pill ${status}`}>{status}</span>
            <button className="ghost-button" type="button" onClick={handleLogout}>
              Вийти
            </button>
          </div>
        </header>

        {status === "error" ? <div className="notice">{error}</div> : null}

        <section className="metrics" aria-label="Summary">
          <article className="metric income">
            <span>Total income</span>
            <strong>{formatCurrency(summary.total_income)}</strong>
          </article>
          <article className="metric expense">
            <span>Total expense</span>
            <strong>{formatCurrency(summary.total_expense)}</strong>
          </article>
          <article className="metric balance">
            <span>Balance</span>
            <strong>{formatCurrency(summary.balance)}</strong>
          </article>
        </section>

        <section className="content-grid">
          <article className="panel table-panel">
            <div className="panel-header">
              <h2>Transactions</h2>
              <span>{transactions.length} rows</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Category</th>
                    <th>User</th>
                    <th>Type</th>
                    <th className="amount-cell">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr key={transaction.id}>
                      <td>{formatDate(transaction.created_at)}</td>
                      <td>{transaction.category}</td>
                      <td>{transaction.user}</td>
                      <td>
                        <span className={`tag ${transaction.type}`}>
                          {transaction.type}
                        </span>
                      </td>
                      <td className="amount-cell">
                        {formatCurrency(transaction.amount)}
                      </td>
                    </tr>
                  ))}
                  {!transactions.length ? (
                    <tr>
                      <td className="empty-row" colSpan="5">
                        No transactions
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
