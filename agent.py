import json
from typing import List, Literal, Optional, Dict, Any, Annotated, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langchain.storage import InMemoryStore
from openai import OpenAI
import datetime
import os
import glob

class State(TypedDict):
    messages: Annotated[list, add_messages]
    thread_id: str
    metadata: Dict[str, Any]

class ThreadedAgent:
    def __init__(self, model_name: str = "google/gemini-2.0-flash-exp:free"):
        """
        Initialize the ThreadedAgent with the specified model name and API key.
        
        Args:
        """
        self.store = InMemoryStore()
        self.api_key = "sk-"
        self.model = model_name
        self.base_url = "https://openrouter.ai/api/v1"
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "http://localhost:3000",  # Required for OpenRouter
                "X-Title": "Desktop Assistant"  # Optional, but helpful for tracking
            }
        )
        self.memory_saver = MemorySaver()
        self.workflow = self._create_workflow()
        self.load_previous_conversations()
        
    def load_previous_conversations(self):
        """Load previous conversations from JSON files"""
        summaries_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'summaries')
        if not os.path.exists(summaries_dir):
            return

        # Get all summary files from the summaries folder
        summary_files = glob.glob(os.path.join(summaries_dir, 'thread_*.json'))
        
        for file_path in summary_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                
                # Extract thread_id from filename
                thread_id = os.path.splitext(os.path.basename(file_path))[0].replace('thread_', '')
                
                # Convert messages back to LangChain message objects
                messages = []
                for msg in summary_data.get('messages', []):
                    if msg['role'] == 'user':
                        messages.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'assistant':
                        messages.append(AIMessage(content=msg['content']))
                
                # Store in memory
                self.store.mset([(f"thread_{thread_id}", {"messages": messages})])
                
            except Exception as e:
                print(f"Error loading conversation from {file_path}: {str(e)}")
        
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
        
    def _convert_to_api_message(self, message) -> dict:
        """Convert LangChain message to API message format"""
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            return {"role": "assistant", "content": message.content}
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        return None

    def _prepare_messages(self, history: list, current_messages: list) -> list:
        """Prepare messages for API call"""
        # Start with system message
        content="""You are an assistant to listen to the user and help them with their problems.
                   You should be emotional and empathetic to the user's problems.
                   You must respond with at least 5 words.
                   You cannot respond with empty content.
        """
        system_message = SystemMessage(
            content=content
        )
        api_messages = [self._convert_to_api_message(system_message)]

        # Add history messages
        for msg in history:
            api_msg = self._convert_to_api_message(msg)
            if api_msg:
                api_messages.append(api_msg)

        # Add current messages
        for msg in current_messages:
            api_msg = self._convert_to_api_message(msg)
            if api_msg:
                api_messages.append(api_msg)

        return api_messages

    async def _agent_node(self, state: State, config: RunnableConfig) -> Dict:
        """Process the message and generate a response"""
        try:
            # Extract state
            messages = state["messages"]
            thread_id = state["thread_id"]
            print(f"\n[DEBUG] _agent_node - Thread ID: {thread_id}")
            print(f"[DEBUG] Current messages: {[msg.content for msg in messages]}")
            
            # Get conversation history
            history_data = self.store.mget([f"thread_{thread_id}"])[0]
            history = history_data.get("messages", []) if history_data else []
            print(f"[DEBUG] History messages: {[msg.content for msg in history]}")
            
            # Prepare messages for API
            api_messages = self._prepare_messages(history, messages)
            print(f"[DEBUG] Prepared API messages: {api_messages}")
            
            # Generate response using OpenRouter API
            try:
                print(f"[DEBUG] Calling API with model: {self.model}")
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=api_messages,
                    max_tokens=500,
                    temperature=0.7,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                
                print(f"[DEBUG] API Response: {completion}")
                
                if not completion:
                    raise ValueError("No response received from API")
                    
                if not completion.choices:
                    raise ValueError("No choices in API response")
                    
                if not completion.choices[0].message.content:
                    raise ValueError("Empty content in API response")
                    
                response = AIMessage(content=completion.choices[0].message.content)
                print(f"[DEBUG] Generated response: {response.content}")
                return {"messages": [response]}
                
            except Exception as api_error:
                print(f"[ERROR] API Error details: {str(api_error)}")
                raise ValueError(f"API Error: {str(api_error)}")
            
        except Exception as e:
            print(f"[ERROR] General error: {str(e)}")
            error_message = AIMessage(content=f"Sorry, I encountered an error: {str(e)}")
            return {"messages": [error_message]}
        
    async def _update_memory_node(self, state: State, config: RunnableConfig) -> Dict:
        """Update the conversation history"""
        thread_id = state["thread_id"]
        messages = state["messages"]
        print(f"\n[DEBUG] _update_memory_node - Thread ID: {thread_id}")
        print(f"[DEBUG] Messages to update: {[msg.content for msg in messages]}")
        
        # Get current history
        history_data = self.store.mget([f"thread_{thread_id}"])[0]
        history = history_data.get("messages", []) if history_data else []
        print(f"[DEBUG] Current history: {[msg.content for msg in history]}")
        
        # Add new messages to history
        history.extend(messages)
        print(f"[DEBUG] Updated history: {[msg.content for msg in history]}")
        
        # Save updated history
        self.store.mset([(f"thread_{thread_id}", {"messages": history})])
        
        return {"messages": messages}
        
    async def chat(self, message: str, thread_id: str) -> str:
        """Process a message and return the response"""
        print(f"\n[DEBUG] Received chat request - Thread ID: {thread_id}")
        print(f"[DEBUG] User message: {message}")
        
        # Initialize thread if it doesn't exist
        if not self.store.mget([f"thread_{thread_id}"])[0]:
            print(f"[DEBUG] Creating new thread: {thread_id}")
            self.store.mset([(f"thread_{thread_id}", {"messages": []})])
            
        # Create input state
        state: State = {
            "messages": [HumanMessage(content=message)],
            "thread_id": thread_id,
            "metadata": {}
        }
        print(f"[DEBUG] Created state with message: {message}")
        
        # Run the workflow
        result = await self.workflow.ainvoke(state)
        print(f"[DEBUG] Workflow result: {result}")
        
        # Return the last message content
        return result["messages"][-1].content
        
    def get_thread_history(self, thread_id: str) -> List[Dict]:
        """Get the conversation history for a thread"""
        history_data = self.store.mget([f"thread_{thread_id}"])[0]
        return history_data.get("messages", []) if history_data else []
        
    async def save_conversation(self, thread_id: str) -> dict:
        """Save the conversation to a file without generating a summary"""
        history = self.get_thread_history(thread_id)
        
        # Prepare messages for saving
        messages = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})
        
        # Create a simple dictionary with messages and timestamp
        conversation_dict = {
            "messages": messages,
            "timestamp": str(datetime.datetime.now())
        }
        
        return conversation_dict