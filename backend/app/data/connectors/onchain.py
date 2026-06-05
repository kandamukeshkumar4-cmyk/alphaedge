from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnchainReadOnlyConnector:
    polygon_rpc_url: str
    polymarket_subgraph_url: str

    def fetch_wallet_positions(self, wallet_address: str):
        raise NotImplementedError("read-only on-chain position ingestion is not implemented yet")
