#!/bin/bash
# Setup AWS Billing Alerts Script
# This script sets up CloudWatch billing alarms

set -e

echo "=== LifeStream AWS Billing Alerts Setup ==="
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI is not configured."
    echo "Run: ./scripts/setup_aws_credentials.sh"
    exit 1
fi

echo "✅ AWS CLI is configured"
echo ""

# Get email from user
read -p "Enter email for billing alerts: " email
if [[ -z "$email" ]]; then
    echo "❌ Email is required"
    exit 1
fi

# Get threshold
read -p "Enter billing alert threshold in USD (default: 50): " threshold
threshold=${threshold:-50}

echo ""
echo "Setting up billing alerts..."
echo "  Email: $email"
echo "  Threshold: \$$threshold USD"
echo ""

# Create SNS topic
TOPIC_NAME="lifestream-billing-alerts"
TOPIC_ARN=$(aws sns create-topic --name "$TOPIC_NAME" --query 'TopicArn' --output text 2>/dev/null || \
            aws sns list-topics --query "Topics[?contains(TopicArn, '$TOPIC_NAME')].TopicArn" --output text | head -1)

if [[ -z "$TOPIC_ARN" ]]; then
    echo "❌ Failed to create SNS topic"
    exit 1
fi

echo "✅ Created SNS topic: $TOPIC_ARN"

# Subscribe email
echo "Subscribing email to topic..."
aws sns subscribe \
    --topic-arn "$TOPIC_ARN" \
    --protocol email \
    --notification-endpoint "$email" \
    --output text > /dev/null

echo "✅ Email subscription created"
echo ""
echo "⚠️  IMPORTANT: Check your email ($email) and confirm the subscription!"
echo "   The billing alarm will not work until you confirm."
echo ""

# Create CloudWatch alarm
ALARM_NAME="lifestream-billing-alert"
echo "Creating CloudWatch billing alarm..."

aws cloudwatch put-metric-alarm \
    --alarm-name "$ALARM_NAME" \
    --alarm-description "Alert when estimated charges exceed \$$threshold USD" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 86400 \
    --evaluation-periods 1 \
    --threshold "$threshold" \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=Currency,Value=USD \
    --alarm-actions "$TOPIC_ARN" \
    --output text > /dev/null

echo "✅ Billing alarm created: $ALARM_NAME"
echo ""
echo "Summary:"
echo "  SNS Topic: $TOPIC_ARN"
echo "  Alarm: $ALARM_NAME"
echo "  Threshold: \$$threshold USD"
echo "  Email: $email"
echo ""
echo "✅ Billing alerts setup complete!"
echo "   Remember to confirm the email subscription!"
