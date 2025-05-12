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
import datetime
import os
import glob

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
        
        # Load previous conversations
        self.load_previous_conversations()
        
    def load_previous_conversations(self):
        """Load previous conversations from JSON files"""
        summaries_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'summaries')
        if not os.path.exists(summaries_dir):
            return

        # Get all summary files
        summary_files = glob.glob(os.path.join(summaries_dir, 'conversation_summary_*.json'))
        
        for file_path in summary_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                
                # Extract thread_id from filename
                thread_id = os.path.splitext(os.path.basename(file_path))[0]
                
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

    async def generate_summary(self, thread_id: str) -> dict:
        """Generate a summary of the conversation and return as a dictionary"""
        history = self.get_thread_history(thread_id)
        
        # Prepare messages for summary
        messages = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})
        
        # Add system message for summary generation
        system_message = {
            "role": "system",
            "content": """You are a conversation analyzer. Please analyze the conversation and provide a structured summary in English.
            Format your response as a JSON object with the following structure:
            {
                "main_topics": ["topic1", "topic2", ...],
                "key_decisions": ["decision1", "decision2", ...],
                "important_information": ["info1", "info2", ...],
                "action_items": ["action1", "action2", ...],
                "overall_summary": "A brief paragraph summarizing the entire conversation"
            }
            
            Guidelines:
            1. Always provide at least one item in each array
            2. Keep the overall_summary concise but informative
            3. Focus on extracting meaningful information from the conversation
            4. Ensure all content is in English and maintain a professional tone
            5. If a category has no relevant items, include a placeholder like "No specific [category] identified"
            """
        }
        messages.insert(0, system_message)
        
        try:
            # Generate summary using OpenRouter API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,  # Increased token limit for longer summaries
                temperature=0.7   # Add some creativity to the summary
            )
            
            # Parse the summary response
            summary_text = completion.choices[0].message.content
            try:
                summary_dict = json.loads(summary_text)
            except json.JSONDecodeError:
                # If the response isn't valid JSON, create a structured summary
                summary_dict = {
                    "main_topics": ["No specific topics identified"],
                    "key_decisions": ["No specific decisions identified"],
                    "important_information": ["No specific information identified"],
                    "action_items": ["No specific actions identified"],
                    "overall_summary": summary_text
                }
            
            # Add the original messages and timestamp
            summary_dict["messages"] = messages[1:]  # Exclude system message
            summary_dict["timestamp"] = str(datetime.datetime.now())
            
            # Remove raw_messages if it exists to avoid duplication
            if "raw_messages" in summary_dict:
                del summary_dict["raw_messages"]
            
            return summary_dict
            
        except Exception as e:
            return {
                "error": str(e),
                "messages": messages[1:],
                "timestamp": str(datetime.datetime.now()),
                "main_topics": ["Error occurred during summary generation"],
                "key_decisions": ["No decisions could be extracted"],
                "important_information": ["No information could be extracted"],
                "action_items": ["No actions could be extracted"],
                "overall_summary": f"Error occurred while generating summary: {str(e)}"
            } 