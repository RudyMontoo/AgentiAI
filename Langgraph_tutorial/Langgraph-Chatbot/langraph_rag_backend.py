# langraph_rag_backend.py
import os
import sqlite3
import tempfile
from typing import Annotated, Any, Dict, Optional, TypedDict

import requests
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_community.vectorstores import FAISS
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

# -------------------
# 1. LLM + Embeddings
# -------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0,
)

embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=GEMINI_API_KEY,
)

# -------------------
# 2. Per-thread PDF store (in-memory)
# -------------------
# thread_id -> retriever / metadata  (har chat ka apna PDF index)
_THREAD_RETRIEVERS: Dict[str, Any] = {}
_THREAD_METADATA: Dict[str, dict] = {}


def _get_retriever(thread_id: Optional[str]):
    if thread_id is None:
        return None
    return _THREAD_RETRIEVERS.get(str(thread_id))


def ingest_pdf(file_bytes: bytes, thread_id: str, filename: Optional[str] = None) -> dict:
    """Load a PDF, split it, embed it into FAISS and attach the retriever to this thread."""
    if not file_bytes:
        raise ValueError("Empty file received.")

    filename = filename or "uploaded.pdf"

    # PyPDFLoader ko path chahiye, isliye bytes ko temp file mein likho
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    try:
        docs = PyPDFLoader(temp_path).load()
        for d in docs:
            d.metadata["source"] = filename  # temp path ki jagah real filename

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents(docs)
        if not chunks:
            raise ValueError("No text found in this PDF (scanned / image-only PDF?).")

        vector_store = FAISS.from_documents(chunks, embeddings)
        retriever = vector_store.as_retriever(
            search_type="similarity", search_kwargs={"k": 4}
        )

        summary = {"filename": filename, "documents": len(docs), "chunks": len(chunks)}
        _THREAD_RETRIEVERS[str(thread_id)] = retriever
        _THREAD_METADATA[str(thread_id)] = summary
        return dict(summary)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def thread_document_metadata(thread_id: str) -> dict:
    return dict(_THREAD_METADATA.get(str(thread_id), {}))


# -------------------
# 3. Tools
# -------------------
search_tool = DuckDuckGoSearchRun(
    api_wrapper=DuckDuckGoSearchAPIWrapper(region="us-en", backend="duckduckgo")
)


@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}

        return {
            "first_num": first_num,
            "second_num": second_num,
            "operation": operation,
            "result": result,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA')
    using Alpha Vantage.
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@tool
def rag_tool(query: str, config: RunnableConfig) -> dict:
    """
    Retrieve relevant passages from the PDF uploaded in this chat.
    Use this tool for any factual / conceptual question about the user's
    uploaded document or notes.
    """
    # `config` LangGraph khud inject karta hai (LLM ko dikhta bhi nahi),
    # isliye frontend wala thread_id seedha yahan mil jaata hai.
    thread_id = config.get("configurable", {}).get("thread_id")
    retriever = _get_retriever(thread_id)

    if retriever is None:
        return {"error": "No PDF indexed for this chat. Ask the user to upload one first."}

    result = retriever.invoke(query)
    return {
        "query": query,
        "source_file": _THREAD_METADATA.get(str(thread_id), {}).get("filename"),
        "context": [doc.page_content for doc in result],
        "metadata": [doc.metadata for doc in result],
    }


tools = [search_tool, get_stock_price, calculator, rag_tool]
llm_with_tools = llm.bind_tools(tools)

# -------------------
# 4. State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# -------------------
# 5. Nodes
# -------------------
SYSTEM_PROMPT = """You are a helpful multi-utility assistant.
- For questions about the user's uploaded PDF / notes, call `rag_tool` and answer
  only from the returned context. Mention page numbers from metadata when useful.
- If `rag_tool` says no PDF is indexed, ask the user to upload one from the sidebar.
- Use the web search tool for current information, `get_stock_price` for stock
  prices, and `calculator` for arithmetic.
"""


def chat_node(state: ChatState):
    """LLM node that may answer or request a tool call."""
    # System prompt har call pe aage lagta hai, state/DB mein save nahi hota
    messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


tool_node = ToolNode(tools, handle_tool_errors=True)

# -------------------
# 6. Checkpointer (persistent SQLite)
# -------------------
conn = sqlite3.connect(database="chatbot.db", check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

# -------------------
# 7. Graph
# -------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)  # tools ya END
graph.add_edge("tools", "chat_node")

chatbot = graph.compile(checkpointer=checkpointer)


# -------------------
# 8. Helper
# -------------------
def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)


# -------------------
# Quick test:  python langraph_rag_backend.py
# -------------------
if __name__ == "__main__":
    tid = "test-rag"
    pdf_path = "intro-to-ml.pdf"

    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            print(ingest_pdf(f.read(), thread_id=tid, filename=pdf_path))

    out = chatbot.invoke(
        {"messages": [HumanMessage(content="Using the pdf notes, explain how to find the ideal value of K in KNN")]},
        config={"configurable": {"thread_id": tid}},
    )
    print(out["messages"][-1].content)