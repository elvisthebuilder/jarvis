"""Jarvis D-Bus Service — provides IPC for the GNOME extension.

Exposes the 'org.jarvis.Assistant' interface on the session bus.
Methods:
- Ask(text: s) -> s: Pass natural language to Jarvis and get a response.
- Toggle(): Emit the ToggleSignal for the UI.
- Clear(): Reset the current conversation session.
"""

import asyncio
import logging
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, dbus_property, PropertyAccess, signal
from dbus_next import Variant

from ..brain.agent import JarvisAgent

logger = logging.getLogger(__name__)

class AssistantInterface(ServiceInterface):
    """The D-Bus interface for the J.A.R.V.I.S. Assistant."""
    
    def __init__(self, agent: JarvisAgent):
        super().__init__('org.jarvis.Assistant')
        self.agent = agent
        self._is_thinking = False
        self._on_toggle = None

    def set_on_toggle(self, callback):
        """Register a callback for when Toggle() is called."""
        self._on_toggle = callback

    @method()
    async def Toggle(self):
        """Toggle the visibility of the UI via signal."""
        logger.info("D-Bus request: Toggle visibility")
        self.Toggled()

    @signal()
    def Toggled(self):
        """Signal emitted when the UI should toggle."""
        return None

    @method()
    async def Notify(self, message: 's'):
        """Method to trigger a notification from external sources."""
        logger.info(f"D-Bus request: Notify -> {message}")
        self.NotifySignal(message)

    @signal()
    def NotifySignal(self, message: 's'):
        """Signal emitted when Jarvis wants to send a proactive message."""
        return [message]

    @method()
    async def Ask(self, text: 's') -> 's':
        """Process a request from the UI and return the response."""
        if not text.strip():
            return "Sir?"
        
        logger.info(f"D-Bus request: {text}")
        self._is_thinking = True
        try:
            # We use the existing agent's process method
            response = await self.agent.process(text)
            return response
        except Exception as e:
            logger.error(f"D-Bus process error: {e}")
            return f"I encountered an error while processing that, Sir: {str(e)}"
        finally:
            self._is_thinking = False

    @method()
    async def Clear(self):
        """Clear the current conversation context."""
        logger.info("D-Bus request: Clear session")
        self.agent.new_session()

    @dbus_property(access=PropertyAccess.READ)
    def IsThinking(self) -> 'b':
        """Whether Jarvis is currently processing a request."""
        return self._is_thinking


async def start_dbus_service(agent: JarvisAgent):
    """Start the J.A.R.V.I.S. D-Bus service on the session bus."""
    try:
        bus = await MessageBus().connect()
        interface = AssistantInterface(agent)
        bus.export('/org/jarvis/Assistant', interface)
        
        # Request the name on the bus
        await bus.request_name('org.jarvis.Assistant')
        
        logger.info("D-Bus service 'org.jarvis.Assistant' started at /org/jarvis/Assistant")
        
        # Wait until the bus is closed
        await bus.wait_for_disconnect()
    except Exception as e:
        logger.error(f"Failed to start D-Bus service: {e}")
        raise
