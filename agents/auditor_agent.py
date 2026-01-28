def audit_and_recommend(bank_data, gst_data, kpis):
    """Triangulation + Final Verdict"""
   
    # Risk Flag 1: GST Turnover Validation
    bank_turnover = kpis['avg_monthly_income'] * 12
    gst_turnover = gst_data['taxable_value'].sum() if 'taxable_value' in gst_data else 0
   
    gst_variance = abs(bank_turnover - gst_turnover) / max(bank_turnover, 1)
   
    # Risk Flag 2: Bounced Transactions
    bounce_count = bank_data['raw_transactions']['flags'].sum()
   
    # Risk Flag 3: FOIR Breach
    foir_breach = kpis['foir'] > 0.50
   
    flags = {
        'gst_underreporting': gst_variance > 0.20,
        'bounce_count': bounce_count,
        'foir_excess': kpis['foir'] - 0.50,
        'income_instability': kpis['income_stability'] > 0.30
    }
   
    # NPA Probability (weighted scoring)
    npa_score = (
        flags['gst_underreporting'] * 0.40 +
        (bounce_count / 10) * 0.30 +
        flags['foir_excess'] * 0.20 +
        flags['income_instability'] * 0.10
    )
   
    # Final Recommendation
    if npa_score < 0.20:
        recommendation = "✅ GO - Low Risk"
    elif npa_score < 0.40:
        recommendation = "⚠️ CONDITIONAL - Medium Risk"
    else:
        recommendation = "❌ NO-GO - High NPA Risk"
   
    return {
        "flags": flags,
        "npa_risk": round(npa_score, 3),
        "recommendation": recommendation,
        "gst_variance_pct": round(gst_variance * 100, 1)
    }
