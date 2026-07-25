#!/bin/sh
set -e

exec python -c "
from spark.web.app import create_app
import uvicorn
uvicorn.run(create_app('/data'), host='0.0.0.0', port=8000)
"
