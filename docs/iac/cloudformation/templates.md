---
tool: cloudformation
category: iac
version: "2023-01-01"
topics:
  - templates
  - stacks
  - aws
---
# AWS CloudFormation Templates

## Common Patterns

### Basic Template Structure
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Basic EC2 Instance
Parameters:
  InstanceType:
    Type: String
    Default: t2.micro
Resources:
  MyEC2Instance:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: !Ref InstanceType
      ImageId: ami-0c55b159cbfafe1f0
```

## Common Issues and Solutions

### Error: No updates to perform
```error
No updates are to be performed
```

Solution:
1. Check template changes:
```bash
aws cloudformation detect-stack-drift \
  --stack-name my-stack
```

2. Force update:
```bash
aws cloudformation update-stack \
  --stack-name my-stack \
  --template-body file://template.yaml \
  --use-previous-template
```

### Error: Resource Creation Failed
```error
CREATE_FAILED: Resource creation cancelled
```

Solution:
1. Check resource dependencies:
```yaml
DependsOn:
  - ResourceName
```

2. Verify IAM permissions:
```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME \
  --action-names cloudformation:CreateStack
```

### Error: Stack Rollback
```error
UPDATE_ROLLBACK_IN_PROGRESS
```

Solution:
1. Check rollback triggers:
```bash
aws cloudformation describe-stack-events \
  --stack-name my-stack
```

2. Continue rollback:
```bash
aws cloudformation continue-update-rollback \
  --stack-name my-stack
```
