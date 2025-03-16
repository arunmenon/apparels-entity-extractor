"""
OpenAI-inspired Agent Framework - A flexible framework for building LLM-powered agents.

This module implements an agent framework inspired by OpenAI's Agents SDK with:
1. Tool-using agents that can make decisions about next actions
2. Context sharing and persistence between tools and agents
3. Typed, structured outputs using Pydantic models
4. Agent-to-agent handoffs for specialized delegation
5. Streaming support for incremental responses
6. Comprehensive tracing for debugging and analytics
7. Policy guardrails for validation and safety
"""

import inspect
import json
import logging
import os
import time
import uuid
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union, get_type_hints

import pydantic
from pydantic import BaseModel, create_model, Field

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Type variables for generics
T = TypeVar('T')
AgentContextType = TypeVar('AgentContextType')

class AgentContextWrapper(Generic[AgentContextType]):
    """Wrapper for agent context that can be passed to tools."""
    
    def __init__(self, agent_context: AgentContextType):
        self.agent_context = agent_context


class ToolDefinition(BaseModel):
    """Definition of a tool that an agent can use."""
    
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    is_async: bool = False
    
    class Config:
        arbitrary_types_allowed = True


def function_tool(_func=None, *, name: Optional[str] = None, description: Optional[str] = None):
    """Decorator to create a tool from a function."""
    
    def decorator(func):
        func_name = name or func.__name__
        func_desc = description or func.__doc__ or f"Call the {func_name} function."
        
        # Get function signature
        sig = inspect.signature(func)
        params = {}
        
        # Extract param info from type hints and docstrings
        type_hints = get_type_hints(func)
        for param_name, param in sig.parameters.items():
            # Skip context parameter for tools that take context
            if param_name == 'context' and param.annotation != inspect.Parameter.empty:
                continue
                
            param_type = type_hints.get(param_name, Any)
            param_default = None if param.default is inspect.Parameter.empty else param.default
            param_required = param.default is inspect.Parameter.empty
            
            params[param_name] = {
                "type": param_type,
                "description": "", # Could parse from docstring
                "required": param_required,
                "default": param_default
            }
        
        # Create tool definition
        tool_def = ToolDefinition(
            name=func_name,
            description=func_desc,
            parameters=params,
            function=func,
            is_async=inspect.iscoroutinefunction(func)
        )
        
        # Attach tool definition to function
        func._tool_definition = tool_def
        
        return func
    
    if _func is None:
        return decorator
    return decorator(_func)


class GuardrailTripwireTriggered(Exception):
    """Exception raised when a guardrail is triggered."""
    pass


class Guardrail(ABC):
    """Base class for guardrails that validate inputs or outputs."""
    
    @abstractmethod
    async def validate(self, data: Any, context: Any) -> bool:
        """Validate the given data with the guardrail.
        
        Args:
            data: The data to validate
            context: The agent context
            
        Returns:
            True if validation passes, False otherwise
        """
        pass


class CustomGuardrail(Guardrail):
    """Custom guardrail with a user-defined validation function."""
    
    def __init__(self, 
                 guardrail_function: Callable[[Any, Any], Union[bool, asyncio.coroutine]],
                 tripwire_config: Optional[Callable[[bool], bool]] = None,
                 error_message: str = "Guardrail check failed"):
        """Initialize the custom guardrail.
        
        Args:
            guardrail_function: Function that performs validation
            tripwire_config: Function that determines if an exception should be raised
            error_message: Message to include in the exception
        """
        self.guardrail_function = guardrail_function
        self.tripwire_config = tripwire_config or (lambda x: not x)
        self.error_message = error_message
        self.is_async = inspect.iscoroutinefunction(guardrail_function)
    
    async def validate(self, data: Any, context: Any) -> bool:
        """Validate the given data against the guardrail function.
        
        Args:
            data: The data to validate
            context: The agent context
            
        Returns:
            True if validation passes, False otherwise
            
        Raises:
            GuardrailTripwireTriggered: If validation fails and tripwire is configured to raise
        """
        # Call the guardrail function (async or sync)
        if self.is_async:
            result = await self.guardrail_function(data, context)
        else:
            result = self.guardrail_function(data, context)
        
        # Check if we should raise an exception
        if self.tripwire_config(result):
            raise GuardrailTripwireTriggered(self.error_message)
        
        return result


class ContentPolicyGuardrail(Guardrail):
    """Guardrail that checks content against a policy using an LLM."""
    
    def __init__(self, 
                 policy: str,
                 llm_client: Any,
                 error_message: str = "Content policy violation detected"):
        """Initialize the content policy guardrail.
        
        Args:
            policy: Description of the content policy
            llm_client: Client for the LLM service
            error_message: Message to include in the exception
        """
        self.policy = policy
        self.llm_client = llm_client
        self.error_message = error_message
    
    async def validate(self, data: Any, context: Any) -> bool:
        """Validate the given data against the content policy.
        
        Args:
            data: The data to validate (usually a string)
            context: The agent context
            
        Returns:
            True if validation passes, False otherwise
            
        Raises:
            GuardrailTripwireTriggered: If validation fails
        """
        # Convert data to string if it's not already
        if not isinstance(data, str):
            data = str(data)
        
        # Call LLM to check if content violates policy
        system_prompt = f"""
        You are a content policy checker. Your job is to determine if the given content
        violates the following policy:
        
        {self.policy}
        
        Return a JSON object with:
        1. "complies": true/false indicating if the content complies with the policy
        2. "reason": Explanation of why it does or doesn't comply
        """
        
        try:
            response = await self.llm_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": data}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            complies = result.get("complies", True)
            
            if not complies:
                reason = result.get("reason", "Unknown policy violation")
                raise GuardrailTripwireTriggered(f"{self.error_message}: {reason}")
            
            return complies
            
        except Exception as e:
            if isinstance(e, GuardrailTripwireTriggered):
                raise
            logger.error(f"Error in content policy check: {e}")
            # Default to allowing content if check fails
            return True


class TraceEvent(BaseModel):
    """Event in an agent trace."""
    
    event_type: str
    timestamp: float = Field(default_factory=time.time)
    data: Dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    """Record of an agent's execution."""
    
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    agent_name: str
    events: List[TraceEvent] = Field(default_factory=list)
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    
    def add_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Add an event to the trace.
        
        Args:
            event_type: Type of the event
            data: Data associated with the event
        """
        self.events.append(TraceEvent(event_type=event_type, data=data))
    
    def finish(self) -> None:
        """Mark the trace as finished."""
        self.end_time = time.time()


class TracingProcessor(ABC):
    """Base class for processors that handle agent traces."""
    
    @abstractmethod
    async def process_trace(self, trace: Trace) -> None:
        """Process a completed trace.
        
        Args:
            trace: The trace to process
        """
        pass


class ConsoleTracingProcessor(TracingProcessor):
    """Tracing processor that logs traces to the console."""
    
    async def process_trace(self, trace: Trace) -> None:
        """Log the trace to the console.
        
        Args:
            trace: The trace to log
        """
        logger.info(f"Trace {trace.trace_id} for agent {trace.agent_name}:")
        for event in trace.events:
            logger.info(f"  {event.event_type} at {event.timestamp}: {event.data}")


class FileTracingProcessor(TracingProcessor):
    """Tracing processor that writes traces to a file."""
    
    def __init__(self, output_dir: str = "traces"):
        """Initialize the file tracing processor.
        
        Args:
            output_dir: Directory to write traces to
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    async def process_trace(self, trace: Trace) -> None:
        """Write the trace to a file.
        
        Args:
            trace: The trace to write
        """
        file_path = os.path.join(self.output_dir, f"{trace.trace_id}.json")
        with open(file_path, 'w') as f:
            f.write(trace.json(indent=2))


class TracingManager:
    """Manager for trace processing."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TracingManager, cls).__new__(cls)
            cls._instance.processors = []
            
            # Add default processor based on environment
            if os.environ.get("LLM_DEBUG", "").lower() in ("true", "1", "yes"):
                cls._instance.processors.append(ConsoleTracingProcessor())
        
        return cls._instance
    
    def add_processor(self, processor: TracingProcessor) -> None:
        """Add a tracing processor.
        
        Args:
            processor: The processor to add
        """
        self.processors.append(processor)
    
    def set_processors(self, processors: List[TracingProcessor]) -> None:
        """Set the list of tracing processors.
        
        Args:
            processors: The processors to use
        """
        self.processors = processors
    
    async def process_trace(self, trace: Trace) -> None:
        """Process a trace with all registered processors.
        
        Args:
            trace: The trace to process
        """
        for processor in self.processors:
            try:
                await processor.process_trace(trace)
            except Exception as e:
                logger.error(f"Error processing trace with {processor.__class__.__name__}: {e}")


class StreamEventType(str, Enum):
    """Types of events that can be streamed."""
    
    THINKING_START = "thinking_start"
    THINKING_UPDATE = "thinking_update"
    THINKING_END = "thinking_end"
    TOOL_START = "tool_start"
    TOOL_UPDATE = "tool_update"
    TOOL_END = "tool_end"
    TEXT_DELTA = "text_delta"
    FINAL_ANSWER = "final_answer"
    HANDOFF = "handoff"
    ERROR = "error"


@dataclass
class StreamEvent:
    """Event in a stream of agent output."""
    
    event_type: StreamEventType
    delta: Any
    data: Dict[str, Any] = field(default_factory=dict)


class AgentStream:
    """Stream of events from an agent execution."""
    
    def __init__(self):
        """Initialize an agent stream."""
        self.queue = asyncio.Queue()
        self.finished = False
    
    def add_event(self, event: StreamEvent) -> None:
        """Add an event to the stream.
        
        Args:
            event: The event to add
        """
        self.queue.put_nowait(event)
    
    def finish(self) -> None:
        """Mark the stream as finished."""
        self.finished = True
        self.queue.put_nowait(None)  # Sentinel to indicate end of stream
    
    async def stream_events(self) -> AsyncGenerator[StreamEvent, None]:
        """Generate events from the stream.
        
        Yields:
            StreamEvent: The next event in the stream
        """
        while not self.finished or not self.queue.empty():
            event = await self.queue.get()
            if event is None:  # End of stream
                break
            yield event


class HandoffTarget(BaseModel):
    """Target for an agent handoff."""
    
    agent_name: str
    agent: Any
    filter_conversation: Optional[Callable] = None
    
    class Config:
        arbitrary_types_allowed = True


def handoff(agent: Any, filter_conversation: Optional[Callable] = None) -> HandoffTarget:
    """Create a handoff target for an agent.
    
    Args:
        agent: The agent to hand off to
        filter_conversation: Function to filter conversation history
        
    Returns:
        HandoffTarget: The handoff target
    """
    return HandoffTarget(
        agent_name=agent.name,
        agent=agent,
        filter_conversation=filter_conversation
    )


class ModelBehaviorError(Exception):
    """Exception raised when a model behaves unexpectedly."""
    pass


@dataclass
class AgentRunResult:
    """Result of an agent run."""
    
    agent_output: Any
    conversation_history: List[Dict[str, Any]]
    final_agent_name: str
    trace: Trace
    processing_time: float


class AgentRunConfig(BaseModel):
    """Configuration for an agent run."""
    
    run_name: str = Field(default_factory=lambda: f"run_{uuid.uuid4()}")
    max_turns: int = 10
    tracing_disabled: bool = False
    trace_non_openai_generations: bool = True


class Agent(Generic[AgentContextType]):
    """An LLM-powered agent that can use tools and hand off to other agents."""
    
    def __init__(self,
                 name: str,
                 instructions: Optional[str] = None,
                 instructions_function: Optional[Callable[[AgentContextType], str]] = None,
                 description: Optional[str] = None,
                 tools: Optional[List[Callable]] = None,
                 handoffs: Optional[List[HandoffTarget]] = None,
                 model_settings: Optional[Dict[str, Any]] = None,
                 output_type: Optional[Type] = None,
                 context_type: Optional[Type[AgentContextType]] = None,
                 input_guardrails: Optional[List[Guardrail]] = None,
                 output_guardrails: Optional[List[Guardrail]] = None):
        """Initialize an agent.
        
        Args:
            name: Name of the agent
            instructions: Static instructions for the agent
            instructions_function: Function to generate dynamic instructions
            description: Description of the agent (shown when used as a handoff target)
            tools: Tools the agent can use
            handoffs: Handoff targets the agent can use
            model_settings: Settings for the LLM
            output_type: Type for structured output
            context_type: Type for the agent context
            input_guardrails: Guardrails for input validation
            output_guardrails: Guardrails for output validation
        """
        if instructions is None and instructions_function is None:
            raise ValueError("Either instructions or instructions_function must be provided")
        
        self.name = name
        self.instructions = instructions
        self.instructions_function = instructions_function
        self.description = description or f"Agent named {name}"
        self.tools = tools or []
        self.handoffs = handoffs or []
        self.model_settings = model_settings or {"model": "gpt-4-turbo"}
        self.output_type = output_type
        self.context_type = context_type
        self.input_guardrails = input_guardrails or []
        self.output_guardrails = output_guardrails or []
    
    def clone(self, **kwargs) -> 'Agent':
        """Create a copy of this agent with modified attributes.
        
        Args:
            **kwargs: Attributes to override
            
        Returns:
            Agent: A new agent with the specified changes
        """
        # Get all current attributes
        current_attrs = {
            'name': self.name,
            'instructions': self.instructions,
            'instructions_function': self.instructions_function,
            'description': self.description,
            'tools': self.tools,
            'handoffs': self.handoffs,
            'model_settings': self.model_settings,
            'output_type': self.output_type,
            'context_type': self.context_type,
            'input_guardrails': self.input_guardrails,
            'output_guardrails': self.output_guardrails,
        }
        
        # Override with provided kwargs
        current_attrs.update(kwargs)
        
        # Create new agent
        return Agent(**current_attrs)


class AgentRunner:
    """Runner for agent execution."""
    
    @staticmethod
    async def run(agent: Agent,
                  input: Union[str, List[Dict[str, Any]]],
                  context: Optional[Any] = None,
                  run_config: Optional[AgentRunConfig] = None) -> AgentRunResult:
        """Run an agent with the given input.
        
        Args:
            agent: The agent to run
            input: User input as text or conversation history
            context: Context object for the agent
            run_config: Configuration for the run
            
        Returns:
            AgentRunResult: The result of the agent run
        """
        # Convert string input to conversation format
        if isinstance(input, str):
            conversation = [{"role": "user", "content": input}]
        else:
            conversation = input
        
        # Create run config if not provided
        if run_config is None:
            run_config = AgentRunConfig()
        
        # Create trace if tracing is enabled
        trace = None
        if not run_config.tracing_disabled:
            trace = Trace(
                run_id=run_config.run_name,
                agent_name=agent.name
            )
            trace.add_event("run_start", {
                "agent_name": agent.name,
                "input": conversation[-1] if conversation else None,
                "config": run_config.dict()
            })
        
        # Initialize LLM client
        from scripts.client import get_llm_client
        llm_client = get_llm_client()
        
        # Set up context wrapper if needed
        context_wrapper = None
        if context is not None:
            context_wrapper = AgentContextWrapper(context)
        
        # Apply input guardrails
        for guardrail in agent.input_guardrails:
            await guardrail.validate(conversation, context_wrapper)
        
        # Start timing
        start_time = time.time()
        
        # Get agent instructions
        if agent.instructions_function and context is not None:
            instructions = agent.instructions_function(context)
        else:
            instructions = agent.instructions
        
        # Prepare system message
        system_message = {
            "role": "system",
            "content": instructions
        }
        
        # Initialize variables for the agent loop
        current_agent = agent
        final_output = None
        turn_count = 0
        handoff_performed = False
        
        # Start the agent loop
        while turn_count < run_config.max_turns and not handoff_performed:
            turn_count += 1
            
            # Get current conversation with system message
            current_conversation = [system_message] + conversation
            
            # Add available tools to the request
            tools = []
            for tool in current_agent.tools:
                if hasattr(tool, '_tool_definition'):
                    tool_def = tool._tool_definition
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": tool_def.name,
                            "description": tool_def.description,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    param_name: {
                                        "type": "string",  # Simplified for now
                                        "description": param_info.get("description", "")
                                    }
                                    for param_name, param_info in tool_def.parameters.items()
                                },
                                "required": [
                                    param_name
                                    for param_name, param_info in tool_def.parameters.items()
                                    if param_info.get("required", False)
                                ]
                            }
                        }
                    })
            
            # Add handoff tools
            for handoff_target in current_agent.handoffs:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": f"handoff_{handoff_target.agent_name}",
                        "description": f"Hand off the conversation to the {handoff_target.agent_name} agent.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {
                                    "type": "string",
                                    "description": "Reason for handing off to this agent."
                                }
                            },
                            "required": ["reason"]
                        }
                    }
                })
            
            # Add output tool if using structured output
            if current_agent.output_type is not None:
                # Create JSONSchema from Pydantic model
                if issubclass(current_agent.output_type, pydantic.BaseModel):
                    schema = current_agent.output_type.schema()
                    # Clean up schema
                    if 'title' in schema:
                        del schema['title']
                else:
                    # Handle basic types
                    schema = {"type": "string"}  # Simplified
                
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "final_output",
                        "description": f"Provide the final output in the required format.",
                        "parameters": schema
                    }
                })
            
            # Add trace event for turn start
            if trace:
                trace.add_event("turn_start", {
                    "turn": turn_count,
                    "agent_name": current_agent.name,
                    "conversation": current_conversation,
                    "tools": tools
                })
            
            # Call the model
            try:
                response = await llm_client.chat.completions.create(
                    messages=current_conversation,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    **current_agent.model_settings
                )
                
                # Add trace event for model response
                if trace:
                    trace.add_event("model_response", {
                        "turn": turn_count,
                        "response": response.model_dump()
                    })
                
                message = response.choices[0].message
                
                # Add the message to conversation
                conversation.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": message.tool_calls or []
                })
                
                # Handle tool calls
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        # Handle output tool
                        if function_name == "final_output" and current_agent.output_type is not None:
                            try:
                                # Parse output using the specified type
                                if issubclass(current_agent.output_type, pydantic.BaseModel):
                                    final_output = current_agent.output_type.parse_obj(function_args)
                                else:
                                    final_output = function_args
                                
                                # Apply output guardrails
                                for guardrail in current_agent.output_guardrails:
                                    await guardrail.validate(final_output, context_wrapper)
                                
                                # Add trace event for final output
                                if trace:
                                    trace.add_event("final_output", {
                                        "turn": turn_count,
                                        "output": function_args
                                    })
                                
                                # Exit the loop
                                break
                                
                            except Exception as e:
                                # Output format error
                                error_msg = f"Error parsing output: {str(e)}"
                                conversation.append({
                                    "role": "system",
                                    "content": error_msg
                                })
                                
                                if trace:
                                    trace.add_event("error", {
                                        "turn": turn_count,
                                        "error": error_msg
                                    })
                                
                                continue
                        
                        # Handle handoff
                        elif function_name.startswith("handoff_"):
                            handoff_agent_name = function_name[len("handoff_"):]
                            handoff_target = next((h for h in current_agent.handoffs 
                                                 if h.agent_name == handoff_agent_name), None)
                            
                            if handoff_target:
                                # Filter conversation if needed
                                if handoff_target.filter_conversation:
                                    filtered_conversation = handoff_target.filter_conversation(conversation)
                                else:
                                    filtered_conversation = conversation
                                
                                # Add trace event for handoff
                                if trace:
                                    trace.add_event("handoff", {
                                        "turn": turn_count,
                                        "from_agent": current_agent.name,
                                        "to_agent": handoff_agent_name,
                                        "reason": function_args.get("reason", "")
                                    })
                                
                                # Recursive call to the new agent
                                handoff_result = await AgentRunner.run(
                                    handoff_target.agent,
                                    filtered_conversation,
                                    context,
                                    run_config
                                )
                                
                                # Use the handoff result
                                final_output = handoff_result.agent_output
                                conversation = handoff_result.conversation_history
                                
                                # Mark handoff as performed
                                handoff_performed = True
                                break
                        
                        # Handle regular tool calls
                        else:
                            # Find the tool
                            tool = next((t for t in current_agent.tools 
                                       if hasattr(t, '_tool_definition') and 
                                       t._tool_definition.name == function_name), None)
                            
                            if tool:
                                tool_def = tool._tool_definition
                                
                                # Add trace event for tool call
                                if trace:
                                    trace.add_event("tool_call", {
                                        "turn": turn_count,
                                        "tool_name": function_name,
                                        "arguments": function_args
                                    })
                                
                                try:
                                    # Call the tool
                                    if tool_def.is_async:
                                        if context_wrapper and 'context' in inspect.signature(tool).parameters:
                                            tool_result = await tool(context=context_wrapper, **function_args)
                                        else:
                                            tool_result = await tool(**function_args)
                                    else:
                                        if context_wrapper and 'context' in inspect.signature(tool).parameters:
                                            tool_result = tool(context=context_wrapper, **function_args)
                                        else:
                                            tool_result = tool(**function_args)
                                    
                                    # Convert tool result to string if needed
                                    if not isinstance(tool_result, (str, int, float, bool, list, dict, type(None))):
                                        tool_result = str(tool_result)
                                    
                                    # Add trace event for tool result
                                    if trace:
                                        trace.add_event("tool_result", {
                                            "turn": turn_count,
                                            "tool_name": function_name,
                                            "result": tool_result
                                        })
                                    
                                    # Add tool result to conversation
                                    conversation.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "name": function_name,
                                        "content": json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)
                                    })
                                    
                                except Exception as e:
                                    error_msg = f"Error calling tool {function_name}: {str(e)}"
                                    
                                    # Add trace event for tool error
                                    if trace:
                                        trace.add_event("tool_error", {
                                            "turn": turn_count,
                                            "tool_name": function_name,
                                            "error": error_msg
                                        })
                                    
                                    # Add error message to conversation
                                    conversation.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "name": function_name,
                                        "content": error_msg
                                    })
                            else:
                                # Unknown tool
                                error_msg = f"Unknown tool: {function_name}"
                                
                                # Add trace event for unknown tool
                                if trace:
                                    trace.add_event("tool_error", {
                                        "turn": turn_count,
                                        "tool_name": function_name,
                                        "error": error_msg
                                    })
                                
                                # Add error message to conversation
                                conversation.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": function_name,
                                    "content": error_msg
                                })
                else:
                    # No tool calls, use the message content as final output
                    if current_agent.output_type is None:
                        # For unstructured output, use the message content
                        final_output = message.content
                        
                        # Apply output guardrails
                        for guardrail in current_agent.output_guardrails:
                            await guardrail.validate(final_output, context_wrapper)
                        
                        # Add trace event for final output
                        if trace:
                            trace.add_event("final_output", {
                                "turn": turn_count,
                                "output": final_output
                            })
                        
                        # Exit the loop
                        break
                    else:
                        # For structured output, require using the final_output tool
                        error_msg = "Please use the final_output tool to provide a structured response."
                        conversation.append({
                            "role": "system",
                            "content": error_msg
                        })
                        
                        if trace:
                            trace.add_event("error", {
                                "turn": turn_count,
                                "error": error_msg
                            })
            
            except Exception as e:
                error_msg = f"Error in agent loop: {str(e)}"
                
                # Add trace event for error
                if trace:
                    trace.add_event("error", {
                        "turn": turn_count,
                        "error": error_msg
                    })
                
                # Add error message to conversation
                conversation.append({
                    "role": "system",
                    "content": error_msg
                })
                
                # Reraise the exception
                raise
        
        # Check if we reached max turns
        if turn_count >= run_config.max_turns and final_output is None:
            error_msg = f"Reached maximum number of turns ({run_config.max_turns}) without producing a final output."
            
            # Add trace event for max turns
            if trace:
                trace.add_event("error", {
                    "turn": turn_count,
                    "error": error_msg
                })
            
            raise ModelBehaviorError(error_msg)
        
        # End timing
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Finish trace
        if trace:
            trace.add_event("run_end", {
                "processing_time": processing_time,
                "final_agent": current_agent.name,
                "handoff_performed": handoff_performed
            })
            trace.finish()
            
            # Process trace
            if not run_config.tracing_disabled:
                await TracingManager().process_trace(trace)
        
        # Return result
        return AgentRunResult(
            agent_output=final_output,
            conversation_history=conversation,
            final_agent_name=current_agent.name,
            trace=trace,
            processing_time=processing_time
        )
    
    @staticmethod
    async def run_streamed(agent: Agent,
                           input: Union[str, List[Dict[str, Any]]],
                           context: Optional[Any] = None,
                           run_config: Optional[AgentRunConfig] = None) -> AgentStream:
        """Run an agent with the given input and stream the output.
        
        Args:
            agent: The agent to run
            input: User input as text or conversation history
            context: Context object for the agent
            run_config: Configuration for the run
            
        Returns:
            AgentStream: Stream of agent output events
        """
        # Create stream
        stream = AgentStream()
        
        # Run the agent in a background task
        async def background_run():
            try:
                result = await AgentRunner.run(agent, input, context, run_config)
                
                # Add final output event
                stream.add_event(StreamEvent(
                    event_type=StreamEventType.FINAL_ANSWER,
                    delta=result.agent_output,
                    data={"processing_time": result.processing_time}
                ))
            except Exception as e:
                # Add error event
                stream.add_event(StreamEvent(
                    event_type=StreamEventType.ERROR,
                    delta=str(e),
                    data={"error_type": type(e).__name__}
                ))
            finally:
                # Mark stream as finished
                stream.finish()
        
        # Start background task
        asyncio.create_task(background_run())
        
        return stream


# Example of creating an OpenAI-style GraphRAG agent using the new framework
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import List
    
    # Define models for API
    class QuestionRequest(BaseModel):
        question: str
    
    class AnswerResponse(BaseModel):
        answer: str
        reasoning: str
        evidence: List[str]
        confidence: float
        processing_time: float
    
    # Import our existing components
    from agentic_workflow.graph_rag_agent import (
        QueryDecompositionAgent, GraphRetrieverAgent, ReasoningAgent
    )
    
    # Convert our existing agents to the new framework
    # This is just a sketch of how it would look - implementation details would vary
    
    # Define output types
    class QueryPlan(BaseModel):
        query_plan: List[Dict[str, str]]
        thought_process: str
    
    class ReasoningOutput(BaseModel):
        answer: str
        reasoning: str
        evidence: List[str]
        confidence: float
    
    # Define tools
    @function_tool
    async def execute_query(cypher: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query against the Neo4j graph database."""
        from graph_db.graph_strategy_factory import GraphDatabaseFactory
        
        db = GraphDatabaseFactory.create_graph_database_strategy()
        db.connect()
        try:
            result = db.execute_query(cypher)
            return result
        finally:
            db.close()
    
    # Create agents
    query_decomposition_agent = Agent(
        name="query_decomposition",
        instructions="You are a query decomposition specialist. Convert natural language questions into Neo4j Cypher queries.",
        output_type=QueryPlan,
        tools=[]
    )
    
    retrieval_agent = Agent(
        name="graph_retrieval",
        instructions="You are a graph retrieval specialist. Execute Neo4j Cypher queries and return the results.",
        tools=[execute_query]
    )
    
    reasoning_agent = Agent(
        name="reasoning",
        instructions="You are a reasoning specialist. Analyze graph database results and answer questions.",
        output_type=ReasoningOutput,
        tools=[]
    )
    
    # Create main Graph RAG agent
    graph_rag_agent = Agent(
        name="graph_rag",
        instructions="You are a graph-based question answering system. Follow these steps:\n1. Decompose the question into Neo4j Cypher queries\n2. Execute the queries to retrieve information\n3. Reason over the results to answer the question",
        tools=[],
        handoffs=[
            handoff(query_decomposition_agent),
            handoff(retrieval_agent),
            handoff(reasoning_agent)
        ]
    )
    
    # Create FastAPI app
    app = FastAPI(
        title="Taxonomy Graph RAG API",
        description="API for querying taxonomy information using a graph RAG approach",
        version="1.0.0"
    )
    
    @app.post("/query", response_model=AnswerResponse)
    async def query_taxonomy(request: QuestionRequest):
        """Query the taxonomy with a natural language question."""
        try:
            result = await AgentRunner.run(graph_rag_agent, request.question)
            
            # Extract the relevant fields for the response
            if isinstance(result.agent_output, ReasoningOutput):
                response = AnswerResponse(
                    answer=result.agent_output.answer,
                    reasoning=result.agent_output.reasoning,
                    evidence=result.agent_output.evidence,
                    confidence=result.agent_output.confidence,
                    processing_time=result.processing_time
                )
            else:
                response = AnswerResponse(
                    answer=str(result.agent_output),
                    reasoning="",
                    evidence=[],
                    confidence=0.5,
                    processing_time=result.processing_time
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Run the app
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)