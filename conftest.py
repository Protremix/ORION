import sys
import os

# Add src and simulation directories to Python path
impl_dir = os.path.dirname(os.path.abspath(__file__))
for subdir in ['src', 'src/memory', 'src/audit', 'src/safety', 'src/arbitration', 
               'src/contracts', 'src/config', 'src/cognitive', 'src/state', 'simulation']:
    path = os.path.join(impl_dir, subdir)
    if path not in sys.path:
        sys.path.insert(0, path)
