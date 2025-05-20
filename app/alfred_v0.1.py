import streamlit as st
from langchain.agents import load_tools
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import os
import json
from langchain_community.tools.tavily_search import TavilySearchResults

def load_bounty_specifications():
    """Load bounty specifications from JSON file"""
    with open("app/bounty_specifications.json", "r") as f:
        return json.load(f)

def generate_chat_summary(messages):
    """Generate structured bounty specification from chat history"""
    llm = ChatOpenAI(model="gpt-4")
    specs = load_bounty_specifications()
    
    system_message = SystemMessage(content=f"""
    You are a bounty specification generator. Analyze the conversation history and create a structured bounty specification.
    Follow these specifications exactly:
    
    {json.dumps(specs, indent=2)}
    
    Do not output the final specification in JSON format.Format the output in a clear, structured way using markdown syntax.
    """)
    
    # Prepare the conversation history
    conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
    human_message = HumanMessage(content=f"Generate a bounty specification based on this conversation:\n{conversation_text}")
    
    # Get the specification from LLM
    response = llm.invoke([system_message, human_message])
    return response.content

def download_message_history(messages):
    """Create a formatted text file with summary and full chat history"""
    # Generate summary
    summary = generate_chat_summary(messages)
    
    with open("bounty_conversation.txt", "w") as file:
        # Write summary section
        file.write("=== CONVERSATION SUMMARY ===\n\n")
        file.write(summary)
        file.write("\n\n")
        
        # Write delimiter
        file.write("\n" + "="*50 + "\n")
        
        # Write full conversation section
        file.write("\n=== FULL CONVERSATION ===\n\n")
        for message in messages:
            file.write(f"{message['role'].upper()}:\n{message['content']}\n\n")
    
    return "bounty_conversation.txt"


st.set_page_config(layout="wide")
@st.cache_resource
def bounty_builder():
    
    # Initialize the language model
    llm = ChatOpenAI(model="gpt-4o")
    memory = MemorySaver()

    # Load the necessary tools
    #tools = load_tools(["ddg-search"])
    tools = [TavilySearchResults(max_results=3)]

    prompt = SystemMessage(content="""Your name is Alfred. You are an expert assistant specializing in designing decentralized bounties for climate action and sustainability. \
    Your mission is to help users create impactful and actionable bounty programs that promote environmental sustainability through decentralized initiatives. \
    Engage actively with users to understand their specific needs and offer tailored, practical guidance step by step. \
    Be mindful of how much information you share at one go - introduce concepts and steps needed one at a time  \
    In your responses, include clear examples and actionable suggestions to inspire users and help them refine their bounty ideas. \
    When sharing results from TavilySearchResults tool, include the source URL in the response. \                            
    Encourage feedback by asking users if adjustments are needed or if further clarity is required. \
    Focus exclusively on questions and discussions related to designing bounties, and politely redirect any unrelated inquiries.""")


    # Create the agent
    agent = create_react_agent(llm, tools,  checkpointer=memory, state_modifier=prompt)

    return agent

config = {"configurable": {"thread_id": "abc123"}}

st.title("Welcome to Alfred by Atlantis 🔱")

st.markdown("""
**Alfred** is your personal AI-powered assistant, designed to help you create impactful bounties in climate and sustainability. Whether you're championing clean water initiatives, renewable energy projects, or waste management solutions, Alfred transforms your ideas into actionable plans that drive meaningful change.
""")

st.markdown("""
### How to Get Started 🚀
1. **Share Your Idea**: Start by telling Alfred about the bounty you have in mind. Provide as much detail as possible—your goals, target audience, and any specific requirements or constraints. The more context you give, the better Alfred can assist.
2. **Ask for Help**: Use Alfred to ask questions, brainstorm ideas, or get feedback on specific aspects of your bounty. Whether you need advice or creative input, Alfred is here to collaborate.
3. **Refine and Finalize**: Once you're satisfied with your bounty, click the **"Create Bounty Specifications"** button. Alfred will generate a clear and concise specification based on your conversation history.

### Launch Your Impact 🌱
Take your refined bounty and share it on platforms like [Atlantis Impact Foundry](https://impactfoundry.atlantisp2p.com/) or other bounty tools. 
""")

# Add a button to clear the chat history
if st.button("Clear Chat History"):
    st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []



# Initialize session state for download
if "download_ready" not in st.session_state:
    st.session_state.download_ready = False

# Add a button to download the message history
download_button = st.button(
    "Create Bounty Specifications",
    key="download_button",
    disabled=len(st.session_state.messages) == 0,  # Disable if no messages
    help="Start a conversation first to enable download"
)

if download_button:
    with st.spinner("Generating specs and preparing download..."):
        message_history = st.session_state.messages
        file_path = download_message_history(message_history)
        st.session_state.download_ready = True
        st.success("✅ Specifications generated successfully!")
        
        # Add download link after generation
        with open(file_path, "r") as file:
            st.download_button(
                label="📥 Download Specifications",
                data=file.read(),
                file_name="bounty_specifications.txt",
                mime="text/plain",
                key="download_link"
            )


for message in st.session_state.messages:
    avatar = "🔱" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Chat interface code
if user_prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)
    
    input_message = HumanMessage(content=user_prompt)
        
    with st.chat_message("assistant", avatar="🔱"):
        agent = bounty_builder()
        # Stream the agent's response
        for response_stream in agent.stream(
            {"messages": [input_message]}, config, stream_mode="values"
        ):
            display = response_stream["messages"][-1].content
            #st.markdown(display)    
        
        st.markdown(display)    
    # Append the assistant's full response to the chat history
    st.session_state.messages.append({"role": "assistant", "content": display})



