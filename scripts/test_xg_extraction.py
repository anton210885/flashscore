"""Test xG extraction from API"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config as cfg
from api.sstats_client import SStatsClient
import json

def test_xg():
    """Test extracting xG from API"""
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, 'API_KEY', None))
    
    # Test with game ID 924516 (from user's example)
    game_id = 924516
    print(f"Testing Game ID: {game_id}")
    print("=" * 70)
    
    try:
        game_data = client.get_game(game_id)
        
        print("\nFull API Response Structure:")
        print(json.dumps(game_data, indent=2)[:2000])  # First 2000 chars
        
        print("\n" + "=" * 70)
        print("Extracting xG:")
        print("=" * 70)
        
        # Check structure
        if "data" in game_data and isinstance(game_data["data"], dict):
            data = game_data["data"]
            game = data.get("game", {})
            stats = data.get("statistics", {})
            
            print(f"\nFound 'data' key")
            print(f"  'game' in data: {'game' in data}")
            print(f"  'statistics' in data: {'statistics' in data}")
            
            if stats:
                print(f"\nStatistics found in data.statistics:")
                print(f"  calculatedXgHome: {stats.get('calculatedXgHome')}")
                print(f"  calculatedXgAway: {stats.get('calculatedXgAway')}")
            else:
                print("\nNo statistics in data.statistics")
                
            # Also check if statistics are in game
            game_stats = game.get("statistics", {})
            if game_stats:
                print(f"\nStatistics also found in data.game.statistics:")
                print(f"  calculatedXgHome: {game_stats.get('calculatedXgHome')}")
                print(f"  calculatedXgAway: {game_stats.get('calculatedXgAway')}")
        else:
            print("No 'data' key found")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_xg()























