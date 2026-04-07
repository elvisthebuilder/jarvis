"""Jarvis AI Agent — orchestrates Gemma 4 (via Ollama Cloud) and Gemini Flash.

Gemma 4 (Ollama Cloud): Primary brain for understanding intent and calling tools.
Gemini Flash: Real-time knowledge — web searches, current events, live data.
"""

import json
import logging
import os
from datetime import datetime

import ollama
from google import genai
from google.genai import types as genai_types

from .prompts import build_system_prompt
from .conversation import ConversationManager
from ..tools.registry import registry
from ..memory.store import MemoryStore
from ..memory.preferences import PreferenceManager
from ..config.settings import JarvisConfig
from ..utils.resilience import retry_async

logger = logging.getLogger(__name__)


class JarvisAgent:
    """The core AI brain of Jarvis.
    
    Routes requests between Gemma 4 (via Ollama Cloud) for general intelligence
    and Gemini Flash for real-time, current information.
    """

    def __init__(self, config: JarvisConfig, memory: MemoryStore, preferences: PreferenceManager):
        self.config = config
        self.memory = memory
        self.preferences = preferences
        self.conversation = ConversationManager()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Initialize Ollama client (cloud)
        # The ollama library reads OLLAMA_HOST env var automatically,
        # but we also need to set the API key via environment
        if config.ollama.api_key:
            os.environ["OLLAMA_API_KEY"] = config.ollama.api_key
        
        # Set the host for the client
        os.environ["OLLAMA_HOST"] = config.ollama.host
        
        self._ollama_client = ollama.Client(
            host=config.ollama.host,
        )

        # Initialize Gemini client
        self._gemini_client = None
        if config.gemini.api_key:
            self._gemini_client = genai.Client(api_key=config.gemini.api_key)

        self._incognito = False

        logger.info(
            f"Agent initialized — Ollama: {config.ollama.model}@{config.ollama.host} | "
            f"Gemini: {'available' if self._gemini_client else 'not configured'}"
        )

    def set_incognito(self, enabled: bool = True):
        """Enable or disable incognito mode for this agent."""
        self._incognito = enabled
        if enabled:
            logger.info("Incognito mode activated — no context will be loaded or logged.")

    async def load_last_context(self, limit: int = 5):
        """Fetch and load the most recent interactions from the database.
        
        This enables 'Total Recall' — your terminal session will remember
        what you just asked J.A.R.V.I.S. in the GNOME overlay.
        """
        if self._incognito:
            return

        try:
            # Fetch last 5 interactions (user input + assistant response)
            recent = await self.memory.get_recent_interactions(limit=limit)
            
            # Interactions are ordered by timestamp DESC, so we reverse for chronological order
            history = []
            for entry in reversed(recent):
                history.append({"role": "user", "content": entry["user_input"]})
                history.append({"role": "assistant", "content": entry["assistant_response"]})
            
            if history:
                self.conversation.load_history(history)
                logger.info(f"Synchronized context: Loaded {len(recent)} recent interactions.")
        except Exception as e:
            logger.warning(f"Failed to synchronize context: {e}")

    async def process(self, user_input: str) -> str:
        """Process a user request and return Jarvis's response.
        
        This is the main entry point. It:
        1. Routes to the appropriate AI backend
        2. Handles tool calling
        3. Logs the interaction for learning
        4. Returns the final response
        
        Args:
            user_input: The user's natural language input
            
        Returns:
            Jarvis's response string
        """
        logger.info(f"Processing: {user_input}")
        
        # Extract any preferences from the input
        await self.preferences.extract_and_store(user_input)

        # Add to conversation context
        self.conversation.add_user_message(user_input)

        # Route all queries to the primary brain (Gemma).
        # It will use the realtime tool if it determines it needs to.
        response = await self._process_with_gemma(user_input)

        # Add response to conversation
        self.conversation.add_assistant_message(response)

        # Log interaction for learning (unless incognito)
        if not self._incognito:
            await self.memory.log_interaction(
                user_input=user_input,
                assistant_response=response,
                session_id=self.session_id,
            )

        return response

    async def _process_with_gemma(self, user_input: str) -> str:
        """Process a request using Gemma 4 via Ollama Cloud with function calling.
        
        Implements the observe-think-act loop:
        1. Send user input + tool definitions to Gemma 4
        2. If Gemma wants to call tools, execute them
        3. Feed results back to Gemma for final response
        """
        # Step 1: Get the current system prompt
        prefs = self.preferences.get_preferences_for_prompt()
        recent_ctx = self.conversation.get_recent_context_summary()
        system_prompt = build_system_prompt(
            user_title=self.config.user_title,
            user_name=self.config.user_name,
            user_occupation=self.config.user_occupation,
            user_interests=self.config.user_interests,
            user_context=self.config.user_context,
            preferences=prefs if prefs else None,
            recent_context=recent_ctx,
        )

        # Get conversation history
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation.get_messages_for_api())

        # Get tool schemas
        tool_schemas = registry.get_schemas()

        try:
            # Step 1: Ask Gemma 4
            response = self._ollama_client.chat(
                model=self.config.ollama.model,
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                options={
                    "temperature": self.config.ollama.temperature,
                },
            )

            # Step 2: Handle tool calls (may be multiple rounds)
            max_tool_rounds = 5
            tools_used = []

            while response.message.tool_calls and max_tool_rounds > 0:
                max_tool_rounds -= 1

                # Execute each tool call
                for tool_call in response.message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = tool_call.function.arguments or {}

                    logger.info(f"Tool call: {func_name}({func_args})")
                    
                    # Execute the tool
                    result = await registry.execute(func_name, func_args)
                    tools_used.append(func_name)

                    # Record tool usage for pattern learning
                    await self.preferences.record_tool_usage(func_name, user_input)

                    # Add tool result to conversation
                    messages.append(response.message.model_dump())
                    messages.append({
                        "role": "tool",
                        "content": result,
                    })

                # Step 3: Get Gemma's response incorporating tool results
                response = self._ollama_client.chat(
                    model=self.config.ollama.model,
                    messages=messages,
                    tools=tool_schemas if tool_schemas else None,
                    options={
                        "temperature": self.config.ollama.temperature,
                    },
                )

            # Update interaction log with tools used
            if tools_used:
                logger.info(f"Tools used: {tools_used}")

            return response.message.content or "Done."

        except ollama.ResponseError as e:
            logger.error(f"Ollama API error: {e}")
            
            # Provide clean error messages
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestion = (
                    f"The model '{self.config.ollama.model}' wasn't found on Ollama Cloud, Sir. "
                    f"This might be a naming issue — try checking available models at ollama.com."
                )
            elif "401" in error_str or "unauthorized" in error_str:
                suggestion = "My Ollama credentials appear to be invalid, Sir. Please check the API key."
            else:
                suggestion = f"I encountered a connection issue with my primary brain, Sir."
            
            # Fallback to Gemini
            if self._gemini_client:
                logger.info("Falling back to Gemini")
                try:
                    return await self._process_with_gemini_tools(user_input)
                except Exception as fallback_err:
                    logger.error(f"Gemini fallback also failed: {fallback_err}")
            
            return suggestion

        except Exception as e:
            logger.error(f"Gemma processing failed: {e}")
            
            # Fallback to Gemini if available
            if self._gemini_client:
                logger.info("Falling back to Gemini")
                try:
                    return await self._process_with_gemini_tools(user_input)
                except Exception as fallback_err:
                    logger.error(f"Gemini fallback also failed: {fallback_err}")
            
            return f"I encountered an issue, Sir. Both my primary and backup connections are down."

    async def _process_with_gemini_tools(self, user_input: str) -> str:
        """Process a request using Gemini with tool/function calling support.
        
        This is the full-featured Gemini path with tool execution,
        used as either a fallback for Ollama or for real-time queries.
        """
        if not self._gemini_client:
            return "I don't have a backup connection configured, Sir."

        prefs = self.preferences.get_preferences_for_prompt()
        recent_ctx = self.conversation.get_recent_context_summary()
        system_prompt = build_system_prompt(
            user_title=self.config.user_title,
            user_name=self.config.user_name,
            user_occupation=self.config.user_occupation,
            user_interests=self.config.user_interests,
            user_context=self.config.user_context,
            preferences=prefs if prefs else None,
            recent_context=recent_ctx,
        )

        # Build tool definitions for Gemini
        tool_functions = []
        for tool_name in registry.list_tools():
            func = registry.get_tool(tool_name)
            if func:
                tool_functions.append(func)

        try:
            # Wrap the Gemini call in the Resilience Protocol (async retry)
            response = await retry_async(
                self._gemini_client.aio.models.generate_content,
                max_retries=3,
                initial_delay=2.0,
                model=self.config.gemini.model,
                contents=user_input,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.config.gemini.temperature,
                    tools=tool_functions if tool_functions else None,
                ),
            )

            # Handle function calls from Gemini
            if response.candidates and response.candidates[0].content:
                parts = response.candidates[0].content.parts
                tools_used = []
                
                for part in parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        func_name = part.function_call.name
                        func_args = dict(part.function_call.args) if part.function_call.args else {}
                        
                        logger.info(f"Gemini tool call: {func_name}({func_args})")
                        result = await registry.execute(func_name, func_args)
                        tools_used.append(func_name)
                        
                        await self.preferences.record_tool_usage(func_name, user_input)

                if tools_used:
                    logger.info(f"Gemini tools used: {tools_used}")

            return response.text or "Done, Sir."

        except Exception as e:
            error_str = str(e)
            logger.error(f"Gemini processing failed: {e}")
            
            # Clean error messages — never show raw JSON to the user
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                return (
                    "I've hit my API rate limit, Sir. This usually resets within a minute. "
                    "Try again shortly."
                )
            elif "INVALID" in error_str or "400" in error_str:
                return "There was an issue with my request format, Sir. I'll need to look into it."
            elif "PERMISSION" in error_str or "403" in error_str:
                return "My API credentials don't have the right permissions, Sir. Please check the key."
            else:
                return f"I'm having trouble connecting to my backup systems, Sir. Error: {type(e).__name__}"



    def new_session(self):
        """Start a fresh conversation session."""
        self.conversation.clear()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"New session started: {self.session_id}")
