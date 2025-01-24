---
tool: terraform
category: iac
version: 1.0.0
topics:
  - state management
  - backends
  - s3
---
# Terraform S3 Backend Configuration

## Common Issues and Solutions

### Error: Failed to load state
When you encounter the error "Failed to load state: RequestError: send request failed", it usually indicates one of these issues:

1. AWS credentials are not properly configured
2. S3 bucket permissions are incorrect
3. Network connectivity issues

To resolve this:

```error
Error: Failed to load state: RequestError: send request failed
caused by: Get "https://my-bucket.s3.amazonaws.com/": dial tcp: lookup my-bucket.s3.amazonaws.com: no such host
```

Fix:
1. Verify AWS credentials:
```bash
aws configure list
aws sts get-caller-identity
```

2. Check S3 bucket permissions:
```hcl
terraform {
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "state/terraform.tfstate"
    region = "us-west-2"
  }
}
```

3. Ensure proper network connectivity to AWS S3.
