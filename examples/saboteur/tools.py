from mesa_llm.tools.tool_decorator import tool
from examples.saboteur.agents import impostor_tool_manager, crewmate_tool_manager

# ==============================================================================
#                               SHARED TOOLS
# ==============================================================================

@tool(tool_manager=impostor_tool_manager)
@tool(tool_manager=crewmate_tool_manager)
def move_randomly(agent: "LLMAgent", **kwargs) -> str:
    """
    Move to an adjacent cell (up, down, left, right, or diagonals).
    
    Args:
        agent: Provided automatically.
        kwargs: (Optional) Ignores extra arguments like 'direction'.
        
    Returns:
        Result of the movement.
    """
    # 1. Capture old position for the log
    old_pos = agent.pos

    # 2. Get possible moves (Force include_center=False)
    possible_steps = agent.model.grid.get_neighborhood(
        agent.pos,
        moore=True,
        include_center=False
    )
    
    if not possible_steps:
        return "You are stuck and cannot move."

    # 3. Pick one and move
    new_position = agent.random.choice(possible_steps)
    agent.model.grid.move_agent(agent, new_position)
    
    return f"Moved from {old_pos} to {new_position}."


@tool(tool_manager=impostor_tool_manager)
@tool(tool_manager=crewmate_tool_manager)
def stay(agent: "LLMAgent", **kwargs) -> str:
    """
    Stay in the current position for one turn.
    
    Args:
        agent: Provided automatically.
        kwargs: (Optional) Ignores extra arguments.
        
    Returns:
        Confirmation message.
    """
    return f"You stayed at {agent.pos}."


# ==============================================================================
#                               IMPOSTOR TOOLS
# ==============================================================================

@tool(tool_manager=impostor_tool_manager)
def kill_agent(agent: "LLMAgent", target_id: int, **kwargs) -> str:
    """
    Kill a specific Crewmate in the same cell. 
    REQUIRES: Kill Cooldown must be 0.
    
    Args:
        agent: Provided automatically.
        target_id: The integer ID of the agent to kill.
        kwargs: (Optional) Ignores extra arguments.
        
    Returns:
        Success or Failure message.
    """
    # 1. Check Cooldown
    if agent.kill_cooldown > 0:
        return f"FAILURE: Kill Cooldown is not 0. You must wait {agent.kill_cooldown} turns."

    if target_id is None:
        return "FAILURE: You called kill_agent but did not provide a 'target_id'. You must specify WHO to kill (e.g., target_id=5)."
    
    # 2. Check location (Must be in same cell)
    nearby_cells = agent.model.grid.get_neighborhood(
        agent.pos, moore=True, include_center=True, radius=1
    )
    nearby_agents = agent.model.grid.get_cell_list_contents(nearby_cells)
    
    target = None
    for a in nearby_agents:
        if a.unique_id == target_id:
            target = a
            break
            
    if not target:
        return f"FAILURE: Agent {target_id} is not in your cell. You can only kill agents standing on exactly the same square."

    if target.unique_id == agent.unique_id:
        return "FAILURE: You cannot kill yourself."

    # 3. EXECUTE KILL
    target.state = "dead"
    target.remove() # Remove from simulation loop
    
    agent.kill_cooldown = 3 # Reset cooldown
    
    return f"SUCCESS: You killed Agent {target_id}. Their body is now on the floor. MOVE AWAY immediately!"


@tool(tool_manager=impostor_tool_manager)
def fake_task(agent: "LLMAgent", **kwargs) -> str:
    """
    Pretend to do a task to blend in.
    
    Args:
        agent: Provided automatically.
        kwargs: (Optional) Ignores extra arguments.
        
    Returns:
        Status message.
    """
    agent.state = "doing_task" 
    return f"You are faking a task at {agent.pos}. You look busy."


# ==============================================================================
#                               CREWMATE TOOLS
# ==============================================================================

@tool(tool_manager=crewmate_tool_manager)
def do_task(agent: "LLMAgent", **kwargs) -> str:
    """
    Perform a task at the current location.
    
    Args:
        agent: Provided automatically.
        kwargs: (Optional) Ignores extra arguments.
        
    Returns:
        Success or Failure message.
    """
    # 1. Check if valid task location
    try:
        is_task_loc = agent.model.task_layer.data[agent.pos] == 1
    except:
        return "Error checking task layer."

    if not is_task_loc:
        return "FAILURE: There is no task here to perform."

    # 2. Start Task
    agent.state = "doing_task"
    agent.busy_duration = 1 
    
    # 3. Remove task from grid (Task completed)
    agent.model.task_layer.set_cell(agent.pos, 0)
    
    return f"SUCCESS: You started the task at {agent.pos}. It will be finished next turn."
