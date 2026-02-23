import streamlit as st
import time
import os
import base64
from src.backend import (
    generate_next_question, 
    is_skill_vague, 
    get_clarification_question, 
    generate_roadmap, 
    generate_user_profile_summary,
    wrap_html
)
from reportlab.platypus import Table, TableStyle
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListItem, ListFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
import re
import io

# ---------------- IMAGE ENCODING ----------------
def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

try:
    hero_img_base64 = get_base64_image(os.path.join("static", "image.png"))
except Exception:
    hero_img_base64 = "" # Fallback if image missing

st.set_page_config(page_title="RAAH AI - Your Career Roadmap", layout="wide")
# ---------------- SIDEBAR STYLING ----------------
st.markdown("""
<style>
/* Sidebar background (optional, light gray to not clash) */
[data-testid="stSidebar"] {
    background-color: #1e1e1e;
}

/* Sidebar title "RAAH AI 🚀" color */
[data-testid="stSidebar"] .css-1d391kg h1,
[data-testid="stSidebar"] .css-1d391kg h2 {
    background: linear-gradient(90deg, #008080, #00FFFF, #4B0082);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* "Your Progress" labels color */
[data-testid="stSidebar"] .css-1d391kg p,
[data-testid="stSidebar"] .css-1d391kg span {
    color: #00FFFF;
}

/* Reset button color persistent */
[data-testid="stSidebar"] div.stButton > button {
    background-color: transparent !important;
    border: 2px solid #4B0082 !important;
    color: #00FFFF !important;
    padding: 10px 20px !important;
    font-weight: bold !important;
    border-radius: 10px !important;
    transition: 0.3s !important;
}

[data-testid="stSidebar"] div.stButton > button:hover {
    transform: scale(1.03);
    border-color: #00FFFF !important;
}
</style>
""", unsafe_allow_html=True)
# ---------------- SESSION STATE INITIALIZATION ----------------
if "started" not in st.session_state:
    st.session_state.started = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "user_context" not in st.session_state:
    st.session_state.user_context = {}
if "current_field" not in st.session_state:
    st.session_state.current_field = None
if "finalized" not in st.session_state:
    st.session_state.finalized = False
if "clarification_count" not in st.session_state:
    st.session_state.clarification_count = 0
if "roadmap_text" not in st.session_state:
    st.session_state.roadmap_text = ""
if "profile_summary" not in st.session_state:
    st.session_state.profile_summary = ""
if "awaiting_confirmation" not in st.session_state:
    st.session_state.awaiting_confirmation = False
# ---------------- RESET APP ----------------
def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ---------------- UI HELPERS ----------------
def add_message(role, content):
    st.session_state.chat_history.append({"role": role, "content": content})

def stream_text(text, placeholder):
    """Simulates a typing animation by updating the placeholder word by word."""
    full_text = ""
    for word in text.split():
        full_text += word + " "
        placeholder.markdown(full_text + "▌")
        time.sleep(0.04)  # Adjust speed here
    placeholder.markdown(full_text)

def create_pdf_reportlab(summary_html, roadmap_html):
    """Generates a PDF from the HTML content using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # ---- Custom Styles (UNCHANGED) ----
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor("#4A90E2"),
        alignment=TA_CENTER,
        spaceAfter=20
    )

    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor("#4A90E2"),
        spaceBefore=15,
        spaceAfter=10,
        borderLeftColor=colors.HexColor("#4A90E2"),
        borderLeftWidth=3,
        borderPadding=5
    )

    body_style = styles['BodyText']

    elements = []

    # ---- Title ----
    elements.append(Paragraph("RAAH AI Career Roadmap", title_style))
    elements.append(Spacer(1, 20))

    SECTION_TITLES = [
        "Executive Summary",
        "Learning Phases",
        "Weekly Breakdown",
        "Recommended Resources",
        "Tips and Notes"
    ]

    from reportlab.platypus import Table, TableStyle

    def html_to_flowables(html_text):
        flowables = []

        # ---------- TABLE HANDLING ----------
        tables = re.findall(r"<table.*?>.*?</table>", html_text, re.DOTALL)

        for table_html in tables:
            rows = re.findall(r"<tr>(.*?)</tr>", table_html, re.DOTALL)
            table_data = []

            for row in rows:
                cells = re.findall(r"<t[hd]>(.*?)</t[hd]>", row, re.DOTALL)
                clean_cells = [re.sub(r'<.*?>', '', cell).strip() for cell in cells]
                table_data.append(clean_cells)

            if table_data:
                rl_table = Table(table_data, hAlign='LEFT')

                rl_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4A90E2")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))

                flowables.append(rl_table)
                flowables.append(Spacer(1, 15))

        # Remove tables from text so they don't render twice
        html_text = re.sub(r"<table.*?>.*?</table>", "", html_text, flags=re.DOTALL)

        # ---------- NORMAL BLOCK PROCESSING ----------
        blocks = re.split(
            r'(<h2.*?>|</h2>|<h3.*?>|</h3>|<p.*?>|</p>|<ul.*?>|</ul>|<li>|</li>)',
            html_text
        )

        in_list = False
        list_items = []

        for block in blocks:
            clean_block = re.sub(r'<.*?>', '', block).strip()
            if not clean_block:
                continue

            # Force Section Titles Blue
            if any(clean_block.startswith(title) for title in SECTION_TITLES):
                flowables.append(Paragraph(clean_block, section_style))
                continue

            # Handle Lists
            if "<ul>" in block:
                in_list = True
                list_items = []
                continue

            if "</ul>" in block:
                if list_items:
                    flowables.append(ListFlowable(list_items, bulletType='bullet'))
                in_list = False
                continue

            if "<li>" in block:
                continue

            if "</li>" in block:
                if in_list:
                    list_items.append(ListItem(Paragraph(clean_block, body_style)))
                continue

            # Everything else normal paragraph
            if in_list:
                list_items.append(ListItem(Paragraph(clean_block, body_style)))
            else:
                flowables.append(Paragraph(clean_block, body_style))

        return flowables

    # ---- User Profile Summary ----
    elements.append(Paragraph("User Profile Summary", section_style))
    elements.extend(html_to_flowables(summary_html))
    elements.append(Spacer(1, 20))

    # ---- Roadmap ----
    elements.extend(html_to_flowables(roadmap_html))

    # ---- Footer ----
    elements.append(Spacer(1, 40))
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Italic'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    elements.append(
        Paragraph(
            "Generated by RAAH AI - Your Personalized Career Growth Assistant",
            footer_style
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown(f"""
    <div style="
        font-size:2rem;
        font-weight:800;
        background: linear-gradient(90deg, #008080, #00FFFF, #4B0082);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    ">
        RAAH AI
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    if st.session_state.user_context:
        st.markdown(f"""
        <div style="
            font-size:1.25rem;
            font-weight:700;
            background: linear-gradient(90deg, #009090, #00FFFF, #4B0082);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom:10px;
        ">
            Your Progress
        </div>
        """, unsafe_allow_html=True)
        for k, v in st.session_state.user_context.items():
            label = k.replace('_', ' ').capitalize()
            # Truncate long values
            display_val = (v[:30] + '...') if len(str(v)) > 30 else v
            st.write(f"**{label}:** {display_val}")
    else:
        st.info("Start the conversation to see your progress here!")
    
    st.markdown("---")
    if st.button("Reset Session", use_container_width=True):
        reset_app()

# ---------------- LANDING PAGE ----------------
if not st.session_state.started:
    # Custom CSS for the button
    st.markdown("""
    <style>
        div.stButton > button {
            background-color: transparent !important;
            border: 2px solid #4B0082 !important;
            color: #00FFFF !important;
            padding: 12px 35px !important;
            font-weight: bold !important;
            font-size: 1.1rem !important;
            border-radius: 10px !important;
            transition: 0.3s !important;
            margin-top: 20px !important;
        }
        div.stButton > button:hover {
            transform: scale(1.03);
            border-color: #00FFFF !important;
        }
    </style>
    """, unsafe_allow_html=True)
    logo_path = os.path.join("static", "images.png")
    if not st.session_state.started:
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                img_bytes = f.read()
            encoded_logo = base64.b64encode(img_bytes).decode()
        else:
            encoded_logo = None
    # Hero Section (StudyMate-style, only landing page)
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px;">
        <div>
            <div style="
                font-size:5rem;
                font-weight:800;
                background: linear-gradient(90deg, #008080, #00FFFF, #4B0082);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            ">
                RAAH AI
            </div>
            <div style="font-size:1.2rem; color:#636e72; margin-top:5px;">
                Navigate your career path with AI-driven clarity. Build a personalized learning roadmap tailored to your goals, budget, and schedule.            
            </div>
        </div>
        <div>
            {f'<img src="data:image/jpg;base64,{encoded_logo}" style="width:500px;" />' if encoded_logo else '<div style="width:150px;height:150px;background:#ddd;"></div>'}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Functional button placed below the left text area via flow
    if st.button("Get Started →"):
        st.session_state.started = True
        with st.spinner("RAAH AI is waking up... ⏳"):
            field, question = generate_next_question([], {})
            st.session_state.current_field = field
            st.session_state.pending_stream = question
        st.rerun()

# ---------------- ROADMAP PAGE ----------------
elif st.session_state.finalized:
    st.markdown(f"""
<div style="display:flex; align-items:center; justify-content:flex-start; margin-bottom:20px;">
    <div>
        <div style="
            font-size:5rem;
            font-weight:800;
            background: linear-gradient(90deg, #008080, #00FFFF, #4B0082);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        ">
            Your Personalized Roadmap 🗺️
        </div>
        <div style="font-size:1.2rem; color:#636e72; margin-top:5px;">
            Here’s your tailored learning path, crafted by RAAH AI just for you.            
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
    st.markdown("---")
    
    # Display AI-generated Summary in HTML
    st.markdown(f"""
<div style="
    padding:20px;
    border-radius:12px;
    background: linear-gradient(135deg, #004d4d, #008080);
    border-left: 5px solid #00FFFF;
    font-family: Time New Roman, sans-serif;
    color: #e0f7fa;  /* light text to contrast dark bg */
    font-size:1rem;
">
    <strong>👤 Your Profile Summary</strong><br><br>
    {st.session_state.profile_summary}
</div>
""", unsafe_allow_html=True)
    st.markdown("---")
    # Display Roadmap in HTML
    st.markdown(f"""
<div style="
    padding:20px;
    border-radius:12px;
    background: linear-gradient(135deg, #004d4d, #008080);
    border-left: 5px solid #00FFFF;
    font-family: 'Times New Roman', sans-serif;
    color: #e0f7fa;
    font-size:1rem;
">
    {st.session_state.roadmap_text}
</div>
""", unsafe_allow_html=True)
    
    st.markdown("---")
    col1, col2 = st.columns([1, 1])
    with col1:
        # PDF Export using ReportLab (Pure Python, Cloud Compatible)
        with st.spinner("Generating PDF..."):
            try:
                pdf_bytes = create_pdf_reportlab(st.session_state.profile_summary, st.session_state.roadmap_text)
                st.markdown(f"""
<style>
.download-btn {{
    background-color: transparent !important;
    border: 2px solid #4B0082 !important;
    color: #00FFFF !important;
    padding: 12px 35px !important;
    font-weight: bold !important;
    font-size: 1.1rem !important;
    border-radius: 10px !important;
    transition: 0.3s !important;
}}
.download-btn:hover {{
    transform: scale(1.03);
    border-color: #00FFFF !important;
}}
</style>
<a href="data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode()}" download="raaahi_roadmap.pdf" class="download-btn">Download Roadmap as PDF 📄</a>
""", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error generating PDF: {e}")
                st.info("Ensure the reportlab library is installed.")


# ---------------- CHAT PAGE ----------------
# ---------------- CHAT PAGE ----------------
else:
    # Gradient header
    st.markdown("""
    <div style="
        font-size:3rem;
        font-weight:800;
        background: linear-gradient(90deg, #008080, #00FFFF, #4B0082);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom:20px;
    ">
        RAAH AI Chat 💬
    </div>
    """, unsafe_allow_html=True)
    
    # Display chat history with emoji avatars
    for msg in st.session_state.chat_history:
        emoji = "🤖" if msg["role"] == "assistant" else "🧑"
        with st.chat_message(msg["role"], avatar=emoji):
            st.markdown(msg["content"])

    # Handle streamed response if pending
    if "pending_stream" in st.session_state:
        question = st.session_state.pop("pending_stream")
        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            stream_text(question, placeholder)
        add_message("assistant", question)

    # Chat input with emoji avatar
    user_input = st.chat_input("Share your details here...")
    
    if user_input:
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(user_input)
        add_message("user", user_input)
        
        with st.spinner("RAAH AI is thinking... ⏳"):
            current_field = st.session_state.current_field
            
            # --- SKILL CLARIFICATION LOGIC ---
            if current_field == "skill_to_learn" and st.session_state.clarification_count < 2:
                if is_skill_vague(user_input):
                    st.session_state.clarification_count += 1
                    clarification_q = get_clarification_question(user_input)
                    st.session_state.pending_stream = clarification_q
                    st.rerun()
            
            # --- REGULAR FIELD COLLECTION ---
            st.session_state.user_context[current_field] = user_input
            
            # Generate next question or finalize
            next_field, next_question = generate_next_question(
                st.session_state.chat_history, 
                st.session_state.user_context
            )
            
            if next_field:
                st.session_state.current_field = next_field
                st.session_state.pending_stream = next_question
            else:
                # Roadmap Generation Transition
                progress_placeholder = st.empty()
                status_placeholder = st.empty()
                progress_bar = progress_placeholder.progress(0)
                
                stages = [
                    (0.20, "Analyzing your career path... 🔍"),
                    (0.40, "Summarizing your profile... 👤"),
                    (0.60, "Structuring learning modules... 🏗️"),
                    (0.80, "Selecting best resources... 📚"),
                    (1.00, "Finalizing your master plan... ✨")
                ]
                
                for percent, status in stages:
                    status_placeholder.markdown(f"**{status}**")
                    progress_bar.progress(percent)
                    time.sleep(0.8)
                
                # Generate Profile Summary and Roadmap
                with st.spinner("Building your personalized experience..."):
                    st.session_state.profile_summary = generate_user_profile_summary(st.session_state.user_context)
                    st.session_state.roadmap_text = generate_roadmap(st.session_state.user_context)
                    st.session_state.finalized = True
                
                progress_placeholder.empty()
                status_placeholder.empty()
        
        st.rerun()
