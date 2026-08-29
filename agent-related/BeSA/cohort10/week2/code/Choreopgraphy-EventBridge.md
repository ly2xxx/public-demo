export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export STACK_NAME=merged-multi-agent-workshop

# Get the EventBridge bus name
EVENT_BUS_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='ChoreographyEventBusName'].OutputValue" \
  --output text)

# Get Lambda function ARNs
PLANNER_FUNCTION_ARN=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='PlannerFunctionArn'].OutputValue" \
  --output text)

WEATHER_FUNCTION_ARN=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='WeatherFunctionArn'].OutputValue" \
  --output text)

FLIGHT_FUNCTION_ARN=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='FlightManagerFunctionArn'].OutputValue" \
  --output text)

echo "Event Bus: $EVENT_BUS_NAME"
echo "Flight Function: $FLIGHT_FUNCTION_ARN"

# Create rule for initial travel requests
aws events put-rule \
  --name InitialTravelRequestRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.travel-request"],"detail-type":["TravelRequestSubmitted"]}' \
  --state ENABLED

# Add Planner Agent as target
aws events put-targets \
  --rule InitialTravelRequestRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="$PLANNER_FUNCTION_ARN"

# Create rule for DatesFinalized events from Planner
aws events put-rule \
  --name PlannerDatesRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.planner-agent"],"detail-type":["DatesFinalized"]}' \
  --state ENABLED

# Add Weather and Flight Manager as targets
aws events put-targets \
  --rule PlannerDatesRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="$WEATHER_FUNCTION_ARN" "Id"="2","Arn"="$FLIGHT_FUNCTION_ARN"

# Weather analysis completed -> Planner
aws events put-rule \
  --name WeatherCompletedRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.weather-agent"],"detail-type":["WeatherAnalysisCompleted"]}' \
  --state ENABLED

aws events put-targets \
  --rule WeatherCompletedRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="$PLANNER_FUNCTION_ARN"

# Flight search completed -> Planner
aws events put-rule \
  --name FlightCompletedRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.flight-manager-agent"],"detail-type":["FlightSearchCompleted"]}' \
  --state ENABLED

aws events put-targets \
  --rule FlightCompletedRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="$PLANNER_FUNCTION_ARN"

# Permission for initial travel requests
aws lambda add-permission \
  --function-name $PLANNER_FUNCTION_ARN \
  --statement-id "AllowEventBridgeInitialRequest" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:$AWS_REGION:$AWS_ACCOUNT_ID:rule/$EVENT_BUS_NAME/InitialTravelRequestRule"

# Permission for DatesFinalized events
DATES_RULE_ARN="arn:aws:events:$AWS_REGION:$AWS_ACCOUNT_ID:rule/$EVENT_BUS_NAME/PlannerDatesRule"

aws lambda add-permission \
  --function-name $WEATHER_FUNCTION_ARN \
  --statement-id "AllowEventBridgeDates" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$DATES_RULE_ARN"

aws lambda add-permission \
  --function-name $FLIGHT_FUNCTION_ARN \
  --statement-id "AllowEventBridgeDates" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$DATES_RULE_ARN"

# Permissions for return events
WEATHER_RULE_ARN="arn:aws:events:$AWS_REGION:$AWS_ACCOUNT_ID:rule/$EVENT_BUS_NAME/WeatherCompletedRule"
FLIGHT_RULE_ARN="arn:aws:events:$AWS_REGION:$AWS_ACCOUNT_ID:rule/$EVENT_BUS_NAME/FlightCompletedRule"

aws lambda add-permission \
  --function-name $PLANNER_FUNCTION_ARN \
  --statement-id "AllowEventBridgeWeatherReturn" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$WEATHER_RULE_ARN"

aws lambda add-permission \
  --function-name $PLANNER_FUNCTION_ARN \
  --statement-id "AllowEventBridgeFlightReturn" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$FLIGHT_RULE_ARN"

# Create an SQS queue for human review
aws sqs create-queue --queue-name multi-agent-human-review

# Get the queue URL and ARN
QUEUE_URL=$(aws sqs get-queue-url --queue-name multi-agent-human-review --query QueueUrl --output text)
QUEUE_ARN=$(aws sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names QueueArn \
  --query Attributes.QueueArn --output text)

# Create a rule to capture Planner escalation events
aws events put-rule \
  --name HumanReviewRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.planner-agent"],"detail-type":["HumanReviewRequired"]}' \
  --state ENABLED

# Attach the SQS queue as the target
aws events put-targets \
  --rule HumanReviewRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="$QUEUE_ARN"

# Set SQS permissions for EventBridge
aws sqs set-queue-attributes \
  --queue-url $QUEUE_URL \
  --attributes "{\"Policy\":\"{\\\"Version\\\":\\\"2012-10-17\\\",\\\"Statement\\\":[{\\\"Effect\\\":\\\"Allow\\\",\\\"Principal\\\":{\\\"Service\\\":\\\"events.amazonaws.com\\\"},\\\"Action\\\":\\\"sqs:SendMessage\\\",\\\"Resource\\\":\\\"$QUEUE_ARN\\\"}]}\"}"

# Create rule for human approval decisions
aws events put-rule \
  --name HumanApprovalRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.human-review"],"detail-type":["HumanApprovalDecision"]}' \
  --state ENABLED

# Add Planner Agent as target for human decisions
aws events put-targets \
  --rule HumanApprovalRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="$PLANNER_FUNCTION_ARN"

# Grant permission for human approval events
aws lambda add-permission \
  --function-name $PLANNER_FUNCTION_ARN \
  --statement-id "AllowEventBridgeHumanApproval" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:$AWS_REGION:$AWS_ACCOUNT_ID:rule/$EVENT_BUS_NAME/HumanApprovalRule"

{
  "Source": "workshop.human-review",
  "DetailType": "HumanApprovalDecision",
  "Detail": {
    "bookingID": "booking-123",
    "decision": "approved", // or "rejected"
    "reviewer": "admin-user",
    "timestamp": "2026-09-20T10:00:00Z",
    "notes": "Approval reason or rejection explanation"
  },
  "EventBusName": "your-event-bus-name"
}

# Create CloudWatch Log Group for event monitoring
aws logs create-log-group --log-group-name /aws/events/multi-agent-workshop

# Create catch-all rule
aws events put-rule \
  --name CatchAllEventsRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.travel-request","workshop.planner-agent","workshop.weather-agent","workshop.flight-manager-agent","workshop.human-review"]}' \
  --state ENABLED

# Add CloudWatch Logs as target
aws events put-targets \
  --rule CatchAllEventsRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="arn:aws:logs:$AWS_REGION:$AWS_ACCOUNT_ID:log-group:/aws/events/multi-agent-workshop"

# Set CloudWatch Logs permissions
aws logs put-resource-policy \
  --policy-name EventBridgeLogsPolicy \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"events.amazonaws.com"},"Action":["logs:CreateLogStream","logs:PutLogEvents"],"Resource":"arn:aws:logs:'$AWS_REGION':'$AWS_ACCOUNT_ID':log-group:/aws/events/multi-agent-workshop:*"}]}'

#### test test
# If you haven't set these yet, set your environment variables
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Event Bus: $EVENT_BUS_NAME"
echo "AWS Region: $AWS_REGION"

# Create a travel request event (high-risk scenario for Miami in March)
aws events put-events --entries '[
  {
    "Source": "workshop.travel-request",
    "DetailType": "TravelRequestSubmitted",
    "Detail": "{\"bookingID\":\"high-risk-test-456\",\"userId\":\"workshop-participant\",\"origin\":\"LAX\",\"destination\":\"Miami\",\"travel_dates\":{\"start\":\"2026-09-20\",\"end\":\"2026-09-23\"},\"travelers\":2,\"budget\":1000,\"airline_preference\":\"American\",\"interests\":[\"beaches\",\"nightlife\",\"culture\"]}",
    "EventBusName": "'$EVENT_BUS_NAME'"
  }
]' --region $AWS_REGION

echo "✅ Travel request event published!"
echo "📋 Booking ID: high-risk-test-456"
echo "🛫 Route: LAX → Miami"
echo "📅 Dates: March 20-23, 2026"

Cloudwatch
fields @timestamp, @message
| parse @message /"detail-type":"(?<event_type>[^"]+)"/
| parse @message /"source":"(?<source>[^"]+)"/
| parse @message /"id":"(?<event_id>[^"]+)"/
| parse @message /"bookingID":"(?<bookingID_camel>[^"]+)"/
| parse @message /"booking_id":"(?<booking_id_snake>[^"]+)"/
| display @timestamp, source, event_type, coalesce(bookingID_camel, booking_id_snake) as booking_id, event_id
| filter booking_id = "high-risk-test-456"
| sort @timestamp asc

# Check if there are messages in the human review queue

aws sqs get-queue-attributes \
  --queue-url https://sqs.$AWS_REGION.amazonaws.com/$AWS_ACCOUNT_ID/multi-agent-human-review \
  --attribute-names ApproximateNumberOfMessages
# Receive and inspect the human review message
aws sqs receive-message \
  --queue-url https://sqs.$AWS_REGION.amazonaws.com/$AWS_ACCOUNT_ID/multi-agent-human-review \
  --max-number-of-messages 1

# Send human approval decision
aws events put-events --entries '[
  {
    "Source": "workshop.human-review",
    "DetailType": "HumanApprovalDecision",
    "Detail": "{\"bookingID\":\"high-risk-test-456\",\"decision\":\"approved\",\"reviewer\":\"workshop-admin\",\"timestamp\":\"2026-09-20T10:30:00Z\",\"notes\":\"Approved after reviewing weather forecast - conditions expected to improve by travel date\"}",
    "EventBusName": "'$EVENT_BUS_NAME'"
  }
]' --region $AWS_REGION

echo "✅ Human approval decision sent!"
echo "📋 Booking ID: high-risk-test-456"
echo "✅ Decision: APPROVED"
echo "👤 Reviewer: workshop-admin"