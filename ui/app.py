import streamlit as st
import requests

API_URL = "http://localhost:8000/api/v1/incidents/analyze"

st.set_page_config(
    page_title="OPS AI Runbook Assistant",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 OPS AI Runbook Assistant")

st.markdown(
    "AI-Powered Incident Analysis using RAG + Multi-Agent System"
)

incident = st.text_area(
    "Enter Incident Description",
    height=200,
    placeholder="""
Production API returning 503 errors.

Symptoms:
- Customers unable to login
- Increased latency
- Multiple pods restarting
"""
)

if st.button("Analyze Incident"):

    if len(incident.strip()) < 20:
        st.warning(
            "Please provide a meaningful incident description."
    )
    st.stop()
    

    with st.spinner("Running AI Agents..."):

        response = requests.post(
            API_URL,
            json={
                "incident": incident
            },
            timeout=300
        )

    if response.status_code == 200:

        data = response.json()

        st.success("Analysis Complete")

        tab1, tab2, tab3 = st.tabs(
            [
                "Incident Analysis",
                "Root Cause",
                "Recommendations"
            ]
        )

        with tab1:
            st.markdown(
                data["incident_analysis"]
            )

        with tab2:
            st.markdown(
                data["root_cause"]
            )

        with tab3:
            st.markdown(
                data["recommendations"]
            )

    else:
        st.error(
            f"API Error: {response.status_code}"
        )