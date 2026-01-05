"""Unit tests for user agent pool rotation."""

import pytest
import threading
from unittest.mock import patch
from src.user_agent_pool import UserAgentPool


class TestUserAgentPool:
    """Test suite for UserAgentPool class."""

    def test_initialization(self):
        """Test pool initializes with provided agents."""
        agents = ['Agent1', 'Agent2', 'Agent3']
        pool = UserAgentPool(agents)
        assert pool._agents == agents
        assert pool._lock is not None

    def test_round_robin_rotation(self):
        """Test round-robin rotation returns different agents sequentially."""
        agents = ['Agent1', 'Agent2', 'Agent3']
        pool = UserAgentPool(agents)
        
        # Get agents in sequence
        agent1 = pool.get_next()
        agent2 = pool.get_next()
        agent3 = pool.get_next()
        agent4 = pool.get_next()  # Should wrap around
        
        # Should cycle through all agents
        assert agent1 in agents
        assert agent2 in agents
        assert agent3 in agents
        # Fourth call should return first agent again
        assert agent4 == agent1

    def test_random_start_index_initialization(self):
        """Test pool initializes with random start index."""
        agents = ['Agent1', 'Agent2', 'Agent3']
        
        # Create multiple pools and check they don't all start at same index
        start_agents = set()
        for _ in range(10):
            pool = UserAgentPool(agents)
            start_agents.add(pool.get_next())
        
        # With 10 attempts and 3 agents, we should see at least 2 different starting points
        # (statistically very likely, not deterministic but good enough)
        assert len(start_agents) >= 2, "Random start should produce varied initial agents"

    def test_thread_safety(self):
        """Test thread safety with concurrent calls."""
        agents = ['Agent1', 'Agent2', 'Agent3']
        pool = UserAgentPool(agents)
        results = []
        
        def get_agent():
            for _ in range(10):
                results.append(pool.get_next())
        
        # Create multiple threads
        threads = [threading.Thread(target=get_agent) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have 50 results (5 threads * 10 calls each)
        assert len(results) == 50
        # All results should be from the agent list
        assert all(agent in agents for agent in results)

    def test_pool_exhaustion_cycles_back(self):
        """Test pool exhaustion handling (cycles back to start)."""
        agents = ['Agent1', 'Agent2']
        pool = UserAgentPool(agents)
        
        # Exhaust the pool multiple times
        results = [pool.get_next() for _ in range(6)]
        
        # Should cycle: Agent1, Agent2, Agent1, Agent2, Agent1, Agent2
        # (or Agent2, Agent1, Agent2, Agent1, Agent2, Agent1 depending on random start)
        assert len(set(results)) == 2  # Only 2 unique agents
        # Check it cycles properly
        assert results[0] == results[2] == results[4]
        assert results[1] == results[3] == results[5]

    def test_empty_pool_raises_error(self):
        """Test empty pool raises ValueError."""
        with pytest.raises(ValueError, match="User agent pool cannot be empty"):
            UserAgentPool([])

    def test_get_current_without_rotation(self):
        """Test get_current returns current agent without rotation."""
        agents = ['Agent1', 'Agent2', 'Agent3']
        pool = UserAgentPool(agents)
        
        # Get current should not advance
        current1 = pool.get_current()
        current2 = pool.get_current()
        assert current1 == current2
        
        # Now advance with get_next
        pool.get_next()
        current3 = pool.get_current()
        
        # Current should have changed
        assert current3 != current1

    def test_reset_to_random_start(self):
        """Test reset() resets to random start index."""
        agents = ['Agent1', 'Agent2', 'Agent3']
        pool = UserAgentPool(agents)
        
        # Advance the pool
        for _ in range(5):
            pool.get_next()
        
        current_before_reset = pool.get_current()
        
        # Reset
        pool.reset()
        current_after_reset = pool.get_current()
        
        # After reset, current agent should be valid (might be same by chance)
        assert current_after_reset in agents
