"""Fair-value research: deterministic valuation models and their sourced inputs.

The arithmetic lives here and only here. `engine` holds the formulas and has no
I/O; `inputs` reads the filings and the quote and says where every figure came
from; `defaults` turns history into a starting set of assumptions and says why;
`analysis` runs scenarios, sensitivities and the reverse DCF; `service` puts the
pieces together for the routes. Milo explains these results and never computes
them. METHODS.md in this folder documents each formula and convention.
"""

MODEL_VERSION = "dcf-1.0"
