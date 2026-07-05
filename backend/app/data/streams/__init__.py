"""Real-time market data streams (WebSocket).

These feed the same tick path as the REST pollers: normalize -> epsilon-persist
to odds_snapshots -> publish to the broadcast hub. REST polling stays as market
discovery and as a fallback when a stream is down.
"""
