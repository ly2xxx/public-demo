# Set environment variables
export AWS_REGION=us-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export STACK_NAME=merged-multi-agent-workshop

# Create SNS topic for hotel recommendations
SNS_TOPIC_ARN=$(aws sns create-topic \
  --name hotel-recommendations \
  --query 'TopicArn' \
  --output text)

echo "✅ SNS Topic created: $SNS_TOPIC_ARN"

# Subscribe your email to receive the funny hotel emails
read -p "Enter your email address to receive hotel recommendations: " USER_EMAIL

aws sns subscribe \
  --topic-arn $SNS_TOPIC_ARN \
  --protocol email \
  --notification-endpoint $USER_EMAIL

echo "📧 Check your email and confirm the SNS subscription!"
echo "⏳ Waiting for you to confirm... (check your inbox)"
read -p "Press Enter after you've confirmed the subscription..."

# Get the event bus name and session bucket
EVENT_BUS_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='ChoreographyEventBusName'].OutputValue" \
  --output text)

SESSION_BUCKET="$STACK_NAME-agent-sessions-$AWS_ACCOUNT_ID"

# Get the Lambda execution role ARN
LAMBDA_ROLE_ARN=$(aws iam get-role \
  --role-name $STACK_NAME-shared-agent-execution-role \
  --query 'Role.Arn' \
  --output text)

echo "Event Bus: $EVENT_BUS_NAME"
echo "Session Bucket: $SESSION_BUCKET"
echo "Lambda Role: $LAMBDA_ROLE_ARN"
echo "SNS Topic: $SNS_TOPIC_ARN"

# Create inline policy to allow Lambda to publish to SNS
aws iam put-role-policy \
  --role-name $STACK_NAME-shared-agent-execution-role \
  --policy-name HotelAgentSNSPolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": "sns:Publish",
        "Resource": "'$SNS_TOPIC_ARN'"
      }
    ]
  }'

echo "✅ Lambda role granted SNS publish permission"

# Create the deployment package
zip -r hotel-agent.zip lambda_function.py

aws lambda create-function \
  --function-name $STACK_NAME-hotel-agent \
  --runtime python3.13 \
  --handler lambda_function.lambda_handler \
  --role $LAMBDA_ROLE_ARN \
  --timeout 60 \
  --memory-size 512 \
  --environment "Variables={EVENT_BUS_NAME=$EVENT_BUS_NAME,SESSION_BUCKET=$SESSION_BUCKET,STACK_NAME=$STACK_NAME,SNS_TOPIC_ARN=$SNS_TOPIC_ARN}" \
  --layers $(aws lambda list-layers --query 'Layers[?contains(LayerName, `merged`)].LatestMatchingVersion.LayerVersionArn' --output text) \
  --zip-file fileb://hotel-agent.zip

# Get the function ARN
HOTEL_FUNCTION_ARN=$(aws lambda get-function \
  --function-name $STACK_NAME-hotel-agent \
  --query 'Configuration.FunctionArn' \
  --output text)

echo "✅ Hotel Agent deployed: $HOTEL_FUNCTION_ARN"

# Create rule to trigger Hotel Agent on FinalBookingCompleted events
aws events put-rule \
  --name HotelAgentRule \
  --event-bus-name $EVENT_BUS_NAME \
  --event-pattern '{"source":["workshop.planner-agent"],"detail-type":["FinalBookingCompleted"]}' \
  --state ENABLED

# Add Hotel Agent as target
aws events put-targets \
  --rule HotelAgentRule \
  --event-bus-name $EVENT_BUS_NAME \
  --targets "Id"="1","Arn"="$HOTEL_FUNCTION_ARN"

# Grant EventBridge permission to invoke the Hotel Agent
HOTEL_RULE_ARN="arn:aws:events:$AWS_REGION:$AWS_ACCOUNT_ID:rule/$EVENT_BUS_NAME/HotelAgentRule"

aws lambda add-permission \
  --function-name $HOTEL_FUNCTION_ARN \
  --statement-id "AllowEventBridgeHotelAgent" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$HOTEL_RULE_ARN"

echo "✅ Hotel Agent wired into EventBridge"

#### test test
# Send a test booking request (reuse from Module 1)
aws events put-events --entries '[
  {
    "Source": "workshop.travel-request",
    "DetailType": "TravelRequestSubmitted",
    "Detail": "{\"bookingID\":\"hotel-test-001\",\"userId\":\"workshop-participant\",\"origin\":\"LAX\",\"destination\":\"Miami\",\"travel_dates\":{\"start\":\"2026-09-20\",\"end\":\"2026-09-23\"},\"travelers\":2,\"budget\":1000,\"airline_preference\":\"American\",\"interests\":[\"beaches\",\"nightlife\"]}",
    "EventBusName": "'$EVENT_BUS_NAME'"
  }
]' --region $AWS_REGION

echo "✅ Test booking submitted: hotel-test-001"