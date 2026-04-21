import os
import json
import re
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# -------------------------------
# Telegram Bot Token
# -------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

# -------------------------------
# Google Sheets Setup
# -------------------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials safely from environment
creds_json = os.getenv("GOOGLE_CREDS")

print("Checking GOOGLE_CREDS...")

if creds_json:
    print(creds_json[:50])
else:
    print("GOOGLE_CREDS is None ❌")

if not creds_json:
    raise ValueError("GOOGLE_CREDS not found in environment variables")

creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)

client = gspread.authorize(creds)

# -------------------------------
# Smart Logic Function
# -------------------------------
def process_expense(text):
    text = text.lower()

    # Amount extraction
    amount_match = re.search(r'\d+', text)
    amount = amount_match.group() if amount_match else "0"

    # Category detection
    categories = {

    "Food": [
        "food", "biryani", "lunch", "dinner", "snacks", "breakfast",
        "tea", "coffee", "juice", "hotel", "restaurant",
        "swiggy", "zomato"
    ],

    "Groceries": [
        "grocery", "groceries", "vegetables", "vegetable",
        "fruits", "fruit", "milk", "bread", "eggs",
        "rice", "dal", "oil", "sugar", "salt",
        "almonds", "cashew", "dry fruits", "dry fruit"
    ],

    "Shopping": [
        "shopping", "amazon", "flipkart", "clothes",
        "shirt", "pant", "dress", "shoes", "mall"
    ],

    "Travel": [
        "uber", "ola", "rapido", "bus", "train", "metro",
        "petrol", "fuel", "diesel", "auto", "cab"
    ],

    "Health": [
        "doctor", "medicine", "hospital", "pharmacy",
        "tablet", "checkup", "clinic"
    ],

    "Entertainment": [
        "movie", "netflix", "ott", "game", "gaming",
        "music", "concert"
    ]
}

    category = "General"
    for key, words in categories.items():
        if any(word in text for word in words):
            category = key
            break

    # Date detection
    if "yesterday" in text:
        date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        date = datetime.today().strftime('%Y-%m-%d')

    return date, amount, category, text

# -------------------------------
# Summary Functions
# -------------------------------
def generate_monthly_pdf(sheet, file_name="report.pdf"):
    records = sheet.get_all_records()
    current_month = datetime.today().strftime('%Y-%m')

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(file_name)

    elements = []

    # Title
    elements.append(Paragraph("Monthly Expense Report", styles['Title']))
    elements.append(Spacer(1, 10))

    total = 0
    category_totals = {}

    for row in records:
        date = row.get("Date", "")
        amount = int(row.get("Amount", 0))
        category = row.get("Category", "General")

        if current_month in date:
            total += amount

            if category in category_totals:
                category_totals[category] += amount
            else:
                category_totals[category] = amount

            elements.append(Paragraph(f"{date} - ₹{amount} - {category}", styles['Normal']))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Total: ₹{total}", styles['Heading2']))
    elements.append(Spacer(1, 10))

    # Category breakdown
    elements.append(Paragraph("Category Breakdown:", styles['Heading3']))
    for cat, amt in category_totals.items():
        elements.append(Paragraph(f"{cat}: ₹{amt}", styles['Normal']))

    doc.build(elements)

    return file_name
def get_today_summary(sheet):
    records = sheet.get_all_records()
    today = datetime.today().strftime('%Y-%m-%d')
    total = 0

    for row in records:
        if row.get("Date") == today:
            total += int(row.get("Amount", 0))

    return total


def get_monthly_summary(sheet):
    records = sheet.get_all_records()
    current_month = datetime.today().strftime('%Y-%m')
    total = 0

    for row in records:
        if current_month in row.get("Date", ""):
            total += int(row.get("Amount", 0))

    return total
def get_category_breakdown(sheet):
    records = sheet.get_all_records()
    current_month = datetime.today().strftime('%Y-%m')

    category_totals = {}

    for row in records:
        date = row.get("Date", "")
        category = row.get("Category", "General")
        amount = int(row.get("Amount", 0))

        if current_month in date:
            if category in category_totals:
                category_totals[category] += amount
            else:
                category_totals[category] = amount

    return category_totals
def get_user_sheet(user_name):
    spreadsheet = client.open("Expense Tracker")

    try:
        # Try to open existing sheet
        sheet = spreadsheet.worksheet(user_name)
    except:
        # If not exists → create new sheet
        sheet = spreadsheet.add_worksheet(title=user_name, rows="1000", cols="4")

        # Add header row
        sheet.append_row(["Date", "Amount", "Category", "Note"])

    return sheet
def delete_last_entry(sheet):
    all_values = sheet.get_all_values()
    row_count = len(all_values)

    # Keep header safe
    if row_count <= 1:
        return False

    sheet.delete_rows(row_count)
    return True
# -------------------------------
# Handle Telegram Message
# -------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.lower()

    user = update.message.from_user
    user_id = str(user.id)
    user_name = user.first_name

    #print(user_name)
    
    # Open sheet
    sheet_name = f"{user_name}_{user_id}"
    sheet = get_user_sheet(sheet_name)

    # -------------------------------
    # Commands
    # -------------------------------

    # TODAY
    if user_text == "today":
        total = get_today_summary(sheet)
        await update.message.reply_text(f"📊 Today’s spending: ₹{total}")
        return

    # MONTHLY
    if user_text == "summary":
        total = get_monthly_summary(sheet)
        await update.message.reply_text(f"💰 This month: ₹{total}")
        return
    # CATEGORY BREAKDOWN
    if user_text == "breakdown":
        data = get_category_breakdown(sheet)

        if not data:
            await update.message.reply_text("No expenses found for this month.")
            return

        message = "📊 Category Breakdown:\n"
        for cat, amt in data.items():
            message += f"{cat}: ₹{amt}\n"

        await update.message.reply_text(message)
        return
    # UNDO LAST ENTRY
    if user_text == "undo":
        success = delete_last_entry(sheet)

        if success:
            await update.message.reply_text("↩️ Last entry deleted")
        else:
            await update.message.reply_text("No data to delete")

        return
    # PDF REPORT
    if user_text == "report":
        file_path = generate_monthly_pdf(sheet)

        await update.message.reply_document(
            document=open(file_path, "rb")
        )
        return   
    # -------------------------------
    # Expense entry
    # -------------------------------
    date, amount, category, note = process_expense(user_text)

    # ❌ Block invalid inputs
    if amount == "0":
        await update.message.reply_text(
            "❌ Please enter valid expense (e.g., 'Spent 250 on food')"
        )
        return

    # Save to sheet
    sheet.append_row([date, amount, category, note])

    await update.message.reply_text(
        f"✅ Added: {amount} | {category} | {date}"
    )

# -------------------------------
# Main Function
# -------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")

    app.run_polling()

if __name__ == "__main__":
    main()
