DEFAULT_RULES = {
    "Salary":["salary","payroll"],
    "Food":["zomato","swiggy","dominos","mcdonald"],
    "Groceries":["blinkit","zepto","instamart","grofers"],
    "Rent":["rent","house rent"],
    "Electricity":["electricity","torrent power","power bill"],
    "Cash":["cash"],
    "Bank Charges":["bank charge","service charge","sms charge"],
    "Transfer":["upi","neft","rtgs","imps"],
}

def classify(particulars, rules):
    text = str(particulars).lower()
    for head, keywords in rules.items():
        if any(str(k).lower() in text for k in keywords):
            return head
    return "Uncategorized"
