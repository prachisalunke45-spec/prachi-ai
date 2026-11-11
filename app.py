import time, datetime
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="Prachi AI", page_icon="🎓")
st.title("🎓 Prachi AI")
st.caption("Ask in English, Hindi or Marathi. 20 questions per day.")

LIMIT = 20
MODEL = "gemini-3.5-flash-lite"
SYSTEM = ("You are a friendly study assistant for students. "
          "Reply in the same language the student uses: English, Hindi or Marathi. "
          "Keep answers short and simple.")

@st.cache_resource
def get_usage():
    return {"date": "", "count": 0}

usage = get_usage()
today = str(datetime.date.today())
if usage["date"] != today:
    usage["date"] = today
    usage["count"] = 0

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

q = st.chat_input("Type your question...")
if q:
    if usage["count"] >= LIMIT:
        st.warning("Daily limit of 20 questions reached. Please come back tomorrow.")
    else:
        st.session_state.messages.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        contents = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part(text=m["content"])],
            )
            for m in st.session_state.messages
        ]
        answer = "Server is busy. Please try again in a minute."
        for i in range(3):
            try:
                r = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM),
                )
                answer = r.text
                usage["count"] += 1
                break
            except Exception:
                time.sleep(5)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)

st.sidebar.write(f"Questions used today: {usage['count']}/{LIMIT}")
