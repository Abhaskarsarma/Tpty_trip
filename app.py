from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import uuid

app = Flask(__name__)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name('tpty-trip-a6a49355e844.json', scope)
client = gspread.authorize(creds)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1b6yiBWLchqAd5dvnIxenEDT-_vfcFAZzc3mXdShX5Yw/edit")
members_sheet = sheet.worksheet("Members")
expenses_sheet = sheet.worksheet("Expenses")
balances_sheet = sheet.worksheet("Balances")

@app.route('/get_members', methods=['GET'])
def get_members_list():
    members = get_members()
    return jsonify([{'id': pid, 'name': data['name']} for pid, data in members.items()])

def calculate_balances():
    members = get_members()
    expenses = expenses_sheet.get_all_records()

    paid = {pid: 0 for pid in members}
    owed = {pid: 0 for pid in members}
    total_shares = sum(m['shares'] for m in members.values())

    for row in expenses:
        amount = float(row['Amount'])
        payer = row['Payer ID']
        share_per_unit = amount / total_shares

        for pid in members:
            owed[pid] += share_per_unit * members[pid]['shares']
        paid[payer] += amount

    # Update balances sheet
    balances_sheet.clear()
    balances_sheet.append_row(['Person ID', 'Name', 'Paid', 'Share Owed', 'Net Balance'])
    for pid in members:
        net = round(paid[pid] - owed[pid], 2)
        balances_sheet.append_row([
            pid,
            members[pid]['name'],
            round(paid[pid], 2),
            round(owed[pid], 2),
            net
        ])

    return {pid: round(paid[pid] - owed[pid], 2) for pid in members}

@app.route('/add_expense', methods=['POST'])
def add_expense():
    data = request.get_json()
    payer = data['payer_id']
    amount = float(data['amount'])
    description = data.get('description', '')
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    expense_id = f"E-{uuid.uuid4().hex[:6].upper()}"

    expenses_sheet.append_row([expense_id, date, payer, amount, description])
    balances = calculate_balances()
    return jsonify({"message": "Expense added and balances updated.", "balances": balances})

@app.route('/get_balances', methods=['GET'])
def get_balances():
    calculate_balances()
    rows = balances_sheet.get_all_records()
    return jsonify(rows)

if __name__ == '__main__':
    app.run(debug=True)
