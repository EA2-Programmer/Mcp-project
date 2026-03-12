# Load .env file into environment
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"')
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

# Langfuse config for OpenWebUI (note: OpenWebUI uses LANGFUSE_HOST not LANGFUSE_BASE_URL)
$env:LANGFUSE_BASE_URL = "http://localhost:3000"
$env:ENABLE_OPENAI_API_USAGE_TRACKING = "true"

# Start OpenWebUI
open-webui serve