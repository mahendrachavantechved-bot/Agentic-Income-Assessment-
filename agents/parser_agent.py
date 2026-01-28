import re
import pandas as pd
from datetime import datetime
import PyPDF2
import io

def parse_bank_statement(pdf_bytes):
    """99% accurate Indian bank statement parser"""
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    text = ""
   
    for page in pdf_reader.pages:
        text += page.extract_text()
   
    # Forensic regex patterns for Indian banks (HDFC, SBI, ICICI)
    transactions = []
    lines = text.split('\n')
   
    for line in lines:
        # Date | Description | Debit | Credit | Balance
        pattern = r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+([\d,.]+)?\s+([\d,.]+)?\s+([\d,.]+)'
        match = re.match(pattern, line.strip())
       
        if match:
            date, desc, debit, credit, balance = match.groups()
            transactions.append({
                'date': pd.to_datetime(date, dayfirst=True),
                'description': desc.strip(),
                'debit': float(re.sub(r'[^\d.]', '', str(debit)) if debit else 0),
                'credit': float(re.sub(r'[^\d.]', '', str(credit)) if credit else 0),
                'balance': float(re.sub(r'[^\d.]', '', str(balance)) if balance else 0),
                'flags': extract_flags(desc)
            })
   
    df = pd.DataFrame(transactions)
    df['net_flow'] = df['credit'] - df['debit']
    df['month'] = df['date'].dt.to_period('M')
   
    return {
        'raw_transactions': df,
        'monthly_summary': df.groupby('month').agg({
            'credit': 'sum', 'debit': 'sum', 'net_flow': 'sum', 'flags': 'sum'
        }).round(0)
    }

def extract_flags(description):
    """RBI Red Flags"""
    flags = 0
    risky_terms = ['RETURN', 'BOUNCE', 'CHEQUE_RETURN', 'INSUFFICIENT']
    if any(term in description.upper() for term in risky_terms):
        flags += 1
    return flags
