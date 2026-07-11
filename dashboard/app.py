import streamlit as st
import pandas as pd

st.set_page_config(page_title="Grant Tracker", layout="wide", page_icon=None)

DATE_COLS = ["Submission Date", "Decision Date", "Project Start Date", "Project End Date", "Closure Date"]

STATUS_COLORS = {
    "Proposed": "#9e9e9e", "Under Review": "#f0ad4e", "Approved": "#5bc0de",
    "In Progress": "#428bca", "Completed": "#5cb85c", "Closed": "#6c757d", "Rejected": "#d9534f",
}

REQUIRED_COLUMNS = [
    "S No", "Grant ID", "Cycle/Year", "PI Name", "Department", "Proposal Title",
    "Submission Date", "Eligibility Confirmed", "Reviewer Names", "Review Score",
    "Recommendation", "Decision", "Decision Date", "Amount Requested", "Amount Approved",
    "Project Start Date", "Project End Date", "Ethics Required", "Ethics Approved",
    "Progress Report Submitted", "Final Report Submitted", "Publications Produced",
    "Students Involved", "Budget Utilization %", "Project Status", "Closure Date", "Remarks",
]

# ──────────────────────────────────────────────────────────────
# LOAD (from the uploaded file only — nothing is written back, ever)
# ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data(file_bytes):
    df = pd.read_excel(file_bytes)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected column(s): {', '.join(missing)}")
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    return df

# ──────────────────────────────────────────────────────────────
# SIDEBAR — upload only, no download/write-back
# ──────────────────────────────────────────────────────────────
st.sidebar.header("Data file")
uploaded = st.sidebar.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

st.title("Grants Visualization Dashboard")

if uploaded is None:
    st.info("Upload your Excel file from the sidebar to get started.")
    st.stop()

try:
    df = load_data(uploaded)
except ValueError as e:
    st.error(f"This file doesn't look right: {e}")
    st.stop()
except Exception as e:
    st.error(f"Couldn't read this file. Make sure it's a valid Excel file. ({e})")
    st.stop()

# ──────────────────────────────────────────────────────────────
# SORT / FILTER CONTROLS
# ──────────────────────────────────────────────────────────────
st.sidebar.header("Filter & sort")
years = ["All"] + sorted(df["Cycle/Year"].dropna().unique().tolist())
depts = ["All"] + sorted(df["Department"].dropna().unique().tolist())
statuses_present = ["All"] + sorted(df["Project Status"].dropna().unique().tolist())

f_year = st.sidebar.selectbox("Cycle/Year", years)
f_dept = st.sidebar.selectbox("Department", depts)
f_status = st.sidebar.selectbox("Project Status", statuses_present)
sort_by = st.sidebar.selectbox("Sort by", ["Project Status", "Cycle/Year", "Department", "Submission Date", "Amount Requested"])
sort_dir = st.sidebar.radio("Order", ["Ascending", "Descending"], horizontal=True)

filtered = df.copy()
if f_year != "All":
    filtered = filtered[filtered["Cycle/Year"] == f_year]
if f_dept != "All":
    filtered = filtered[filtered["Department"] == f_dept]
if f_status != "All":
    filtered = filtered[filtered["Project Status"] == f_status]

filtered = filtered.sort_values(by=sort_by, ascending=(sort_dir == "Ascending"))

# ──────────────────────────────────────────────────────────────
# STATS — recompute on filtered set
# ──────────────────────────────────────────────────────────────
STAT_CARD_CSS = """
<style>
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 8px;
}
.stat-card {
    background: #f7f8fa;
    border: 1px solid #e3e5e8;
    border-radius: 8px;
    padding: 12px 16px;
}
.stat-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 4px;
}
.stat-value {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1f2937;
    line-height: 1.2;
}
.stat-unit {
    font-size: 0.85rem;
    font-weight: 500;
    color: #6b7280;
    margin-left: 3px;
}
</style>
"""

def _stat_card(label, value, unit=""):
    return (
        f"<div class='stat-card'>"
        f"<div class='stat-label'>{label}</div>"
        f"<div class='stat-value'>{value}<span class='stat-unit'>{unit}</span></div>"
        f"</div>"
    )

def render_stats(data):
    st.markdown(STAT_CARD_CSS, unsafe_allow_html=True)
    st.subheader("Summary statistics")

    avg_score = f"{data['Review Score'].mean():.1f}" if len(data) else "—"
    avg_util = f"{data['Budget Utilization %'].mean():.1f}" if len(data) else "—"

    cards_row1 = [
        _stat_card("Total entries", f"{len(data):,}"),
        _stat_card("Total requested", f"{data['Amount Requested'].sum():,.0f}", "PKR"),
        _stat_card("Total approved", f"{data['Amount Approved'].sum(skipna=True):,.0f}", "PKR"),
        _stat_card("Avg. review score", avg_score, "/ 10"),
        _stat_card("In progress", f"{int((data['Project Status'] == 'In Progress').sum()):,}"),
    ]
    cards_row2 = [
        _stat_card("Completed", f"{int((data['Project Status'] == 'Completed').sum()):,}"),
        _stat_card("Rejected", f"{int((data['Project Status'] == 'Rejected').sum()):,}"),
        _stat_card("Total publications", f"{int(data['Publications Produced'].sum()):,}"),
        _stat_card("Avg. budget utilization", avg_util, "%"),
    ]

    st.markdown(f"<div class='stat-grid'>{''.join(cards_row1)}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-grid'>{''.join(cards_row2)}</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# CARD VIEW
# ──────────────────────────────────────────────────────────────
def render_cards(data):
    st.subheader(f"Entries ({len(data)})")
    if len(data) == 0:
        st.info("No entries match the current filters.")
        return

    cols_per_row = 3
    rows_of_data = [data.iloc[i:i + cols_per_row] for i in range(0, len(data), cols_per_row)]

    for chunk in rows_of_data:
        cols = st.columns(cols_per_row)
        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                color = STATUS_COLORS.get(row["Project Status"], "#9e9e9e")
                with st.container(border=True):
                    st.markdown(
                        f"<span style='background-color:{color};color:white;"
                        f"padding:2px 8px;border-radius:10px;font-size:0.8em'>"
                        f"{row['Project Status']}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**{row['Proposal Title']}**")
                    st.caption(f"{row['Grant ID']} · {row['Cycle/Year']}")
                    st.write(f"{row['PI Name']}  \n{row['Department']}")
                    st.write(f"Requested: PKR {row['Amount Requested']:,.0f}")
                    if st.button("View details", key=f"view_{row['S No']}", use_container_width=True):
                        st.session_state.selected_s_no = row["S No"]
                        st.session_state.mode = "detail"
                        st.rerun()

# ──────────────────────────────────────────────────────────────
# DETAIL VIEW
# ──────────────────────────────────────────────────────────────
def render_detail(data, s_no):
    entry = data[data["S No"] == s_no]
    if entry.empty:
        st.warning("Entry not found (it may have been filtered out).")
        if st.button("← Back to list"):
            st.session_state.mode = "list"
            st.rerun()
        return
    row = entry.iloc[0]

    if st.button("← Back to list"):
        st.session_state.mode = "list"
        st.rerun()

    color = STATUS_COLORS.get(row["Project Status"], "#9e9e9e")
    st.markdown(
        f"<span style='background-color:{color};color:white;padding:4px 12px;"
        f"border-radius:12px;font-size:0.9em'>{row['Project Status']}</span>",
        unsafe_allow_html=True,
    )
    st.header(row["Proposal Title"])
    st.caption(f"{row['Grant ID']} · {row['Cycle/Year']} · {row['Department']}")

    tab1, tab2, tab3 = st.tabs(["Overview", "Timeline & Budget", "Deliverables & Remarks"])

    with tab1:
        c1, c2 = st.columns(2)
        c1.write(f"**PI Name:** {row['PI Name']}")
        c1.write(f"**Reviewer(s):** {row['Reviewer Names']}")
        c1.write(f"**Review Score:** {row['Review Score']}")
        c1.write(f"**Recommendation:** {row['Recommendation']}")
        c2.write(f"**Decision:** {row['Decision']}")
        c2.write(f"**Decision Date:** {row['Decision Date']}")
        c2.write(f"**Eligibility Confirmed:** {row['Eligibility Confirmed']}")

    with tab2:
        c1, c2 = st.columns(2)
        c1.write(f"**Submission Date:** {row['Submission Date']}")
        c1.write(f"**Project Start Date:** {row['Project Start Date']}")
        c1.write(f"**Project End Date:** {row['Project End Date']}")
        c1.write(f"**Closure Date:** {row['Closure Date']}")
        c2.write(f"**Amount Requested:** PKR {row['Amount Requested']:,.0f}")
        approved = row['Amount Approved']
        c2.write(f"**Amount Approved:** {'PKR ' + format(approved, ',.0f') if pd.notna(approved) else '—'}")
        c2.write(f"**Budget Utilization:** {row['Budget Utilization %']}%")
        st.progress(min(float(row["Budget Utilization %"]) / 100, 1.0))

    with tab3:
        c1, c2 = st.columns(2)
        c1.write(f"**Ethics Required:** {row['Ethics Required']}")
        c1.write(f"**Ethics Approved:** {row['Ethics Approved']}")
        c1.write(f"**Progress Report Submitted:** {row['Progress Report Submitted']}")
        c1.write(f"**Final Report Submitted:** {row['Final Report Submitted']}")
        c2.write(f"**Publications Produced:** {row['Publications Produced']}")
        c2.write(f"**Students Involved:** {row['Students Involved']}")
        st.write("**Remarks:**")
        st.info(row["Remarks"] if row["Remarks"] else "No remarks recorded.")

# ──────────────────────────────────────────────────────────────
# ROUTER
# ──────────────────────────────────────────────────────────────
if "mode" not in st.session_state:
    st.session_state.mode = "list"

if st.session_state.mode == "list":
    render_stats(filtered)
    st.divider()
    render_cards(filtered)
elif st.session_state.mode == "detail":
    render_detail(df, st.session_state.selected_s_no)