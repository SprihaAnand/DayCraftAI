import streamlit as st

def render_header():
    st.set_page_config(
        page_title="AI Productivity Assistant with Visualizations",
        page_icon="🤖",
        layout="wide"
    )
    st.title("🤖 AI Productivity Assistant")
    st.markdown("*Powered by Google Gemini AI with Advanced Visualizations*")
    st.markdown("---")
