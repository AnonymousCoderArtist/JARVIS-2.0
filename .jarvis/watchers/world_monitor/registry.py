"""WorldMonitor Endpoint Registry"""

class EndpointRegistry:
    # Categories of geopolitical subsets
    INTELLIGENCE = {
        "telegram": "/api/telegram-feed?limit=50",
        "feed": "/api/news/v1/list-feed-digest?variant=full&lang=en",
        "pizzint": "/api/intelligence/v1/get-pizzint-status?include_gdelt=true",
        "signals": "/api/intelligence/v1/list-cross-source-signals",
        "gdelt": "/api/intelligence/v1/get-gdelt-topic-timeline?topic=military",
        "india_defense": "https://stratnewsglobal.com/feed/",
    }
    
    CONFLICT = {
        "acled": "/api/conflict/v1/list-acled-events",
        "military": "/api/military/v1/list-military-flights?ne_lat=85&ne_lon=57&sw_lat=13&sw_lon=-10",
        "usni": "/api/military/v1/get-usni-fleet-report",
        "defense": "/api/military/v1/list-defense-patents?limit=50",
        "wingbits": "/api/military/v1/get-wingbits-status",
    }
    
    SUPPLY_CHAIN = {
        "energy": "/api/supply-chain/v1/list-energy-disruptions?ongoingOnly=true",
        "pipelines": "/api/supply-chain/v1/list-pipelines",
        "chokepoints": "/api/supply-chain/v1/get-chokepoint-status",
        "hormuz": "/api/supply-chain/hormuz-tracker",
    }
    
    CLIMATE = {
        "fires": "/api/climate/v1/list-fires",
        "climate_news": "/api/climate/v1/list-climate-news",
        "oref": "/api/oref-alerts",
    }
    
    MARKETS = {
        "fear": "/api/market/v1/get-fear-greed-index",
        "stablecoin": "/api/market/v1/list-stablecoin-markets",
        "etf": "/api/bootstrap?keys=etfFlows",
        "gold": "/api/market/v1/get-gold-intelligence",
    }
    
    ECONOMIC = {
        "macro": "/api/economic/v1/get-macro-signals",
        "fx": "/api/economic/v1/get-ecb-fx-rates",
        "yields": "/api/economic/v1/get-eu-yield-curve",
        "energy_prices": "/api/economic/v1/get-energy-prices",
    }
    
    INFRASTRUCTURE = {
        "gpsjam": "/api/gpsjam",
        "outages": "/api/bootstrap?tier=slow", # Includes outages
        "airport_ops": "/api/aviation/v1/get-airport-ops-summary?airports=LHR,FRA,CDG,DXB,IST,JFK",
    }

    @classmethod
    def get_all(cls) -> dict[str, str]:
        all_endpoints = {}
        for category in [cls.INTELLIGENCE, cls.CONFLICT, cls.SUPPLY_CHAIN, cls.CLIMATE, cls.MARKETS, cls.ECONOMIC, cls.INFRASTRUCTURE]:
            all_endpoints.update(category)
        return all_endpoints

    @classmethod
    def get_high_priority(cls) -> list[str]:
        return ["pizzint", "oref", "telegram", "military", "energy", "gpsjam"]
