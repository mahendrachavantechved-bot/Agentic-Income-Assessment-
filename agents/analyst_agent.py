import pandas as pd

def calculate_kpis(bank_data):
    """RBI-mandated credit underwriting KPIs"""
    df = bank_data['raw_transactions']
   
    # 1. Income Stability (last 6 months)
    recent = df[df['date'] >= (df['date'].max() - pd.DateOffset(months=6))]
    monthly_income = recent[recent['credit'] > 5000].groupby('month')['credit'].sum()
   
    kpis = {
        'avg_monthly_income': monthly_income.mean(),
        'income_stability': monthly_income.std() / monthly_income.mean(), # CV < 0.3 = stable
        'amb': df['balance'].mean(), # Average Monthly Balance
        'peak_monthly_income': monthly_income.max(),
        'emi_obligations': detect_emis(df),
        'business_income_ratio': calculate_business_ratio(df)
    }
   
    # FOIR Calculation (RBI max 50%)
    proposed_emi = kpis['avg_monthly_income'] * 0.40 # Conservative 40% DSR
    kpis['foir'] = (kpis['emi_obligations'] + proposed_emi) / kpis['avg_monthly_income']
   
    return kpis

def detect_emis(df):
    """Identify loan EMIs from recurring debits"""
    monthly_debits = df.groupby(['month', 'description'])['debit'].sum()
    recurring = monthly_debits[monthly_debits > 1000].groupby('description').count()
    return recurring[recurring >= 2].sum() # Appears 2+ months

def calculate_business_ratio(df):
    """Business vs Salary credits (NBFC requirement: >60%)"""
    business_keywords = ['BUSINESS', 'SALES', 'GST', 'INVOICE']
    salary_keywords = ['SALARY', 'PAYROLL']
   
    business_credits = df[df['description'].str.contains('|'.join(business_keywords), na=False, case=False)]['credit'].sum()
    salary_credits = df[df['description'].str.contains('|'.join(salary_keywords), na=False, case=False)]['credit'].sum()
   
    total = business_credits + salary_credits
    return business_credits / total if total > 0 else 0
