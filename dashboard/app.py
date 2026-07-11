import streamlit as st
import pandas as pd

st.set_page_config(page_title="Internal Metrics Dashboard", layout="wide")
st.title("📊 Enterprise Dashboard (Excel Resource)")

# 1. Fetch secure variable from Render Environment Config
try:
    EXCEL_URL = st.secrets["EXCEL_URL"]
except Exception:
    st.error("Missing configuration: Define 'EXCEL_URL' in your environment secrets.")
    st.stop()

# 2. Caching prevents lagging on every user mouse click
@st.cache_data(ttl=60)  # Data auto-refreshes every 60 seconds if users reload
def fetch_data(url):
    # openpyxl processes the raw spreadsheet stream 
    return pd.read_excel(url)

try:
    df = fetch_data(EXCEL_URL)
    
    # Simple metric overview blocks
    m1, m2 = st.columns(2)
    m1.metric("Total Document Rows", len(df))
    m2.metric("Data Engine Status", "Synchronized")

    st.markdown("### Interactive Worksheet Viewer")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error fetching live resource from Cloud Storage. Verify URL format. Details: {e}")