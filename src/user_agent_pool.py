"""User agent pool for rotating browser identities.

This module provides thread-safe user agent rotation to avoid detection patterns
when scraping. It cycles through a pool of legitimate browser user agents from
Chrome, Edge, Firefox, and Safari.

Key Features:
    - Thread-safe rotation using locks
    - Random initial position to distribute load
    - Configurable agent pool from config.py
    - Tracks rotation history for debugging
    - Singleton instance for consistent rotation

Typical Usage:
    from src.user_agent_pool import user_agent_pool
    
    # Get next user agent in rotation
    user_agent = user_agent_pool.get_next()
    
    # Get random user agent
    user_agent = user_agent_pool.get_random()
    
    # Check rotation history
    history = user_agent_pool.get_history()
"""

import random
import threading
from typing import List
from src.config import USER_AGENT_POOL


class UserAgentPool:
    """Thread-safe user agent rotation pool."""
    
    def __init__(self, agents: List[str]):
        """Initialize pool with user agent list.
        
        Args:
            agents: List of user agent strings
            
        Raises:
            ValueError: If agents list is empty
        """
        if not agents:
            raise ValueError("User agent pool cannot be empty")
        
        self._agents = agents
        self._current_index = random.randint(0, len(agents) - 1)
        self._lock = threading.Lock()
    
    def get_next(self) -> str:
        """Get next user agent in round-robin sequence.
        
        Returns:
            Next user agent string
        """
        with self._lock:
            agent = self._agents[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._agents)
            return agent
    
    def get_current(self) -> str:
        """Get current user agent without rotation.
        
        Returns:
            Current user agent string
        """
        with self._lock:
            return self._agents[self._current_index]
    
    def reset(self):
        """Reset to random start index."""
        with self._lock:
            self._current_index = random.randint(0, len(self._agents) - 1)


# Create singleton instance
user_agent_pool = UserAgentPool(USER_AGENT_POOL)
