# Database

## Схема фінансового бота

Цей документ описує першу модель бази даних для фінансових функцій у Telegram-боті.

На цьому етапі база даних ще не підключається до backend. Мета - лише змоделювати таблиці та візуалізувати зв'язки між ними на https://dbdiagram.io.

## Таблиці

- `users` - користувачі бота.
- `categories` - фінансові категорії, які належать користувачам.
- `transactions` - записи про доходи або витрати, які належать користувачам і категоріям.

## Зв'язки

- Один `user` може мати багато `categories`.
- Один `user` може мати багато `transactions`.
- Одна `category` може мати багато `transactions`.
- Кожна `transaction` належить одному `user` і одній `category`.

## DBML для dbdiagram.io

Скопіюй цей код і встав його на https://dbdiagram.io:

```dbml
Table users {
  id integer [primary key, increment]
  telegram_id bigint [not null, unique]
  username varchar
  first_name varchar
  created_at timestamp [not null]
}

Table categories {
  id integer [primary key, increment]
  user_id integer [not null]
  name varchar [not null]
  created_at timestamp [not null]
}

Table transactions {
  id integer [primary key, increment]
  user_id integer [not null]
  category_id integer [not null]
  amount decimal(12,2) [not null]
  created_at timestamp [not null]
}

Ref: users.id < categories.user_id
Ref: users.id < transactions.user_id
Ref: categories.id < transactions.category_id
```
