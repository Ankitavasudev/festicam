"""Allow python -m festicam from anywhere."""

import sys

from .app import main

sys.exit(main())
