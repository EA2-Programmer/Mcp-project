# Run tests from inside the traksys-mcp container
docker exec -it traksys-mcp bash -c "
  cd /app &&
  pip install promptfoo &&
  promptfoo eval -c /app/tests/promptfoo/config/production.yaml
"