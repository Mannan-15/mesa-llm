from mesa_llm.tools.tool_decorator import tool
from mesa_llm.llm_agent import LLMAgent 
from examples.saboteur.agents import impostor_tool_manager, crewmate_tool_manager

# ==============================================================================
#                               HELPER FUNCTIONS
# ==============================================================================

def _move_randomly_logic(agent):
    old_pos = agent.pos
    # include_center=False ensures they actually move
    possible_steps = agent.model.grid.get_neighborhood(
        agent.pos, moore=True, include_center=False
    )
    
    if not possible_steps:
        return "You are stuck and cannot move."

    new_position = agent.random.choice(possible_steps)
    agent.model.grid.move_agent(agent, new_position)
    return f"Moved from {old_pos} to {new_position}."

def _stay_logic(agent):
    return f"You stayed at {agent.pos}."

def _move_to_logic(agent):
    next

# ==============================================================================
#                             IMPOSTOR TOOLS
# ==============================================================================

@tool(tool_manager=impostor_tool_manager)
def move_randomly(agent: "LLMAgent", **kwargs) -> str:
    """
    Move to an adjacent cell (up, down, left, right, or diagonals).

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored by this tool.
    """
    return _move_randomly_logic(agent)

@tool(tool_manager=impostor_tool_manager)
def move_to():
    next

@tool(tool_manager=impostor_tool_manager)
def stay(agent: "LLMAgent", **kwargs) -> str:
    """
    Stay in the current position for one turn.

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    return _stay_logic(agent)

@tool(tool_manager=impostor_tool_manager)
def kill_agent(agent: "LLMAgent", target_id: int = None, **kwargs) -> str:
    """
    Kill a specific Crewmate in the same cell or adjacent cell (Distance <= 1).
    REQUIRES: Kill Cooldown must be 0.
    
    Args:
        agent: The agent instance.
        target_id: The integer ID of the agent to kill.
        kwargs: Extra arguments ignored.
    """
    # Import Task to check against it
    from examples.saboteur.agents import Task, Impostor

    # 1. Check Cooldown
    if agent.kill_cooldown > 0:
        return f"FAILURE: Kill Cooldown is {agent.kill_cooldown}. You cannot kill yet."

    if target_id is None:
        return "FAILURE: You forgot the 'target_id'. Usage: kill_agent(target_id=12)."
    
    # 2. Check nearby agents (Radius 1)
    nearby_cells = agent.model.grid.get_neighborhood(
        agent.pos, moore=True, include_center=True, radius=1
    )
    nearby_agents = agent.model.grid.get_cell_list_contents(nearby_cells)
    
    target = None
    for a in nearby_agents:
        try:
            if int(a.unique_id) == int(target_id):
                target = a
                break
        except ValueError:
            continue
            
    if not target:
        return f"FAILURE: Agent {target_id} is not within range (1 cell). You must get closer."

    # --- NEW CHECK: PREVENT KILLING TASKS ---
    if isinstance(target, Task):
        return f"FAILURE: Agent {target_id} is a Task (inanimate object). You can only kill Crewmates!"
    
    if isinstance(target, Impostor):
        return f"Failure: Agent {target_id} is other Impostor (your ally). You can only kill Crewmates!"
    
    if target.unique_id == agent.unique_id:
        return "FAILURE: You cannot kill yourself."

    # 3. EXECUTE KILL
    target.state = "dead"
    agent.kill_cooldown = 5 
    
    return f"SUCCESS: You killed Agent {target_id} at {target.pos}."

@tool(tool_manager=impostor_tool_manager)
def fake_task(agent: "LLMAgent", **kwargs) -> str:
    """
    Pretend to do a task to blend in.

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    agent.state = "doing_task" 
    return f"You are faking a task at {agent.pos}. You look busy."


# ==============================================================================
#                             CREWMATE TOOLS
# ==============================================================================

@tool(tool_manager=crewmate_tool_manager)
def move_randomly(agent: "LLMAgent", **kwargs) -> str:
    """
    Move to an adjacent cell (up, down, left, right, or diagonals).

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    return _move_randomly_logic(agent)

@tool(tool_manager=crewmate_tool_manager)
def stay(agent: "LLMAgent", **kwargs) -> str:
    """
    Stay in the current position for one turn.

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    return _stay_logic(agent)

@tool(tool_manager=crewmate_tool_manager)
def do_task(agent: "LLMAgent", **kwargs) -> str:
    """
    Perform a task. 
    CONDITION: Can only be used if 'Task Available' is YES in your radar.

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    # Import Task locally to avoid circular import
    from examples.saboteur.agents import Task

    # 1. Check Task Layer
    is_task_loc = False
    try:
        if hasattr(agent.model, "task_layer"):
            is_task_loc = agent.model.task_layer.data[agent.pos] == 1
    except: pass

    if not is_task_loc:
        return "FAILURE: There is no task here. Check your Radar for 'Task Available: YES'."

    # 2. Start Task
    agent.state = "doing_task"
    agent.busy_duration = 1 
    
    # 3. Complete Task Logic
    agent.model.task_layer.set_cell(agent.pos, 0)
    
    # Remove the visual Task agent
    cell_contents = agent.model.grid.get_cell_list_contents([agent.pos])
    for obj in cell_contents:
        if isinstance(obj, Task):
            agent.model.grid.remove_agent(obj)
    
    return f"SUCCESS: Task started at {agent.pos}."

@tool(tool_manager=crewmate_tool_manager)
def trigger_discussion():
    next

@tool(tool_manager=crewmate_tool_manager)
def move_to():
    next
    