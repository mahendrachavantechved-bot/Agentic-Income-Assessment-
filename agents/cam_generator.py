def generate_cam(kpis, verdict, bank_data, gst_data):
    """Generate Credit Assessment Memo as Markdown string"""
    cam_md = "# Credit Assessment Memo (CAM)\n\n"
    
    cam_md += "## Applicant Summary\n"
    cam_md += "- **Average Monthly Income**: ₹{:.2f}\n".format(kpis.get('avg_monthly_income', 0))
    cam_md += "- **Income Stability (CV)**: {:.2f}\n".format(kpis.get('income_stability', 0))
    cam_md += "- **Average Monthly Balance (AMB)**: ₹{:.2f}\n".format(kpis.get('amb', 0))
    cam_md += "- **Peak Monthly Income**: ₹{:.2f}\n".format(kpis.get('peak_monthly_income', 0))
    cam_md += "- **Business Income Ratio**: {:.2%}\n".format(kpis.get('business_income_ratio', 0))
    cam_md += "- **FOIR**: {:.2%}\n".format(kpis.get('foir', 0))
    
    cam_md += "## Risk Assessment\n"
    cam_md += "- **GST Variance**: {:.1f}%\n".format(verdict.get('gst_variance_pct', 0))
    cam_md += "- **Bounce Count**: {}\n".format(verdict['flags'].get('bounce_count', 0))
    cam_md += "- **FOIR Excess**: {:.2f}\n".format(verdict['flags'].get('foir_excess', 0))
    cam_md += "- **Income Instability**: {}\n".format(verdict['flags'].get('income_instability', False))
    
    cam_md += "## Final Verdict\n"
    cam_md += f"**Recommendation**: {verdict['recommendation']}\n"
    cam_md += f"**NPA Risk Probability**: {verdict['npa_risk'] * 100:.1f}%\n"
    
    # Add excerpts from data (limited for brevity)
    cam_md += "## Data Excerpts\n"
    cam_md += "### Recent Transactions (Last 5)\n"
    recent_tx = bank_data['raw_transactions'].tail(5).to_markdown(index=False)
    cam_md += recent_tx + "\n"
    
    cam_md += "### GST Summary\n"
    gst_summary = gst_data.describe().to_markdown()
    cam_md += gst_summary + "\n"
    
    return cam_md
