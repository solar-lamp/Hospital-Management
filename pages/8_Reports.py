import streamlit as st

from services import report_service
from utils import clock, ui
from utils.export_utils import to_csv_bytes, to_excel_bytes

user = ui.require_page("reports.view")

st.title("Reports")
st.caption("Filters are applied before export. Choose only the columns you need; exported "
           "text is protected against spreadsheet formula injection.")

reports = report_service.available_reports(user)
key = st.selectbox("Report", list(reports), format_func=reports.get)
start, end = ui.date_range("rep", default_days=30)
df = report_service.run_report(user, key, start, end)

if df.empty:
    st.info("No records for the selected filters.")
else:
    columns = st.multiselect("Columns", list(df.columns), default=list(df.columns))
    shown = df[columns] if columns else df
    st.caption(f"{len(shown)} row(s)")
    st.dataframe(shown, hide_index=True, width="stretch")
    name = f"{key}_{start}_{end}"
    c1, c2 = st.columns(2)
    c1.download_button("Download CSV", to_csv_bytes(df, columns or None), f"{name}.csv",
                       "text/csv", width="stretch")
    c2.download_button("Download Excel", to_excel_bytes(df, columns or None, reports[key]),
                       f"{name}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")
st.caption(f"Generated {clock.ts()} by {user['username']}.")
