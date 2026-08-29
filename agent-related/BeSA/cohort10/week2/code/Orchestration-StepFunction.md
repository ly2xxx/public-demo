# Set environment variables
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export STACK_NAME=orchestration-multi-agent-workshop

# Get Lambda function ARNs
ORCH_PLANNER_ARN=$(aws lambda get-function \
  --function-name $STACK_NAME-orch-planner-agent \
  --query 'Configuration.FunctionArn' \
  --output text)

ORCH_WEATHER_ARN=$(aws lambda get-function \
  --function-name $STACK_NAME-orch-weather-agent \
  --query 'Configuration.FunctionArn' \
  --output text)

ORCH_FLIGHT_ARN=$(aws lambda get-function \
  --function-name $STACK_NAME-orch-flight-manager-agent \
  --query 'Configuration.FunctionArn' \
  --output text)

# Get Step Functions Activity ARN
ACTIVITY_ARN=$(aws stepfunctions list-activities \
  --query 'activities[?contains(name, `human-review`)].activityArn' \
  --output text)

# Get Step Functions execution role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name $STACK_NAME-stepfunctions-execution-role \
  --query 'Role.Arn' \
  --output text)

echo "Planner Function: $ORCH_PLANNER_ARN"
echo "Weather Function: $ORCH_WEATHER_ARN"
echo "Flight Function: $ORCH_FLIGHT_ARN"
echo "Activity ARN: $ACTIVITY_ARN"
echo "Execution Role: $ROLE_ARN"


# Replace placeholders with your actual ARNs
sed -i.bak "s|\${OrchPlannerFunctionArn}|$ORCH_PLANNER_ARN|g" travel-booking-orchestration.json
sed -i.bak "s|\${OrchWeatherFunctionArn}|$ORCH_WEATHER_ARN|g" travel-booking-orchestration.json
sed -i.bak "s|\${OrchFlightFunctionArn}|$ORCH_FLIGHT_ARN|g" travel-booking-orchestration.json
sed -i.bak "s|\${HumanReviewActivityArn}|$ACTIVITY_ARN|g" travel-booking-orchestration.json

echo "✅ ASL definition prepared with actual ARNs"

# Create the state machine
aws stepfunctions create-state-machine \
  --name "travel-booking-orchestration" \
  --definition file://travel-booking-orchestration.json \
  --role-arn $ROLE_ARN \
  --type STANDARD

# Save the state machine ARN
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
  --query 'stateMachines[?contains(name, `travel-booking`)].stateMachineArn' \
  --output text)

echo "✅ State machine created successfully!"
echo "State Machine ARN: $STATE_MACHINE_ARN"

#### test test
{
  "bookingID": "booking-high-risk-001",
  "userId": "user-test-001",
  "origin": "New York, NY",
  "destination": "Miami, FL",
  "travel_dates": {
    "departure": "2026-09-15",
    "return": "2026-09-20"
  },
  "travelers": {
    "adults": 2,
    "children": 0
  },
  "budget": 800,
  "airline_preference": "American",
  "interests": ["beach", "nightlife", "dining"]
}

# Set environment variables if not already set
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Replace with your actual state machine ARN
STATE_MACHINE_ARN="arn:aws:states:$AWS_REGION:$AWS_ACCOUNT_ID:stateMachine:travel-booking-orchestration"

# Start the execution
EXEC_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --input file://high-risk-booking.json \
  --name "high-risk-test-$(date +%s)" \
  --query executionArn --output text)

echo "Started high-risk execution: $EXEC_ARN"

# Check execution status
aws stepfunctions describe-execution \
  --execution-arn "$EXEC_ARN" \
  --query '{Status:status,StartDate:startDate,Input:input}' \
  --output json

# View execution history to see state transitions
aws stepfunctions get-execution-history \
  --execution-arn "$EXEC_ARN" \
  --max-items 10 \
  --query 'events[*].{Type:type,Timestamp:timestamp,StateEntered:stateEnteredEventDetails.name}' \
  --output table

# Poll for pending tasks (ACTIVITY_ARN was set in the previous chapter)
aws stepfunctions get-activity-task \
  --activity-arn "$ACTIVITY_ARN" \
  --query '{TaskToken:taskToken,Input:input}' \
  --output json

# Replace TASK_TOKEN with the actual token from step 4
TASK_TOKEN="AQCsAAAAKgAAAAIAAAAAAAAAAZDrGTzzDBALMKy5se+tJs/kOK8m2j0RjQaiEYWmAIr10s2FQ/qTn49AaSLlk2MnUKGFO3FbkD459yxOdf6ZkSCWaeR6kpb7RO514Yt0kxqyATsif/XFLNZmdPHfNYzTkuBtjduaxveNkDWgFAs1XUA=AAAAKgAAAAIAAAAAAAAAATyy5vrtPN+eT82o1f8qeya3t2PS5L4ygcFpcvpv000HtwaAWmojqZQZ8I8Ia3TIoEQ+kMmuD/kAwA+s30FZqXhFYM06dJLDPPKpsg8jQyJJ0Con6/vREq9M9ZG+fs4oE08p/7s5yrsYYojPHjL2MQRLLIrWbIMpZL8SCMYVl1U8DPLKIIZ1cYjoxLB0pkqII1yyk2CLN54EqojiFLMMKgY="

# Approve the booking despite the risks
aws stepfunctions send-task-success \
  --task-token "$TASK_TOKEN" \
  --task-output '{
    "decision": "approved",
    "reason": "Customer accepts the risks and wants to proceed despite high weather risk and budget constraints",
    "approved_by": "workshop-participant",
    "approval_timestamp": "2026-11-03T16:25:30Z",
    "risk_acknowledgment": "Customer acknowledges thunderstorm risks and budget overrun"
  }'

# Check final execution status
aws stepfunctions describe-execution \
  --execution-arn "$EXEC_ARN" \
  --query '{Status:status,Output:output,StopDate:stopDate}' \
  --output json