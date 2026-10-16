from dotenv import load_dotenv
from typing import TypedDict,Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_mcp_adapters.client import MultiServerMCPClient

import asyncio
load_dotenv()
import os
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")



llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GEMINI_API_KEY,
)

# MCP client for local FastMCP server
client = MultiServerMCPClient(
    {
        "arith": {
            "transport": "stdio",  #two type of server local and online  so we are using local thats why stdio
            "command": "python3",          
            "args": ["/home/rudra/dev/learning/Agentic_AI/Langgraph_tutorial/Langgraph-Chatbot/Chatbot_server/main.py"],
        },
        "expense": {
            "transport": "streamable_http",  # if this fails, try "sse"
            "url": "https://splendid-gold-dingo.fastmcp.app/mcp"
        }
    }    
)



class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

async def build_graph():
    tools=await client.get_tools()
    print(tools)
    llm_with_tools = llm.bind_tools(tools)
    # nodes
    async def chat_node(state: ChatState):

        messages = state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}


    tool_node = ToolNode(tools)

    # defining graph and nodes
    graph = StateGraph(ChatState)

    graph.add_node("chat_node", chat_node)
    graph.add_node("tools", tool_node)

    # defining graph connections
    graph.add_edge(START, "chat_node")
    graph.add_conditional_edges("chat_node", tools_condition)
    graph.add_edge("tools", "chat_node")

    chatbot = graph.compile()
    return chatbot



async def main():
    chatbot=await build_graph()
    result=await chatbot.ainvoke(
        {"messages": [HumanMessage(content="What is 25 multiplied by 4?")]}
    )
    print(result["messages"][-1].content)


if __name__=="__main__":
    asyncio.run(main())

