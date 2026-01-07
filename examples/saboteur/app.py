# app.py
import sys
import os

# --- OLLAMA CONFIGURATION (Must run before model init) ---
# This redirects the OpenAI client to your local Ollama server
os.environ["OPENAI_API_KEY"] = "ollama"
os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
os.environ["OLLAMA_API_KEY"] = "ollama"       # <--- Add this
os.environ["OLLAMA/LLAMA3.1_API_KEY"] = "ollama"
# Add this line to satisfy the library's check for "llama3.1":
os.environ["LLAMA3.1_API_KEY"] = "ollama"

# Add the project root to system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import logging
import warnings
import os  # Added os import
import numpy as np
import matplotlib.colors as mcolors

from dotenv import load_dotenv
from mesa.visualization import (
    SolaraViz,
    make_plot_component,
    make_space_component,
)

# Adjust these imports to match your folder structure
from examples.saboteur.agents import Impostor, Crewmate
from examples.saboteur.model import GameModel
from mesa_llm.parallel_stepping import enable_automatic_parallel_stepping
from mesa_llm.reasoning.react import ReActReasoning

# --- Setup & Configuration ---
# Suppress Pydantic and other warnings for cleaner logs
warnings.filterwarnings("ignore", category=UserWarning)
logging.getLogger("pydantic").setLevel(logging.ERROR)

enable_automatic_parallel_stepping(mode="threading")
load_dotenv()

# --- Visual Constants ---
IMPOSTOR_COLOR = "#FF0000"  # Red
CREWMATE_COLOR = "#00FF00"  # Green
TASK_COLOR = "#FFD700"      # Gold (for the background task layer)

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
        "max": 3, # Reduced max for local performance
    },
    "initial_cms": {
        "type": "SliderInt",
        "value": 4, # Reduced default for local performance
        "label": "Crewmate Count",
        "min": 1,
        "max": 10,
    },
    # Reduced grid size slightly for faster pathfinding/rendering with local LLM lag
    "width": 10, 
    "height": 10,
    "vision": 6, # Reduced vision slightly to reduce prompt token count (speed up Llama 3)
    "max_steps": 30,
    "reasoning": ReActReasoning,
    "llm_model": "ollama/llama3.1",  # CHANGED: Default to local Llama 3.1
}

# --- Initial Model Instance ---
# SolaraViz needs an initial instance to build the layout
model = GameModel(
    initial_imps=model_params["initial_imps"]["value"],
    initial_cms=model_params["initial_cms"]["value"],
    width=model_params["width"],
    height=model_params["height"],
    reasoning=model_params["reasoning"],
    llm_model=model_params["llm_model"],
    vision=model_params["vision"],
    max_steps=model_params["max_steps"],
    n_tasks=5,
    seed=model_params["seed"]["value"],
)

# --- Agent Portrayal ---
def agent_portrayal(agent):
    if agent is None:
        return

    portrayal = {
        "size": 50,  # Size of the dot
    }

    if isinstance(agent, Impostor):
        portrayal["color"] = IMPOSTOR_COLOR
        # Optional: Make Impostor slightly larger or distinct shape if supported
        # portrayal["marker"] = "v" 

    elif isinstance(agent, Crewmate):
        portrayal["color"] = CREWMATE_COLOR
        # If the crewmate is dead (if you track that state), turn them gray
        if hasattr(agent, "state") and agent.state == "dead":
            portrayal["color"] = "#808080"

    return portrayal

# --- Grid & Task Layer Visualization ---
def post_process(ax):
    """
    Custom drawing function to render the Task PropertyLayer 
    underneath the agents.
    """
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.get_figure().set_size_inches(8, 8)

    # Note: Visualizing the property layer (tasks) directly inside this specific 
    # Solara component hook is complex without passing the model state explicitly.
    # For V1, we stick to the agent grid.
    pass

# --- Components ---
space_component = make_space_component(
    agent_portrayal, 
    post_process=post_process, 
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
        name="Saboteur: AI Impostor Simulation (Local Llama 3.1)",
    )
    