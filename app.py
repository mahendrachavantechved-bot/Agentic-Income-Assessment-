pip install streamlit pandas pypdf
streamlit run app.py
import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
from pypdf import PdfReader

st.set_page_config(page_title="GROK Income Validator - Single File", layout="wide")
st.title("🤖 GROK - Rule-based Credit Assessment (Single File Version)")
st.markdown("Upload Bank Statement (PDF) + GST CSV → Get RBI-style Credit Assessment Memo")
st.info("No LLM used – pure rule-based logic. Uses pypdf instead of PyPDF2.")

# ────────────────────────────────────────────────
# Helper Functions (all agents in one file)
# ────────────────────────────────────────────────

def parse_bank_statement(pdf_bytes):
    """Extract transactions from Indian bank PDF (rule-based regex)"""
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"

        # Debug: show first part of extracted text
        if len(text.strip()) < 100:
            st.warning("PDF text extraction returned almost nothing. Possibly scanned/image PDF?")
        
        transactions = []
        lines = text.splitlines()

        for line in lines:
            line = line.strip()
            if not line or len(line) < 15:
                continue

            # Flexible date match (DD/MM/YY or DD-MM-YYYY etc.)
            date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', line)
            if not date_match:
                continue

            date_str = date_match.group(1)
            rest = line[date_match.end():].strip()

            # Split on multiple spaces / tabs
            parts = re.split(r'\s{2,}|\t+', rest)

            if len(parts) < 3:
                continue

            # Description is everything except last 2-3 parts (debit/credit/balance)
            desc = " ".join(parts[:-3]).strip() if len(parts) > 4 else parts[0].strip()
            potential_numbers = parts[-3:]

            # Clean number function
            def clean_num(s):
                if not s:
                    return 0.0
                s = re.sub(r'[^\d.]', '', s.strip())
                try:
                    return float(s)
                except:
                    return 0.0

            # Heuristic: last is usually balance, before that credit or debit
            balance = clean_num(potential_numbers[-1])
            credit = clean_num(potential_numbers[-2]) if len(potential_numbers) >= 2 else 0.0
            debit  = clean_num(potential_numbers[-3]) if len(potential_numbers) >= 3 else 0.0

            # If debit and credit both zero → maybe wrong split
            if debit == 0 and credit == 0 and balance > 0:
                continue

            try:
                trans_date = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
                if pd.isna(trans_date):
                    continue
            except:
                continue

            transactions.append({
                'date': trans_date,
                'description': desc,
                'debit': debit,
                'credit': credit,
                'balance': balance,
                'flags': extract_flags(desc)
            })

        if not transactions:
            st.warning("No transactions were parsed. PDF format may not match expected pattern.")
            return {'raw_transactions': pd.DataFrame(), 'monthly_summary': pd.DataFrame()}

        df = pd.DataFrame(transactions)

        # Ensure numeric columns
        for col in ['debit', 'credit', 'balance']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['net_flow'] = df['credit'] - df['debit']
        df['month'] = df['date'].dt.to_period('M')

        return {
            'raw_transactions': df,
            'monthly_summary': df.groupby('month').agg({
                'credit': 'sum', 'debit': 'sum', 'net_flow': 'sum', 'flags': 'sum'
            }).round(0)
        }

    except Exception as e:
        st.error(f"PDF parsing failed: {str(e)}")
        return {'raw_transactions': pd.DataFrame(), 'monthly_summary': pd.DataFrame()}


def extract_flags(description):
    risky_terms = ['RETURN', 'BOUNCE', 'CHEQUE_RETURN', 'INSUFFICIENT', 'BOUNCED', 'DISHONOURED']
    return 1 if any(term in description.upper() for term in risky_terms) else 0


def calculate_kpis(bank_data):
    df = bank_data['raw_transactions']
    if df.empty:
        return {
            'avg_monthly_income': 0.0,
            'income_stability': 0.0,
            'amb': 0.0,
            'peak_monthly_income': 0.0,
            'emi_obligations': 0,
            'business_income_ratio': 0.0,
            'foir': 0.0
        }

    # Last 6 months income
    if 'date' in df.columns and not df['date'].empty:
        recent = df[df['date'] >= (df['date'].max() - pd.DateOffset(months=6))]
        monthly_income = recent[recent['credit'] > 5000].groupby('month')['credit'].sum()
    else:
        monthly_income = pd.Series()

    avg_income = monthly_income.mean() if not monthly_income.empty else 0.0

    kpis = {
        'avg_monthly_income': avg_income,
        'income_stability': (monthly_income.std() / avg_income) if avg_income > 0 else 0.0,
        'amb': df['balance'].mean() if 'balance' in df else 0.0,
        'peak_monthly_income': monthly_income.max() if not monthly_income.empty else 0.0,
        'emi_obligations': detect_emis(df),
        'business_income_ratio': calculate_business_ratio(df)
    }

    proposed_emi = avg_income * 0.40
    kpis['foir'] = (kpis['emi_obligations'] + proposed_emi) / avg_income if avg_income > 0 else 0.0

    return kpis


def detect_emis(df):
    if df.empty:
        return 0
    monthly_debits = df.groupby(['month', 'description'])['debit'].sum()
    recurring = monthly_debits[monthly_debits > 1000].groupby('description').count()
    return recurring[recurring >= 2].sum()


def calculate_business_ratio(df):
    if df.empty:
        return 0.0
    business_keywords = r'BUSINESS|SALES|GST|INVOICE|COLLECTION|CUSTOMER|DEPOSIT'
    salary_keywords   = r'SALARY|PAYROLL|SAL|WAGE|CREDIT SAL'
    business_credits = df[df['description'].str.contains(business_keywords, na=False, case=False, regex=True)]['credit'].sum()
    salary_credits   = df[df['description'].str.contains(salary_keywords, na=False, case=False, regex=True)]['credit'].sum()
    total = business_credits + salary_credits
    return business_credits / total if total > 0 else 0.0


def audit_and_recommend(bank_data, gst_data, kpis):
    if 'raw_transactions' not in bank_data or bank_data['raw_transactions'].empty:
        return {
            "flags": {"no_data": True},
            "npa_risk": 1.0,
            "recommendation": "❌ NO-GO - No valid bank data parsed",
            "gst_variance_pct": 0.0
        }

    bank_turnover = kpis['avg_monthly_income'] * 12
    gst_turnover = gst_data.get('taxable_value', pd.Series()).sum() if 'taxable_value' in gst_data else 0

    gst_variance = abs(bank_turnover - gst_turnover) / max(bank_turnover, 1)

    bounce_count = bank_data['raw_transactions']['flags'].sum()

    flags = {
        'gst_underreporting': gst_variance > 0.20,
        'bounce_count': bounce_count,
        'foir_excess': max(0, kpis['foir'] - 0.50),
        'income_instability': kpis['income_stability'] > 0.30
    }

    npa_score = (
        flags['gst_underreporting'] * 0.40 +
        (bounce_count / 10) * 0.30 +
        flags['foir_excess'] * 0.20 +
        flags['income_instability'] * 0.10
    )

    if npa_score < 0.20:
        rec = "✅ GO - Low Risk"
    elif npa_score < 0.40:
        rec = "⚠️ CONDITIONAL - Medium Risk"
    else:
        rec = "❌ NO-GO - High NPA Risk"

    return {
        "flags": flags,
        "npa_risk": round(npa_score, 3),
        "recommendation": rec,
        "gst_variance_pct": round(gst_variance * 100, 1)
    }


def generate_cam(kpis, verdict, bank_data, gst_data):
    cam = "# Credit Assessment Memo (CAM)\n\n"

    cam += "## Key Metrics\n"
    cam += f"- **Avg Monthly Income**: ₹{kpis.get('avg_monthly_income', 0):,.2f}\n"
    cam += f"- **FOIR**: {kpis.get('foir', 0):.1%}  (max allowed 50%)\n"
    cam += f"- **AMB**: ₹{kpis.get('amb', 0):,.2f}\n"
    cam += f"- **Income Stability (CV)**: {kpis.get('income_stability', 0):.2f}\n"
    cam += f"- **Business Income Ratio**: {kpis.get('business_income_ratio', 0):.0%}\n"

    cam += "\n## Risk Flags\n"
    for k, v in verdict['flags'].items():
        cam += f"- **{k.replace('_', ' ').title()}**: {v}\n"
    cam += f"- **GST Variance**: {verdict['gst_variance_pct']}% \n"

    cam += f"\n## Recommendation: **{verdict['recommendation']}**\n"
    cam += f"**Estimated NPA Risk**: {verdict['npa_risk']*100:.1f}%\n"

    if not bank_data['raw_transactions'].empty:
        cam += "\n### Last 5 Transactions\n"
        cam += bank_data['raw_transactions'].tail(5).to_markdown(index=False)

    return cam


# ────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("GST-3B (CSV)")
    gst_file = st.file_uploader("Upload GST CSV", type=["csv"])

with col2:
    st.subheader("Bank Statement (PDF)")
    bank_file = st.file_uploader("Upload Bank PDF", type=["pdf"])

if gst_file and bank_file:
    with st.spinner("Analyzing documents (rule-based agents)..."):
        try:
            # Parse bank
            bank_bytes = bank_file.read()
            bank_data = parse_bank_statement(bank_bytes)

            # Parse GST
            gst_bytes = gst_file.read()
            gst_data = pd.read_csv(io.BytesIO(gst_bytes))

            # Analyze
            kpis = calculate_kpis(bank_data)

            # Audit
            verdict = audit_and_recommend(bank_data, gst_data, kpis)

            # Generate CAM
            cam_text = generate_cam(kpis, verdict, bank_data, gst_data)

            # Display results
            st.subheader("Results")
            st.markdown("### Final Recommendation")
            st.markdown(f"**{verdict['recommendation']}**")
            st.metric("NPA Risk Probability", f"{verdict['npa_risk']*100:.1f}%")

            with st.expander("Credit Assessment Memo", expanded=True):
                st.markdown(cam_text)

            with st.expander("Detailed KPIs"):
                st.json(kpis)

            with st.expander("Risk Flags"):
                st.json(verdict["flags"])

            if not bank_data['raw_transactions'].empty:
                with st.expander("Parsed Transactions"):
                    st.dataframe(bank_data['raw_transactions'])

        except Exception as e:
            st.error(f"Processing error: {str(e)}")
            st.info("Common causes: invalid PDF/CSV format, no text in PDF, or parsing mismatch.")
