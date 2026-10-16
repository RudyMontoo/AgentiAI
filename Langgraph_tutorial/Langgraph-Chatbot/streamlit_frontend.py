import streamlit as st
from langgraph_backend import chatbot
from langchain_core.messages import HumanMessage

# LangGraph thread configuration
CONFIG = {
    'configurable': {
        'thread_id': 'thread-1'
    }
}

# Initialize Streamlit chat history
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

# Load conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

# User input
user_input = st.chat_input('Type here')

if user_input:

    # Store user message
    st.session_state['message_history'].append({
        'role': 'user',
        'content': user_input
    })

    # Display user message
    with st.chat_message('user'):
        st.text(user_input)

    # Generate and stream AI response
    with st.chat_message('assistant'):

        ai_message = st.write_stream(
            message_chunk.content[0]['text']
            for message_chunk, metadata in chatbot.stream(
                {
                    'messages': [
                        HumanMessage(content=user_input)
                    ]
                },
                config=CONFIG,
                stream_mode='messages'
            )
            if (
                message_chunk.content
                and isinstance(message_chunk.content, list)
                and message_chunk.content[0].get('type') == 'text'
                and message_chunk.content[0].get('text')
            )
        )

    # Store AI response
    st.session_state['message_history'].append({
        'role': 'assistant',
        'content': ai_message
    })