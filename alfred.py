import getpass
import os
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain import hub
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import operator
from typing import Annotated, List, Tuple
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from typing import Union
from typing import Literal
from langgraph.graph import END
from langgraph.graph import StateGraph, START
import asyncio
import streamlit as st


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("OPENAI_API_KEY")
_set_env("TAVILY_API_KEY")

tools = [TavilySearchResults(max_results=3)]

# Get the prompt to use - you can modify this!
prompt = hub.pull("ih/ih-react-agent-executor")
prompt.pretty_print()

# Choose the LLM that will drive the agent
llm = ChatOpenAI(model="gpt-4-turbo-preview")
agent_executor = create_react_agent(llm, tools, state_modifier=prompt)

class PlanExecute(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple], operator.add]
    response: str

class Plan(BaseModel):
    """Plan to follow in future"""

    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )

planner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert in designing bounties. For the given funding objective for creating a bounty, come up with a simple step by step plan. \
Keep it limited to 4 to 6 steps. The bounty should be well-defined, time-bound, practical, measurable, engaging and impactful.
This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. \
The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.""",
        ),
        ("placeholder", "{messages}"),
    ]
)

planner = planner_prompt | ChatOpenAI(
    model="gpt-4o", temperature=0
).with_structured_output(Plan)


class Response(BaseModel):
    """Response to user."""

    response: str


class Act(BaseModel):
    """Action to perform."""

    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )


replanner_prompt = ChatPromptTemplate.from_template(
    """For the given objective, come up with a simple step by step plan. \
This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. \
The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.

Your objective was this:
{input}

Your original plan was this:
{plan}

You have currently done the follow steps:
{past_steps}

Update your plan accordingly. If no more steps are needed and you can return to the user, then respond with that. Otherwise, fill out the plan. Only add steps to the plan that still NEED to be done. Do not return previously done steps as part of the plan."""
)


replanner = replanner_prompt | ChatOpenAI(
    model="gpt-4o", temperature=0
).with_structured_output(Act)

async def execute_step(state: PlanExecute):
    plan = state["plan"]
    plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
    task = plan[0]
    task_formatted = f"""For the following plan:
{plan_str}\n\nYou are tasked with executing step {1}, {task}."""
    agent_response = await agent_executor.ainvoke(
        {"messages": [("user", task_formatted)]}
    )
    return {
        "past_steps": [(task, agent_response["messages"][-1].content)],
    }


async def plan_step(state: PlanExecute):
    plan = await planner.ainvoke({"messages": [("user", state["input"])]})
    return {"plan": plan.steps}


async def replan_step(state: PlanExecute):
    output = await replanner.ainvoke(state)
    if isinstance(output.action, Response):
        return {"response": output.action.response}
    else:
        return {"plan": output.action.steps}


def should_end(state: PlanExecute):
    if "response" in state and state["response"]:
        return END
    else:
        return "agent"
    

workflow = StateGraph(PlanExecute)

# Add the plan node
workflow.add_node("planner", plan_step)

# Add the execution step
workflow.add_node("agent", execute_step)

# Add a replan node
workflow.add_node("replan", replan_step)

workflow.add_edge(START, "planner")

# From plan we go to agent
workflow.add_edge("planner", "agent")

# From agent, we replan
workflow.add_edge("agent", "replan")

workflow.add_conditional_edges(
    "replan",
    # Next, we pass in the function that will determine which node is called next.
    should_end,
    ["agent", END],
)

# Finally, we compile it!
# This compiles it into a LangChain Runnable,
# meaning you can use it as you would any other runnable
app = workflow.compile()

async def main():

    st.markdown("# Welcome to Alfred by Atlantis")
    st.markdown("Alfred v0 is your AI-powered assistant for designing impactful bounties in climate and sustainability. \
    Whether you’re funding clean water projects, renewable energy initiatives, or waste management solutions, \
    Alfred helps you create actionable plans that drive real-world results. Simply tell Alfred your funding objective, \
    and it will guide you through the process of creating, executing, and refining a step-by-step plan.")
    st.markdown("Check out the [Github Repo](https://github.com/AtlantisDAO1/Alfred) for more context on the motivation for this project and upcoming improvements to v0. \
    [Click here](https://github.com/AtlantisDAO1/Alfred/issues) to provide feedback or report an issue.")

    # Define scenarios
    scenarios = [
        "Create a bounty for surface runoff rainwater harvesting in Bangalore.",
        "Reward content creators for raising awareness on air quality in urban areas.",
        "Incentivize volunteers promoting waste management solutions in local communities."
    ]

    # Initialize the session state for the selected scenario
    if 'selected_scenario' not in st.session_state:
        st.session_state.selected_scenario = ""

    # Display clickable text for each scenario
    st.markdown("Select a scenario from following examples or enter your own. The tool will create an initial plan and suggest best practices for execution.")
    for scenario_text in scenarios:
        if st.button(scenario_text):
            st.session_state.selected_scenario = scenario_text

    # Text input box
    user_input = st.text_input("What would you like to fund?", st.session_state.selected_scenario)

    # Check if the user has entered input
    if user_input:
        # Use the user input in your application
        inputs = {"input": user_input}
        
        # Example configuration
        config = {"recursion_limit": 50}

        async for event in app.astream(inputs, config=config):
            for k, v in event.items():
                if k != "__end__":                    
                    
                    if "plan" in v:
                        st.markdown("# Remaining Plan to Execute:")
                        for step in v["plan"]:                            
                            st.markdown(f"- {step}")
                    elif "past_steps" in v:
                        for step, explanation in v["past_steps"]:
                            st.subheader(step)
                            st.markdown(explanation)
                    else:
                            st.markdown("unknown")
                    

                    
# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
