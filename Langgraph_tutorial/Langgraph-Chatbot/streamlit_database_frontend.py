import streamlit as st
from langraph_database_backend import chatbot, retrieve_all_threads
from langchain_core.messages import HumanMessage, AIMessage
import uuid


# **************************************** Utility Functions *************************

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
    state = chatbot.get_state(
        config={
            'configurable': {
                'thread_id': thread_id
            }
        }
    )

    return state.values.get('messages', [])


def get_message_content(msg):
    content = msg.content

    # Normal string
    if isinstance(content, str):
        return content

    # Gemini content blocks
    if isinstance(content, list):
        text = ""

        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text += block.get("text", "")

        return text

    return str(content)


# **************************************** Session Setup ******************************

if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []


if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

# here we need to do change as u can see in chat_thread=[] 
# but now we have past history in database 
# so now here u will add all the thread that in db
# Load threads from SQLite database
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()


# Make sure current thread exists in the list
add_thread(st.session_state['thread_id'])


# **************************************** Sidebar UI *********************************

st.sidebar.title('LangGraph Chatbot')


if st.sidebar.button('New Chat'):
    reset_chat()


st.sidebar.header('My Conversations')


for thread_id in st.session_state['chat_threads'][::-1]:

    if st.sidebar.button(str(thread_id)):

        # Set selected thread
        st.session_state['thread_id'] = thread_id

        # Load messages from SQLite
        messages = load_conversation(thread_id)

        temp_messages = []

        for msg in messages:

            if isinstance(msg, HumanMessage):
                role = 'user'
            else:
                role = 'assistant'

            temp_messages.append({
                'role': role,
                'content': get_message_content(msg)
            })

        # Replace current UI history
        st.session_state['message_history'] = temp_messages

        # Rerun UI
        st.rerun()


# **************************************** Main UI ************************************

# Display conversation history

for message in st.session_state['message_history']:

    with st.chat_message(message['role']):
        st.write(message['content'])


# **************************************** Chat Input *********************************

user_input = st.chat_input('Type here')


if user_input:

    # Add user message to UI
    st.session_state['message_history'].append({
        'role': 'user',
        'content': user_input
    })

    with st.chat_message('user'):
        st.write(user_input)


    # LangGraph configuration
    CONFIG = {
        'configurable': {
            'thread_id': st.session_state['thread_id']
        }
    }


    # Generate AI response
    with st.chat_message('assistant'):

        def ai_only_stream():

            for message_chunk, metadata in chatbot.stream(
                {
                    "messages": [
                        HumanMessage(content=user_input)
                    ]
                },
                config=CONFIG,
                stream_mode="messages"
            ):

                if isinstance(message_chunk, AIMessage):

                    content = get_message_content(message_chunk)

                    if content:
                        yield content


        ai_message = st.write_stream(ai_only_stream())


    # Save AI response in Streamlit session history
    st.session_state['message_history'].append({
        'role': 'assistant',
        'content': ai_message
    })