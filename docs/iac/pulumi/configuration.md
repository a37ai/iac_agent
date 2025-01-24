---
tool: pulumi
category: iac
version: "3.0"
topics:
  - configuration
  - state
  - providers
---
# Pulumi Configuration

## Common Patterns

### Basic Stack Configuration
```typescript
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

const config = new pulumi.Config();
const instanceType = config.require("instanceType");

const instance = new aws.ec2.Instance("web-server", {
    instanceType: instanceType,
    ami: "ami-0c55b159cbfafe1f0"
});
```

## Common Issues and Solutions

### Error: Stack Reference Not Found
```error
error: Stack reference not found: organization/project/stack
```

Solution:
1. Check stack exists:
```bash
pulumi stack ls
```

2. Create stack if missing:
```bash
pulumi stack init dev
```

3. Configure organization:
```bash
pulumi org set-default myorg
```

### Error: Resource Already Exists
```error
error: creating urn:pulumi:dev::project::aws:s3/bucket:Bucket::my-bucket: 
       BucketAlreadyExists: The bucket already exists
```

Solution:
1. Import existing resource:
```bash
pulumi import aws:s3/bucket:Bucket my-bucket existing-bucket-name
```

2. Use custom name:
```typescript
const bucket = new aws.s3.Bucket("my-bucket", {
    bucket: "unique-bucket-name-123"
});
```

### Error: Provider Configuration
```error
error: no valid credentials found for provider 'aws'
```

Solution:
1. Configure provider:
```typescript
const provider = new aws.Provider("aws", {
    region: "us-west-2",
    profile: "dev"
});
```

2. Set environment variables:
```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
```
