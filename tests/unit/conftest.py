"""
Shared test configuration for ORION unit tests.
"""

import os

# Enable debug mode for all tests by default (fail-closed auth bypass for testing)
# Individual tests that need to verify auth behavior can unset this locally.
os.environ["ORION_DEBUG_MODE"] = "1"
