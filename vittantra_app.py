"""



VITTANTRA



Day 71 — Investment Intelligence Command Center







This application is the presentation layer for the Vittantra research,



portfolio, risk, governance, remediation, and approval engines.







Run:



    streamlit run vittantra_app.py



"""







from __future__ import annotations







from pathlib import Path



from typing import Optional







import pandas as pd



import plotly.express as px



import plotly.graph_objects as go



import streamlit as st

from vittantra_ai_analyst import render_ai_analyst











# ============================================================



# CONFIGURATION



# ============================================================







APP_NAME = "Vittantra"



APP_SUBTITLE = "AI Investment Research & Portfolio Intelligence"







BASE_DIR = Path(__file__).resolve().parent







FILES = {



    "risk_dashboard": BASE_DIR / "day67_portfolio_risk_dashboard.csv",



    "governance": BASE_DIR / "day68_instrument_governance_actions.csv",



    "remediation": BASE_DIR / "day69_portfolio_remediation_summary.csv",



    "approval": BASE_DIR / "day70_portfolio_approval_summary.csv",



}







st.set_page_config(



    page_title="Vittantra",



    page_icon="V",



    layout="wide",



    initial_sidebar_state="expanded",



)











# ============================================================



# STYLING



# ============================================================







st.markdown(



    """



    <style>



    .block-container {



        padding-top: 1.5rem;



        padding-bottom: 3rem;



    }







    [data-testid="stSidebar"] {



        border-right: 1px solid rgba(128,128,128,0.18);



    }







    .vittantra-title {



        font-size: 2.25rem;



        font-weight: 800;



        letter-spacing: -0.04em;



        margin-bottom: 0;



    }







    .vittantra-subtitle {



        opacity: 0.70;



        margin-top: -0.25rem;



        margin-bottom: 1.4rem;



    }







    .section-title {



        font-size: 1.15rem;



        font-weight: 700;



        margin-top: 0.4rem;



        margin-bottom: 0.8rem;



    }







    .status-critical {



        padding: 0.45rem 0.75rem;



        border-radius: 0.55rem;



        background: rgba(255, 75, 75, 0.12);



        border: 1px solid rgba(255, 75, 75, 0.30);



        font-weight: 700;



    }







    .status-warning {



        padding: 0.45rem 0.75rem;



        border-radius: 0.55rem;



        background: rgba(255, 170, 0, 0.12);



        border: 1px solid rgba(255, 170, 0, 0.30);



        font-weight: 700;



    }







    .status-normal {



        padding: 0.45rem 0.75rem;



        border-radius: 0.55rem;



        background: rgba(0, 190, 120, 0.12);



        border: 1px solid rgba(0, 190, 120, 0.30);



        font-weight: 700;



    }







    .small-note {



        opacity: 0.68;



        font-size: 0.86rem;



    }







    div[data-testid="stMetric"] {



        border: 1px solid rgba(128,128,128,0.18);



        padding: 0.8rem 1rem;



        border-radius: 0.75rem;



    }



    </style>



    """,



    unsafe_allow_html=True,



)











# ============================================================



# DATA HELPERS



# ============================================================







@st.cache_data(show_spinner=False)



def load_csv(path: Path) -> pd.DataFrame:



    if not path.exists():



        return pd.DataFrame()







    try:



        return pd.read_csv(path)



    except Exception:



        return pd.DataFrame()











def get_value(



    df: pd.DataFrame,



    candidates: list[str],



    default=None,



):



    if df.empty:



        return default







    for column in candidates:



        if column in df.columns:



            series = df[column].dropna()







            if not series.empty:



                return series.iloc[0]







    return default











def find_column(



    df: pd.DataFrame,



    candidates: list[str],



) -> Optional[str]:



    for column in candidates:



        if column in df.columns:



            return column







    return None











def safe_float(value, default=0.0) -> float:



    try:



        if pd.isna(value):



            return default



        return float(value)



    except (TypeError, ValueError):



        return default











def safe_int(value, default=0) -> int:



    try:



        if pd.isna(value):



            return default



        return int(float(value))



    except (TypeError, ValueError):



        return default











def pct(value) -> str:



    return f"{safe_float(value) * 100:,.1f}%"











def multiple(value) -> str:



    return f"{safe_float(value):,.2f}×"











def status_html(status: str) -> str:



    normalized = str(status).upper()







    if "CRITICAL" in normalized:



        css_class = "status-critical"



    elif (



        "WARNING" in normalized



        or "WATCH" in normalized



        or "REVIEW" in normalized



        or "AWAIT" in normalized



    ):



        css_class = "status-warning"



    else:



        css_class = "status-normal"







    return (



        f'<span class="{css_class}">'



        f'{str(status).replace("_", " ")}'



        f"</span>"



    )











# ============================================================



# LOAD VITTANTRA OUTPUTS



# ============================================================







risk_df = load_csv(FILES["risk_dashboard"])



governance_df = load_csv(FILES["governance"])



remediation_df = load_csv(FILES["remediation"])



approval_df = load_csv(FILES["approval"])











# ============================================================



# PORTFOLIO STATE



# ============================================================







workflow_status = get_value(



    approval_df,



    ["portfolio_workflow_status"],



    "UNKNOWN",



)







decision_ticket_count = safe_int(



    get_value(



        approval_df,



        ["decision_ticket_count"],



        0,



    )



)







pending_review_count = safe_int(



    get_value(



        approval_df,



        ["pending_review_count"],



        0,



    )



)







risk_review_count = safe_int(



    get_value(



        approval_df,



        ["risk_review_required_count"],



        0,



    )



)







portfolio_review_count = safe_int(



    get_value(



        approval_df,



        ["portfolio_review_required_count"],



        0,



    )



)







dual_approval_count = safe_int(



    get_value(



        approval_df,



        ["dual_approval_required_count"],



        0,



    )



)







risk_reduction_count = safe_int(



    get_value(



        approval_df,



        ["risk_reduction_ticket_count"],



        0,



    )



)







immediate_priority_count = safe_int(



    get_value(



        approval_df,



        ["immediate_priority_count"],



        0,



    )



)







approval_queue_count = safe_int(



    get_value(



        approval_df,



        ["approval_queue_count"],



        0,



    )



)







current_max_utilization = safe_float(



    get_value(



        approval_df,



        ["maximum_current_risk_budget_utilization"],



        0,



    )



)







post_max_utilization = safe_float(



    get_value(



        approval_df,



        ["maximum_estimated_post_remediation_utilization"],



        0,



    )



)







automatic_execution_count = safe_int(



    get_value(



        approval_df,



        ["automatic_execution_authorized_count"],



        0,



    )



)











# Risk dashboard fields







portfolio_status = str(



    get_value(



        risk_df,



        ["portfolio_status"],



        "UNKNOWN",



    )



)







instrument_count = safe_int(



    get_value(



        risk_df,



        ["instrument_count"],



        len(governance_df),



    )



)







warning_count = safe_int(



    get_value(



        risk_df,



        ["warning_count"],



        0,



    )



)







breach_count = safe_int(



    get_value(



        risk_df,



        ["breach_count"],



        0,



    )



)







critical_count = safe_int(



    get_value(



        risk_df,



        ["critical_count"],



        0,



    )



)







review_count = safe_int(



    get_value(



        risk_df,



        ["requires_review_count"],



        0,



    )



)







mean_utilization = safe_float(



    get_value(



        risk_df,



        ["mean_risk_budget_utilization"],



        0,



    )



)







dashboard_max_utilization = safe_float(



    get_value(



        risk_df,



        ["maximum_risk_budget_utilization"],



        current_max_utilization,



    )



)







if current_max_utilization == 0:



    current_max_utilization = dashboard_max_utilization











# ============================================================



# SIDEBAR



# ============================================================







with st.sidebar:







    st.markdown("## VITTANTRA")







    st.caption("Investment Intelligence System")







    page = st.radio(



        "Workspace",



        [



            "Command Center",



            "Portfolio",



            "Risk Intelligence",



            "Governance",



            "Remediation",



            "AI Analyst",



            "System",



        ],



        label_visibility="collapsed",



    )







    st.divider()







    st.caption("PORTFOLIO STATE")







    st.markdown(



        status_html(portfolio_status),



        unsafe_allow_html=True,



    )







    st.write("")







    st.caption("WORKFLOW")







    st.markdown(



        status_html(workflow_status),



        unsafe_allow_html=True,



    )







    st.divider()







    if automatic_execution_count == 0:



        st.success("Automatic execution disabled")



    else:



        st.error(



            f"{automatic_execution_count} automatic execution "



            "authorization(s) detected."



        )







    st.caption(



        "Research and decision-support environment. "



        "Human approval remains required."



    )











# ============================================================



# HEADER



# ============================================================







st.markdown(



    '<div class="vittantra-title">Vittantra</div>',



    unsafe_allow_html=True,



)







st.markdown(



    f'<div class="vittantra-subtitle">{APP_SUBTITLE}</div>',



    unsafe_allow_html=True,



)











# ============================================================



# COMMAND CENTER



# ============================================================







if page == "Command Center":







    st.markdown("### Investment Command Center")







    col1, col2, col3, col4, col5 = st.columns(5)







    col1.metric(



        "Portfolio Status",



        str(portfolio_status).replace("_", " "),



    )







    col2.metric(



        "Instruments",



        instrument_count,



    )







    col3.metric(



        "Approval Queue",



        approval_queue_count,



    )







    col4.metric(



        "Immediate Priority",



        immediate_priority_count,



    )







    col5.metric(



        "Automatic Execution",



        automatic_execution_count,



    )







    st.write("")







    left, right = st.columns([1.35, 1])







    with left:







        st.markdown(



            '<div class="section-title">Risk Budget Utilization</div>',



            unsafe_allow_html=True,



        )







        gauge = go.Figure(



            go.Indicator(



                mode="gauge+number",



                value=current_max_utilization * 100,



                number={



                    "suffix": "%",



                    "valueformat": ".1f",



                },



                title={



                    "text": "Maximum Current Utilization"



                },



                gauge={



                    "axis": {



                        "range": [



                            0,



                            max(



                                150,



                                current_max_utilization * 110,



                            ),



                        ]



                    },



                    "bar": {},



                    "steps": [



                        {



                            "range": [0, 80],



                        },



                        {



                            "range": [80, 100],



                        },



                        {



                            "range": [



                                100,



                                max(



                                    150,



                                    current_max_utilization * 110,



                                ),



                            ],



                        },



                    ],



                    "threshold": {



                        "line": {



                            "width": 4,



                        },



                        "thickness": 0.75,



                        "value": 100,



                    },



                },



            )



        )







        gauge.update_layout(



            height=340,



            margin=dict(



                l=25,



                r=25,



                t=70,



                b=20,



            ),



        )







        st.plotly_chart(



            gauge,



            use_container_width=True,



        )







    with right:







        st.markdown(



            '<div class="section-title">Workflow State</div>',



            unsafe_allow_html=True,



        )







        st.markdown(



            status_html(workflow_status),



            unsafe_allow_html=True,



        )







        st.write("")







        st.metric(



            "Decision Tickets",



            decision_ticket_count,



        )







        st.metric(



            "Risk Reduction Tickets",



            risk_reduction_count,



        )







        st.metric(



            "Dual Approval Required",



            dual_approval_count,



        )







        st.metric(



            "Pending Review",



            pending_review_count,



        )







    st.divider()







    st.markdown("### Risk → Remediation")







    before, arrow, after = st.columns(



        [1, 0.25, 1]



    )







    before.metric(



        "Current Maximum Utilization",



        pct(current_max_utilization),



    )







    arrow.markdown(



        """



        <div style="



            text-align:center;



            font-size:2rem;



            padding-top:1.2rem;">



            →



        </div>



        """,



        unsafe_allow_html=True,



    )







    after.metric(



        "Estimated Post-Remediation",



        pct(post_max_utilization),



    )







    if current_max_utilization > 0:







        reduction = (



            current_max_utilization



            - post_max_utilization



        )







        reduction_pct = (



            reduction / current_max_utilization



        )







        st.progress(



            min(



                max(reduction_pct, 0.0),



                1.0,



            )



        )







        st.caption(



            f"Estimated modeled-risk reduction: "



            f"{reduction_pct * 100:,.1f}%"



        )







    st.divider()







    st.markdown("### Portfolio Alerts")







    a1, a2, a3, a4 = st.columns(4)







    a1.metric(



        "Warnings",



        warning_count,



    )







    a2.metric(



        "Breaches",



        breach_count,



    )







    a3.metric(



        "Critical",



        critical_count,



    )







    a4.metric(



        "Requires Review",



        review_count,



    )







    if str(portfolio_status).upper() == "CRITICAL":







        st.error(



            "Portfolio risk state is CRITICAL. "



            "New incremental risk should remain subject "



            "to governance controls and human review."



        )







    elif breach_count > 0:







        st.warning(



            "Risk-budget breaches are present."



        )







    else:







        st.success(



            "No critical portfolio-level risk state "



            "was detected in the loaded dashboard."



        )











# ============================================================



# PORTFOLIO



# ============================================================



elif page == "Portfolio":



    st.markdown("### Portfolio Intelligence")

    st.caption(

        "Instrument-level risk-budget, modeled-risk contribution, "

        "governance and concentration diagnostics."

    )



    if governance_df.empty:

        st.info("Day 68 instrument governance data is unavailable.")

    else:

        portfolio_df = governance_df.copy()



        symbol_col = find_column(portfolio_df, ["symbol", "ticker", "instrument"])

        asset_col = find_column(portfolio_df, ["asset_class"])

        type_col = find_column(portfolio_df, ["instrument_type"])

        budget_col = find_column(portfolio_df, ["risk_budget"])

        contribution_col = find_column(portfolio_df, ["modeled_risk_contribution"])

        utilization_col = find_column(portfolio_df, ["risk_budget_utilization"])

        excess_col = find_column(portfolio_df, ["risk_budget_excess"])

        budget_status_col = find_column(portfolio_df, ["day66_risk_budget_status"])

        gov_status_col = find_column(portfolio_df, ["governance_status"])

        gov_action_col = find_column(portfolio_df, ["governance_action"])

        gov_reason_col = find_column(portfolio_df, ["governance_reason"])

        review_col = find_column(portfolio_df, ["requires_review"])

        block_col = find_column(portfolio_df, ["block_incremental_risk"])



        for col in [budget_col, contribution_col, utilization_col, excess_col]:

            if col:

                portfolio_df[col] = pd.to_numeric(portfolio_df[col], errors="coerce")



        def flag_count(column):

            if not column:

                return 0

            values = portfolio_df[column].astype(str).str.strip().str.upper()

            return int(values.isin(

                ["TRUE", "1", "YES", "Y", "REQUIRED", "BLOCK", "BLOCKED"]

            ).sum())



        n_instruments = (

            int(portfolio_df[symbol_col].nunique())

            if symbol_col else len(portfolio_df)

        )

        n_review = flag_count(review_col)

        n_blocked = flag_count(block_col)



        if utilization_col:

            mean_u = safe_float(portfolio_df[utilization_col].mean())

            max_u = safe_float(portfolio_df[utilization_col].max())

            n_breached = int((portfolio_df[utilization_col] > 1.0).sum())

        else:

            mean_u = mean_utilization

            max_u = current_max_utilization

            n_breached = breach_count



        total_risk = (

            safe_float(portfolio_df[contribution_col].sum())

            if contribution_col else 0.0

        )

        total_excess = (

            safe_float(portfolio_df[excess_col].clip(lower=0).sum())

            if excess_col else 0.0

        )



        st.markdown("#### Portfolio Snapshot")



        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Instruments", n_instruments)

        c2.metric("Mean Utilization", pct(mean_u))

        c3.metric("Maximum Utilization", pct(max_u))

        c4.metric("Budget Breaches", n_breached)

        c5.metric("Blocked / Review", f"{n_blocked} / {n_review}")



        c6, c7, c8 = st.columns(3)

        c6.metric("Modeled Risk Contribution", f"{total_risk:,.4f}")

        c7.metric("Positive Budget Excess", f"{total_excess:,.4f}")

        c8.metric("Workflow", str(workflow_status).replace("_", " "))



        st.divider()

        st.markdown("#### Risk-Budget Utilization Ranking")



        if symbol_col and utilization_col:

            cols = [

                c for c in [

                    symbol_col, asset_col, budget_col,

                    contribution_col, utilization_col, excess_col

                ] if c

            ]

            ranked = (

                portfolio_df[cols]

                .dropna(subset=[utilization_col])

                .sort_values(utilization_col, ascending=False)

            )



            fig = px.bar(

                ranked,

                x=symbol_col,

                y=utilization_col,

                color=asset_col if asset_col else None,

                hover_data=[

                    c for c in [budget_col, contribution_col, excess_col] if c

                ],

                title="Instrument Risk-Budget Utilization",

            )

            fig.add_hline(

                y=1.0,

                line_dash="dash",

                annotation_text="100% Risk Budget",

            )

            fig.update_layout(

                xaxis_title="Instrument",

                yaxis_title="Utilization (× budget)",

            )

            st.plotly_chart(fig, width="stretch")

        else:

            st.info(

                "Symbol and risk-budget-utilization fields "

                "are required for this chart."

            )



        st.markdown("#### Asset-Class Risk Allocation")



        if asset_col:

            agg = {}

            if budget_col:

                agg[budget_col] = "sum"

            if contribution_col:

                agg[contribution_col] = "sum"

            if utilization_col:

                agg[utilization_col] = "mean"

            if excess_col:

                agg[excess_col] = "sum"



            if agg:

                asset_summary = (

                    portfolio_df

                    .groupby(asset_col, dropna=False)

                    .agg(agg)

                    .reset_index()

                )



                counts = (

                    portfolio_df

                    .groupby(asset_col, dropna=False)

                    .size()

                    .reset_index(name="instrument_count")

                )

                asset_summary = asset_summary.merge(

                    counts,

                    on=asset_col,

                    how="left",

                )



                if contribution_col:

                    denominator = safe_float(

                        asset_summary[contribution_col].abs().sum()

                    )

                    asset_summary["absolute_risk_share"] = (

                        asset_summary[contribution_col].abs() / denominator

                        if denominator else 0.0

                    )



                left, right = st.columns([1.15, 1])



                with left:

                    y_col = contribution_col or utilization_col

                    if y_col:

                        fig = px.bar(

                            asset_summary.sort_values(y_col, ascending=False),

                            x=asset_col,

                            y=y_col,

                            title="Asset-Class Risk Profile",

                        )

                        if y_col == utilization_col:

                            fig.add_hline(

                                y=1.0,

                                line_dash="dash",

                                annotation_text="Risk Budget",

                            )

                        st.plotly_chart(fig, width="stretch")



                with right:

                    st.dataframe(

                        asset_summary,

                        width="stretch",

                        hide_index=True,

                    )



        st.divider()

        st.markdown("#### Risk Contribution Concentration")



        if symbol_col and contribution_col:

            cols = [

                c for c in [symbol_col, asset_col, contribution_col] if c

            ]

            concentration = (

                portfolio_df[cols]

                .dropna(subset=[contribution_col])

                .copy()

            )

            concentration["absolute_risk_contribution"] = (

                concentration[contribution_col].abs()

            )

            denominator = safe_float(

                concentration["absolute_risk_contribution"].sum()

            )



            if denominator > 0:

                concentration["risk_share"] = (

                    concentration["absolute_risk_contribution"] / denominator

                )

                concentration = concentration.sort_values(

                    "risk_share",

                    ascending=False,

                )

                concentration["cumulative_risk_share"] = (

                    concentration["risk_share"].cumsum()

                )



                top1 = safe_float(concentration["risk_share"].iloc[0])

                top3 = safe_float(concentration["risk_share"].head(3).sum())

                hhi = safe_float((concentration["risk_share"] ** 2).sum())

                effective_n = 1 / hhi if hhi > 0 else 0



                k1, k2, k3 = st.columns(3)

                k1.metric("Largest Risk Share", pct(top1))

                k2.metric("Top 3 Risk Share", pct(top3))

                k3.metric("Effective Risk Positions", f"{effective_n:,.2f}")



                fig = px.bar(

                    concentration,

                    x=symbol_col,

                    y="risk_share",

                    color=asset_col if asset_col else None,

                    title="Absolute Modeled-Risk Contribution Share",

                )

                fig.update_layout(

                    xaxis_title="Instrument",

                    yaxis_title="Share of Absolute Risk",

                )

                st.plotly_chart(fig, width="stretch")



                with st.expander("Concentration detail", expanded=False):

                    st.dataframe(

                        concentration,

                        width="stretch",

                        hide_index=True,

                    )

            else:

                st.info(

                    "Modeled risk contribution is zero; "

                    "concentration cannot be calculated."

                )



        st.markdown("#### Risk-Budget Excess")



        if symbol_col and excess_col:

            cols = [c for c in [symbol_col, asset_col, excess_col] if c]

            excess = (

                portfolio_df[cols]

                .dropna(subset=[excess_col])

                .sort_values(excess_col, ascending=False)

            )

            positive = excess[excess[excess_col] > 0].copy()



            if positive.empty:

                st.success(

                    "No positive instrument-level risk-budget excess is present."

                )

            else:

                fig = px.bar(

                    positive,

                    x=symbol_col,

                    y=excess_col,

                    color=asset_col if asset_col else None,

                    title="Positive Risk-Budget Excess by Instrument",

                )

                st.plotly_chart(fig, width="stretch")

                st.warning(

                    f"{len(positive)} instrument(s) show "

                    "positive risk-budget excess."

                )



        st.markdown("#### Governance Overlay")



        display_cols = [

            c for c in [

                symbol_col,

                asset_col,

                type_col,

                budget_col,

                contribution_col,

                utilization_col,

                excess_col,

                budget_status_col,

                gov_status_col,

                gov_action_col,

                gov_reason_col,

                review_col,

                block_col,

            ] if c

        ]



        overlay = (

            portfolio_df[display_cols].copy()

            if display_cols

            else portfolio_df.copy()

        )



        if utilization_col and utilization_col in overlay.columns:

            overlay = overlay.sort_values(

                utilization_col,

                ascending=False,

            )



        st.dataframe(

            overlay,

            width="stretch",

            hide_index=True,

        )



        st.markdown("#### Portfolio Observations")



        observations = []



        if max_u > 1.0:

            observations.append(

                f"Maximum instrument risk-budget utilization is "

                f"{max_u * 100:,.1f}%, above the modeled budget threshold."

            )

        else:

            observations.append(

                f"Maximum instrument risk-budget utilization is "

                f"{max_u * 100:,.1f}%."

            )



        observations.append(

            f"{n_breached} instrument(s) are above 100% "

            "of modeled risk budget."

            if n_breached

            else "No instrument is above 100% of modeled risk budget."

        )



        if n_blocked:

            observations.append(

                f"{n_blocked} instrument(s) are flagged "

                "to block incremental risk."

            )



        if n_review:

            observations.append(

                f"{n_review} instrument(s) require human review."

            )



        if current_max_utilization > 0:

            change = current_max_utilization - post_max_utilization

            observations.append(

                f"Day 69 remediation estimates maximum utilization moving "

                f"from {current_max_utilization * 100:,.1f}% to "

                f"{post_max_utilization * 100:,.1f}%, a modeled change of "

                f"{change * 100:,.1f} percentage points."

            )



        for item in observations:

            st.write(f"• {item}")



        st.info(

            "Portfolio Intelligence is a research and decision-support layer. "

            "Risk-budget, governance and remediation outputs remain subject "

            "to human review and do not constitute automatic trade instructions."

        )





# ============================================================



# RISK INTELLIGENCE



# ============================================================







elif page == "Risk Intelligence":







    st.markdown("### Risk Intelligence")







    r1, r2, r3, r4 = st.columns(4)







    r1.metric(



        "Mean Utilization",



        pct(mean_utilization),



    )







    r2.metric(



        "Maximum Utilization",



        pct(current_max_utilization),



    )







    r3.metric(



        "Breaches",



        breach_count,



    )







    r4.metric(



        "Critical",



        critical_count,



    )







    st.divider()







    if governance_df.empty:







        st.info(



            "No instrument risk dataset is available."



        )







    else:







        symbol_col = find_column(



            governance_df,



            ["symbol", "ticker"],



        )







        util_col = find_column(



            governance_df,



            ["risk_budget_utilization"],



        )







        asset_col = find_column(



            governance_df,



            ["asset_class"],



        )







        if symbol_col and util_col:







            risk_chart = governance_df.copy()







            risk_chart[util_col] = pd.to_numeric(



                risk_chart[util_col],



                errors="coerce",



            )







            risk_chart = risk_chart.dropna(



                subset=[util_col]



            )







            if asset_col:







                fig = px.bar(



                    risk_chart.sort_values(



                        util_col,



                        ascending=False,



                    ),



                    x=symbol_col,



                    y=util_col,



                    color=asset_col,



                    title=(



                        "Risk Utilization by Instrument "



                        "and Asset Class"



                    ),



                )







            else:







                fig = px.bar(



                    risk_chart.sort_values(



                        util_col,



                        ascending=False,



                    ),



                    x=symbol_col,



                    y=util_col,



                    title="Risk Utilization by Instrument",



                )







            fig.add_hline(



                y=1.0,



                line_dash="dash",



                annotation_text="100% Risk Budget",



            )







            st.plotly_chart(



                fig,



                use_container_width=True,



            )







        st.dataframe(



            governance_df,



            use_container_width=True,



            hide_index=True,



        )











# ============================================================



# GOVERNANCE



# ============================================================







elif page == "Governance":







    st.markdown("### Portfolio Governance")







    g1, g2, g3, g4 = st.columns(4)







    g1.metric(



        "Decision Tickets",



        decision_ticket_count,



    )







    g2.metric(



        "Risk Reviews",



        risk_review_count,



    )







    g3.metric(



        "Portfolio Reviews",



        portfolio_review_count,



    )







    g4.metric(



        "Dual Approvals",



        dual_approval_count,



    )







    st.divider()







    st.markdown("### Governance Workflow")







    st.markdown(



        status_html(workflow_status),



        unsafe_allow_html=True,



    )







    st.write("")







    if governance_df.empty:







        st.info(



            "Day 68 governance output is unavailable."



        )







    else:







        preferred = [



            "symbol",



            "asset_class",



            "instrument_type",



            "risk_budget_utilization",



            "risk_budget_excess",



            "day66_risk_budget_status",



            "governance_status",



            "governance_action",



            "governance_reason",



            "requires_review",



            "block_incremental_risk",



        ]







        available = [



            c for c in preferred



            if c in governance_df.columns



        ]







        st.dataframe(



            governance_df[



                available



                if available



                else governance_df.columns



            ],



            use_container_width=True,



            hide_index=True,



        )







    st.warning(



        "Vittantra governance outputs are research controls "



        "and decision-support recommendations. "



        "They do not automatically execute trades."



    )











# ============================================================



# REMEDIATION



# ============================================================







elif page == "Remediation":







    st.markdown("### Portfolio Risk Remediation")







    c1, c2, c3 = st.columns(3)







    c1.metric(



        "Current Maximum Utilization",



        pct(current_max_utilization),



    )







    c2.metric(



        "Post-Remediation Estimate",



        pct(post_max_utilization),



    )







    if current_max_utilization > 0:







        modeled_reduction = (



            1



            - (



                post_max_utilization



                / current_max_utilization



            )



        )







    else:



        modeled_reduction = 0







    c3.metric(



        "Modeled Reduction",



        f"{modeled_reduction * 100:,.1f}%",



    )







    st.divider()







    if remediation_df.empty:







        st.info(



            "Day 69 remediation summary is unavailable."



        )







    else:







        st.markdown("### Remediation Summary")







        st.dataframe(



            remediation_df,



            use_container_width=True,



            hide_index=True,



        )







    st.divider()







    st.markdown("### Control Boundary")







    st.info(



        "Remediation represents modeled risk-control "



        "recommendations. Human review and approval remain "



        "required before any real-world implementation."



    )











# ============================================================
# AI ANALYST
# ============================================================

elif page == "AI Analyst":
    render_ai_analyst()


# ============================================================



# SYSTEM



# ============================================================







elif page == "System":







    st.markdown("### Vittantra System")







    system_rows = []







    for name, path in FILES.items():







        exists = path.exists()







        if exists:



            df = load_csv(path)



            rows = len(df)



            columns = len(df.columns)



        else:



            rows = 0



            columns = 0







        system_rows.append(



            {



                "module": name,



                "file": path.name,



                "available": exists,



                "rows": rows,



                "columns": columns,



            }



        )







    system_df = pd.DataFrame(system_rows)







    st.dataframe(



        system_df,



        use_container_width=True,



        hide_index=True,



    )







    available_count = int(



        system_df["available"].sum()



    )







    s1, s2, s3 = st.columns(3)







    s1.metric(



        "Connected Modules",



        f"{available_count}/{len(system_df)}",



    )







    s2.metric(



        "Automatic Execution",



        automatic_execution_count,



    )







    s3.metric(



        "Workflow",



        str(workflow_status).replace("_", " "),



    )







    st.divider()







    st.markdown("### Architecture")







    st.code(



        "Research & Data\n"



        "      ↓\n"



        "Machine Learning\n"



        "      ↓\n"



        "Portfolio Construction\n"



        "      ↓\n"



        "Risk Engine\n"



        "      ↓\n"



        "Exposure & Risk Budgeting\n"



        "      ↓\n"



        "Risk Monitoring\n"



        "      ↓\n"



        "Governance\n"



        "      ↓\n"



        "Remediation\n"



        "      ↓\n"



        "Approval Workflow\n"



        "      ↓\n"



        "Human Decision"



    )











# ============================================================



# FOOTER



# ============================================================







st.divider()







st.caption(



    "Vittantra • Research & Portfolio Intelligence • "



    "Day 73 AI Analyst Integration"



)