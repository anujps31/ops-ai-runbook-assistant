import streamlit as st
import requests

API_URL = "http://localhost:8000/api/v1/incidents/analyze"

st.set_page_config(
    page_title="OPS AI Runbook Assistant",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.markdown("# OPS AI Runbook Assistant")
    st.markdown("**Model**")
    st.markdown("- qwen3:8b")
    st.markdown("**Vector store**")
    st.markdown("- ChromaDB")
    st.markdown("**Runtime**")
    st.markdown("- FastAPI + Streamlit")
    st.markdown("**Version**")
    st.markdown("- 0.1.0")
    st.markdown("---")
    sample_incidents = [
        "Production API returning 503 errors",
        "High latency on checkout service",
        "Redis connection timeouts in payment pipeline",
        "Kafka consumer lag exceeding SLA",
        "Database connection pool exhaustion",
    ]
    selected_sample = st.selectbox("Sample Incident", sample_incidents)
    st.markdown("---")
    st.markdown("### Status")
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.metric("Ollama", "Running")
    with status_col2:
        st.metric("ChromaDB", "Running")

st.markdown("# Incident Analysis Dashboard")
st.markdown(
    "### Enterprise-grade incident triage for Kubernetes, cloud, and platform operations."
)

incident = st.text_area(
    "Enter Incident Description",
    value=selected_sample,
    height=240,
    placeholder="Provide a detailed incident description with symptoms and context.",
)

if st.button("Analyze Incident"):
    if len(incident.strip()) < 20:
        st.warning("Please provide a meaningful incident description.")
        st.stop()

    with st.spinner("Running incident analysis agents..."):
        try:
            response = requests.post(
                API_URL,
                json={"incident": incident},
                timeout=300,
            )

            if response.status_code != 200:
                st.error(f"Backend returned status code {response.status_code}")
                st.write(response.text)
                st.stop()

            data = response.json()
            analysis = data.get("data", {})
            incident_analysis = analysis.get("incident_analysis", {})
            root_cause = analysis.get("root_cause", "")
            recommendations = analysis.get("recommendations", "")
            execution_time = analysis.get("execution_time_seconds", 0.0)

            st.success("Incident analysis complete")

            header_col1, header_col2, header_col3 = st.columns([1, 1, 1])
            header_col1.metric("Severity", incident_analysis.get("severity", "N/A"))
            header_col2.metric("Confidence", incident_analysis.get("confidence_score", "N/A"))
            header_col3.metric("Execution Time", f"{execution_time:.2f}s")

            st.markdown("---")

            with st.expander("Incident Summary", expanded=True):
                st.write(incident_analysis.get("summary", "No summary available."))

            with st.expander("Affected Components", expanded=False):
                affected_components = incident_analysis.get("affected_components", [])
                if affected_components:
                    for component in affected_components:
                        st.write(f"- {component}")
                else:
                    st.write("No affected components identified.")

            with st.expander("Investigation Steps", expanded=False):
                steps = incident_analysis.get("investigation_steps", [])
                if steps:
                    for step in steps:
                        st.write(f"- {step}")
                else:
                    st.write("No investigation steps available.")

            with st.expander("Root Cause Analysis", expanded=True):
                st.write(root_cause)

            with st.expander("Recommendations", expanded=True):
                st.write(recommendations)

            st.markdown("---")
            st.markdown("### Business Impact")
            st.write(incident_analysis.get("business_impact", "No business impact details returned."))

            if st.button("Copy Analysis to Clipboard"):
                st.code(
                    "\n".join([
                        f"Severity: {incident_analysis.get('severity', 'N/A')}",
                        f"Confidence: {incident_analysis.get('confidence_score', 'N/A')}",
                        "---",
                        "Summary:",
                        incident_analysis.get("summary", ""),
                        "---",
                        "Root Cause:",
                        root_cause,
                        "---",
                        "Recommendations:",
                        recommendations,
                    ])
                )

        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to FastAPI backend.")
        except requests.exceptions.Timeout:
            st.error("Request timed out.")
        except Exception as ex:
            st.error(f"Unexpected error: {str(ex)}")