import os
from langfuse import Langfuse

# Simple initialization without auth_check
lf = Langfuse(
    secret_key=os.environ.get('LANGFUSE_SECRET_KEY'),
    public_key=os.environ.get('LANGFUSE_PUBLIC_KEY'),
    host=os.environ.get('LANGFUSE_BASE_URL', 'http://langfuse-web:3000')
)

# Create a trace
trace = lf.trace(name="simple-test")
span = trace.span(name="test-span")
span.end()
lf.flush()

print("Trace sent - check Langfuse UI")