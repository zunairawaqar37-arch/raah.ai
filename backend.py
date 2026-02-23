# backend.py
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
import re

load_dotenv()

# Initialize LLMs
llm_chat = ChatGroq(
    model="llama-3.3-70b-versatile", # High quality for chat
    temperature=0.7,
    groq_api_key=os.getenv("GROQ_API_KEY")
)

llm_roadmap = ChatGroq(
    model="qwen/qwen3-32b", # High quality for complex structured output
    temperature=0.3, # Lower temperature for consistency
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# Field definitions
BASIC_FIELDS = ["name", "location", "age", "role"]
STUDENT_FIELDS = ["student_type", "field_of_study"]
COMMON_FIELDS = ["skill_to_learn", "skill_level", "goal", "daily_commitment", "estimated_time", "learning_budget"]

# Mapping of fields to user-friendly names for prompting
FIELD_LABELS = {
    "name": "Name",
    "location": "Location",
    "age": "Age",
    "role": "Current Role (Student, Professional, or Unemployed)",
    "student_type": "Type of Student (High School, Undergraduate, etc.)",
    "field_of_study": "Field of Study",
    "skill_to_learn": "Skill you want to learn",
    "skill_level": "Current skill level (Beginner, Intermediate, Advanced)",
    "goal": "Primary Goal",
    "daily_commitment": "Daily time commitment (e.g., 2 hours)",
    "estimated_time": "Estimated total time for completion (e.g., 3 months)",
    "learning_budget": "Learning budget (Free or Paid limits)"
}

def format_chat_history(chat_history):
    text = ""
    for msg in chat_history:
        role = msg.get("role")
        content = msg.get("content")
        text += f"{role.upper()}: {content}\n"
    return text

def postprocess_llm_response(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()

def get_next_field(user_context):
    # 1. Basic Fields
    for field in BASIC_FIELDS:
        if field not in user_context:
            return field
    
    # 2. Branching Logic
    role = user_context.get("role", "").lower()
    if "student" in role:
        for field in STUDENT_FIELDS:
            if field not in user_context:
                return field
    
    # 3. Common Fields
    for field in COMMON_FIELDS:
        if field not in user_context:
            return field
            
    return None

def generate_next_question(chat_history, user_context):
    field = get_next_field(user_context)
    if not field:
        return None, None

    system_msg = SystemMessage(content="""
You are RAAH AI, a professional career coach.
Your goal is to collect information from the user to build a personalized roadmap.
Ask ONLY ONE clear, friendly question at a time.
If there is no conversation history, then start with a friendly opening like: 
'Hello! I’m RAAH AI, your career assistant. I’ll help you build a personalized learning roadmap. Let’s start with your full name?'
Don't say Hi or Hello or any greeting after this friendly opening. Just use Hi in the friendly opening.
Don't use the user name in the response after the first message.
When you are at the last question, tell the user that after they answer this question, you will generate the roadmap.
""")
    
    user_msg = HumanMessage(content=f"""Conversation history:
{format_chat_history(chat_history)}

The next piece of information needed is: {FIELD_LABELS.get(field, field)}.
Ask the user for this information.""")

    response = llm_chat.invoke([system_msg, user_msg])
    question = postprocess_llm_response(response.content)
    return field, question

def is_skill_vague(skill_to_learn):
    system_msg = SystemMessage(content="""You are an expert skill analyzer. 
Analyze if the provided skill is too vague to create a specific 3-month roadmap.
Vague examples: 'Coding', 'Business', 'AI', 'Software Engineering'.
Specific examples: 'Python for Data Science', 'React Frontend Development', 'Digital Marketing for E-commerce', 'LLM Fine-tuning'.

Output only 'VAGUE' or 'SPECIFIC'.""")
    
    user_msg = HumanMessage(content=f"Skill: {skill_to_learn}")
    
    response = llm_chat.invoke([system_msg, user_msg])
    result = postprocess_llm_response(response.content).upper()
    return "VAGUE" in result

def get_clarification_question(skill_to_learn):
    system_msg = SystemMessage(content="""You are RAAH AI. The user provided a vague skill. 
Ask them to be more specific and provide 2-3 concrete examples of what they could mean (e.g., if they said 'Coding', suggest 'Web Development with JavaScript' or 'Data Analysis with Python').""")
    
    user_msg = HumanMessage(content=f"User's vague skill: {skill_to_learn}")
    
    response = llm_chat.invoke([system_msg, user_msg])
    return postprocess_llm_response(response.content)

def generate_user_profile_summary(user_context):
    """Generates a concise summary of the user profile based on collected context in semantic HTML."""
    system_msg = SystemMessage(content="""You are a professional assistant. 
Summarize the user's provided context into clean, semantic HTML. 
If answers are long, extract only the core information.
Use only: <ul>, <li>, <strong>, <p>.
Do NOT include <html>, <head>, <body>, or CSS.
Format like:
<ul>
  <li><strong>Name:</strong> [Name]</li>
  <li><strong>Role:</strong> [Role]</li>
  ...
</ul>""")
    
    context_str = "\n".join([f"{k}: {v}" for k, v in user_context.items()])
    user_msg = HumanMessage(content=f"User Context:\n{context_str}")
    
    response = llm_chat.invoke([system_msg, user_msg])
    return postprocess_llm_response(response.content)

def generate_roadmap(user_context):
    """Generates a detailed learning roadmap in semantic HTML."""
    system_msg = SystemMessage(content="""You are RAAH AI, a world-class career strategist.
Generate roadmap HTML ONLY. Follow this EXACT structure:

1. Executive Summary
2. Learning Phases (each with name, duration, resources)
3. Weekly Breakdown (detailed)
4. Recommended Resources (Free / Paid)
5. Tips and Notes

Output MUST be semantic HTML:
- Use <h2> for major sections
- Use <h3> for subsections
- Use <ul><li> for lists
- Use <p> for paragraphs
- Include <table> for phase/resource tables exactly as shown below
Do NOT deviate. Do NOT include CSS.""")
    
    context_str = "\n".join([f"{k}: {v}" for k, v in user_context.items()])
    user_msg = HumanMessage(content=f"User Context:\n{context_str}\n\nPlease generate the semantic HTML roadmap now.")
    
    response = llm_roadmap.invoke([system_msg, user_msg])
    return postprocess_llm_response(response.content)

def wrap_html(inner_html):
    """Wraps inner HTML with a full document structure and professional CSS for PDF generation."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            color: #333;
            line-height: 1.6;
            margin: 40px;
        }}
        h1 {{
            color: #4A90E2;
            text-align: center;
            border-bottom: 2px solid #4A90E2;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #4A90E2;
            margin-top: 30px;
            border-left: 5px solid #4A90E2;
            padding-left: 10px;
        }}
        h3 {{
            color: #2C3E50;
            margin-top: 20px;
        }}
        ul {{
            margin-left: 20px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        .summary-box {{
            background-color: #F8F9FA;
            border: 1px solid #DEE2E6;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .footer {{
            margin-top: 50px;
            text-align: center;
            font-size: 0.9em;
            color: #777;
            border-top: 1px solid #EEE;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <h1>RAAH AI Career Roadmap</h1>
    {inner_html}
    <div class="footer">
        Generated by RAAH AI - Your Personalized Career Growth Assistant
    </div>
</body>
</html>
"""
