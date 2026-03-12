<h1>LLM-Powered Social Deduction (Saboteur/Among Us)</h1>

<p><strong>Disclaimer:</strong> This is a toy model designed for illustrative purposes and is not based on a real research paper. It serves as a flagship demonstration of how Mesa-LLM handles complex multi-agent spatial reasoning, asymmetrical information, and deceptive communication.</p>

<h3>Summary</h3>
<p>This model is a grid-based social deduction simulation inspired by the game <em>Among Us</em>. The objective is to test how effectively Large Language Models can navigate imperfect information, maintain hidden roles, and engage in active deception or logical deduction.</p>
<ul>
  <li><strong>Crewmates:</strong> Their primary goal is to navigate the spatial grid and complete a series of localized tasks. They win if all tasks are completed or if they successfully identify and vote out all the Saboteurs.</li>
  <li><strong>Saboteurs (Impostors):</strong> Their objective is to eliminate the Crewmates before the tasks are finished without getting caught. They have access to restricted tools and can use deceptive communication to frame innocent agents.</li>
</ul>

<h3>Agent Backstories & Identity</h3>
<p>To test complex role-playing, agents are injected with highly specific, asymmetrical <strong>backstories</strong> via their system prompts. A Crewmate might secretly be an <em>Engineer</em> (who is legally allowed to use vents, risking looking like a Saboteur), while a Saboteur might be a <em>Shapeshifter</em> (capable of temporarily mimicking another agent's identity). These backstories dictate their behavioral heuristics and how they defend themselves during interrogations.</p>

<h3>Agent Decision Logic & Robust Parsing</h3>
<p>Both Crewmates and Saboteurs are implemented as autonomous LLM-powered agents navigating a 2D spatial grid. Their actions are determined by a cognitive reasoning module that processes their hidden identity, local spatial observations (e.g., who is in their room), and a strict set of available tools.</p>
<ul>
  <li><strong>Robust Tool Calling:</strong> To ensure the simulation never crashes from hallucinated outputs, all LLM actions are enforced via strict <strong>Pydantic validation</strong>. If the LLM generates malformed JSON, an automated <strong>JSON-repair</strong> and auto-correction fallback mechanism intercepts and fixes the syntax before execution.</li>
  <li><strong>Available Tools:</strong> Saboteurs can use <code>kill_agent</code>, <code>vent</code>, and <code>sabotage_environment</code>. Crewmates use <code>move_to_location</code>, <code>complete_task</code>, and <code>report_body</code>. Both use the <code>speak_to</code> tool to share information or spread misinformation.</li>
</ul>

<h3>Dynamic Execution (TTL & Interruptible Planning)</h3>
<p>Because the grid is a highly dynamic environment, standard "plan-and-execute" loops often fail if the world changes while the agent is acting. To solve this, actions are governed by a <strong>Time-To-Live (TTL)</strong> mechanic.</p>
<p>When an agent generates a multi-step trajectory (e.g., "Walk 5 tiles to the Cafeteria"), the simulation executes it step-by-step. However, if a critical environmental change occurs in the middle of execution—such as another agent dropping dead in their field of view or an emergency alarm triggering—the TTL is instantly revoked. The current plan is <strong>interrupted</strong> mid-stride, forcing the agent's LLM to reassess the new state and generate an immediate reaction.</p>

<h3>Social Deduction & Voting Protocol</h3>
<p>The core friction of the simulation occurs during the "Emergency Meeting" phase. When a Crewmate uses the <code>report_body</code> tool, the standard spatial simulation pauses. Agents are thrust into a synchronous chat room where they must use the <code>speak_to</code> tool to debate, defend themselves, or accuse others based on their memory buffers. The phase concludes with the <code>cast_vote</code> tool, simulating realistic deception and jury dynamics.</p>

<h3>Data Collection</h3>
<p>The model tracks the survival rate of Crewmates, the number of completed tasks, the accuracy of the voting phase, and token-usage/API costs for the underlying LLMs to analyze the efficiency of deceptive reasoning.</p>

<h3>Files</h3>
<ul>
  <li><code>model.py</code>: Core grid simulation, state management, TTL execution loops, and voting protocol logic.</li>
  <li><code>agent.py</code>: Crewmate and Saboteur class definitions, backstory ingestion, and cognitive reasoning loops.</li>
  <li><code>app.py</code>: Sets up the interactive Solara visualization and web interface.</li>
  <li><code>tools.py</code>: Pydantic-validated tool schemas (<code>kill_agent</code>, <code>vent</code>, <code>report_body</code>) equipped with JSON-repair mechanisms for the LLM agents to execute.</li>
</ul>
