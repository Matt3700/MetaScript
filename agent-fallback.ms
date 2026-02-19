# Agent fallback demo — local model will signal inability via 'force-fallback'
agent frontend [ "natural_text": "force-fallback say Hello 3 times", "target_syntax": "python-style" ]
# The external model should be used and print EXTERNAL lines.