"""
tests/test_state.py — Unit tests for ObservationParser.

Tests work against hand-crafted observation dicts.
No kaggle_environments instance is required.

Coverage:
    - parse() with a valid step-0 observation (the common case)
    - GameState fields populated correctly
    - FarmState fields: money, tiles, farmer, hands, quadrants, shed, seeds
    - Tile kinds: empty, locked, weed, plant, coop/pasture (with and without animal)
    - MarketState and TownState fields
    - Validation errors: invalid step, inconsistent day/hour,
      out-of-bounds coordinates, negative money, negative inventory counts,
      missing NW quadrant, hand/inventory count mismatch
"""

import pytest

from fieldops.state import (
    FarmState,
    Farmer,
    GameState,
    Hand,
    Inventory,
    MarketState,
    ObservationParser,
    Position,
    Tile,
    TownState,
)


# ---------------------------------------------------------------------------
# Observation builder helpers
# ---------------------------------------------------------------------------

def _empty_tiles(size: int = 10) -> list[list[None]]:
    """Return a size×size grid of None (empty) tiles."""
    return [[None] * size for _ in range(size)]


def _base_farm(money: float = 3000.0) -> dict:
    """Return a minimal valid farm dict."""
    return {
        "money": money,
        "tiles": _empty_tiles(),
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
    }


def _base_private() -> dict:
    """Return a minimal valid private dict (no hands)."""
    products = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
                "EGG", "MILK", "WOOL", "FERTILIZER", "GOOSE", "COW", "SHEEP"]
    crops = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
    return {
        "shed": {k: 0 for k in products},
        "seeds": {k: 0 for k in crops},
        "inventories": [{}],  # index 0 = farmer, no hands
    }


_PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
             "EGG", "MILK", "WOOL", "FERTILIZER"]


def _base_market() -> dict:
    return {
        "inventory": {k: 10_000 for k in _PRODUCTS},
        "prices": {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
                   "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 1},
    }


def _base_town() -> dict:
    return {"unlocked_shops": []}


def _base_obs(step: int = 0, player: int = 0) -> dict:
    """Return a minimal valid observation dict at `step` for `player`."""
    day = step // 24
    hour = step % 24
    return {
        "step": step,
        "day": day,
        "hour": hour,
        "player": player,
        "remainingOverageTime": 60,
        "farms": [_base_farm(), _base_farm()],
        "private": _base_private(),
        "market": _base_market(),
        "town": _base_town(),
    }


# ---------------------------------------------------------------------------
# Valid observation — basic structure
# ---------------------------------------------------------------------------


class TestValidParse:
    def test_returns_game_state(self):
        obs = _base_obs(step=0, player=0)
        state = ObservationParser.parse(obs)
        assert isinstance(state, GameState)

    def test_step_day_hour_at_step_0(self):
        state = ObservationParser.parse(_base_obs(step=0))
        assert state.step == 0
        assert state.day == 0
        assert state.hour == 0

    def test_step_day_hour_mid_episode(self):
        # step=25 => day=1, hour=1
        state = ObservationParser.parse(_base_obs(step=25))
        assert state.step == 25
        assert state.day == 1
        assert state.hour == 1

    def test_max_valid_step(self):
        # TOTAL_TURNS - 2 = 718
        state = ObservationParser.parse(_base_obs(step=718))
        assert state.step == 718

    def test_player_index(self):
        state = ObservationParser.parse(_base_obs(step=0, player=1))
        assert state.player_index == 1

    def test_my_farm_vs_opponent_farm(self):
        obs = _base_obs(step=0, player=0)
        obs["farms"][0]["money"] = 1234.0
        obs["farms"][1]["money"] = 5678.0
        state = ObservationParser.parse(obs)
        assert state.my_farm.player_index == 0
        assert state.my_farm.money == 1234.0
        assert state.opponent_farm.player_index == 1
        assert state.opponent_farm.money == 5678.0

    def test_player1_perspective(self):
        obs = _base_obs(step=0, player=1)
        obs["farms"][0]["money"] = 1234.0
        obs["farms"][1]["money"] = 5678.0
        state = ObservationParser.parse(obs)
        assert state.my_farm.player_index == 1
        assert state.my_farm.money == 5678.0
        assert state.opponent_farm.player_index == 0
        assert state.opponent_farm.money == 1234.0


class TestFarmState:
    def test_money(self):
        obs = _base_obs()
        obs["farms"][0]["money"] = 2500.5
        state = ObservationParser.parse(obs)
        assert state.my_farm.money == 2500.5

    def test_tile_grid_shape(self):
        state = ObservationParser.parse(_base_obs())
        assert len(state.my_farm.tiles) == 10
        for row in state.my_farm.tiles:
            assert len(row) == 10

    def test_farmer_position(self):
        state = ObservationParser.parse(_base_obs())
        assert state.my_farm.farmer.position == Position(4, 4)

    def test_farmer_inventory_empty(self):
        state = ObservationParser.parse(_base_obs())
        assert state.my_farm.farmer.inventory.total() == 0

    def test_unlocked_quadrants(self):
        state = ObservationParser.parse(_base_obs())
        assert "NW" in state.my_farm.unlocked_quadrants

    def test_hires_today(self):
        obs = _base_obs()
        obs["farms"][0]["hires_today"] = 3
        state = ObservationParser.parse(obs)
        assert state.my_farm.hires_today == 3

    def test_shed_populated_for_own_farm(self):
        obs = _base_obs()
        obs["private"]["shed"]["WHEAT"] = 5
        state = ObservationParser.parse(obs)
        assert state.my_farm.shed is not None
        assert state.my_farm.shed.get("WHEAT") == 5

    def test_seeds_populated_for_own_farm(self):
        obs = _base_obs()
        obs["private"]["seeds"]["CARROT"] = 3
        state = ObservationParser.parse(obs)
        assert state.my_farm.seeds is not None
        assert state.my_farm.seeds["CARROT"] == 3

    def test_opponent_farm_shed_is_none(self):
        state = ObservationParser.parse(_base_obs())
        assert state.opponent_farm.shed is None

    def test_opponent_farm_seeds_is_none(self):
        state = ObservationParser.parse(_base_obs())
        assert state.opponent_farm.seeds is None

    def test_no_hands(self):
        state = ObservationParser.parse(_base_obs())
        assert state.my_farm.hands == ()

    def test_one_hand(self):
        obs = _base_obs()
        obs["farms"][0]["hands"] = [[5, 4]]
        obs["private"]["inventories"].append({"WHEAT": 2})
        state = ObservationParser.parse(obs)
        assert len(state.my_farm.hands) == 1
        hand = state.my_farm.hands[0]
        assert hand.index == 0
        assert hand.position == Position(5, 4)
        assert hand.inventory.get("WHEAT") == 2

    def test_two_hands(self):
        obs = _base_obs()
        obs["farms"][0]["hands"] = [[5, 4], [4, 5]]
        obs["private"]["inventories"].extend([{}, {}])
        state = ObservationParser.parse(obs)
        assert len(state.my_farm.hands) == 2
        assert state.my_farm.hands[0].index == 0
        assert state.my_farm.hands[1].index == 1


class TestTileParsing:
    def _obs_with_tile(self, x: int, y: int, tile_value) -> dict:
        obs = _base_obs()
        obs["farms"][0]["tiles"][y][x] = tile_value
        return obs

    def test_empty_tile(self):
        state = ObservationParser.parse(_base_obs())
        tile = state.my_farm.tiles[0][0]
        assert tile.is_empty()
        assert tile.kind is None

    def test_opponent_farm_tile_is_parsed(self):
        obs = _base_obs()
        obs["farms"][1]["tiles"][2][3] = {"kind": "WEED"}
        state = ObservationParser.parse(obs)
        assert state.opponent_farm.tiles[2][3].is_weed()

    def test_locked_tile(self):
        obs = self._obs_with_tile(0, 0, "LOCKED")
        state = ObservationParser.parse(obs)
        tile = state.my_farm.tiles[0][0]
        assert tile.is_locked()
        assert tile.kind == "LOCKED"

    def test_weed_tile(self):
        obs = self._obs_with_tile(2, 3, {"kind": "WEED"})
        state = ObservationParser.parse(obs)
        tile = state.my_farm.tiles[3][2]
        assert tile.is_weed()
        assert not tile.is_plant()

    def test_plant_tile_fields(self):
        raw_plant = {
            "kind": "PLANT",
            "crop": "WHEAT",
            "planted_day": 0,
            "watered_today": True,
            "consecutive_unwatered": 0,
            "yield_units": 2,
            "max_lifespan_step": 120,
            "fertilized_until_day": -1,
        }
        obs = self._obs_with_tile(1, 1, raw_plant)
        state = ObservationParser.parse(obs)
        tile = state.my_farm.tiles[1][1]

        assert tile.is_plant()
        assert tile.crop == "WHEAT"
        assert tile.planted_day == 0
        assert tile.watered_today is True
        assert tile.consecutive_unwatered == 0
        assert tile.yield_units == 2
        assert tile.max_lifespan_step == 120
        assert tile.fertilized_until_day == -1
        assert tile.x == 1
        assert tile.y == 1

    def test_plant_tile_is_harvestable(self):
        raw_plant = {
            "kind": "PLANT", "crop": "CARROT", "planted_day": 2,
            "watered_today": False, "consecutive_unwatered": 1,
            "yield_units": 3, "max_lifespan_step": -1, "fertilized_until_day": -1,
        }
        obs = self._obs_with_tile(0, 0, raw_plant)
        tile = ObservationParser.parse(obs).my_farm.tiles[0][0]
        assert tile.is_harvestable()

    def test_plant_tile_not_harvestable(self):
        raw_plant = {
            "kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
            "watered_today": False, "consecutive_unwatered": 1,
            "yield_units": 0, "max_lifespan_step": 120, "fertilized_until_day": -1,
        }
        obs = self._obs_with_tile(0, 0, raw_plant)
        tile = ObservationParser.parse(obs).my_farm.tiles[0][0]
        assert not tile.is_harvestable()

    def test_coop_empty_structure(self):
        # Empty coop: no "animal" key
        raw_coop = {"kind": "COOP"}
        obs = self._obs_with_tile(3, 3, raw_coop)
        tile = ObservationParser.parse(obs).my_farm.tiles[3][3]

        assert tile.is_animal()
        assert tile.kind == "COOP"
        assert not tile.has_animal()
        assert tile.animal is None

    def test_empty_coop_is_not_harvestable(self):
        obs = self._obs_with_tile(0, 0, {"kind": "COOP"})
        tile = ObservationParser.parse(obs).my_farm.tiles[0][0]
        assert not tile.is_harvestable()

    def test_coop_with_animal_fields(self):
        raw_coop = {
            "kind": "COOP",
            "animal": "GOOSE",
            "placed_day": 1,
            "yield_units": 2,
            "fed_today": True,
            "consecutive_unfed": 0,
            "cared_today": False,
            "fertilizer_available": True,
            "pending_care_bonus": 1,
        }
        obs = self._obs_with_tile(2, 2, raw_coop)
        tile = ObservationParser.parse(obs).my_farm.tiles[2][2]

        assert tile.is_animal()
        assert tile.has_animal()
        assert tile.animal == "GOOSE"
        assert tile.placed_day == 1
        assert tile.yield_units == 2
        assert tile.fed_today is True
        assert tile.consecutive_unfed == 0
        assert tile.cared_today is False
        assert tile.fertilizer_available is True
        assert tile.pending_care_bonus == 1

    def test_pasture_with_cow(self):
        raw_pasture = {
            "kind": "PASTURE",
            "animal": "COW",
            "placed_day": 3,
            "yield_units": 0,
            "fed_today": False,
            "consecutive_unfed": 0,
            "cared_today": False,
            "fertilizer_available": False,
            "pending_care_bonus": 0,
        }
        obs = self._obs_with_tile(5, 5, raw_pasture)
        tile = ObservationParser.parse(obs).my_farm.tiles[5][5]

        assert tile.is_animal()
        assert tile.kind == "PASTURE"
        assert tile.animal == "COW"

    def test_tile_coordinates_are_correct(self):
        """tiles[y][x] must have x and y set to match index position."""
        state = ObservationParser.parse(_base_obs())
        for y in range(10):
            for x in range(10):
                tile = state.my_farm.tiles[y][x]
                assert tile.x == x
                assert tile.y == y


class TestMarketState:
    def test_market_inventory(self):
        state = ObservationParser.parse(_base_obs())
        assert state.market.inventory["WHEAT"] == 10_000

    def test_market_prices(self):
        state = ObservationParser.parse(_base_obs())
        assert state.market.prices["WHEAT"] == 25
        assert state.market.prices["CARROT"] == 35

    def test_market_custom_values(self):
        obs = _base_obs()
        obs["market"]["inventory"]["CARROT"] = 9500
        obs["market"]["prices"]["CARROT"] = 40
        state = ObservationParser.parse(obs)
        assert state.market.inventory["CARROT"] == 9500
        assert state.market.prices["CARROT"] == 40


class TestTownState:
    def test_no_shops_initially(self):
        state = ObservationParser.parse(_base_obs())
        assert state.town.unlocked_shops == []

    def test_unlocked_shops(self):
        obs = _base_obs()
        obs["town"]["unlocked_shops"] = ["BAKERY", "PET_CAFE"]
        state = ObservationParser.parse(obs)
        assert "BAKERY" in state.town.unlocked_shops
        assert "PET_CAFE" in state.town.unlocked_shops


class TestInventoryHelpers:
    def test_get_present_item(self):
        inv = Inventory({"WHEAT": 5, "EGG": 2})
        assert inv.get("WHEAT") == 5

    def test_get_absent_item(self):
        inv = Inventory({"WHEAT": 5})
        assert inv.get("EGG") == 0

    def test_has_sufficient(self):
        inv = Inventory({"WHEAT": 3})
        assert inv.has("WHEAT", 3) is True

    def test_has_insufficient(self):
        inv = Inventory({"WHEAT": 2})
        assert inv.has("WHEAT", 3) is False

    def test_total(self):
        inv = Inventory({"WHEAT": 4, "EGG": 6})
        assert inv.total() == 10

    def test_empty_inventory(self):
        inv = Inventory({})
        assert inv.total() == 0
        assert inv.get("WHEAT") == 0
        assert inv.has("WHEAT") is False


# ---------------------------------------------------------------------------
# Validation error cases
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_step_negative(self):
        obs = _base_obs(step=0)
        obs["step"] = -1
        obs["day"] = 0
        obs["hour"] = 0
        with pytest.raises(ValueError, match="step"):
            ObservationParser.parse(obs)

    def test_step_too_large(self):
        obs = _base_obs(step=0)
        obs["step"] = 719
        obs["day"] = 29
        obs["hour"] = 23
        with pytest.raises(ValueError, match="step"):
            ObservationParser.parse(obs)

    def test_day_inconsistent_with_step(self):
        obs = _base_obs(step=0)
        obs["day"] = 5  # should be 0
        with pytest.raises(ValueError, match="day"):
            ObservationParser.parse(obs)

    def test_hour_inconsistent_with_step(self):
        obs = _base_obs(step=0)
        obs["hour"] = 10  # should be 0
        with pytest.raises(ValueError, match="hour"):
            ObservationParser.parse(obs)

    def test_farmer_x_out_of_bounds(self):
        obs = _base_obs()
        obs["farms"][0]["farmer"] = [10, 4]  # x=10 is out of range
        with pytest.raises(ValueError, match="position"):
            ObservationParser.parse(obs)

    def test_farmer_y_out_of_bounds(self):
        obs = _base_obs()
        obs["farms"][0]["farmer"] = [4, -1]  # y=-1 is out of range
        with pytest.raises(ValueError, match="position"):
            ObservationParser.parse(obs)

    def test_hand_out_of_bounds(self):
        obs = _base_obs()
        obs["farms"][0]["hands"] = [[11, 4]]
        obs["private"]["inventories"].append({})
        with pytest.raises(ValueError, match="position"):
            ObservationParser.parse(obs)

    def test_negative_money(self):
        obs = _base_obs()
        obs["farms"][0]["money"] = -100.0
        with pytest.raises(ValueError, match="money"):
            ObservationParser.parse(obs)

    def test_negative_shed_count(self):
        obs = _base_obs()
        obs["private"]["shed"]["WHEAT"] = -1
        with pytest.raises(ValueError, match="inventory"):
            ObservationParser.parse(obs)

    def test_negative_seed_count(self):
        obs = _base_obs()
        obs["private"]["seeds"]["CARROT"] = -3
        with pytest.raises(ValueError, match="inventory"):
            ObservationParser.parse(obs)

    def test_missing_nw_quadrant(self):
        obs = _base_obs()
        obs["farms"][0]["unlocked_quadrants"] = ["NE"]
        with pytest.raises(ValueError, match="NW"):
            ObservationParser.parse(obs)

    def test_hand_inventory_count_mismatch(self):
        obs = _base_obs()
        obs["farms"][0]["hands"] = [[5, 4]]
        # Intentionally NOT adding a second inventory entry
        with pytest.raises(ValueError, match="inventories"):
            ObservationParser.parse(obs)

    def test_tile_grid_wrong_row_count(self):
        obs = _base_obs()
        obs["farms"][0]["tiles"] = _empty_tiles(size=10)[:9]  # only 9 rows
        with pytest.raises(ValueError, match="rows"):
            ObservationParser.parse(obs)

    def test_tile_grid_wrong_col_count(self):
        obs = _base_obs()
        obs["farms"][0]["tiles"][0] = [None] * 9  # row 0 has only 9 cols
        with pytest.raises(ValueError, match="cols"):
            ObservationParser.parse(obs)

    def test_unknown_tile_kind(self):
        obs = _base_obs()
        obs["farms"][0]["tiles"][0][0] = {"kind": "GREENHOUSE"}
        with pytest.raises(ValueError, match="unknown tile kind"):
            ObservationParser.parse(obs)
