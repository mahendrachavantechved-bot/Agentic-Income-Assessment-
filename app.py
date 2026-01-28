import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Bank + GST → CAM", layout="wide")

st.title("Bank Statement + GST → Credit Assessment Memo")
st.caption("Single-file version – rule-based – no LLM")

# ────────────────────────────────────────────────
# File upload
# ────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    gst_file = st.file_uploader("GST file (CSV)", type=["csv"])

with col2:
    bank_file = st.file_uploader("Bank statement (PDF)", type=["pdf"])

# ────────────────────────────────────────────────
# Parsing function
# ────────────────────────────────────────────────

def parse_bank_pdf(pdf_bytes):
    try:
        import PyPDF2
    except ImportError:
        st.error("PyPDF2 is not installed → contact platform support or switch to pypdf")
        return None, "PyPDF2 not available"

    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = ""

        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"

        if len(text.strip()) < 200:
            return None, "Very little text extracted – probably scanned/image PDF"

        # ────── Simple flexible line parser ──────
        transactions = []
        lines = text.splitlines()

        for line in lines:
            line = line.strip()
            if len(line) < 20:
                continue

            # Look for date pattern at beginning
            match = re.match(
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)(?:\s{2,}|\t+)'
                r'([\d,]+\.?\d*)?\s*([\d,]+\.?\d*)?\s*([\d,]+\.?\d*)?',
                line
            )

            if match:
                date_str, desc, debit_str, credit_str, balance_str = match.groups()

                def clean(s):
                    if not s:
                        return 0.0
                    s = re.sub(r'[^\d.]', '', s)
                    try:
                        return float(s)
                    except:
                        return 0.0

                try:
                    date = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
                    if pd.isna(date):
                        continue

                    transactions.append({
                        'date': date,
                        'description': desc.strip(),
                        'debit': clean(debit_str),
                        'credit': clean(credit_str),
                        'balance': clean(balance_str),
                    })
                except:
                    continue

        if not transactions:
            return None, "No transaction lines matched the pattern"

        df = pd.DataFrame(transactions)

        # Make sure numeric columns exist
        for col in ['debit','credit','balance']:
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['net'] = df['credit'] - df['debit']

        if 'date' in df.columns:
            df['month'] = df['date'].dt.to_period('M')

        return df, None

    except Exception as e:
        return None, f"PDF reading error: {str(e)}"


# ────────────────────────────────────────────────
# Main logic
# ────────────────────────────────────────────────

if gst_file is not None and bank_file is not None:

    with st.spinner("Processing documents..."):

        # Bank PDF
        bank_bytes = bank_file.read()
        df_bank, parse_error = parse_bank_pdf(bank_bytes)

        if parse_error:
            st.error("Bank statement parsing failed")
            st.info(parse_error)
            if "little text" in parse_error:
                st.warning("The PDF might be image-based (scanned). Text extraction does not work well in this case.")
            st.stop()

        # GST CSV
        try:
            df_gst = pd.read_csv(io.BytesIO(gst_file.read()))
            gst_total = df_gst.get('taxable_value', pd.Series([0])).sum()
        except Exception as e:
            st.error("Could not read GST CSV")
            st.info(str(e))
            st.stop()

        # ────── Very simple KPIs ──────
        if not df_bank.empty:
            monthly_credit = df_bank.groupby('month')['credit'].sum()
            avg_income   = monthly_credit.mean()
            max_income   = monthly_credit.max()
            bounce_count = df_bank['description'].str.contains('return|bounce|dishonour', case=False).sum()

            turnover_estimate = avg_income * 12
            gst_variance_pct = abs(turnover_estimate - gst_total) / max(turnover_estimate, 1) * 100

            recommendation = "✅ APPROVE"
            risk_level = "Low"

            if gst_variance_pct > 25:
                recommendation = "⚠️ REVIEW – GST vs Bank mismatch"
                risk_level = "Medium"
            if bounce_count >= 3:
                recommendation = "❌ HIGH RISK – multiple returns/bounces"
                risk_level = "High"

            # Output
            st.success(f"**Recommendation: {recommendation}**  (Risk: {risk_level})")

            cols = st.columns(3)
            with cols[0]:
                st.metric("Estimated annual turnover (from bank)", f"₹{turnover_estimate:,.0f}")
            with cols[1]:
                st.metric("GST reported", f"₹{gst_total:,.0f}")
            with cols[2]:
                st.metric("GST variance", f"{gst_variance_pct:.1f}%")

            st.markdown("**Average monthly credits**")
            st.bar_chart(monthly_credit)

            with st.expander("Parsed bank transactions (last 15 rows)"):
                st.dataframe(df_bank.tail(15))

            with st.expander("Raw GST data"):
                st.dataframe(df_gst.head(10))

        else:
            st.warning("No usable transactions found in the bank statement")

else:
    st.info("Please upload both files to start analysis.")
