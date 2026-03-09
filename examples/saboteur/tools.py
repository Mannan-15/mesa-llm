from mesa_llm.tools.tool_decorator import tool
from mesa_llm.llm_agent import LLMAgent 
from examples.saboteur.agents import impostor_tool_manager, crewmate_tool_manager

# NEW FEATURE
from pydantic import BaseModel, Field, ValidationError

class KillActionSchema(BaseModel):
    """Strict schema to prevent LLM hallucinations during tool execution."""
    target_id: int = Field(..., description = "The integer ID of the crewmate to eliminate.")
    
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
    pass

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
def move_to(agent: "LLMAgent", **kwargs):
    """
    Move to a specific location on the grid.

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    pass

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
def kill_agent(agent: "LLMAgent", action_data: KillActionSchema = None, **kwargs) -> str:
    """
    Kill a specific Crewmate in the same cell or adjacent cell (Distance <= 1).
    REQUIRES: Kill Cooldown must be 0.
    
    Args:
        agent: The agent instance.
        action_data: The strict Pydantic schema containing the target_id.
        kwargs: Extra arguments ignored.
    """
    from examples.saboteur.agents import Task, Impostor
    import ast
    from pydantic import ValidationError

    # 0. HANDLE MISSING ARGUMENTS (When the LLM gets lazy)
    if action_data is None and 'target_id' not in kwargs:
        return "FAILURE: You forgot to provide the target_id! You must specify who to kill (e.g., target_id=12)."

    # 1. THE GSOC PATCH (Parse whatever messy format mesa-llm throws at us)
    try:
        if isinstance(action_data, str):
            action_dict = ast.literal_eval(action_data)
            action_data = KillActionSchema(**action_dict)
        elif isinstance(action_data, dict):
            action_data = KillActionSchema(**action_data)
        elif 'target_id' in kwargs: # Fallback if framework passes it cleanly in kwargs
            action_data = KillActionSchema(target_id=kwargs['target_id'])
    except (ValueError, SyntaxError) as e:
        return "FAILURE: Your action_data was formatted incorrectly. Use a valid JSON/dictionary."
    except ValidationError as e:
        return f"FAILURE: Invalid format. You must provide a valid target_id. Details: {e}"

    # Ensure it successfully became a schema object
    if not isinstance(action_data, KillActionSchema):
        return "FAILURE: Could not extract target_id from your action."

    clean_target_id = action_data.target_id

    # 2. STATE VALIDATION
    if agent.kill_cooldown > 0:
        return f"FAILURE: Kill Cooldown is {agent.kill_cooldown}. You cannot kill yet."

    # 3. SPATIAL & ENTITY VALIDATION
    nearby_cells = agent.model.grid.get_neighborhood(
        agent.pos, moore=True, include_center=True, radius=1
    )
    nearby_agents = agent.model.grid.get_cell_list_contents(nearby_cells)
    
    # Find the target safely
    target = None
    for a in nearby_agents:
        if getattr(a, 'unique_id', None) == clean_target_id:
            target = a
            break
            
    if not target:
        return f"FAILURE: Agent {clean_target_id} is not within range (1 cell). You must get closer."
    if isinstance(target, Task):
        return f"FAILURE: Agent {clean_target_id} is a Task. You can only kill Crewmates!"
    if isinstance(target, Impostor):
        return f"FAILURE: Agent {clean_target_id} is an Impostor (your ally). Friendly fire is disabled!"
    if target.unique_id == agent.unique_id:
        return "FAILURE: You cannot kill yourself."

    # 4. EXECUTE
    target.state = "dead"
    agent.kill_cooldown = 5 
    
    return f"SUCCESS: You killed Agent {clean_target_id} at {target.pos}."

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
def report_dead_body(agent: "LLMAgent"):
    """
    Report a dead body to trigger an emergency meeting.

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    # agent.model.trigger_meeting()
    pass

@tool(tool_manager=crewmate_tool_manager)
def move_to(agent: "LLMAgent", **kwargs):
    """
    Move to a specific location on the grid.

    Args:
        agent: The agent instance.
        kwargs: Extra arguments ignored.
    """
    pass
