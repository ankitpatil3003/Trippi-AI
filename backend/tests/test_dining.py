from app.agents.dining import rank_dining
from app.schemas.trip import ItineraryDay, RestaurantCandidate


def test_rank_local_and_fancy():
    candidates = [
        RestaurantCandidate(
            id="a", name="Local Spot", city="New York", cuisine="Deli", price_tier="local", description="pastrami"
        ),
        RestaurantCandidate(
            id="b", name="Fancy Room", city="New York", cuisine="French", price_tier="fancy", description="tasting"
        ),
    ]
    itinerary = [ItineraryDay(date="2026-07-21", blocks=[]), ItineraryDay(date="2026-07-22", blocks=[])]
    picks = rank_dining(candidates, itinerary)
    assert picks.local_must_try is not None
    assert picks.fancy_must_try is not None
    assert picks.local_must_try.name == "Local Spot"
    assert picks.fancy_must_try.price_tier == "fancy"
