import streamlit as st
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types

# ---------- Settings ----------
MODEL = "gemini-3.5-flash-lite"
FREE_LIMIT = 20       # questions per person per day
PRO_LIMIT = 100       # questions per person per day (Pro)
GLOBAL_LIMIT = 400    # total questions per day for everyone (protects free API quota)
MAX_FILE_MB = 10

SYSTEM = (
    "You are Prachi AI, a friendly multilingual study assistant for students. "
    "Reply in the same language the student uses (English, Hindi or Marathi). "
    "Explain in simple words, step by step, with short examples. "
    "If a photo or file is given, read it carefully and answer from it."
)
PRO_EXTRA = " Give a more detailed answer with an example and a short summary at the end."

st.set_page_config(page_title="Prachi AI", page_icon="🎓", layout="centered", initial_sidebar_state="expanded")


# ---------- Helpers ----------
@st.cache_resource
def get_counts():
    # Resets when the app restarts. A database can make it permanent later.
    return {}


def today():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%Y-%m-%d")


def used_by(user):
    return get_counts().get((user, today()), 0)


def used_total():
    t = today()
    return sum(v for (u, d), v in get_counts().items() if d == t)


def add_use(user):
    c = get_counts()
    c[(user, today())] = c.get((user, today()), 0) + 1


@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def chat_as_text(messages):
    lines = []
    for m in messages:
        who = "You" if m["role"] == "user" else "Prachi AI"
        note = f" [{m['file']}]" if m.get("file") else ""
        lines.append(f"{who}{note}: {m['content']}\n")
    return "\n".join(lines)


# ---------- State ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pro" not in st.session_state:
    st.session_state.pro = False
if "up_key" not in st.session_state:
    st.session_state.up_key = 0

# ---------- Sidebar ----------
with st.sidebar:
    st.header("👤 Your account")
    name = st.text_input("Enter your name", placeholder="e.g. Prachi")
    user = name.strip().lower()

    pro_code = st.secrets.get("PRO_CODE", "")
    if pro_code:
        with st.expander("⭐ Pro code"):
            code = st.text_input("Enter code", type="password")
            if st.button("Activate Pro"):
                if code == pro_code:
                    st.session_state.pro = True
                    st.success("Pro activated! ⭐")
                else:
                    st.error("Wrong code.")

    limit = PRO_LIMIT if st.session_state.pro else FREE_LIMIT
    st.write("Plan: **" + ("⭐ Pro" if st.session_state.pro else "Free") + "**")
    if user:
        left = max(0, limit - used_by(user))
        st.write(f"Questions left today: **{left}/{limit}**")

    if st.session_state.messages:
        st.download_button(
            "💾 Download chat",
            data=chat_as_text(st.session_state.messages),
            file_name="prachi-ai-chat.txt",
            mime="text/plain",
        )
        if st.button("🗑️ New chat"):
            st.session_state.messages = []
            st.rerun()

# ---------- Main ----------
st.title("🎓 Prachi AI")
st.caption("Your multilingual AI study assistant: English, हिंदी, मराठी")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m.get("file"):
            st.caption(f"📎 {m['file']}")
        st.markdown(m["content"])

with st.expander("📎 Add a photo or file (PNG, JPG, PDF, TXT)"):
    up = st.file_uploader(
        "Choose a file",
        type=["png", "jpg", "jpeg", "pdf", "txt"],
        key=f"up_{st.session_state.up_key}",
        label_visibility="collapsed",
    )
    if up is not None and up.type.startswith("image"):
        st.image(up, width=220)

prompt = st.chat_input("Ask your question...")

if prompt:
    if not user:
        st.warning("Please enter your name in the sidebar first. 👈")
        st.stop()
    if used_by(user) >= limit:
        st.warning(f"You have used all {limit} questions for today. Please come back tomorrow! 😊")
        st.stop()
    if used_total() >= GLOBAL_LIMIT:
        st.warning("The app has reached its daily limit. Please try again tomorrow. 🙏")
        st.stop()
    if up is not None and up.size > MAX_FILE_MB * 1024 * 1024:
        st.warning(f"File must be smaller than {MAX_FILE_MB} MB.")
        st.stop()

    file_name = up.name if up is not None else None
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "file": file_name}
    )
    with st.chat_message("user"):
        if file_name:
            st.caption(f"📎 {file_name}")
        st.markdown(prompt)

    # Build the conversation for Gemini
    contents = []
    for m in st.session_state.messages[:-1]:
        role = "user" if m["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=m["content"])])
        )
    parts = []
    if up is not None:
        data = up.getvalue()
        if up.type == "text/plain":
            parts.append(types.Part.from_text(text=data.decode("utf-8", "ignore")))
        else:
            parts.append(types.Part.from_bytes(data=data, mime_type=up.type))
    parts.append(types.Part.from_text(text=prompt))
    contents.append(types.Content(role="user", parts=parts))

    system = SYSTEM + (PRO_EXTRA if st.session_state.pro else "")
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = get_client().models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=system),
                )
                answer = resp.text or "I could not find an answer. Please try again."
                add_use(user)
            except Exception:
                answer = "Something went wrong. Please try again in a little while. 🙏"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.up_key += 1  # clear the uploaded file for the next question
    st.rerun()
