#!/bin/bash
# Hook script executed after Write or Edit tool use.
# Receives hook input as JSON on stdin.
# Exit 0 = success, Exit 2 = blocking error.

echo "File changed — hook triggered."
exit 0
