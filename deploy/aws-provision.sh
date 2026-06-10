#!/bin/bash
set -euo pipefail

# ===========================================
# MediRide AWS Infrastructure Provisioning
# ===========================================
# Run this from your LOCAL machine with AWS CLI configured
#
# Prerequisites:
#   - AWS CLI v2 installed and configured (aws configure)
#   - An existing EC2 key pair (or we create one below)
#
# Usage: bash deploy/aws-provision.sh

# ==================== CONFIGURATION ====================
# Change these to match your setup

AWS_REGION="ca-central-1"
PROJECT="mediride"
KEY_PAIR_NAME="mediride-prod"
EC2_INSTANCE_TYPE="t3.xlarge"
RDS_INSTANCE_TYPE="db.t3.medium"
RDS_MASTER_USER="mediride"
RDS_MASTER_PASSWORD=""  # Will prompt if empty
RDS_STORAGE_GB=70
S3_BUCKET="mediride-documents"

# ==================== HELPERS ====================

log() { echo -e "\n\033[1;34m[$1]\033[0m $2"; }
ok()  { echo -e "  \033[1;32m✓\033[0m $1"; }
val() { echo -e "  \033[1;33m→\033[0m $1: \033[1m$2\033[0m"; }

# ==================== PRE-FLIGHT ====================

log "0/8" "Pre-flight checks..."

if ! command -v aws &>/dev/null; then
    echo "ERROR: AWS CLI not installed. Install it first: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
    echo "ERROR: AWS CLI not configured. Run 'aws configure' first."
    exit 1
}
ok "AWS account: $AWS_ACCOUNT_ID"
ok "Region: $AWS_REGION"

# Prompt for RDS password if not set
if [ -z "$RDS_MASTER_PASSWORD" ]; then
    echo ""
    read -sp "  Enter RDS master password (min 8 chars): " RDS_MASTER_PASSWORD
    echo ""
    if [ ${#RDS_MASTER_PASSWORD} -lt 8 ]; then
        echo "ERROR: Password must be at least 8 characters."
        exit 1
    fi
fi

# ==================== 1. VPC — use default ====================

log "1/8" "Getting default VPC..."

VPC_ID=$(aws ec2 describe-vpcs \
    --region "$AWS_REGION" \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text)

if [ "$VPC_ID" = "None" ]; then
    echo "ERROR: No default VPC found. Create one or update this script."
    exit 1
fi
ok "Default VPC: $VPC_ID"

# Get subnets
SUBNET_IDS=$(aws ec2 describe-subnets \
    --region "$AWS_REGION" \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[*].SubnetId" \
    --output text)

FIRST_SUBNET=$(echo "$SUBNET_IDS" | awk '{print $1}')
ok "Using subnet: $FIRST_SUBNET"

# ==================== 2. SECURITY GROUPS ====================

log "2/8" "Creating security groups..."

# --- EC2 security group ---
EC2_SG_ID=$(aws ec2 describe-security-groups \
    --region "$AWS_REGION" \
    --filters "Name=group-name,Values=${PROJECT}-ec2-sg" "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[0].GroupId" \
    --output text 2>/dev/null) || true

if [ "$EC2_SG_ID" = "None" ] || [ -z "$EC2_SG_ID" ]; then
    EC2_SG_ID=$(aws ec2 create-security-group \
        --region "$AWS_REGION" \
        --group-name "${PROJECT}-ec2-sg" \
        --description "MediRide production EC2" \
        --vpc-id "$VPC_ID" \
        --query "GroupId" \
        --output text)

    # SSH
    aws ec2 authorize-security-group-ingress \
        --region "$AWS_REGION" \
        --group-id "$EC2_SG_ID" \
        --protocol tcp --port 22 --cidr 0.0.0.0/0

    # HTTP
    aws ec2 authorize-security-group-ingress \
        --region "$AWS_REGION" \
        --group-id "$EC2_SG_ID" \
        --protocol tcp --port 80 --cidr 0.0.0.0/0

    # HTTPS
    aws ec2 authorize-security-group-ingress \
        --region "$AWS_REGION" \
        --group-id "$EC2_SG_ID" \
        --protocol tcp --port 443 --cidr 0.0.0.0/0

    ok "Created EC2 security group: $EC2_SG_ID"
else
    ok "EC2 security group already exists: $EC2_SG_ID"
fi

# --- RDS security group ---
RDS_SG_ID=$(aws ec2 describe-security-groups \
    --region "$AWS_REGION" \
    --filters "Name=group-name,Values=${PROJECT}-rds-sg" "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[0].GroupId" \
    --output text 2>/dev/null) || true

if [ "$RDS_SG_ID" = "None" ] || [ -z "$RDS_SG_ID" ]; then
    RDS_SG_ID=$(aws ec2 create-security-group \
        --region "$AWS_REGION" \
        --group-name "${PROJECT}-rds-sg" \
        --description "MediRide production RDS - EC2 access only" \
        --vpc-id "$VPC_ID" \
        --query "GroupId" \
        --output text)

    # Allow Postgres from EC2 SG only
    aws ec2 authorize-security-group-ingress \
        --region "$AWS_REGION" \
        --group-id "$RDS_SG_ID" \
        --protocol tcp --port 5432 \
        --source-group "$EC2_SG_ID"

    ok "Created RDS security group: $RDS_SG_ID (allows 5432 from EC2 SG)"
else
    ok "RDS security group already exists: $RDS_SG_ID"
fi

# ==================== 3. KEY PAIR ====================

log "3/8" "Setting up key pair..."

KEY_EXISTS=$(aws ec2 describe-key-pairs \
    --region "$AWS_REGION" \
    --key-names "$KEY_PAIR_NAME" \
    --query "KeyPairs[0].KeyName" \
    --output text 2>/dev/null) || true

if [ "$KEY_EXISTS" = "None" ] || [ -z "$KEY_EXISTS" ]; then
    aws ec2 create-key-pair \
        --region "$AWS_REGION" \
        --key-name "$KEY_PAIR_NAME" \
        --query "KeyMaterial" \
        --output text > "${KEY_PAIR_NAME}.pem"
    chmod 400 "${KEY_PAIR_NAME}.pem"
    ok "Created key pair: ${KEY_PAIR_NAME}.pem (SAVE THIS FILE — you cannot download it again)"
else
    ok "Key pair already exists: $KEY_PAIR_NAME"
fi

# ==================== 4. EC2 INSTANCE ====================

log "4/8" "Launching EC2 instance..."

# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
    --region "$AWS_REGION" \
    --owners amazon \
    --filters \
        "Name=name,Values=al2023-ami-2023*-x86_64" \
        "Name=state,Values=available" \
    --query "Images | sort_by(@, &CreationDate) | [-1].ImageId" \
    --output text)
ok "AMI: $AMI_ID (Amazon Linux 2023)"

# Check if instance already exists
EXISTING_INSTANCE=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters \
        "Name=tag:Name,Values=${PROJECT}-prod" \
        "Name=instance-state-name,Values=running,stopped" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text 2>/dev/null) || true

if [ "$EXISTING_INSTANCE" = "None" ] || [ -z "$EXISTING_INSTANCE" ]; then
    INSTANCE_ID=$(aws ec2 run-instances \
        --region "$AWS_REGION" \
        --image-id "$AMI_ID" \
        --instance-type "$EC2_INSTANCE_TYPE" \
        --key-name "$KEY_PAIR_NAME" \
        --security-group-ids "$EC2_SG_ID" \
        --subnet-id "$FIRST_SUBNET" \
        --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3","Encrypted":true}}]' \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${PROJECT}-prod}]" \
        --query "Instances[0].InstanceId" \
        --output text)

    ok "Launched instance: $INSTANCE_ID"

    echo "  Waiting for instance to be running..."
    aws ec2 wait instance-running \
        --region "$AWS_REGION" \
        --instance-ids "$INSTANCE_ID"
    ok "Instance is running"
else
    INSTANCE_ID="$EXISTING_INSTANCE"
    ok "Instance already exists: $INSTANCE_ID"
fi

# ==================== 5. ELASTIC IP ====================

log "5/8" "Allocating Elastic IP..."

# Check if instance already has an EIP
EXISTING_EIP=$(aws ec2 describe-addresses \
    --region "$AWS_REGION" \
    --filters "Name=instance-id,Values=$INSTANCE_ID" \
    --query "Addresses[0].PublicIp" \
    --output text 2>/dev/null) || true

if [ "$EXISTING_EIP" = "None" ] || [ -z "$EXISTING_EIP" ]; then
    ALLOCATION_ID=$(aws ec2 allocate-address \
        --region "$AWS_REGION" \
        --domain vpc \
        --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=${PROJECT}-prod}]" \
        --query "AllocationId" \
        --output text)

    aws ec2 associate-address \
        --region "$AWS_REGION" \
        --instance-id "$INSTANCE_ID" \
        --allocation-id "$ALLOCATION_ID"

    ELASTIC_IP=$(aws ec2 describe-addresses \
        --region "$AWS_REGION" \
        --allocation-ids "$ALLOCATION_ID" \
        --query "Addresses[0].PublicIp" \
        --output text)

    ok "Elastic IP: $ELASTIC_IP → attached to $INSTANCE_ID"
else
    ELASTIC_IP="$EXISTING_EIP"
    ok "Elastic IP already attached: $ELASTIC_IP"
fi

# ==================== 6. RDS SUBNET GROUP ====================

log "6/8" "Creating RDS subnet group & instance..."

# Create DB subnet group
SUBNET_GROUP_EXISTS=$(aws rds describe-db-subnet-groups \
    --region "$AWS_REGION" \
    --db-subnet-group-name "${PROJECT}-db-subnet" \
    --query "DBSubnetGroups[0].DBSubnetGroupName" \
    --output text 2>/dev/null) || true

if [ "$SUBNET_GROUP_EXISTS" = "None" ] || [ -z "$SUBNET_GROUP_EXISTS" ]; then
    # Get all subnet IDs as a proper list
    SUBNET_LIST=$(aws ec2 describe-subnets \
        --region "$AWS_REGION" \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "Subnets[*].SubnetId" \
        --output json)

    aws rds create-db-subnet-group \
        --region "$AWS_REGION" \
        --db-subnet-group-name "${PROJECT}-db-subnet" \
        --db-subnet-group-description "MediRide production RDS subnets" \
        --subnet-ids "$SUBNET_LIST"

    ok "Created DB subnet group: ${PROJECT}-db-subnet"
else
    ok "DB subnet group already exists"
fi

# ==================== 7. RDS INSTANCE ====================

log "7/8" "Creating RDS PostgreSQL instance..."

RDS_EXISTS=$(aws rds describe-db-instances \
    --region "$AWS_REGION" \
    --db-instance-identifier "${PROJECT}-prod" \
    --query "DBInstances[0].DBInstanceIdentifier" \
    --output text 2>/dev/null) || true

if [ "$RDS_EXISTS" = "None" ] || [ -z "$RDS_EXISTS" ]; then
    aws rds create-db-instance \
        --region "$AWS_REGION" \
        --db-instance-identifier "${PROJECT}-prod" \
        --db-instance-class "$RDS_INSTANCE_TYPE" \
        --engine postgres \
        --engine-version "16" \
        --master-username "$RDS_MASTER_USER" \
        --master-user-password "$RDS_MASTER_PASSWORD" \
        --allocated-storage "$RDS_STORAGE_GB" \
        --max-allocated-storage 100 \
        --storage-type gp3 \
        --storage-encrypted \
        --db-name "mediride_auth" \
        --vpc-security-group-ids "$RDS_SG_ID" \
        --db-subnet-group-name "${PROJECT}-db-subnet" \
        --no-publicly-accessible \
        --backup-retention-period 7 \
        --preferred-backup-window "04:00-05:00" \
        --preferred-maintenance-window "sun:06:00-sun:07:00" \
        --no-multi-az \
        --auto-minor-version-upgrade \
        --tags "Key=Name,Value=${PROJECT}-prod"

    ok "RDS instance creating: ${PROJECT}-prod"
    echo "  Waiting for RDS to be available (this can take 5-10 minutes)..."
    aws rds wait db-instance-available \
        --region "$AWS_REGION" \
        --db-instance-identifier "${PROJECT}-prod"
    ok "RDS is available"
else
    ok "RDS instance already exists: ${PROJECT}-prod"
fi

# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --region "$AWS_REGION" \
    --db-instance-identifier "${PROJECT}-prod" \
    --query "DBInstances[0].Endpoint.Address" \
    --output text)
ok "RDS endpoint: $RDS_ENDPOINT"

# ==================== 8. S3 BUCKET + IAM ====================

log "8/8" "Creating S3 bucket and IAM user..."

# Create bucket
if aws s3api head-bucket --bucket "$S3_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
    ok "S3 bucket already exists: $S3_BUCKET"
else
    aws s3api create-bucket \
        --bucket "$S3_BUCKET" \
        --region "$AWS_REGION" \
        --create-bucket-configuration LocationConstraint="$AWS_REGION"

    # Block all public access
    aws s3api put-public-access-block \
        --bucket "$S3_BUCKET" \
        --public-access-block-configuration \
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "$S3_BUCKET" \
        --versioning-configuration Status=Enabled

    ok "Created S3 bucket: $S3_BUCKET (private, versioned)"
fi

# Create IAM user for S3 access
IAM_USER="${PROJECT}-s3-user"
IAM_USER_EXISTS=$(aws iam get-user --user-name "$IAM_USER" --query "User.UserName" --output text 2>/dev/null) || true

if [ "$IAM_USER_EXISTS" = "None" ] || [ -z "$IAM_USER_EXISTS" ]; then
    aws iam create-user --user-name "$IAM_USER"

    # Attach inline policy
    aws iam put-user-policy \
        --user-name "$IAM_USER" \
        --policy-name "${PROJECT}-s3-access" \
        --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {
      \"Effect\": \"Allow\",
      \"Action\": [
        \"s3:PutObject\",
        \"s3:GetObject\",
        \"s3:DeleteObject\",
        \"s3:ListBucket\"
      ],
      \"Resource\": [
        \"arn:aws:s3:::${S3_BUCKET}\",
        \"arn:aws:s3:::${S3_BUCKET}/*\"
      ]
    }
  ]
}"

    # Create access key
    ACCESS_KEY_OUTPUT=$(aws iam create-access-key --user-name "$IAM_USER" --output json)
    S3_ACCESS_KEY=$(echo "$ACCESS_KEY_OUTPUT" | grep -o '"AccessKeyId": *"[^"]*"' | cut -d'"' -f4)
    S3_SECRET_KEY=$(echo "$ACCESS_KEY_OUTPUT" | grep -o '"SecretAccessKey": *"[^"]*"' | cut -d'"' -f4)

    ok "Created IAM user: $IAM_USER"
else
    ok "IAM user already exists: $IAM_USER"
    S3_ACCESS_KEY="(already created — check your records)"
    S3_SECRET_KEY="(already created — check your records)"
fi

# ==================== SUMMARY ====================

echo ""
echo "=========================================="
echo "  AWS Infrastructure Ready!"
echo "=========================================="
echo ""
echo "  Resources created:"
val "EC2 Instance" "$INSTANCE_ID ($EC2_INSTANCE_TYPE)"
val "Elastic IP" "$ELASTIC_IP"
val "EC2 Security Group" "$EC2_SG_ID (ports 22, 80, 443)"
val "RDS Instance" "${PROJECT}-prod ($RDS_INSTANCE_TYPE)"
val "RDS Endpoint" "$RDS_ENDPOINT"
val "RDS Security Group" "$RDS_SG_ID (port 5432 from EC2 only)"
val "S3 Bucket" "$S3_BUCKET"
val "IAM User" "$IAM_USER"
echo ""
echo "  ==================== .env VALUES ===================="
echo ""
echo "  RDS_HOST=$RDS_ENDPOINT"
echo "  RDS_PORT=5432"
echo "  RDS_USERNAME=$RDS_MASTER_USER"
echo "  RDS_PASSWORD=(the password you entered)"
echo "  AWS_REGION=$AWS_REGION"
echo "  AWS_ACCESS_KEY_ID=$S3_ACCESS_KEY"
echo "  AWS_SECRET_ACCESS_KEY=$S3_SECRET_KEY"
echo "  S3_BUCKET_DOCUMENTS=$S3_BUCKET"
echo ""
echo "  ==================== NEXT STEPS ===================="
echo ""
echo "  1. Point DNS: prod-api.getmedigo.com → $ELASTIC_IP"
echo ""
echo "  2. SSH into EC2:"
echo "     ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$ELASTIC_IP"
echo ""
echo "  3. Run server setup:"
echo "     sudo bash deploy/setup-server-prod.sh"
echo ""
echo "  4. Init RDS databases (from EC2):"
echo "     sudo dnf install -y postgresql16"
echo "     psql -h $RDS_ENDPOINT -U $RDS_MASTER_USER -d mediride_auth"
echo "     (then run the SQL from deploy/init-databases-rds.sql)"
echo ""
echo "  5. Deploy:"
echo "     cp deploy/env.prod.example .env"
echo "     nano .env  # paste the values above"
echo "     docker compose -f deploy/docker-compose.prod.yml up -d"
echo "     bash deploy/run-migrations-prod.sh"
echo ""
