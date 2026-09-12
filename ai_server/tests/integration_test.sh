#!/bin/sh

set -euo pipefail

echo "Starting integration test..."
echo "Get session ID from the server..."
export SESSION_ID=$(curl -s -X POST http://localhost:8000/v1/sessions \
-H 'X-Authenticated-User-ID: user-123' | jq -r .session_id)

echo "Session ID: $SESSION_ID"
echo "Update machine information for the session..."
curl -X PUT "http://localhost:8000/v1/sessions/$SESSION_ID/machine-information" \
  -H 'Content-Type: application/json' \
  -H 'X-Authenticated-User-ID: user-123' \
  -d '{
    "name":"SQLインジェクションの基礎2",
    "visibility":"private",
    "theme":"SQL Injection",
    "difficulty":"Easy",
    "operating_system":"Ubuntu 26.04",
    "needs_user_flag":true,
    "user_flag_details":"/home/student/user.txt",
    "needs_system_flag":false
  }'

echo "Create a new scenario for the session..."
curl -N "http://localhost:8000/v1/sessions/$SESSION_ID/scenarios/events" \
  -H 'X-Authenticated-User-ID: user-123'

echo "Create a new machine for the session..."
curl -X POST "http://localhost:8000/v1/sessions/$SESSION_ID/machines" \
  -H 'Content-Type: application/json' \
  -H 'X-Authenticated-User-ID: user-123' \
  -d '{}'

echo "Get session information..."
curl "http://localhost:8000/v1/sessions/$SESSION_ID" \
  -H 'X-Authenticated-User-ID: user-123'  