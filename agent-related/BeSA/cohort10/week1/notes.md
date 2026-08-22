
A software system that acts on behalf of a user or organization by using AI to make decisions and perform tasks.

AI model -> intelligence

Agent (Ironman) -> building block -> Single autonomous software entity (AI Model + Goal + Tools +Actions)

Agentic AI (Avengers) -> Use one or more AI agents , powered by AI models to autonomously achieve goals -> A complete system built around agents (Models + Agents + Planning + Memory + Tool Calling + Orchestration + Guardrails)

NOT use cases:

Task fully definable by rules

Latency is the primary constraint (Emergency stop)

Full explain-ability is required (Loan decision based on credit-score)

Components of Agent:

Goals (what should i achieve)

Planning (Break goal to tasks)

Memory (Maintain context)

Tools (APIs, Databases, Search systems, Calculators)

Actions (Execute tasks, invoke tools)

Feedback (Did it work)

Agent Loop - Every Agent operates in a Continuous Loop: Observe -> Reason -> Act -> Loop (ReAct) => self-terminating

Loop 1: Gather evidence

Loop 2 Verify evidence

Respond on after confidence is sufficient

Production ready -

Scale & Performance (Inference Platform)

Security & Governance (OAuth)

Reliability & Quality (AI Model)

Cost & Efficiency (Inference Optimization)

Operation & Improvement (GPU)

Matt: mattwood.fyi

Protect your space - focus on niche | Be the connector - GenAI crusade channel

Production: *close the fit between MODEL and HARNESS

HARNESS: small use cases to solve a problem and accumulate experience (build robust context layer along the way - knowledge graph) IMPROVE DATA QUALITY OVER TIME

MODEL: self-improve through use - search agents (use the intent to evaluate agent performance - token efficient) MAKE THE NEXT RUN INCREMENTALLY BETTER

Threats:

Technology, Policy, Development, Society etc - Agents to collect and connect

Career:

Explore and satisfy curiosity

Attitude to life and work, relentless problem solver, approachable

Workshop studio:

Email OTP -> business email -> IDE(with Claude) -> autosave on

Focus on first 5 labs.

Runtime, Gateway,

Lab 4: authenticate -> generate tokens CloudFormation->Stacks->Prerequisites

Lab 5: Run on-demand evaluation might give error

aws lambda invoke 
  --function-name $WARRANTY_LAMBDA_ARN 
  --region us-east-1 
  --payload '{"product_id": "PROD-001"}' 
  --cli-binary-format raw-in-base64-out 
  output.json && cat output.json

Agents

  CustomerSupport: Deployed - Runtime: READY (arn:aws:bedrock-agentcore:us-east-1:565529588603:runtime/CustomerSupporU6vyVI4jSu)

  URL: https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A565529588603%3Aruntime%2FCustomerSupport_CustomerSupport-U6vyVI4jSu/invocations

aws bedrock-agentcore list-memory-records \

  --memory-id CustomerSupport_SharedMemory-ZXLczU4UeZ \

  --namespace-path "/" \

  --region us-east-1

SESSION_3=$(python3 -c 'import uuid; print(uuid.uuid4())')

agentcore invoke "Do you know anything about me?" \

  --session-id $SESSION_3 \

  -H "X-Amzn-Bedrock-AgentCore-Runtime-Custom-User-Id: Sarah" \

  --stream

agentcore traces list --limit 10

agentcore traces get 6a8a13fd0e532048033aace5737e4615 --output trace.json

agentcore logs

agentcore logs --since 1h --level error

agentcore logs --since 1h --query "warranty"

participant:~/workshop/CustomerSupportCOGNITO_DISCOVERY_URL=$(aws ssm get-parameter \ \

  --name /app/customersupport/agentcore/cognito_discovery_url \

  --query 'Parameter.Value' --output text)

COGNITO_CLIENT_ID=$(aws ssm get-parameter \

  --name /app/customersupport/agentcore/client_id \

  --query 'Parameter.Value' --output text)

COGNITO_POOL_ID=$(aws ssm get-parameter \

  --name /app/customersupport/agentcore/pool_id \

  --query 'Parameter.Value' --output text)

COGNITO_WEB_CLIENT_ID=$(aws ssm get-parameter \

  --name /app/customersupport/agentcore/web_client_id \

  --query 'Parameter.Value' --output text)

echo "Discovery URL: $COGNITO_DISCOVERY_URL"

echo "Client ID:     $COGNITO_CLIENT_ID"

echo "Pool ID:       $COGNITO_POOL_ID"

echo "Web Client ID: $COGNITO_WEB_CLIENT_ID"

Discovery URL: https://cognito-idp.us-east-1.amazonaws.com/us-east-1_nh4lPLJvX/.well-known/openid-configuration

Client ID:     2ag05clb9goifa4o98k6fa5bnb

Pool ID:       us-east-1_nh4lPLJvX

Web Client ID: 6f9lc4tqjbsgdoad3tjrsq26lo

aws cognito-idp admin-create-user \

  --user-pool-id $COGNITO_POOL_ID \

  --username workshopuser@example.com \

  --temporary-password 'TempPass1!' \

  --user-attributes Name=email,Value=workshopuser@example.com Name=email_verified,Value=true \

  --message-action SUPPRESS \

  --no-cli-pager

# Set a permanent password so the user is confirmed and ready to use

aws cognito-idp admin-set-user-password \

  --user-pool-id $COGNITO_POOL_ID \

  --username workshopuser@example.com \

  --password 'WorkshopPass1!' \

  --permanent \

  --no-cli-pager

echo "User 'workshopuser@example.com' created and confirmed"

===================

# Skip this block if $TOKEN is still set from Lab 4

COGNITO_POOL_ID=$(aws ssm get-parameter \

  --name /app/customersupport/agentcore/pool_id \

  --query 'Parameter.Value' --output text)

COGNITO_WEB_CLIENT_ID=$(aws ssm get-parameter \

  --name /app/customersupport/agentcore/web_client_id \

  --query 'Parameter.Value' --output text)

TOKEN=$(aws cognito-idp initiate-auth \

  --auth-flow USER_PASSWORD_AUTH \

  --client-id $COGNITO_WEB_CLIENT_ID \

  --auth-parameters USERNAME=workshopuser@example.com,PASSWORD='WorkshopPass1!' \

  --query 'AuthenticationResult.AccessToken' --output text)

echo "Token obtained successfully"

======================

agentcore run eval \

  --runtime CustomerSupport \

  --evaluator Builtin.GoalSuccessRate Builtin.Correctness \

  --days 1

agentcore evals history --runtime CustomerSupport --limit 5

https://d2q9dr7th9rq1x.cloudfront.net/ports/8501/

cd /home/participant/workshop
zip -r ~/workshop-backup.zip CustomerSupport/ 
  --exclude "CustomerSupport/app/CustomerSupport/.venv/*" 
  --exclude "CustomerSupport/agentcore/.cache/*" 
  --exclude "CustomerSupport/agentcore/.cli/logs/*" 
  --exclude "*/__pycache__/*" 
  --exclude "*.pyc"
