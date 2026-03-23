# app.py
# import litellm
# litellm._turn_on_debug()

import sys
import os
import logging
import warnings

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
from dotenv import load_dotenv
from mesa.visualization import (
    SolaraViz,
    make_plot_component,
    make_space_component,
)

from examples.saboteur.agents import Impostor, Crewmate, Task
from examples.saboteur.model import GameModel
from mesa_llm.parallel_stepping import enable_automatic_parallel_stepping
from mesa_llm.reasoning.react import ReActReasoning

# Suppress Pydantic serialization warnings
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic.main",
    message=r".*Pydantic serializer warnings.*",
)

# Also suppress through logging
logging.getLogger("pydantic").setLevel(logging.ERROR)

enable_automatic_parallel_stepping(mode="threading")

os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
os.environ["OPENAI_API_KEY"] = "ollama"

# load_dotenv()
# os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# --- Visual Constants ---
IMPOSTOR_COLOR = "#FF0000"  # Red
CREWMATE_COLOR = "#00FF00"  # Green
TASK_COLOR = "#FFD700"      # Gold

# --- Model Parameters (Sidebar) ---
model_params = {
    "seed": {
        "type": "InputText",
        "value": 42,
        "label": "Random Seed",
    },
    "initial_imps": {
        "type": "SliderInt",
        "value": 1,
        "label": "Impostor Count",
        "min": 1,
        "max": 3,
    },
    "initial_cms": {
        "type": "SliderInt",
        "value": 4,
        "label": "Crewmate Count",
        "min": 1,
        "max": 10,
    },
    "width": 10,
    "height": 10,
    "vision": 6,
    "max_steps": 30,
    "reasoning": ReActReasoning,
    "llm_model": "ollama/llama3.1", 
}

# --- Initial Model Instance ---
model = GameModel(
    initial_imps=model_params["initial_imps"]["value"],
    initial_cms=model_params["initial_cms"]["value"],
    width=model_params["width"],
    height=model_params["height"],
    reasoning=model_params["reasoning"],
    llm_model=model_params["llm_model"],
    vision=model_params["vision"],
    max_steps=model_params["max_steps"],
    n_tasks=6,
    seed=model_params["seed"]["value"],
)

# --- Agent Portrayal ---
def agent_portrayal(agent):
    if agent is None:
        return

    portrayal = {
        "size": 50,
        "color": "black"
    }
    
    # 1. Handle Dead Bodies
    if hasattr(agent, "state") and agent.state == "dead":
        portrayal["color"] = "#555555"  # Dark Gray
        portrayal["size"] = 30
        return portrayal

    # 2. Handle Tasks
    # We check string name to avoid import errors
    if type(agent).__name__ == "Task":
        if agent.state == "Completed":
            portrayal["color"] = "#006400"  # Dark Green (Completed)
            portrayal["size"] = 40
        else:
            portrayal["color"] = "#FFD700"  # Gold (Active)
            portrayal["size"] = 200
        portrayal["marker"] = "s"
        return portrayal
    
    # 3. Handle Agents
    elif isinstance(agent, Impostor):
        portrayal["color"] = IMPOSTOR_COLOR
        if agent.kill_cooldown > 0:
             portrayal["color"] = "#8B0000" # Darker red on cooldown

    elif isinstance(agent, Crewmate):
        portrayal["color"] = CREWMATE_COLOR

    return portrayal

# --- Components ---
space_component = make_space_component(
    agent_portrayal, 
    draw_grid=True
)

chart_component = make_plot_component(
    {
        "Crewmates": CREWMATE_COLOR,
        "Impostors": IMPOSTOR_COLOR,
    }
)

# --- Main App ---
if __name__ == "__main__":
    page = SolaraViz(
        model,
        components=[
            space_component,
            chart_component,
        ],
        model_params=model_params,
        name="Saboteur: AI Impostor Simulation",
    )