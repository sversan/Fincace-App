from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
import calendar
from collections import defaultdict, Counter
import re

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "your-secret-key"  # Needed for flash messages


db = SQLAlchemy(app)

# ===== MODELE =====

class Transaction(db.Model):
     # fields
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    ttype = db.Column(db.String(20), nullable=False)  # 'income', 'expense', 'saving'
    category = db.Column(db.String(50), nullable=True)
    date = db.Column(db.Date, default=date.today)
    note = db.Column(db.String(200), nullable=True)
    payment_method = db.Column(db.String(10), nullable=False, default='cash')
    production_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    warranty_end_date = db.Column(db.Date)
    purchase_date = db.Column(db.Date, nullable=False)

    def warranty_status(self):
        expiry_date = self.purchase_date.replace(
            year = self.purchase_date.year + self.warranty_months // 12 )
        return "Valid" if date.today() <= expiry_date else "Unconsumable"
class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    period = db.Column(db.String(10))  # 'monthly' / 'annual'
    year = db.Column(db.Integer)
    month = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Float, nullable=False)

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(120), nullable=True,default="Unknown")
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

# ===== LISTA SURSELOR DE VENIT =====
ALLOWED_INCOME_SOURCES = [
    "salariu",
    "ore suplimentare",
    "voucher guvernamental",
    "chirii",
    "investiții",
    "pensii"
]


# Method might be missing
def warranty_status(self):
    if not self.purchase_date:
        return "Ordered"
    else:
        return "Purchased"
    if hasattr(self.purchase_date, "replace"):
        expiry_date = self.purchase_date.replace(year=self.purchase_date.year + 2)
    else:
        # Dacă e string, îl convertim
        purchase_date = datetime.strptime(self.purchase_date, "%Y-%m-%d").date()
        expiry_date = purchase_date.replace(year=purchase_date.year + 2)

    return "Valid" if expiry_date >= datetime.now().date() else "Expired"

# ===== FUNCȚII UTILE =====
def sum_between(start_date, end_date, ttype=None):
    q = Transaction.query.filter(Transaction.date >= start_date, Transaction.date <= end_date)
    if ttype:
        q = q.filter(Transaction.ttype == ttype)
    items = q.all()
    return sum(t.amount for t in items) if items else 0.0

# ===== RUTE =====

@app.route("/", methods=["GET", "POST"])
def index():
    today = date.today()

    monthly_budget = Budget.query.filter_by(period='monthly', year=today.year, month=today.month).first()

    last_income = Income.query.order_by(Income.date.desc()).first()
    last_income_data = {
        "sursa": last_income.source if last_income else "",
        "suma": last_income.amount if last_income else 0
    }

    incomes_year = Income.query.filter(
        Income.date >= date(today.year, 1, 1),
        Income.date <= date(today.year, 12, 31)
    ).all()

    incomes_summary = defaultdict(float)
    for inc in incomes_year:
        incomes_summary[inc.source] += inc.amount

    total_income = sum(incomes_summary.values())

    # Toate tranzacțiile
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()

    # Calcule zile, luni, ani pentru venituri, cheltuieli, economii
    daily_income = sum_between(today, today, 'income')
    daily_expense = sum_between(today, today, 'expense')
    daily_saving = sum_between(today, today, 'saving')

    month_start = date(today.year, today.month, 1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = date(today.year, today.month, last_day)

    monthly_income = sum_between(month_start, month_end, 'income')
    monthly_expense = sum_between(month_start, month_end, 'expense')
    monthly_saving = sum_between(month_start, month_end, 'saving')

    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)

    annual_income = sum_between(year_start, year_end, 'income')
    annual_expense = sum_between(year_start, year_end, 'expense')
    annual_saving = sum_between(year_start, year_end, 'saving')

 # Date pentru grafic (categorii + sume cheltuieli luna curenta)
    cats = defaultdict(float)
    expenses = Transaction.query.filter(
        Transaction.date >= month_start,
        Transaction.date <= month_end,
        Transaction.ttype == 'expense'
    ).all()

    for e in expenses:
        cats[e.category or 'Altele'] += e.amount

    labels = list(cats.keys())
    values = list(cats.values())

    # Mapare note la categorii produse
    product_map = {
        'apa': 'Drinks',
        'sparkling water': 'Drinks',
        'water sparkling': 'Drinks',
        'oua': 'Alimente',
        'paine': 'Alimente',
        'mezeluri': 'Carne',
        'suc': 'Drinks',
        'ananas': 'Alimente'
    }

    normalized_notes = []

    for t in transactions:
        if t.note:
            note_clean = t.note.lower().strip()
            note_clean = re.sub(r'\d+', '', note_clean)  # elimină cifre
            note_clean = note_clean.replace('buc', '').strip()  # elimină 'buc'

            mapped_product = None
            for key in product_map.keys():
                if key in note_clean:
                    mapped_product = key
                    break

            if mapped_product:
                normalized_notes.append((mapped_product, product_map[mapped_product]))

    counter = Counter(normalized_notes)
    frequent_products = [(prod, cat, cnt) for (prod, cat), cnt in counter.items() if cnt > 2]

    products_by_category = defaultdict(list)
    for prod, cat, cnt in frequent_products:
        products_by_category[cat].append((prod, cnt))

    return render_template('index.html',
                           today=today,
                           daily_income=daily_income,
                           daily_expense=daily_expense,
                           daily_saving=daily_saving,
                           monthly_income=monthly_income,
                           monthly_expense=monthly_expense,
                           monthly_saving=monthly_saving,
                           annual_income=annual_income,
                           annual_expense=annual_expense,
                           annual_saving=annual_saving,
                           monthly_budget=monthly_budget,
                           transactions=transactions,
                           products_by_category=products_by_category,
                           chart_labels=labels,
                           chart_values=values,
                           incomes_summary=incomes_summary,
                           total_income=total_income,
                           last_income_data=last_income_data
                           )

@app.route('/add', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        ttype = request.form['ttype']  # 'income' / 'expense' / 'saving'
        category = request.form.get('category')
        date_str = request.form.get('date')
        payment_method = request.form.get('payment_method', 'cash')  # Fix: include payment_method!
        if date_str:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date_obj = date.today()
        note = request.form.get('note')

        # Pass payment_method when creating Transaction!
        t = Transaction(amount=amount, ttype=ttype, category=category, date=date_obj, note=note, payment_method=payment_method)

        db.session.add(t)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add.html')
@app.route('/transactions')
def transactions():
    items = Transaction.query.order_by(Transaction.date.desc()).limit(200).all()
    notes = [t.note.lower() for t in items if t.note]
    counts = Counter(notes)
    frequent_items = [prod for prod, cnt in counts.items() if cnt >= 3]

    keywords = {
        'apa': 'drinks',
        'paine': 'alimente',
        'mezeluri': 'carne',
        'suc': 'drinks',
        'oua': 'alimente',
        'ananas': 'alimente'
    }

    grouped = {'drinks': [], 'alimente': [], 'carne': []}
    for prod in frequent_items:
        category = keywords.get(prod)
        if category:
            grouped[category].append(prod)

    categories = [t.category.lower() for t in items if t.category]
    counts_cat = Counter(categories)
    top_alimente = [cat for cat, count in counts_cat.most_common(5) if count >= 3]
    transactions_list = Transaction.query.all()

    return render_template('transactions.html',
                           transactions=transactions_list,
                           top_alimente=top_alimente,
                           grouped_alimente=grouped)

@app.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
    if request.method == 'POST':
        period = request.form['period']  # monthly/annual
        amount = float(request.form['amount'])
        year = int(request.form.get('year', date.today().year))
        month = int(request.form.get('month') or 0) or None
        # simplu: ștergem buget existent pentru acea perioadă (exemplu)
        if period == 'monthly':
            # eliminăm buget existent pentru luna respectivă
            Budget.query.filter_by(period='monthly', year=year, month=month).delete()
            b = Budget(period='monthly', year=year, month=month, amount=amount)
        else:
            Budget.query.filter_by(period='annual', year=year).delete()
            b = Budget(period='annual', year=year, month=None, amount=amount)
        db.session.add(b)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('set_budget.html')

@app.route('/sursa_venit', methods=['GET', 'POST'])
def sursa_venit():
    if request.method == 'POST':
        data_str = request.form.get('date')
        suma = request.form.get('amount')
        produs = request.form.get('product')

        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
        suma = float(suma) if suma else 0.0
        # Salvează în baza de date
        new_income = Income(source=produs, amount=suma, date=data_obj)
        db.session.add(new_income)
        db.session.commit()
        print(f"Data: {data_obj}, Suma: {suma}, Produs: {produs}")
        return redirect(url_for('index'))

    return render_template('sursa_venit.html')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

