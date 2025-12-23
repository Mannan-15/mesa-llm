import random
from typing import TYPE_CHECKING

from examples.saboteur.agents import (
    impostor_tool_manager,
    crewmate_tool_manager,
    Impostor,
    Crewmate
)
from mesa_llm.tools.tool_decorator import tool

if TYPE_CHECKING:
    from mesa_llm.llm_agent import LLMAgent


# --- SHARED TOOLS (Movement & Idle) ---

@tool(tool_manager=impostor_tool_manager)
@tool(tool_manager=crewmate_tool_manager)
def move_randomly(agent: "LLMAgent") -> str:
    """
    Move to a random adjacent cell. Use this to patrol, flee, or find tasks.

        Args:
            agent: Provided automatically

        Returns:
            A string confirming the new location.
    """
    # 1. Get valid adjacent cells
    neighborhood = agent.model.grid.get_neighborhood(
        agent.pos, moore=True, include_center=False
    )
    
    if not neighborhood:
        return "Move failed: No valid cells nearby."

    # 2. Pick one random cell
    new_pos = random.choice(neighborhood)
    
    # 3. Move the agent
    agent.model.grid.move_agent(agent, new_pos)
    
    return f"Moved from old position to {new_pos}."


@tool(tool_manager=impostor_tool_manager)
@tool(tool_manager=crewmate_tool_manager)
def stay(agent: "LLMAgent") -> str:
    """
    Stay in the current position for one turn.

        Args:
            agent: Provided automatically

        Returns:
            Confirmation of waiting.
    """
    return f"Agent {agent.unique_id} stayed at {agent.pos}."


# --- CREWMATE SPECIFIC TOOLS ---

@tool(tool_manager=crewmate_tool_manager)
def do_task(agent: "LLMAgent") -> str:
    """
    Start performing a task at the current location.
    Requires 5 steps to complete.
    """
    # 1. Check for valid task location
    try:
        has_task = agent.model.task_layer.data[agent.pos] == 1
    except AttributeError:
        return "Error: Task layer not found."

    if has_task:
        # 2. Set the timer
        agent.state = "task"
        agent.busy_duration = 5 
        return "STARTED TASK: I have started working. I will be busy for the next 5 steps."
    else:
        return "FAILURE: No task found at this location."
    

# --- IMPOSTOR SPECIFIC TOOLS ---

@tool(tool_manager=impostor_tool_manager)
def kill_agent(agent: "LLMAgent", target_id: int) -> str:
    """
    Kill a specific agent. 
    Requirements: Target must be in the same cell (distance 0).

        Args:
            target_id: The unique ID of the target agent.
            agent: Provided automatically

        Returns:
            Result of the kill attempt.
    """
    # 1. Check Cooldown (Safety check, though LLM should handle it)
    if hasattr(agent, "kill_cooldown") and agent.kill_cooldown > 0:
        return f"FAILURE: Kill Cooldown not ready ({agent.kill_cooldown} turns left)."

    # 2. Find the target agent object
    target_agent = next(
        (a for a in agent.model.agents if a.unique_id == int(target_id)), None
    )

    if not target_agent:
        return f"FAILURE: Agent {target_id} not found."

    # 3. Check Range (Must be in same cell)
    if target_agent.pos != agent.pos:
        return f"FAILURE: Target {target_id} is too far away ({target_agent.pos}). You must be in the same cell."

    # 4. Execute Kill
    if isinstance(target_agent, Impostor):
        return "FAILURE: You cannot kill another Impostor."
    
    # Set state to dead (visuals can use this)
    target_agent.state = "dead"
    
    # Remove from scheduler/grid so they stop moving
    agent.model.grid.remove_agent(target_agent)
    # Note: We keep them in agent list for game over check, or handle removal logic in model
    
    # Reset cooldown
    agent.kill_cooldown = 10  # Reset to default cooldown
    
    return f"SUCCESS: Agent {target_id} has been eliminated."


@tool(tool_manager=impostor_tool_manager)
def fake_task(agent: "LLMAgent") -> str:
    """
    Pretend to do a task to blend in with Crewmates.

        Args:
            agent: Provided automatically

        Returns:
            Confirmation of fake task.
    """
    return f"Agent {agent.unique_id} is faking a task at {agent.pos}."
