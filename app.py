import streamlit as st
import pandas as pd
from collections import deque
from datetime import time
import io
from PIL import Image as PILImage

# -------- PDF IMPORTS --------
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm

LOGO_FILE = "vignan_logo.png"

# ================= PDF GENERATION FUNCTION =================
def generate_pdf(grid, room_no, exam_name, exam_date_str, exam_time_range, logo_path=LOGO_FILE):
    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=20,
        rightMargin=20,
        topMargin=15,
        bottomMargin=15
    )

    styles = getSampleStyleSheet()
    elements = []

    # ---------- HEADER ----------
    logo = Image(logo_path, width=7.5 * cm, height=1.5 * cm)
    logo.hAlign = "CENTER"

    room_text = Paragraph(
        f"<b><font size='14'>ROOM NO : {room_no}</font></b>",
        styles["Normal"]
    )

    room_box = Table([[room_text]], colWidths=[6.5 * cm], rowHeights=[1.3 * cm])
    room_box.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 1.2, colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))

    header = Table([[logo, room_box]], colWidths=[21 * cm, 7 * cm])
    elements.append(header)
    elements.append(Spacer(1, 6))

    details = Table([
        ["Exam Name", exam_name],
        ["Date & Time", f"{exam_date_str}  {exam_time_range}"],
    ], colWidths=[6 * cm, 22 * cm])

    details.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 1, colors.black),
        ("INNERGRID", (0,0), (-1,-1), 0.5, colors.black),
    ]))

    elements.append(details)
    elements.append(Spacer(1, 6))

    # ---------- SEATING ----------
    table_data = []
    for row in grid:
        pdf_row = []
        for cell in row:
            if cell:
                cls, roll, sub = cell.split("\n")
                txt = (
                    f"<font size='5'>{cls}</font><br/>"
                    f"<font size='6'><b>{roll}</b></font><br/>"
                    f"<font size='4'>{sub}</font>"
                )
            else:
                txt = ""
            pdf_row.append(Paragraph(txt, styles["Normal"]))
        table_data.append(pdf_row)

    col_width = (27 * cm) / len(grid[0])
    seating = Table(
        table_data,
        colWidths=[col_width] * len(grid[0]),
        rowHeights=[2.4 * cm] * len(grid)
    )

    seating.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))

    elements.append(seating)
    pdf.build(elements)

    buffer.seek(0)
    return buffer


# ================= STREAMLIT APP =================
st.set_page_config(page_title="Seating Arrangement", layout="wide")

# -------- LOGO --------
col1, col2, col3 = st.columns([1,1,1])
with col2:
    logo = PILImage.open(LOGO_FILE)
    logo = logo.resize((750,150))
    st.image(logo)

st.title("🪑 Exam Seating Arrangement")

# -------- EXAM DETAILS --------
exam_name = st.text_input("Exam Name")
exam_date = st.date_input("Exam Date")
exam_date_str = exam_date.strftime("%d-%m-%Y")

start_time = st.time_input("Start Time", value=time(10,0))
end_time = st.time_input("End Time", value=time(11,30))
exam_time_range = f"{start_time.strftime('%I:%M %p')} – {end_time.strftime('%I:%M %p')}"

st.markdown("---")

# -------- ROOM DETAILS --------
room_no = st.text_input("Room Number", "LAB-1")
rows = st.number_input("Rows", min_value=1, value=4)
cols = st.number_input("Columns", min_value=1, value=4)

st.markdown("---")

# -------- EXCEL UPLOAD --------
uploaded = st.file_uploader("Upload Excel", type=["xlsx"])
if not uploaded:
    st.stop()

xls = pd.ExcelFile(uploaded)
sheets = xls.sheet_names

# INIT QUEUES
if "queues" not in st.session_state:
    st.session_state.queues = {}
    for s in sheets:
        df = pd.read_excel(uploaded, sheet_name=s)
        st.session_state.queues[s] = deque(zip(df["Roll_No"], df["Subject"]))

seat_type = st.radio("Seating Type", ["Only one section", "Different sections"])

# ================= ONLY ONE SECTION =================
if seat_type == "Only one section":

    sec = st.selectbox("Select Section", sheets)
    q = st.session_state.queues[sec]

    if st.button("Generate Seating"):
        grid = [["" for _ in range(cols)] for _ in range(rows)]

        for c in range(0, cols, 2):
            for r in range(rows):
                if q:
                    roll, sub = q.popleft()
                    grid[r][c] = f"{sec}\n{roll}\n{sub}"

        st.table(grid)
        pdf_file = generate_pdf(grid, room_no, exam_name, exam_date_str, exam_time_range)
        st.download_button("📄 Download PDF", pdf_file, file_name="Seating.pdf")

# ================= DIFFERENT SECTIONS =================
else:

    start_secs = st.multiselect("Select TWO sections to start", sheets)
    if len(start_secs) != 2:
        st.warning("Select exactly TWO sections")
        st.stop()

    remaining = [s for s in sheets if s not in start_secs]
    pool = start_secs + remaining

    if "active" not in st.session_state:
        st.session_state.active = pool[:2]
        st.session_state.ptr = 2

    if st.button("Generate Seating"):
        grid = [["" for _ in range(cols)] for _ in range(rows)]

        for r in range(rows):
            for c in range(cols):

                # replace finished section only
                for i in range(2):
                    if not st.session_state.queues[st.session_state.active[i]]:
                        if st.session_state.ptr < len(pool):
                            st.session_state.active[i] = pool[st.session_state.ptr]
                            st.session_state.ptr += 1

                secA, secB = st.session_state.active

                if c % 2 == 0 and st.session_state.queues[secA]:
                    roll, sub = st.session_state.queues[secA].popleft()
                    grid[r][c] = f"{secA}\n{roll}\n{sub}"
                elif c % 2 == 1 and st.session_state.queues[secB]:
                    roll, sub = st.session_state.queues[secB].popleft()
                    grid[r][c] = f"{secB}\n{roll}\n{sub}"

        st.table(grid)
        pdf_file = generate_pdf(grid, room_no, exam_name, exam_date_str, exam_time_range)
        st.download_button("📄 Download PDF", pdf_file, file_name="Seating.pdf")

# -------- FOOTER --------
st.markdown(
    """
    <style>
    .modern-footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background: linear-gradient(90deg,#0f2027,#203a43,#2c5364);
        color: white;
        text-align: center;
        padding: 10px;
        font-size: 14px;
        font-family: Segoe UI;
        box-shadow: 0 -2px 8px rgba(0,0,0,0.3);
    }
    </style>
    <div class="modern-footer">
        Developed by <b style="color:#ffd700;">Mr. A.N. Harshith Vardhan</b> | Department of Computer Applications
    </div>
    """,
    unsafe_allow_html=True
)
