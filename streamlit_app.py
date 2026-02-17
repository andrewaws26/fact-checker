import streamlit as st
from tavily import TavilyClient
import json
import re

# --- 1. Page Configuration ---
st.set_page_config(page_title="NewsGrader Pro", page_icon="⚖️", layout="wide")

# --- 2. Custom CSS ---
st.markdown("""
    <style>
    .letter-grade { font-size: 80px; font-weight: 800; text-align: center; line-height: 1; margin-bottom: 10px; }
    .metric-card { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 10px; padding: 20px; height: 100%; text-align: center; }
    .verdict-box { background-color: #eef2f5; border-left: 5px solid #3498db; padding: 15px; border-radius: 5px; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. Helper: JSON Cleaner ---
def clean_and_parse_json(raw_text):
    if not raw_text: return None
    # If we already have a dict (from structured stream), return it
    if isinstance(raw_text, dict): return raw_text
    
    text = str(raw_text)
    # Remove markdown code fences if present
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match: text = match.group(1)
    try:
        return json.loads(text)
    except:
        return None

# --- 4. Main UI ---
st.title("⚖️ NewsGrader Pro")
st.caption("AI-Powered Truth & Accuracy Auditor (Live Streaming)")

with st.sidebar:
    st.title("⚙️ Settings")
    default_key = st.secrets.get("TAVILY_API_KEY", "")
    api_key = st.text_input("Tavily API Key", value=default_key, type="password")
    st.divider()
    model = "mini" if st.radio("Depth:", ["Mini", "Pro"]) == "Mini" else "pro"

with st.form("audit"):
    url = st.text_input("Article URL", placeholder="https://example.com/...")
    run_btn = st.form_submit_button("Run Audit")

if run_btn:
    if not api_key or not url:
        st.error("Please check your API Key and URL.")
        st.stop()
    
    # --- Clean API Key (Prevents latin-1 crash) ---
    safe_key = str(api_key).strip()
    try: safe_key = safe_key.encode("ascii", "ignore").decode("ascii")
    except: pass
        
    client = TavilyClient(api_key=safe_key)
    
    # --- Strict Schema ---
    schema = {
        "properties": {
            "letter_grade": {"type": "string", "enum": ["A","B","C","D","F"], "description": "Grade (A-F) of accuracy."},
            "one_sentence_verdict": {"type": "string", "description": "Concise summary."},
            "red_flags": {"type": "array", "items": {"type": "string"}, "description": "List of errors/lies."},
            "verified_facts": {"type": "array", "items": {"type": "string"}, "description": "List of true claims."},
            "sources_used": {"type": "array", "items": {"type": "string"}, "description": "List of sources."}
        },
        "required": ["letter_grade", "one_sentence_verdict", "red_flags", "verified_facts"]
    }

    # --- OFFICIAL STREAMING LOGIC ---
    full_report = ""
    final_json_object = None
    
    with st.status("🚀 Connecting to Agent...", expanded=True) as status:
        try:
            response = client.research(
                input=f"Fact-check this: {url}",
                model=model,
                output_schema=schema,
                stream=True
            )
            
            # Variables to track stream state
            current_event_type = None
            
            # --- THE LOOP (Adapted from Official Docs) ---
            for chunk in response:
                # 1. Decode bytes to string
                line = chunk.decode("utf-8").strip() if isinstance(chunk, bytes) else str(chunk).strip()
                if not line: continue

                # 2. Parse SSE Event Type
                if line.startswith("event:"):
                    current_event_type = line.split("event:", 1)[1].strip()
                
                # 3. Parse Data Payload
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line.split("data:", 1)[1].strip())
                    except:
                        continue # Skip malformed JSON

                    # Handle Chat Completion Chunk
                    if current_event_type == "chat.completion.chunk":
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        
                        # A. Handle Content (Building the Report)
                        if "content" in delta:
                            content = delta["content"]
                            
                            # Structured Output often sends the WHOLE object at once in streaming
                            if isinstance(content, dict):
                                final_json_object = content
                                status.write("⚡ Receiving structured data...")
                            # Or it sends string tokens
                            else:
                                full_report += str(content)

                        # B. Handle Research Steps (Visual Feedback)
                        elif "step_details" in delta:
                            step = delta["step_details"]
                            step_type = step.get("type", "")
                            
                            if step_type == "research_plan":
                                plan = step.get("step", "Planning...")
                                status.write(f"📋 **Plan:** {plan}")
                            elif step_type == "research":
                                msg = step.get("step", "Researching...")
                                status.write(f"🔍 **Researching:** {msg}")
                            elif step_type == "think":
                                status.write(f"💭 **Thinking...**")

                        # C. Handle Tool Calls (Optional: Show URLs being visited)
                        elif "tool_calls" in delta:
                            # You can parse this to show exactly which URLs are clicked
                            pass
            
            status.update(label="Audit Complete!", state="complete", expanded=False)
            
        except Exception as e:
            st.error(f"Stream Error: {e}")
            st.stop()

    # --- RESULT PARSING ---
    # 1. Prefer the direct JSON object if the API sent it
    if final_json_object:
        final_data = final_json_object
    # 2. Otherwise, parse the accumulated string
    else:
        final_data = clean_and_parse_json(full_report)
    
    # --- DISPLAY ---
    if final_data:
        colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f1c40f", "D": "#e67e22", "F": "#e74c3c"}
        grade = final_data.get("letter_grade", "C")
        
        st.divider()
        c1, c2 = st.columns([1, 4])
        with c1:
            st.markdown(f"<div class='metric-card'><div class='letter-grade' style='color:{colors.get(grade, '#999')}'>{grade}</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown("### Verdict")
            st.info(final_data.get("one_sentence_verdict", "No verdict."))
            if "sources_used" in final_data:
                st.caption(f"📚 Sources: {', '.join(final_data['sources_used'][:3])}")

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.error("🛑 Red Flags")
            for x in final_data.get("red_flags", []): st.write(f"• {x}")
        with col_b:
            st.success("✅ Verified Facts")
            for x in final_data.get("verified_facts", []): st.write(f"• {x}")
            
    else:
        st.error("Parsing Failed. The agent returned no valid data.")
        with st.expander("Debug Raw Output"):
            st.text(full_report)
