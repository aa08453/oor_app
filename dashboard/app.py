import streamlit as st
import pandas as pd

st.set_page_config(page_title="Grant Tracker", layout="wide", page_icon=None)

DATE_COLS = ["Submission Date", "Decision Date", "Project Start Date", "Project End Date", "Closure Date"]
NUMERIC_COLS = ["Review Score", "Amount Requested", "Amount Approved",
                "Publications Produced", "Students Involved", "Budget Utilization %"]

STATUS_COLORS = {
    "Proposed": "#9e9e9e", "Under Review": "#f0ad4e", "Approved": "#5bc0de",
    "In Progress": "#428bca", "Completed": "#5cb85c", "Closed": "#6c757d", "Rejected": "#d9534f",
}

# The full set of columns the app knows how to display. Anything not present in the
# uploaded file is simply never shown — no defaults, no placeholders, no notices.
ALL_KNOWN_COLUMNS = [
    "S No", "Grant ID", "Cycle/Year", "PI Name", "Department", "Proposal Title",
    "Submission Date", "Eligibility Confirmed", "Reviewer Names", "Review Score",
    "Recommendation", "Decision", "Decision Date", "Amount Requested", "Amount Approved",
    "Project Start Date", "Project End Date", "Ethics Required", "Ethics Approved",
    "Progress Report Submitted", "Final Report Submitted", "Publications Produced",
    "Students Involved", "Budget Utilization %", "Project Status", "Closure Date", "Remarks",
]

# ──────────────────────────────────────────────────────────────
# HEADER DETECTION — find the real header row even if there are
# blank rows/columns before it, matching column names loosely
# (case/whitespace-insensitive).
# ──────────────────────────────────────────────────────────────
def _normalize(s):
    return str(s).strip().lower() if pd.notna(s) else ""

def find_header_row(raw, max_scan=25):
    known_lower = {_normalize(c) for c in ALL_KNOWN_COLUMNS}
    best_row, best_score = 0, -1
    for i in range(min(max_scan, len(raw))):
        row_vals = [_normalize(v) for v in raw.iloc[i].tolist()]
        score = sum(1 for v in row_vals if v in known_lower)
        if score > best_score:
            best_score, best_row = score, i
    return best_row

def load_and_adapt(file_bytes):
    """Reads the uploaded Excel file and finds the header row wherever it is.
    Only columns that actually exist in the file are kept — nothing is invented,
    nothing is filled in. An internal row id is added purely for routing between
    the list and detail views; it is never shown to the user."""
    raw = pd.read_excel(file_bytes, header=None)
    header_row_idx = find_header_row(raw)

    header_vals = raw.iloc[header_row_idx].tolist()
    data = raw.iloc[header_row_idx + 1:].reset_index(drop=True)

    known_by_norm = {_normalize(c): c for c in ALL_KNOWN_COLUMNS}
    new_columns = []
    for i, h in enumerate(header_vals):
        norm = _normalize(h)
        if norm in known_by_norm:
            new_columns.append(known_by_norm[norm])
        elif norm:
            new_columns.append(str(h).strip())
        else:
            new_columns.append(f"_blank_{i}")
    data.columns = new_columns

    # Drop fully blank leading/trailing columns and blank rows.
    data = data.loc[:, [c for c in data.columns if not c.startswith("_blank_")]]
    data = data.dropna(how="all").reset_index(drop=True)

    present_date_cols = [c for c in DATE_COLS if c in data.columns]
    present_numeric_cols = [c for c in NUMERIC_COLS if c in data.columns]
    for c in present_date_cols:
        data[c] = pd.to_datetime(data[c], errors="coerce")
    for c in present_numeric_cols:
        data[c] = pd.to_numeric(data[c], errors="coerce")

    # Internal identifier for routing between list/detail views — not a data field,
    # never displayed, just plumbing so clicking a card works regardless of whether
    # the file has an "S No" column at all.
    data["_row_id"] = range(len(data))

    return data

@st.cache_data
def load_data(file_bytes):
    return load_and_adapt(file_bytes)

def has(data, col):
    """Whether a column genuinely exists in the uploaded file's data (not just present
    as an all-null artifact) — used everywhere to decide whether to render something."""
    return col in data.columns

# ──────────────────────────────────────────────────────────────
# SIDEBAR — upload only, no download/write-back
# ──────────────────────────────────────────────────────────────
st.sidebar.header("Data file")
uploaded = st.sidebar.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

st.title("Grant Tracker Dashboard")

if uploaded is None:
    st.info("Upload your Excel file from the sidebar to get started.")
    st.stop()

try:
    df = load_data(uploaded)
except Exception as e:
    st.error(f"Couldn't read this file. Make sure it's a valid Excel file. ({e})")
    st.stop()

# ──────────────────────────────────────────────────────────────
# SORT / FILTER CONTROLS — only offered for columns that exist
# ──────────────────────────────────────────────────────────────
st.sidebar.header("Filter & sort")

f_year = f_dept = f_status = "All"
if has(df, "Cycle/Year"):
    years = ["All"] + sorted(df["Cycle/Year"].dropna().unique().tolist())
    f_year = st.sidebar.selectbox("Cycle/Year", years)
if has(df, "Department"):
    depts = ["All"] + sorted(df["Department"].dropna().unique().tolist())
    f_dept = st.sidebar.selectbox("Department", depts)
if has(df, "Project Status"):
    statuses_present = ["All"] + sorted(df["Project Status"].dropna().unique().tolist())
    f_status = st.sidebar.selectbox("Project Status", statuses_present)

sort_options = [c for c in ["Project Status", "Cycle/Year", "Department", "Submission Date", "Amount Requested"] if has(df, c)]
filtered = df.copy()

if sort_options:
    sort_by = st.sidebar.selectbox("Sort by", sort_options)
    sort_dir = st.sidebar.radio("Order", ["Ascending", "Descending"], horizontal=True)
    if has(df, "Cycle/Year") and f_year != "All":
        filtered = filtered[filtered["Cycle/Year"] == f_year]
    if has(df, "Department") and f_dept != "All":
        filtered = filtered[filtered["Department"] == f_dept]
    if has(df, "Project Status") and f_status != "All":
        filtered = filtered[filtered["Project Status"] == f_status]
    filtered = filtered.sort_values(by=sort_by, ascending=(sort_dir == "Ascending"))

# ──────────────────────────────────────────────────────────────
# FORMAT HELPERS
# ──────────────────────────────────────────────────────────────
def fmt_date(value):
    if pd.isna(value):
        return "—"
    return value.strftime("%Y-%m-%d")

def fmt_num(value, decimals=0):
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}"

def fmt_text(value):
    if pd.isna(value) or str(value).strip() == "":
        return "—"
    return str(value)

def line(container, data, row, label, col, formatter=fmt_text, **kwargs):
    """Render '**label:** value' only if the column exists in the file."""
    if has(data, col):
        val = row[col]
        formatted = formatter(val, **kwargs) if kwargs else formatter(val)
        container.write(f"**{label}:** {formatted}")

# ──────────────────────────────────────────────────────────────
# STATS — only shown for columns that exist, recomputed on filtered set
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
    cards = [_stat_card("Total entries", f"{len(data):,}")]

    if has(data, "Amount Requested"):
        cards.append(_stat_card("Total requested", fmt_num(data["Amount Requested"].sum()), "PKR"))
    if has(data, "Amount Approved"):
        cards.append(_stat_card("Total approved", fmt_num(data["Amount Approved"].sum(skipna=True)), "PKR"))
    if has(data, "Review Score"):
        avg_score = fmt_num(data["Review Score"].mean(), 1) if len(data) else "—"
        cards.append(_stat_card("Avg. review score", avg_score, "/ 10"))
    if has(data, "Project Status"):
        cards.append(_stat_card("In progress", f"{int((data['Project Status'] == 'In Progress').sum()):,}"))
        cards.append(_stat_card("Completed", f"{int((data['Project Status'] == 'Completed').sum()):,}"))
        cards.append(_stat_card("Rejected", f"{int((data['Project Status'] == 'Rejected').sum()):,}"))
    if has(data, "Publications Produced"):
        cards.append(_stat_card("Total publications", f"{int(data['Publications Produced'].sum()):,}"))
    if has(data, "Budget Utilization %"):
        avg_util = fmt_num(data["Budget Utilization %"].mean(), 1) if len(data) else "—"
        cards.append(_stat_card("Avg. budget utilization", avg_util, "%"))

    if len(cards) <= 1:
        return  # nothing meaningful to show beyond entry count

    st.markdown(STAT_CARD_CSS, unsafe_allow_html=True)
    st.subheader("Summary statistics")

    row1, row2 = cards[:5], cards[5:]
    st.markdown(f"<div class='stat-grid'>{''.join(row1)}</div>", unsafe_allow_html=True)
    if row2:
        st.markdown(f"<div class='stat-grid'>{''.join(row2)}</div>", unsafe_allow_html=True)

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
                with st.container(border=True):
                    if has(data, "Project Status"):
                        color = STATUS_COLORS.get(row["Project Status"], "#9e9e9e")
                        st.markdown(
                            f"<span style='background-color:{color};color:white;"
                            f"padding:2px 8px;border-radius:10px;font-size:0.8em'>"
                            f"{fmt_text(row['Project Status'])}</span>",
                            unsafe_allow_html=True,
                        )
                    if has(data, "Proposal Title"):
                        st.markdown(f"**{fmt_text(row['Proposal Title'])}**")
                    caption_bits = [fmt_text(row[c]) for c in ("Grant ID", "Cycle/Year") if has(data, c)]
                    if caption_bits:
                        st.caption(" · ".join(caption_bits))
                    info_bits = [fmt_text(row[c]) for c in ("PI Name", "Department") if has(data, c)]
                    if info_bits:
                        st.write("  \n".join(info_bits))
                    if has(data, "Amount Requested"):
                        st.write(f"Requested: PKR {fmt_num(row['Amount Requested'])}")
                    if st.button("View details", key=f"view_{row['_row_id']}", use_container_width=True):
                        st.session_state.selected_row_id = row["_row_id"]
                        st.session_state.mode = "detail"
                        st.rerun()

# ──────────────────────────────────────────────────────────────
# DETAIL VIEW
# ──────────────────────────────────────────────────────────────
def render_detail(data, row_id):
    entry = data[data["_row_id"] == row_id]
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

    if has(data, "Project Status"):
        color = STATUS_COLORS.get(row["Project Status"], "#9e9e9e")
        st.markdown(
            f"<span style='background-color:{color};color:white;padding:4px 12px;"
            f"border-radius:12px;font-size:0.9em'>{fmt_text(row['Project Status'])}</span>",
            unsafe_allow_html=True,
        )
    st.header(fmt_text(row["Proposal Title"]) if has(data, "Proposal Title") else "Entry details")
    caption_bits = [fmt_text(row[c]) for c in ("Grant ID", "Cycle/Year", "Department") if has(data, c)]
    if caption_bits:
        st.caption(" · ".join(caption_bits))

    tab1, tab2, tab3 = st.tabs(["Overview", "Timeline & Budget", "Deliverables & Remarks"])

    with tab1:
        c1, c2 = st.columns(2)
        line(c1, data, row, "PI Name", "PI Name")
        line(c1, data, row, "Reviewer(s)", "Reviewer Names")
        line(c1, data, row, "Review Score", "Review Score", fmt_num, decimals=1)
        line(c1, data, row, "Recommendation", "Recommendation")
        line(c2, data, row, "Decision", "Decision")
        line(c2, data, row, "Decision Date", "Decision Date", fmt_date)
        line(c2, data, row, "Eligibility Confirmed", "Eligibility Confirmed")

    with tab2:
        c1, c2 = st.columns(2)
        line(c1, data, row, "Submission Date", "Submission Date", fmt_date)
        line(c1, data, row, "Project Start Date", "Project Start Date", fmt_date)
        line(c1, data, row, "Project End Date", "Project End Date", fmt_date)
        line(c1, data, row, "Closure Date", "Closure Date", fmt_date)
        if has(data, "Amount Requested"):
            c2.write(f"**Amount Requested:** PKR {fmt_num(row['Amount Requested'])}")
        if has(data, "Amount Approved"):
            approved = row["Amount Approved"]
            c2.write(f"**Amount Approved:** {'PKR ' + fmt_num(approved) if pd.notna(approved) else '—'}")
        if has(data, "Budget Utilization %"):
            util = row["Budget Utilization %"]
            c2.write(f"**Budget Utilization:** {fmt_num(util, 1)}%")
            st.progress(min(float(util) / 100, 1.0) if pd.notna(util) else 0.0)

    with tab3:
        c1, c2 = st.columns(2)
        line(c1, data, row, "Ethics Required", "Ethics Required")
        line(c1, data, row, "Ethics Approved", "Ethics Approved")
        line(c1, data, row, "Progress Report Submitted", "Progress Report Submitted")
        line(c1, data, row, "Final Report Submitted", "Final Report Submitted")
        line(c2, data, row, "Publications Produced", "Publications Produced", fmt_num)
        line(c2, data, row, "Students Involved", "Students Involved", fmt_num)
        if has(data, "Remarks"):
            st.write("**Remarks:**")
            remark = fmt_text(row["Remarks"])
            st.info(remark if remark != "—" else "No remarks recorded.")

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
    render_detail(df, st.session_state.selected_row_id)