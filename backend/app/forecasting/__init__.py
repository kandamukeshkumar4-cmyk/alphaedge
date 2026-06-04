"""AlphaEdge Mirror — forecast track-record scoring primitives.

Shared tuning constants for the "measure YOUR edge" product. These guard the
integrity of the calibration/edge metrics so the dashboard never lies to a user.
"""

# A forecast within this distance of the market's implied probability is treated
# as "anchored" (it carries no independent signal) and is excluded from
# edge-over-market and calibration aggregates.
ANCHOR_EPSILON = 0.02

# Below this many *live, resolved, scored* forecasts, the headline Brier / edge
# numbers are shown as provisional.
BRIER_MIN_SAMPLE = 30

# Calibration curves need far more data than a headline Brier before they mean
# anything (10 bins => only a handful of points each at 30).
CALIBRATION_MIN_SAMPLE = 150

# Number of equal-width bins used for the calibration curve.
CALIBRATION_BINS = 10
