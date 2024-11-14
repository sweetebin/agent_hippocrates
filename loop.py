from datetime import datetime
import json
import os
import sys
import traceback
from openai import OpenAI
from swarm import Swarm
import agents
from shared_context import SharedContext

def pretty_print_messages(messages) -> None:
    for message in messages:
        if message["role"] != "assistant":
            continue

        # print agent name in blue
        print(f"\033[94m{message['sender']}\033[0m:", end=" ")

        # print response, if any
        if message["content"]:
            print(message["content"])

        # print tool calls in purple, if any
        tool_calls = message.get("tool_calls") or []
        if len(tool_calls) > 1:
            print()

def simple_loop(
    starting_agent, shared_context: SharedContext, stream=False, debug=True, client=None
) -> None:
    print("Starting Swarm CLI 🐝")
    messages = shared_context.get_full_message_history()
    agent_to_run = starting_agent

    while True:
        
        user_input = input("\033[90mUser\033[0m: ")
        current_message = {"role": "user", "content": user_input}
        messages.append(current_message)
        # Update message history in shared context
        shared_context.update_message_history(current_message)
        
        agent_history_messages = messages[-10:]
        if shared_context.patient_data != "":
            agent_history_messages.append({
            "role": "system", 
            "content": f"Patient Data: {shared_context.patient_data}"})

        try:
            response = client.run (
                agent=agent_to_run,
                messages=agent_history_messages,
                stream=stream,
                debug=debug        
            )
        
            if response and response.messages:
                    pretty_print_messages(response.messages)
                    
                    agent_to_run = response.agent
                    shared_context.update_last_handoff(datetime.now())
                    shared_context.update_current_agent(agent_to_run.name)
                    
                    # Update message history with only valid messages
                    for message in response.messages:
                        if message.get("content") and message.get("role") != "tool":
                            new_msg = {
                                "role": message["role"], 
                                "content": message["content"],
                                "sender": message.get("sender", "assistant")
                            }
                            shared_context.update_message_history(new_msg)
                            messages.append(new_msg)
            else:
                    print("No response received from agent, continuing conversation...")
                    continue

 
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Full traceback:")
            traceback.print_exc()
                
if __name__ == "__main__":    
    # Get user_id from command line argument or environment variable
    user_id = None
    
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    
    if not user_id:
        user_id = os.environ.get("USER_ID")
    
    if not user_id:
        print("Error: No user_id provided. Use command line argument or set USER_ID environment variable.")
        sys.exit(1)

    shared_context = SharedContext(user_id=user_id)
    messages = []
    container = agents.AgentContainer(user_id)
    agent = container.medical_assistant_agent
     
    client = OpenAI(
        base_url=os.environ.get("OPENROUTER_BASE_URL"),
        api_key=os.environ.get("OPENROUTER_API_KEY")  # Use environment variable
    )

    swarm = Swarm()
    swarm.client = client
    
    simple_loop(starting_agent=agent, client=swarm, shared_context=shared_context, debug=True)
