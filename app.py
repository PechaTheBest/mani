from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
import sqlite3

app = Flask(__name__)

# Инициализация базы данных
def get_db_connection():
    conn = sqlite3.connect('budget.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT,
                  income REAL,
                  expense REAL,
                  category TEXT)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS settings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  value REAL)''')
    
    savings_goal = conn.execute('SELECT value FROM settings WHERE name = "savings_goal"').fetchone()
    if savings_goal is None:
        conn.execute('INSERT INTO settings (name, value) VALUES (?, ?)', ('savings_goal', 10000))
    
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    conn = get_db_connection()
    transactions = conn.execute('SELECT * FROM transactions ORDER BY date DESC').fetchall()
    
    savings_goal_row = conn.execute('SELECT value FROM settings WHERE name = "savings_goal"').fetchone()
    savings_goal = savings_goal_row['value'] if savings_goal_row else 10000
    
    conn.close()
    
    # Рассчитываем общий доход и расход (включая операции с накоплениями)
    total_income = sum(t['income'] for t in transactions)
    total_expense = sum(t['expense'] for t in transactions)
    
    # Рассчитываем текущий баланс (доступные средства)
    # Все доходы минус все расходы (включая переводы в накопления)
    balance = total_income - total_expense
    
    # Рассчитываем сумму накоплений
    savings_deposits = sum(t['expense'] for t in transactions if t['category'] == 'savings')
    savings_withdrawals = sum(t['income'] for t in transactions if t['category'] == 'savings')
    savings_amount = savings_deposits - savings_withdrawals
    
    # Расчет процента накоплений от цели
    savings_percentage = min(100, (savings_amount / savings_goal) * 100) if savings_goal > 0 else 0
    
    categories = ['Продукты', 'Кафе', 'Аптека', 'Питомцы', 'Транспорт', 
                 'Путешествия', 'Онлайн-покупки', 'Развлечения', 'ЖКУ', 'Накопления', 'Прочие']
    amounts = [0] * len(categories)
    category_mapping = {
        'products': 0,
        'food_restaurants': 1,
        'pharmacy': 2,
        'pets': 3,
        'transport': 4,
        'travel': 5,
        'marketplace': 6,
        'leisure': 7,
        'utilities': 8,
        'savings': 9,
        'other': 10
    }
    
    # Заполняем суммы расходов по категориям (включая накопления)
    for t in transactions:
        if t['category'] in category_mapping and t['expense'] > 0:
            amounts[category_mapping[t['category']]] += t['expense']
    
    return render_template('index.html',
                         transactions=transactions,
                         total_income=total_income,
                         total_expense=total_expense,
                         balance=balance,
                         categories=categories,
                         amounts=amounts,
                         savings_amount=savings_amount,
                         savings_goal=savings_goal,
                         savings_percentage=savings_percentage)

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    income = float(request.form['income']) if request.form['income'] else 0.0
    expense = float(request.form['expense']) if request.form['expense'] else 0.0
    category = request.form['category']
    
    conn = get_db_connection()
    
    if category == 'savings':
        if income > 0:
            # Снятие с накоплений - доход с категорией 'savings'
            conn.execute("INSERT INTO transactions (date, income, expense, category) VALUES (?, ?, ?, ?)",
                        (datetime.now().strftime('%Y-%m-%d %H:%M'), income, 0, 'savings'))
        elif expense > 0:
            # Пополнение накоплений - расход с категорией 'savings'
            conn.execute("INSERT INTO transactions (date, income, expense, category) VALUES (?, ?, ?, ?)",
                        (datetime.now().strftime('%Y-%m-%d %H:%M'), 0, expense, 'savings'))
    else:
        # Обычные транзакции
        if income > 0:
            conn.execute("INSERT INTO transactions (date, income, expense, category) VALUES (?, ?, ?, ?)",
                        (datetime.now().strftime('%Y-%m-%d %H:%M'), income, 0, category))
        if expense > 0:
            conn.execute("INSERT INTO transactions (date, income, expense, category) VALUES (?, ?, ?, ?)",
                        (datetime.now().strftime('%Y-%m-%d %H:%M'), 0, expense, category))
    
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

# Остальные функции остаются без изменений
@app.route('/edit_transaction/<int:id>', methods=['GET', 'POST'])
def edit_transaction(id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        income = float(request.form['income']) if request.form['income'] else 0.0
        expense = float(request.form['expense']) if request.form['expense'] else 0.0
        category = request.form['category']
        
        conn.execute("UPDATE transactions SET income = ?, expense = ?, category = ? WHERE id = ?",
                    (income, expense, category, id))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    
    transaction = conn.execute('SELECT * FROM transactions WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if transaction is None:
        return redirect(url_for('home'))
    
    return render_template('edit.html', transaction=transaction)

@app.route('/delete_transaction/<int:id>')
def delete_transaction(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM transactions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/add_savings', methods=['POST'])
def add_savings():
    amount = float(request.form['amount'])
    operation_type = request.form.get('operation_type', 'income')
    
    conn = get_db_connection()
    
    if operation_type == 'income':
        conn.execute("INSERT INTO transactions (date, income, expense, category) VALUES (?, ?, ?, ?)",
                   (datetime.now().strftime('%Y-%m-%d %H:%M'), amount, 0, 'savings'))
    else:
        conn.execute("INSERT INTO transactions (date, income, expense, category) VALUES (?, ?, ?, ?)",
                   (datetime.now().strftime('%Y-%m-%d %H:%M'), 0, amount, 'savings'))
    
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/update_savings_goal', methods=['POST'])
def update_savings_goal():
    new_goal = float(request.form['goal'])
    
    conn = get_db_connection()
    conn.execute('UPDATE settings SET value = ? WHERE name = "savings_goal"', (new_goal,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)