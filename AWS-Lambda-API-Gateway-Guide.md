# AWS Lambda + API Gateway (HTTP API) Guide (AWS SAM, Python, DynamoDB)

This repository is a complete, working **serverless API example** built on AWS:
- **API Gateway (HTTP API)** exposing `GET /health`, plus CRUD-style `/items` endpoints
- **AWS Lambda** (Python) for request handling
- **Lambda authorizer** (Bearer token from SSM Parameter Store)
- **DynamoDB** for persistence

**Where to start:** Follow this guide top-to-bottom to install tooling, configure AWS, deploy with SAM, test endpoints, troubleshoot common failures, and clean up resources.

---

## Step 1: Prerequisites Setup

### 1.1 Install AWS CLI v2

**macOS:**
```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Verify:**
```bash
aws --version
# Should show: aws-cli/2.x.x ...
```

### 1.2 Install AWS SAM CLI

**macOS (Homebrew):**
```bash
brew tap aws/tap
brew install aws-sam-cli
```

**Linux:**
```bash
# Download latest release from: https://github.com/aws/aws-sam-cli/releases/latest
# Example:
wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip
unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
sudo ./sam-installation/install
```

**Verify:**
```bash
sam --version
# Should show: SAM CLI, version 1.x.x
```

### 1.3 Install Python 3.9+ (if not already installed)

```bash
python3 --version
# Should show: Python 3.9.x or higher
```

### 1.4 Install jq (for testing JSON responses)

**macOS:**
```bash
brew install jq
```

**Linux:**
```bash
sudo apt-get install jq  # Debian/Ubuntu
sudo yum install jq      # RedHat/CentOS
```

---

## Step 2: Configure AWS Credentials

### 2.1 Get AWS Access Keys

1. Log into AWS Console
2. Go to IAM → Users → Your User
3. Security credentials tab
4. Create access key (for CLI)
5. Save the Access Key ID and Secret Access Key

### 2.2 Configure AWS CLI

```bash
aws configure
```

Enter when prompted:
- **AWS Access Key ID**: `<your-access-key>`
- **AWS Secret Access Key**: `<your-secret-key>`
- **Default region name**: `eu-north-1` (or your preferred region)
- **Default output format**: `json`

### 2.3 Verify Configuration

```bash
aws sts get-caller-identity
```

You should see your account ID and user ARN.

---

## Step 2A: Set Up IAM Permissions (Required)

Your IAM user needs specific permissions to deploy and manage this serverless application. You have two options:

### Option A: Using AWS Console (Recommended for Beginners)

#### Method 1: Attach AWS Managed Policies (Quickest)

1. **Log into AWS Console** at https://console.aws.amazon.com/iam/

2. **Navigate to your user**:
   - Click "Users" in the left sidebar
   - Find and click your username (e.g., `test-stabalmo`)

3. **Add permissions**:
   - Click the "Permissions" tab
   - Click "Add permissions" → "Attach policies directly"

4. **Search and select these managed policies**:
   - ✅ `AWSLambda_FullAccess`
   - ✅ `AmazonAPIGatewayAdministrator`
   - ✅ `AmazonSSMFullAccess`
   - ✅ `AmazonDynamoDBFullAccess`
   - ✅ `CloudWatchLogsFullAccess`
   - ✅ `AWSCloudFormationFullAccess`
   - ✅ `IAMFullAccess` (or see custom policy below for minimal IAM permissions)

5. **Review and add**:
   - Click "Next"
   - Click "Add permissions"

6. **Verify**:
   ```bash
   aws iam list-attached-user-policies --user-name YOUR_USERNAME
   ```

#### Method 2: Create Custom Policy (More Secure - Least Privilege)

If you want minimal permissions, follow these steps:

**Step 1: Create the Policy**

1. In AWS Console → IAM → **Policies** (left sidebar)
2. Click **"Create policy"**
3. Click the **JSON** tab
4. **Use this policy file** (replace `YOUR_ACCOUNT_ID` and `YOUR_REGION` inside it):

- `iam/lambda-example-deploy-policy.json`

If you want to create the policy from CLI:

```bash
aws iam create-policy \
  --policy-name LambdaExampleDeployPolicy \
  --policy-document file://iam/lambda-example-deploy-policy.json
```

**What this policy allows:**
- ✅ Create/manage SSM parameters under `/lambda-example/*`
- ✅ Create/manage Lambda functions named `lambda-example-*`
- ✅ Create/manage API Gateway (all resources in your region)
- ✅ Create/manage DynamoDB tables named `lambda-example-*`
- ✅ Create/manage CloudFormation stacks for your app and SAM CLI
- ✅ Create/manage IAM roles for Lambda execution
- ✅ Create/manage CloudWatch Logs for your Lambdas
- ✅ Send traces to X-Ray
- ✅ Store SAM deployment artifacts in S3

**Policy JSON:** see `iam/lambda-example-deploy-policy.json` (edit `YOUR_ACCOUNT_ID` and `YOUR_REGION` there).

5. **Replace placeholders**:
   - Replace `YOUR_ACCOUNT_ID` with your AWS account ID (find it from `aws sts get-caller-identity`)
   - Replace `YOUR_REGION` with your region (e.g., `us-east-1`, `eu-north-1`)

6. **Name the policy**:
   - Click **"Next"**
   - Policy name: `LambdaExampleDeployPolicy`
   - Description: `Permissions for deploying lambda-example serverless application`
   - Click **"Create policy"**

**Step 2: Attach the Policy to Your User**

1. Go to IAM → **Users** → Your username
2. Click **"Permissions"** tab
3. Click **"Add permissions"** → **"Attach policies directly"**
4. Search for `LambdaExampleDeployPolicy`
5. Check the box next to it
6. Click **"Next"** → **"Add permissions"**

**Step 3: Verify Permissions**

```bash
# Test SSM access (should work now)
# Note: Use /lambda-example/ prefix since permissions might be scoped
aws ssm put-parameter \
  --name /lambda-example/test-param \
  --type String \
  --value "test" \
  --overwrite \
  --region YOUR_REGION
```

**Expected output if successful:**
```json
{
    "Version": 1,
    "Tier": "Standard"
}
```

**If you see this error:**
```
An error occurred (AccessDeniedException) when calling the PutParameter operation...
```

You still need SSM permissions. Contact your AWS administrator.

**Clean up test parameter:**
```bash
aws ssm delete-parameter \
  --name /lambda-example/test-param \
  --region YOUR_REGION
```

**Note:** You might not be able to run `aws iam list-attached-user-policies` to view your own permissions (this requires IAM read access). That's OK - you can still use the services if your admin configured them correctly.

---

### Option B: Using AWS CLI (For Advanced Users)

#### Step 1: Save the policy to a file

Create a file `lambda-example-policy.json` with the JSON policy from Method 2 above (with placeholders replaced).

#### Step 2: Get your account ID and region

```bash
# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $ACCOUNT_ID"

# Set your region
REGION="eu-north-1"  # or your preferred region
echo "Region: $REGION"

# Your IAM username
USERNAME="test-stabalmo"  # replace with your actual username
```

#### Step 3: Replace placeholders in the policy file

```bash
# macOS/Linux
sed -i.bak "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" lambda-example-policy.json
sed -i.bak "s/YOUR_REGION/$REGION/g" lambda-example-policy.json

# Verify the file
cat lambda-example-policy.json
```

#### Step 4: Create the policy

```bash
aws iam create-policy \
  --policy-name LambdaExampleDeployPolicy \
  --policy-document file://lambda-example-policy.json \
  --description "Permissions for deploying lambda-example serverless application"
```

**Save the Policy ARN** from the output (looks like: `arn:aws:iam::123456789012:policy/LambdaExampleDeployPolicy`)

#### Step 5: Attach policy to your user

```bash
# Replace with your policy ARN from step 4
POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/LambdaExampleDeployPolicy"

aws iam attach-user-policy \
  --user-name $USERNAME \
  --policy-arn $POLICY_ARN
```

#### Step 6: Verify

```bash
aws iam list-attached-user-policies --user-name $USERNAME
```

---

### Common Permission Errors and Solutions

**Error: `AccessDeniedException` when calling `PutParameter`**
- **Cause**: Missing SSM permissions
- **Solution**: Make sure SSM permissions are added for `/lambda-example/*` path (Step 2A above)

**Error: `User is not authorized to perform: cloudformation:CreateChangeSet`**
- **Cause**: Missing CloudFormation changeset permissions (needed for SAM deployment)
- **Common variations**:
  - `...on resource: arn:aws:cloudformation:REGION:ACCOUNT:stack/aws-sam-cli-managed-default/*`
  - `...on resource: arn:aws:cloudformation:REGION:aws:transform/Serverless-2016-10-31` (SAM Transform)
- **Solution**: Add `cloudformation:CreateChangeSet` (and related actions) with `Resource: "*"` to handle global SAM transforms
- **This is the most common error when running `sam deploy` for the first time**

**Error: `User is not authorized to perform: iam:CreateRole`**
- **Cause**: Missing IAM role creation permissions (Lambda needs execution roles)
- **Solution**: Add IAM role creation permissions or use managed policy `IAMFullAccess`

**Error: `User is not authorized to perform: lambda:CreateFunction`**
- **Cause**: Missing Lambda permissions
- **Solution**: Add Lambda permissions or use managed policy `AWSLambda_FullAccess`

**Error: `User is not authorized to perform: s3:CreateBucket`** or **`s3:PutEncryptionConfiguration`**
- **Cause**: SAM CLI needs S3 to store deployment artifacts and enable bucket encryption
- **Solution**: Add S3 permissions for `aws-sam-cli-managed-default-*` buckets (including encryption permissions)

**Error: Cannot create/modify IAM policies (permission denied)**
- **Cause**: Your user doesn't have `iam:CreatePolicy` permission
- **Solution**: Contact your AWS administrator and ask them to create and attach the policy for you

---

### For AWS Administrators

If you're setting up permissions for another user, use this quick command:

```bash
# Attach managed policies (quick setup)
USERNAME="test-stabalmo"

aws iam attach-user-policy --user-name $USERNAME --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess
aws iam attach-user-policy --user-name $USERNAME --policy-arn arn:aws:iam::aws:policy/AmazonAPIGatewayAdministrator
aws iam attach-user-policy --user-name $USERNAME --policy-arn arn:aws:iam::aws:policy/AmazonSSMFullAccess
aws iam attach-user-policy --user-name $USERNAME --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
aws iam attach-user-policy --user-name $USERNAME --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
aws iam attach-user-policy --user-name $USERNAME --policy-arn arn:aws:iam::aws:policy/AWSCloudFormationFullAccess
aws iam attach-user-policy --user-name $USERNAME --policy-arn arn:aws:iam::aws:policy/IAMFullAccess
```

---

## Step 3: Clone and Prepare the Project

### 3.1 Navigate to the Project Directory

```bash
cd /path/to/lambda-example
```

### 3.2 Review the Project Structure

```bash
ls -la
```

You should see:
- `template.yaml` - SAM template
- `src/` - Lambda code
- `tests/` - Unit tests
- `README.md` - Quick reference
- `GETTING_STARTED.md` - This file

---

## Step 4: Create the Authentication Token in SSM

This token will be used to authenticate API requests.

### 4.1 Choose Your Token

Generate a strong token (or use your own):

```bash
# Generate a random token (recommended)
TOKEN=$(openssl rand -base64 32)
echo "Your token: $TOKEN"
```

**Save this token!** You'll need it later for testing.

### 4.2 Store Token in SSM Parameter Store

```bash
aws ssm put-parameter \
  --name /lambda-example/dev/auth-token \
  --type SecureString \
  --value "$TOKEN" \
  --overwrite \
  --region $REGION
```

**Note:** Replace `$REGION` with your chosen region if different.

### 4.3 Verify the Parameter Was Created

```bash
aws ssm get-parameter \
  --name /lambda-example/dev/auth-token \
  --with-decryption \
  --region $REGION \
  --query 'Parameter.Value' \
  --output text
```

Should display your token.

---

## Step 5: Build the Project

### 5.1 Build Lambda Functions

```bash
sam build
```

You should see:
```
Build Succeeded
...
```

### 5.2 (Optional) Run Unit Tests

```bash
python3 -m unittest discover -s tests -v
```

All tests should pass.

---

## Step 6: Deploy to AWS

### 6.1 Deploy Using Guided Mode (First Time)

```bash
sam deploy --guided
```

Answer the prompts:

- **Stack Name**: `lambda-example-dev` (or your choice)
- **AWS Region**: `eu-north-1` (or your chosen region)
- **Parameter StageName**: `dev` (press Enter for default)
- **Parameter AuthTokenParamName**: `/lambda-example/dev/auth-token` (press Enter for default)
- **Confirm changes before deploy**: `N`
- **Allow SAM CLI IAM role creation**: `Y`
- **Disable rollback**: `N`
- **ApiFunction has no authorization defined**: `Y` (this is expected for /health)
- **Save arguments to configuration file**: `Y`
- **SAM configuration file**: `samconfig.toml` (press Enter)
- **SAM configuration environment**: `default` (press Enter)

### 6.2 Wait for Deployment

The deployment will take 2-5 minutes. You'll see:

```
CloudFormation stack changeset
...
Successfully created/updated stack - lambda-example-dev in eu-north-1
```

### 6.3 Get Your API URL

After deployment completes, look for the **Outputs** section:

```
Key                 ApiUrl
Description         API Gateway endpoint URL
Value               https://xxxxxxxxxx.execute-api.eu-north-1.amazonaws.com/dev
```

**Save this URL!**

Or retrieve it anytime with:

```bash
aws cloudformation describe-stacks \
  --stack-name lambda-example-dev \
  --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text
```

---

## Step 7: Test Your API

### 7.1 Set Environment Variables

```bash
# Replace with your actual values
export API_URL="https://xxxxxxxxxx.execute-api.eu-north-1.amazonaws.com/dev"
export AUTH_TOKEN="<your-token-from-step-4>"
```

### 7.2 Test Health Endpoint (Public)

```bash
curl -sS "$API_URL/health" | jq .
```

**Expected response:**
```json
{
  "ok": true
}
```

### 7.3 Test Create Item (Authenticated)

```bash
curl -sS -X POST "$API_URL/items" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-first-item"}' | jq .
```

**Expected response:**
```json
{
  "item": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "my-first-item",
    "createdAtMs": 1735234567890
  }
}
```

**Save the `id` value for next steps!**

### 7.4 Test Get Item (Authenticated)

```bash
# Replace <item-id> with the ID from the previous response
ITEM_ID="550e8400-e29b-41d4-a716-446655440000"

curl -sS "$API_URL/items/$ITEM_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq .
```

**Expected response:**
```json
{
  "item": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "my-first-item",
    "createdAtMs": 1735234567890
  }
}
```

### 7.5 Test Delete Item (Authenticated)

```bash
curl -sS -X DELETE "$API_URL/items/$ITEM_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -i
```

**Expected response:**
```
HTTP/2 204
...
```

(No response body - status 204 means successful deletion)

### 7.6 Verify Item Was Deleted

```bash
curl -sS "$API_URL/items/$ITEM_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq .
```

**Expected response:**
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Item not found"
  }
}
```

### 7.7 Test Authentication Failure

```bash
# Try without auth header
curl -sS "$API_URL/items" \
  -H "Content-Type: application/json" \
  -d '{"name":"test"}' -i
```

**Expected response:**
```
HTTP/2 401
...
{"message":"Unauthorized"}
```

---

## Step 8: View Logs and Monitoring

### 8.1 View Lambda Logs in CloudWatch

**For API Function:**
```bash
aws logs tail /aws/lambda/lambda-example-dev-ApiFunction --follow
```

**For Authorizer Function:**
```bash
aws logs tail /aws/lambda/lambda-example-dev-AuthorizerFunction --follow
```

Press `Ctrl+C` to stop tailing.

### 8.2 View Logs in AWS Console

1. Go to AWS Console → CloudWatch → Log groups
2. Find `/aws/lambda/lambda-example-dev-ApiFunction`
3. Click on latest log stream
4. View structured JSON logs

### 8.3 View X-Ray Traces

1. Go to AWS Console → X-Ray → Traces
2. Filter by time range
3. Click on a trace to see the full request flow:
   - API Gateway → Lambda Authorizer → API Function → DynamoDB

### 8.4 View DynamoDB Table

1. Go to AWS Console → DynamoDB → Tables
2. Find `lambda-example-dev-items`
3. Click "Explore table items" to see stored data

---

## Step 9: Run Integration Tests (Optional)

### 9.1 Make the Test Script Executable

```bash
chmod +x scripts/integration_test.sh
```

### 9.2 Run All Integration Tests

```bash
./scripts/integration_test.sh "$API_URL" "$AUTH_TOKEN"
```

This will automatically test all endpoints and report results.

---

## Step 10: Local Development (Optional)

### 10.1 Set Local Environment Variable

```bash
export AUTH_TOKEN="$TOKEN"
```

### 10.2 Start Local API

```bash
sam build
sam local start-api
```

The API will start on `http://127.0.0.1:3000`

### 10.3 Test Locally

In a new terminal:

```bash
export LOCAL_URL="http://127.0.0.1:3000"
export AUTH_TOKEN="<your-token>"

curl -sS "$LOCAL_URL/health" | jq .
```

**Note:** DynamoDB calls will fail locally unless you configure local DynamoDB.

---

## Step 11: Update/Redeploy Changes

### 11.1 Make Code Changes

Edit files in `src/` as needed.

### 11.2 Rebuild and Deploy

```bash
sam build
sam deploy
```

(No `--guided` needed after the first deployment)

### 11.3 Verify Changes

Re-run your curl tests or integration tests.

---

## Step 12: Deploy to Production

### 12.1 Create Production Token in SSM

```bash
PROD_TOKEN=$(openssl rand -base64 32)
echo "Production token: $PROD_TOKEN"

aws ssm put-parameter \
  --name /lambda-example/prod/auth-token \
  --type SecureString \
  --value "$PROD_TOKEN" \
  --overwrite \
  --region $REGION
```

### 12.2 Deploy Production Stack

```bash
sam build
sam deploy \
  --stack-name lambda-example-prod \
  --parameter-overrides \
    StageName=prod \
    AuthTokenParamName=/lambda-example/prod/auth-token \
  --no-confirm-changeset
```

### 12.3 Get Production API URL

```bash
aws cloudformation describe-stacks \
  --stack-name lambda-example-prod \
  --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text
```

---

## Step 13: Cleanup (Delete Everything)

### 13.1 Delete CloudFormation Stack

**Dev environment:**
```bash
aws cloudformation delete-stack \
  --stack-name lambda-example-dev \
  --region $REGION
```

**Prod environment (if created):**
```bash
aws cloudformation delete-stack \
  --stack-name lambda-example-prod \
  --region $REGION
```

### 13.2 Wait for Deletion

```bash
aws cloudformation wait stack-delete-complete \
  --stack-name lambda-example-dev \
  --region $REGION
```

### 13.3 Delete SAM Managed Stack (Optional)

SAM CLI creates a managed stack for deployment artifacts. You can delete it too:

```bash
aws cloudformation delete-stack \
  --stack-name aws-sam-cli-managed-default \
  --region $REGION

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name aws-sam-cli-managed-default \
  --region $REGION
```

### 13.4 Delete SSM Parameters

```bash
aws ssm delete-parameter \
  --name /lambda-example/dev/auth-token \
  --region $REGION

# If you created prod:
aws ssm delete-parameter \
  --name /lambda-example/prod/auth-token \
  --region $REGION
```

### 13.5 Verify Cleanup

```bash
aws cloudformation list-stacks \
  --region $REGION \
  --query "StackSummaries[?StackName=='lambda-example-dev'].StackStatus"
```

Should show `DELETE_COMPLETE` or no results.

---

## Troubleshooting

### Issue: "Unable to locate credentials"

**Solution:**
```bash
aws configure
# Re-enter your credentials
```

### Issue: "Stack already exists"

**Solution:**
```bash
# Use a different stack name or delete the existing stack
sam deploy --stack-name lambda-example-dev-v2
```

### Issue: "Stack is in ROLLBACK_FAILED state" or "Stack is missing Tags/Outputs and not in a healthy state"

This happens when a previous deployment failed partway through.

**Solution:**
```bash
# Delete the failed stack
aws cloudformation delete-stack \
  --stack-name aws-sam-cli-managed-default \
  --region $REGION

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name aws-sam-cli-managed-default \
  --region $REGION

# Now retry deployment
sam deploy --guided
```

**If deletion fails (stack is stuck):**
```bash
# Check what resources are causing issues
aws cloudformation describe-stack-events \
  --stack-name aws-sam-cli-managed-default \
  --region $REGION \
  --query 'StackEvents[?ResourceStatus==`DELETE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table

# Force delete via AWS Console:
# 1. Go to CloudFormation console
# 2. Select the stuck stack
# 3. Click Delete
# 4. Check "Retain resources" for any stuck resources
```

**For your main application stack:**
```bash
# Delete your application stack
aws cloudformation delete-stack \
  --stack-name lambda-example-dev \
  --region $REGION

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name lambda-example-dev \
  --region $REGION
```

### Issue: 500 Internal Server Error on authenticated endpoints (POST /items)

**Symptoms:** `/health` works but authenticated endpoints return `{"message":"Internal Server Error"}`

**Cause:** API Gateway doesn't have permission to invoke the Lambda authorizer

**Solution:** Ensure your `template.yaml` includes the authorizer invoke permission:

```yaml
AuthorizerInvokePermission:
  Type: AWS::Lambda::Permission
  Properties:
    FunctionName: !Ref AuthorizerFunction
    Action: lambda:InvokeFunction
    Principal: apigateway.amazonaws.com
    SourceArn: !Sub arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${HttpApi}/*
```

**Verify the permission exists:**
```bash
# Get your authorizer function name
AUTH_FUNC=$(aws cloudformation describe-stack-resources \
  --stack-name lambda-example-dev \
  --region $REGION \
  --query 'StackResources[?LogicalResourceId==`AuthorizerFunction`].PhysicalResourceId' \
  --output text)

# Check if permission exists (should NOT return ResourceNotFoundException)
aws lambda get-policy --function-name $AUTH_FUNC --region $REGION
```

### Issue: "Decimal is not JSON serializable" error in logs

**Symptoms:** GET requests return 500 error, logs show `Object of type Decimal is not JSON serializable`

**Cause:** DynamoDB returns numbers as `Decimal` objects which aren't JSON serializable by default

**Solution:** Use a custom JSON encoder that converts Decimals. This is already included in the provided `src/app.py`:

```python
from decimal import Decimal

def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError

# Then in json.dumps():
json.dumps(data, default=_decimal_default)
```

### Issue: Authorizer not being invoked (no logs in authorizer function)

**Symptoms:** Requests fail but authorizer CloudWatch logs show no activity

**Causes & Solutions:**

1. **Missing invoke permission** - See "500 Internal Server Error" issue above
2. **Authorizer not attached to routes** - Verify routes have authorizer:
   ```bash
   API_ID="<your-api-id>"
   aws apigatewayv2 get-routes --api-id $API_ID --region $REGION \
     --query 'Items[].[RouteKey,AuthorizationType,AuthorizerId]' --output table
   ```
   Should show `CUSTOM` authorization type for protected routes

3. **Cached authorizer response** - API Gateway caches authorizer responses for 5 minutes by default

### Issue: 401 Unauthorized when calling API

**Solutions:**
1. Check token matches SSM parameter:
   ```bash
   aws ssm get-parameter --name /lambda-example/dev/auth-token --with-decryption --region $REGION
   ```
2. Ensure `Authorization: Bearer <token>` header is included (note: capital 'B' in Bearer)
3. Check authorizer Lambda logs for errors:
   ```bash
   # Get authorizer function name
   AUTH_FUNC=$(aws cloudformation describe-stack-resources \
     --stack-name lambda-example-dev --region $REGION \
     --query 'StackResources[?LogicalResourceId==`AuthorizerFunction`].PhysicalResourceId' \
     --output text)
   
   # View logs
   aws logs tail /aws/lambda/$AUTH_FUNC --region $REGION --since 5m
   ```
4. Verify the token value doesn't have extra whitespace or quotes

### Issue: 502 Bad Gateway

**Solutions:**
1. Check Lambda function logs:
   ```bash
   aws logs tail /aws/lambda/lambda-example-dev-ApiFunction
   ```
2. Verify Lambda has permission to access DynamoDB
3. Check for syntax errors in Lambda code

### Issue: Build fails with "Python command not found"

**Solution:**
```bash
# Install Python 3.9+
# Then verify:
python3 --version
```

### Issue: SAM deploy fails with IAM errors

**Solution:**
Ensure your IAM user has permissions for:
- CloudFormation
- Lambda
- API Gateway
- DynamoDB
- IAM role creation
- CloudWatch Logs

---

## Verify Everything Works

After successful deployment, run this complete test:

```bash
export API_URL="<your-api-url-from-outputs>"
export AUTH_TOKEN="<your-token>"

# 1. Test health endpoint (public)
curl -sS "$API_URL/health" | jq .
# Expected: {"ok":true}

# 2. Create an item (authenticated)
curl -sS -X POST "$API_URL/items" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-item"}' | jq .
# Expected: {"item":{"id":"...", "name":"test-item", "createdAtMs":...}}

# 3. Get the item (save the ID from step 2)
ITEM_ID="<id-from-previous-response>"
curl -sS "$API_URL/items/$ITEM_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq .
# Expected: {"item":{"id":"...", "name":"test-item", "createdAtMs":...}}

# 4. Delete the item
curl -sS -X DELETE "$API_URL/items/$ITEM_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" -i
# Expected: HTTP/2 204 (no body)

# 5. Verify deletion
curl -sS "$API_URL/items/$ITEM_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq .
# Expected: {"error":{"code":"NOT_FOUND","message":"Item not found"}}

# 6. Test unauthorized request
curl -sS -X POST "$API_URL/items" \
  -H "Content-Type: application/json" \
  -d '{"name":"test"}' -i
# Expected: HTTP/2 401 {"message":"Unauthorized"}
```

**All tests passing?** ✅ Your API is fully functional!

---

## Next Steps

1. **Add more endpoints** - Extend `src/app.py` with PUT/PATCH operations
2. **Add request validation** - Use JSON schema validation
3. **Set up CI/CD** - Automate deployment with GitHub Actions or AWS CodePipeline
4. **Add custom domain** - Use Route53 + ACM for a custom domain
5. **Add CORS** - Configure CORS if calling from a web frontend
6. **Monitor costs** - Set up billing alerts in AWS Console
7. **Set up CloudWatch alarms** - Alert on errors, throttles, or high latency

---

## Useful Commands Reference

```bash
# Build
sam build

# Deploy dev
sam deploy

# Deploy prod
sam deploy --stack-name lambda-example-prod --parameter-overrides StageName=prod

# View logs (live tail) - SAM auto-finds function names
sam logs --stack-name lambda-example-dev --tail

# Or view logs directly (get function names from CloudFormation first)
API_FUNC=$(aws cloudformation describe-stack-resources \
  --stack-name lambda-example-dev --region $REGION \
  --query 'StackResources[?LogicalResourceId==`ApiFunction`].PhysicalResourceId' \
  --output text)
aws logs tail /aws/lambda/$API_FUNC --region $REGION --follow

# Validate template
sam validate

# Delete stack (replace region as needed)
aws cloudformation delete-stack --stack-name lambda-example-dev --region $REGION

# Wait for stack deletion
aws cloudformation wait stack-delete-complete --stack-name lambda-example-dev --region $REGION

# Delete SAM managed resources
aws cloudformation delete-stack --stack-name aws-sam-cli-managed-default --region $REGION

# Get stack outputs
aws cloudformation describe-stacks --stack-name lambda-example-dev --region $REGION

# Check stack events (troubleshooting)
aws cloudformation describe-stack-events --stack-name lambda-example-dev --region $REGION

# List all stacks
aws cloudformation list-stacks --region $REGION

# Get API Gateway routes and their authorizers
API_ID=$(aws cloudformation describe-stack-resources \
  --stack-name lambda-example-dev --region $REGION \
  --query 'StackResources[?LogicalResourceId==`HttpApi`].PhysicalResourceId' \
  --output text)
aws apigatewayv2 get-routes --api-id $API_ID --region $REGION

# Invoke function locally
sam local invoke ApiFunction -e events/test-event.json

# Start local API
sam local start-api
```

---

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [API Gateway HTTP API](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/)
- [CloudWatch Logs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
- [AWS X-Ray](https://docs.aws.amazon.com/xray/)

---

**Questions or issues?** Check the main [README.md](README.md) or open an issue in the repository.

