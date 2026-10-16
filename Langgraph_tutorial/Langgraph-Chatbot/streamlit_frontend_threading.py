import streamlit as st
from langgraph_tool_backend import chatbot, retrieve_all_threads
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import uuid

# **************************************** utility functions *************************

def generate_thread_id():
    return str(uuid.uuid4())

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(thread_id)
    st.session_state['message_history'] = []

def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)

def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    return state.values.get('messages', [])

def extract_text(content):
    """Gemini content (string ya list of blocks) ko plain string mein convert karta hai."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return ""


# **************************************** Session Setup ******************************
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()

add_thread(st.session_state['thread_id'])


# **************************************** Sidebar UI *********************************

st.sidebar.title('LangGraph Chatbot')

if st.sidebar.button('New Chat'):
    reset_chat()

st.sidebar.header('My Conversations')

for thread_id in st.session_state['chat_threads'][::-1]:
    if st.sidebar.button(str(thread_id), key=f"thread_{thread_id}"):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = 'user'
            elif isinstance(msg, AIMessage):
                role = 'assistant'
            else:
                continue

            text = extract_text(msg.content)
            if text:
                temp_messages.append({'role': role, 'content': text})

        st.session_state['message_history'] = temp_messages


# **************************************** Main UI ************************************

for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.markdown(message['content'])

user_input = st.chat_input('Type here')

if user_input:

    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.markdown(user_input)

    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

    with st.chat_message("assistant"):
        # status box ko yahan store karenge (shuru mein koi box nahi)
        status_holder = {"box": None}

        def ai_only_stream():
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode="messages"
            ):
                # Tool ka result aaya -> status box mein tool ka naam dikhao
                if isinstance(message_chunk, ToolMessage):
                    tool_name = message_chunk.name
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(f"🔧 Using `{tool_name}` ...", expanded=True)
                    else:
                        status_holder["box"].update(label=f"🔧 Using `{tool_name}` ...", state="running")

                # AI ka text -> stream karo
                if isinstance(message_chunk, AIMessage):
                    text = extract_text(message_chunk.content)
                    if text:
                        yield text

        ai_message = st.write_stream(ai_only_stream())

        # Tool use hua tha to status box ko "done" mark karo
        if status_holder["box"] is not None:
            status_holder["box"].update(label="✅ Tool finished", state="complete", expanded=False)

    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})