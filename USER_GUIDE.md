# Budgy by Kay – User Guide

Welcome to your budgeting bot on Telegram: **@Budgy_by_kay_bot**. This guide shows new users how to start, log expenses, view reports, and manage budgets.

## 1) Start the bot
- Open Telegram, search for **@Budgy_by_kay_bot**, tap **Start**, or send `/start`.
- The bot walks you through a quick onboarding: you'll set your monthly income and budgets for each spending category. After that you'll see the main menu.

## 2) Add expenses
- Quick text: type an expense in one line:
  ```
  groceries 45.50 weekly shopping
  dining 28.00 ramen
  uber 12 ride home
  ```
- With a receipt: send a photo and put the expense in the caption:
  ```
  dining 28.00 ramen
  ```
- Via the menu: tap **Add Expense**, pick a category, enter the amount, and optionally add a note.
- The bot auto-detects the category from text input. If a merchant is unknown, you'll get a prompt to pick the right category — just tap one of the suggestions.

## 3) Use the menu (`/menu`)
- **Add Expense** – pick a category, enter amount, add an optional note.
- **Add Income** – choose a source (Salary, Freelance, etc.) and enter the amount.
- **Reports** – Today / Week / Month summaries with charts.
- **Budget Plan** – set monthly budgets per category, set projected income, or copy last month's plan.
- **Recent Transactions** – view your last 10 entries.
- **Export CSV** – download all transactions as a spreadsheet.
- **Delete** – remove the last entry, last 5/10 entries, or clear expenses/income/budgets.
- **Settings** – toggle the daily expense summary report on or off.

## 4) Handy commands
- `/start` – welcome + onboarding (or menu if already set up)
- `/menu` – open the main menu
- `/today`, `/week`, `/month` – summaries with charts
- `/budget` – view or set budgets
- `/income` – add income
- `/recent` – show last 10 transactions
- `/delete_last` – remove the most recent entry
- `/export` – download CSV of all transactions
- `/settings` – toggle daily reports
- `/help` – full list of commands

## 5) Tips
- Amounts must be positive; notes are optional.
- If the menu disappears, send `/start` or `/menu` to bring it back.
- You can re-send `/start` at any time to reset the conversation flow.

## 6) Automatic logging from Apple Pay / Wallet (iPhone)

You can have expenses logged automatically every time you tap your card or Apple Pay. This works by creating an Apple Shortcut that fires when your bank app sends a payment notification.

### What you need
- Your Budgy webhook URL (provided by the bot admin):
  ```
  https://<your-cloud-run-url>/webhook/apple_pay
  ```
- An iPhone with the **Shortcuts** app.
- A bank or wallet app that sends push notifications for transactions (most do).

### Step 1 — Create the Shortcut

1. Open the **Shortcuts** app on your iPhone.
2. Tap **+** to create a new shortcut. Name it **"Send to Budgy"**.
3. Add a **Get Contents of URL** action and configure it:
   - **URL**: your Budgy webhook URL from above
   - **Method**: POST
   - **Headers**: `Content-Type` = `application/json`
   - **Request Body** (JSON):
     | Key | Value |
     |-----|-------|
     | `merchant` | The merchant/store name (from the notification text, or typed manually) |
     | `amount` | The transaction amount as a number |
     | `card_name` | The card used, e.g. "Apple Card" or "Visa" |
     | `date` | The transaction date in ISO format, e.g. `2025-06-15T14:30:00` |

   A minimal example request body:
   ```json
   {
     "merchant": "Starbucks",
     "amount": 5.75,
     "card_name": "Visa",
     "date": "2025-06-15T14:30:00"
   }
   ```
4. Save the shortcut.

### Step 2 — Create a Personal Automation

1. In the Shortcuts app, go to **Automation** → tap **+**.
2. Choose **Personal Automation** → **Notification**.
3. Pick your bank or Wallet app. Select "When I receive a notification containing..." and optionally filter by keywords like "purchase" or "payment".
4. Add the action: **Run Shortcut** → choose **"Send to Budgy"**.
5. Turn off **Ask Before Running** so it fires silently.
6. Save.

### Step 3 — Test it

Make a small purchase (or send a test notification). When the bank notification arrives, the Shortcut runs and sends the transaction to Budgy. The bot categorizes the merchant automatically using its built-in map and Gemini AI fallback. Check `/recent` in the bot to confirm.

### Troubleshooting
- **Notification automation not available?** Some bank apps restrict this. You can still run the "Send to Budgy" shortcut manually after a purchase.
- **Wrong category?** The bot uses Gemini AI to categorize unknown merchants automatically. If Gemini can't figure it out either, you'll get a Telegram prompt to pick the category manually. Either way, the bot remembers your choice for next time.
- **Missing fields?** Only `merchant` and `amount` are required. `card_name` defaults to "Apple Pay" and `date` defaults to now if omitted.
