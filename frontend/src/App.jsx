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

const emptyFilters = {
  dateFrom: "",
  dateTo: "",
  type: "",
  user: "",
};

const emptyNewTransaction = {
  created_at: "",
  amount: "",
  category: "",
  type: "expense",
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

function getCurrentDateTimeLocal() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
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

function filterTransactions(transactions, filters) {
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
}

function App() {
  const [activeTab, setActiveTab] = useState("finance");
  const [currentUser, setCurrentUser] = useState(null);
  const [credentials, setCredentials] = useState({
    username: "admin",
    password: "",
  });
  const [transactions, setTransactions] = useState([]);
  const [financeFilters, setFinanceFilters] = useState(emptyFilters);
  const [editFilters, setEditFilters] = useState(emptyFilters);
  const [newTransaction, setNewTransaction] = useState(emptyNewTransaction);
  const [status, setStatus] = useState("checking");
  const [error, setError] = useState("");
  const [editError, setEditError] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const [addedTransactionId, setAddedTransactionId] = useState(null);
  const [activeTransactionId, setActiveTransactionId] = useState(null);
  const [financialAnalysis, setFinancialAnalysis] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState("idle");
  const [analysisError, setAnalysisError] = useState("");

  const isAdmin = currentUser?.role === "admin";
  const currentDateTimeLocal = getCurrentDateTimeLocal();

  const userOptions = useMemo(() => {
    return [...new Set(transactions.map((transaction) => transaction.user))].sort(
      (firstUser, secondUser) => firstUser.localeCompare(secondUser, "uk"),
    );
  }, [transactions]);

  const categoryOptions = useMemo(() => {
    return [...new Set(transactions.map((transaction) => transaction.category))].sort(
      (firstCategory, secondCategory) => firstCategory.localeCompare(secondCategory, "uk"),
    );
  }, [transactions]);

  const filteredFinanceTransactions = useMemo(
    () => filterTransactions(transactions, financeFilters),
    [financeFilters, transactions],
  );

  const filteredEditTransactions = useMemo(
    () => filterTransactions(transactions, editFilters),
    [editFilters, transactions],
  );

  const summary = useMemo(
    () => getTransactionSummary(filteredFinanceTransactions),
    [filteredFinanceTransactions],
  );

  const hasExpenseTransactions = useMemo(
    () => filteredFinanceTransactions.some((transaction) => transaction.type === "expense"),
    [filteredFinanceTransactions],
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
      setFinancialAnalysis(null);
      setAnalysisError("");
      setAnalysisStatus("idle");
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
    setActiveTab("finance");
    setStatus("login");
  }

  function updateFilter(setFilter, name, value) {
    if (analysisStatus === "loading") {
      return;
    }

    setFilter((previousFilters) => ({
      ...previousFilters,
      [name]: value,
    }));

    if (setFilter === setFinanceFilters) {
      setFinancialAnalysis(null);
      setAnalysisError("");
      setAnalysisStatus("idle");
    }
  }

  function updateNewTransaction(name, value) {
    setNewTransaction((previousTransaction) => ({
      ...previousTransaction,
      [name]: value,
    }));
  }

  function validateNewTransaction() {
    const amount = Number(newTransaction.amount);

    if (!newTransaction.created_at) {
      return "Дата транзакції обов'язкова.";
    }

    if (newTransaction.created_at > currentDateTimeLocal) {
      return "Дата та час транзакції не можуть бути пізніше поточного моменту.";
    }

    if (!Number.isFinite(amount) || amount <= 0) {
      return "Сума має бути додатним числом.";
    }

    if (amount > 100000) {
      return "Сума не може бути більше 100 000 грн.";
    }

    if (!newTransaction.category.trim()) {
      return "Категорія обов'язкова.";
    }

    return "";
  }

  async function handleCreateTransaction(event) {
    event.preventDefault();

    const validationError = validateNewTransaction();
    if (validationError) {
      setEditError(validationError);
      setEditMessage("");
      return;
    }

    try {
      setEditError("");
      setEditMessage("");

      const response = await fetch(`${API_BASE_URL}/api/transactions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          ...newTransaction,
          amount: Number(newTransaction.amount),
          category: newTransaction.category.trim(),
        }),
      });

      if (!response.ok) {
        let message = "Не вдалося додати транзакцію.";
        try {
          const data = await response.json();
          if (data.detail) {
            message = Array.isArray(data.detail)
              ? data.detail.map((item) => item.msg || item.detail || String(item)).join(" ")
              : data.detail;
          }
        } catch {
          // Keep the fallback message when the API does not return JSON.
        }
        throw new Error(message);
      }

      const createdTransaction = await response.json();
      setNewTransaction(emptyNewTransaction);
      setEditFilters(emptyFilters);
      setEditMessage("Транзакцію додано.");
      await loadDashboard();
      setAddedTransactionId(createdTransaction.id);
    } catch (createError) {
      setEditError(createError.message);
    }
  }

  function handleEditTabPointerDown(event) {
    if (addedTransactionId !== null) {
      setAddedTransactionId(null);
    }

    const row = event.target.closest("[data-transaction-id]");
    setActiveTransactionId(row ? Number(row.dataset.transactionId) : null);
  }

  async function handleDeleteTransaction(transactionId) {
    const confirmed = window.confirm("Видалити цю транзакцію?");
    if (!confirmed) {
      return;
    }

    try {
      setEditError("");
      setEditMessage("");

      const response = await fetch(`${API_BASE_URL}/api/transactions/${transactionId}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Не вдалося видалити транзакцію.");
      }

      setEditMessage("Транзакцію видалено.");
      await loadDashboard();
      setActiveTransactionId(null);
    } catch (deleteError) {
      setEditError(deleteError.message);
    }
  }

  async function handleAnalyzeTransactions() {
    if (!hasExpenseTransactions) {
      return;
    }

    try {
      setAnalysisStatus("loading");
      setAnalysisError("");
      setFinancialAnalysis(null);

      const response = await fetch(`${API_BASE_URL}/api/ai/analyze-transactions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          date_from: financeFilters.dateFrom || null,
          date_to: financeFilters.dateTo || null,
          transaction_type: financeFilters.type || null,
          user: financeFilters.user || null,
        }),
      });

      if (!response.ok) {
        let message = "Не вдалося виконати аналіз фінансового стану.";
        try {
          const data = await response.json();
          if (data.detail) {
            message = data.detail;
          }
        } catch {
          // Keep the fallback message when the API does not return JSON.
        }
        throw new Error(message);
      }

      setFinancialAnalysis(await response.json());
      setAnalysisStatus("ready");
    } catch (analysisRequestError) {
      setAnalysisStatus("error");
      setAnalysisError(analysisRequestError.message);
    }
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
          <button
            className={activeTab === "finance" ? "active" : ""}
            type="button"
            onClick={() => setActiveTab("finance")}
          >
            Фінансовий стан
          </button>
          {isAdmin ? (
            <button
              className={activeTab === "edit" ? "active" : ""}
              type="button"
              onClick={() => setActiveTab("edit")}
            >
              Редагування
            </button>
          ) : null}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{activeTab === "edit" ? "Редагування" : "Фінансовий стан"}</h1>
            <p>
              {activeTab === "edit"
                ? "Додавання та видалення транзакцій"
                : "Дані станом на поточний момент"}
            </p>
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

        {activeTab === "finance" ? (
          <>
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

            <section className="panel analysis-action-panel">
              <div>
                <h2>AI-аналіз</h2>
                <p>Аналізуються транзакції відповідно до активних фільтрів.</p>
                {!hasExpenseTransactions ? (
                  <p className="analysis-requirement">
                    Для аналізу потрібна щонайменше одна витрата.
                  </p>
                ) : null}
              </div>
              <button
                className={`primary-button analysis-button ${
                  analysisStatus === "loading"
                    ? "is-loading"
                    : !hasExpenseTransactions
                      ? "is-unavailable"
                      : ""
                }`}
                disabled={analysisStatus === "loading" || !hasExpenseTransactions}
                type="button"
                onClick={handleAnalyzeTransactions}
              >
                {analysisStatus === "loading"
                  ? "⌛ Аналізуємо…"
                  : !hasExpenseTransactions
                    ? "🔒 Аналіз недоступний"
                    : "✨ Аналіз фінансового стану"}
              </button>
            </section>

            {analysisError ? <div className="notice">{analysisError}</div> : null}

            {financialAnalysis ? (
              <section className="analysis-grid" aria-label="Результати AI-аналізу">
                <AnalysisCard title="Висновок">
                  <p>{financialAnalysis.summary}</p>
                </AnalysisCard>
                <AnalysisCard title="Топ категорій витрат">
                  <AnalysisList
                    items={financialAnalysis.top_expense_categories}
                    emptyText="Витрат за вибраними фільтрами немає."
                  />
                </AnalysisCard>
                <AnalysisCard title="Ризики">
                  <AnalysisList
                    items={financialAnalysis.risks}
                    emptyText="Можливих ризиків не виявлено."
                  />
                </AnalysisCard>
                <AnalysisCard title="Поради">
                  <AnalysisList items={financialAnalysis.advice} />
                </AnalysisCard>
              </section>
            ) : null}

            <section className="content-grid">
              <article className="panel filters-panel">
                <div className="panel-header">
                  <h2>Фільтри</h2>
                  <button
                    className="ghost-button"
                    type="button"
                    disabled={analysisStatus === "loading"}
                    onClick={() => {
                      setFinanceFilters(emptyFilters);
                      setFinancialAnalysis(null);
                      setAnalysisError("");
                      setAnalysisStatus("idle");
                    }}
                  >
                    Скинути
                  </button>
                </div>
                <div className="filter-grid">
                  <label>
                    Дата з
                    <input
                      max={financeFilters.dateTo || undefined}
                      type="date"
                      value={financeFilters.dateFrom}
                      disabled={analysisStatus === "loading"}
                      onChange={(event) =>
                        updateFilter(setFinanceFilters, "dateFrom", event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Дата по
                    <input
                      min={financeFilters.dateFrom || undefined}
                      type="date"
                      value={financeFilters.dateTo}
                      disabled={analysisStatus === "loading"}
                      onChange={(event) =>
                        updateFilter(setFinanceFilters, "dateTo", event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Тип
                    <select
                      value={financeFilters.type}
                      disabled={analysisStatus === "loading"}
                      onChange={(event) =>
                        updateFilter(setFinanceFilters, "type", event.target.value)
                      }
                    >
                      <option value="">Усі типи</option>
                      <option value="income">Дохід</option>
                      <option value="expense">Витрата</option>
                    </select>
                  </label>
                  <label>
                    Користувач
                    <select
                      value={financeFilters.user}
                      disabled={analysisStatus === "loading"}
                      onChange={(event) =>
                        updateFilter(setFinanceFilters, "user", event.target.value)
                      }
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

              <TransactionsTable
                transactions={filteredFinanceTransactions}
                emptyText="Немає транзакцій за вибраними фільтрами"
              />
            </section>
          </>
        ) : null}

        {activeTab === "edit" && isAdmin ? (
          <section className="content-grid" onPointerDownCapture={handleEditTabPointerDown}>
            <article className="panel table-panel">
              <div className="panel-header">
                <h2>Transactions</h2>
                <span>{filteredEditTransactions.length} записів</span>
              </div>

              {editError ? <div className="notice">{editError}</div> : null}
              {editMessage ? <div className="notice success">{editMessage}</div> : null}

              <div className="table-wrap">
                <table className="edit-table">
                  <thead>
                    <tr>
                      <th>
                        <div className="column-filter">
                          <span>Дата</span>
                          <input
                            max={editFilters.dateTo || undefined}
                            type="date"
                            value={editFilters.dateFrom}
                            onChange={(event) =>
                              updateFilter(setEditFilters, "dateFrom", event.target.value)
                            }
                          />
                          <input
                            min={editFilters.dateFrom || undefined}
                            type="date"
                            value={editFilters.dateTo}
                            onChange={(event) =>
                              updateFilter(setEditFilters, "dateTo", event.target.value)
                            }
                          />
                        </div>
                      </th>
                      <th className="amount-cell">Сума</th>
                      <th>Категорія</th>
                      <th>
                        <div className="column-filter">
                          <span>Тип</span>
                          <select
                            value={editFilters.type}
                            onChange={(event) =>
                              updateFilter(setEditFilters, "type", event.target.value)
                            }
                          >
                            <option value="">Усі типи</option>
                            <option value="income">Дохід</option>
                            <option value="expense">Витрата</option>
                          </select>
                        </div>
                      </th>
                      <th>
                        <div className="column-filter">
                          <span>Користувач</span>
                          <select
                            value={editFilters.user}
                            onChange={(event) =>
                              updateFilter(setEditFilters, "user", event.target.value)
                            }
                          >
                            <option value="">Усі користувачі</option>
                            {userOptions.map((user) => (
                              <option key={user} value={user}>
                                {user}
                              </option>
                            ))}
                          </select>
                        </div>
                      </th>
                      <th className="actions-cell">
                        <div className="column-filter column-filter-action">
                          <span>Дія</span>
                          <button
                            className="ghost-button table-button"
                            type="button"
                            onClick={() => setEditFilters(emptyFilters)}
                          >
                            Скинути
                          </button>
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="create-row">
                      <td>
                        <input
                          max={currentDateTimeLocal}
                          type="datetime-local"
                          value={newTransaction.created_at}
                          onChange={(event) =>
                            updateNewTransaction("created_at", event.target.value)
                          }
                        />
                      </td>
                      <td>
                        <input
                          max="100000"
                          min="1"
                          step="1"
                          type="number"
                          value={newTransaction.amount}
                          onChange={(event) =>
                            updateNewTransaction("amount", event.target.value)
                          }
                        />
                      </td>
                      <td>
                        <input
                          list="category-options"
                          value={newTransaction.category}
                          onChange={(event) =>
                            updateNewTransaction("category", event.target.value)
                          }
                        />
                        <datalist id="category-options">
                          {categoryOptions.map((category) => (
                            <option key={category} value={category} />
                          ))}
                        </datalist>
                      </td>
                      <td>
                        <select
                          value={newTransaction.type}
                          onChange={(event) =>
                            updateNewTransaction("type", event.target.value)
                          }
                        >
                          <option value="income">Дохід</option>
                          <option value="expense">Витрата</option>
                        </select>
                      </td>
                      <td>
                        <span className="readonly-cell">
                          {currentUser?.username || "admin"}
                        </span>
                      </td>
                      <td className="actions-cell">
                        <button
                          className="primary-button table-button"
                          type="button"
                          onClick={handleCreateTransaction}
                        >
                          Додати
                        </button>
                      </td>
                    </tr>
                    {filteredEditTransactions.map((transaction) => (
                      <tr
                        className={[
                          transaction.id === addedTransactionId ? "added-row" : "",
                          transaction.id === activeTransactionId ? "active-row" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        key={transaction.id}
                        data-transaction-id={transaction.id}
                      >
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
                        <td className="actions-cell">
                          <button
                            className="danger-button table-button"
                            type="button"
                            onClick={() => handleDeleteTransaction(transaction.id)}
                          >
                            Видалити
                          </button>
                        </td>
                      </tr>
                    ))}
                    {!filteredEditTransactions.length ? (
                      <tr>
                        <td className="empty-row" colSpan="6">
                          Немає транзакцій за вибраними фільтрами
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </article>
          </section>
        ) : null}
      </section>
    </main>
  );
}

function AnalysisCard({ title, children }) {
  return (
    <article className="panel analysis-card">
      <h2>{title}</h2>
      <div className="analysis-content">{children}</div>
    </article>
  );
}

function AnalysisList({ items, emptyText = "Немає даних." }) {
  if (!items.length) {
    return <p>{emptyText}</p>;
  }

  return (
    <ul>
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

function TransactionsTable({ transactions, emptyText }) {
  return (
    <article className="panel table-panel">
      <div className="panel-header">
        <h2>Transactions</h2>
        <span>{transactions.length} записів</span>
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
            {transactions.map((transaction) => (
              <tr key={transaction.id}>
                <td>{formatDate(transaction.created_at)}</td>
                <td className="amount-cell">{formatCurrency(transaction.amount)}</td>
                <td>{transaction.category}</td>
                <td>
                  <span className={`tag ${transaction.type}`}>
                    {typeLabels[transaction.type] || transaction.type}
                  </span>
                </td>
                <td>{transaction.user}</td>
              </tr>
            ))}
            {!transactions.length ? (
              <tr>
                <td className="empty-row" colSpan="5">
                  {emptyText}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </article>
  );
}

export default App;
