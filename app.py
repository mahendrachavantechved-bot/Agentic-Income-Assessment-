import streamlit as st
import pandas as pd
from agents.parser_agent import parse_bank_statement
from agents.analyst_agent import calculate_kpis
from agents.auditor_agent import audit_and_recommend
from agents.cam_generator import generate_cam
import io

st.set_page_config(page_title="GROK Income Validator", layout="wide")
st.title("🤖 GROK - Agentic AI Credit Assessment")
st.markdown("**Upload Bank Statement + GST → Instant CAM with NPA Prediction**")
st.markdown("This is a rule-based system compliant with RBI guidelines. No LLM used.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("📋 GST-3B Upload")
    gst_file = st.file_uploader("GST CSV", type=['csv'])
   
with col2:
    st.subheader("🏦 Bank Statement")
    bank_file = st.file_uploader("Bank PDF", type=['pdf'])

if gst_file and bank_file:
    with st.spinner("GROK Agents analyzing (rule-based)..."):
        # Read files
        bank_bytes = bank_file.read()
        bank_data = parse_bank_statement(bank_bytes)
        gst_bytes = gst_file.read()
        gst_data = pd.read_csv(io.BytesIO(gst_bytes))
   
        # Agent B: Analyze
        kpis = calculate_kpis(bank_data)
   
        # Agent C: Audit + Triangulate
        verdict = audit_and_recommend(bank_data, gst_data, kpis)
   
        # Generate CAM
        cam = generate_cam(kpis, verdict, bank_data, gst_data)
        
        result = {
            "credit_assessment_memo": cam,
            "kpis": kpis,
            "risk_flags": verdict["flags"],
            "final_recommendation": verdict["recommendation"],
            "npa_probability": verdict["npa_risk"]
        }
       
        col1, col2 = st.columns([2, 1])
           
        with col1:
            st.markdown("### 💰 **Credit Assessment Memo (CAM)**")
            st.markdown(result['credit_assessment_memo'])  # Display the CAM markdown
            st.markdown(f"**Recommendation:** {result['final_recommendation']}")
            st.markdown(f"**NPA Probability:** {result['npa_probability']*100:.1f}%")
            st.json(result['kpis'])
           
        with col2:
            st.markdown("### 🚨 **Risk Flags**")
            for flag, value in result['risk_flags'].items():
                color = "red" if (isinstance(value, bool) and value) or (isinstance(value, (int, float)) and value > 0) else "green"
                st.markdown(f"**{flag.replace('_', ' ').title()}:** <span style='color:{color}'>{value}</span>",
                            unsafe_allow_html=True)
