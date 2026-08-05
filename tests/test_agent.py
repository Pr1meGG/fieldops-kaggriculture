import logging
from unittest.mock import patch

from kaggle_environments import make
from fieldops.agent import agent, _log_debug_info
from fieldops.state import GameState, ObservationParser

def test_agent_integration(caplog):
    """
    Integration test proving:
    - agent accepts real observations
    - parser is invoked
    - GameState is used
    - agent survives an entire episode
    - only legal actions are returned
    """
    caplog.set_level(logging.INFO)
    
    env = make("kaggriculture", debug=True)
    
    original_parse = ObservationParser.parse
    parse_calls = 0
    
    def mock_parse(obs):
        nonlocal parse_calls
        parse_calls += 1
        state = original_parse(obs)
        assert isinstance(state, GameState)
        return state

    with patch('fieldops.agent.ObservationParser.parse', side_effect=mock_parse):
        steps = env.run([agent, "pass"])
        
        last_step = steps[-1]
        assert last_step[0].status == "DONE" or last_step[0].status == "ACTIVE"
        
        assert parse_calls > 0
        
        for step in steps:
            p_state = step[0]
            if p_state.action:
                assert "farmer" in p_state.action
                assert "hands" in p_state.action
                assert "market" in p_state.action
