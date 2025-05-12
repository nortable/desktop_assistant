import json
from typing import List, Literal, Optional, Dict, Any, Annotated, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langchain.storage import InMemoryStore
from openai import OpenAI

class State(TypedDict):
    messages: Annotated[list, add_messages]
    thread_id: str
    metadata: Dict[str, Any]

class ThreadedAgent:
    def __init__(self, model_name: str = "google/gemini-2.5-flash-preview"):
        self.store = InMemoryStore()
        self.api_key = "sk-"
        self.model = model_name
        self.base_url = "https://openrouter.ai/api/v1"
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.memory_saver = MemorySaver()
        
        # Define the agent's workflow
        self.workflow = self._create_workflow()
        
    def _create_workflow(self) -> StateGraph:
        # Create the graph
        workflow = StateGraph(State)
        
        # Add nodes
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("update_memory", self._update_memory_node)
        
        # Add edges
        workflow.add_edge(START, "agent")
        workflow.add_edge("agent", "update_memory")
        workflow.add_edge("update_memory", END)
        
        # Compile the workflow
        return workflow.compile()
        
    async def _agent_node(self, state: State, config: RunnableConfig) -> Dict:
        """Process the message and generate a response"""
        messages = state["messages"]
        thread_id = state["thread_id"]
        
        # Get conversation history
        history_data = self.store.mget([f"thread_{thread_id}"])[0]
        history = history_data.get("messages", []) if history_data else []
        
        # Prepare the prompt
        system_message = SystemMessage(content="You are a helpful AI assistant. Use the conversation history to provide contextual responses. Always respond to every part of the user's message and ensure you address all questions or requests they make. Be thorough and engaging in your responses.")
        api_messages = [{"role": "system", "content": system_message.content}]
        
        # Add history messages
        for msg in history:
            if isinstance(msg, HumanMessage):
                api_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                api_messages.append({"role": "assistant", "content": msg.content})
                
        # Add current messages
        for msg in messages:
            if isinstance(msg, HumanMessage):
                api_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                api_messages.append({"role": "assistant", "content": msg.content})
        
        try:
            # Generate response using OpenRouter API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                max_tokens=150
            )
            response = AIMessage(content=completion.choices[0].message.content)
            print(response)
            return {"messages": [response]}
        except Exception as e:
            error_message = AIMessage(content=f"Sorry, I encountered an error: {str(e)}")
            return {"messages": [error_message]}
        
    async def _update_memory_node(self, state: State, config: RunnableConfig) -> Dict:
        """Update the conversation history"""
        thread_id = state["thread_id"]
        messages = state["messages"]
        
        # Get current history
        history_data = self.store.mget([f"thread_{thread_id}"])[0]
        history = history_data.get("messages", []) if history_data else []
        
        # Add new messages to history
        history.extend(messages)
        
        # Save updated history
        self.store.mset([(f"thread_{thread_id}", {"messages": history})])
        
        return {"messages": messages}
        
    async def chat(self, message: str, thread_id: str = None) -> str:
        """Process a message and return the response"""
        if thread_id is None:
            thread_id = str(hash(message))  # Simple way to generate a unique thread ID
            
        # Initialize thread if it doesn't exist
        if not self.store.mget([f"thread_{thread_id}"])[0]:
            self.store.mset([(f"thread_{thread_id}", {"messages": []})])
            
        # Create input state
        state: State = {
            "messages": [HumanMessage(content=message)],
            "thread_id": thread_id,
            "metadata": {}
        }
        
        # Run the workflow
        result = await self.workflow.ainvoke(state)
        
        # Return the last message content
        return result["messages"][-1].content
        
    def get_thread_history(self, thread_id: str) -> List[Dict]:
        """Get the conversation history for a thread"""
        history_data = self.store.mget([f"thread_{thread_id}"])[0]
        return history_data.get("messages", []) if history_data else []
        
    def clear_thread(self, thread_id: str):
        """Clear the conversation history for a thread"""
        self.store.mset([(f"thread_{thread_id}", {"messages": []})]) 