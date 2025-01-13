# DevOps Agent Test Configuration

This directory contains test configuration files for the DevOps Agent Packer build.

## Files

- `agent-config.json` - Main configuration file with test credentials
- `ansible-inventory.ini` - Sample Ansible inventory file
- `kubeconfig.yaml` - Sample Kubernetes configuration
- `ansible-ssh-key` - Sample SSH private key for Ansible

## Test Setup

The configuration enables several key services for testing:

1. Cloud Providers:
   - AWS (with example credentials)

2. Version Control:
   - GitHub (with example PAT)

3. Container & Orchestration:
   - Docker
   - Kubernetes
   - Terraform
   - Helm

4. Configuration Management:
   - Ansible

5. CI/CD & Monitoring:
   - Jenkins
   - Datadog
   - HashiCorp Vault

6. Notifications:
   - Slack
   - Email

## Important Notes

1. All credentials in these files are dummy values for testing
2. Do not use these credentials in production
3. The Packer build will install tools for enabled services
4. Credentials will be stored in `C:/Agent/<service>` directories

## Testing

1. Run the Packer build:
   ```bash
   packer build windows-devops-base.pkr.hcl
   ```

2. The build will:
   - Install required tools
   - Create credential files
   - Configure the environment

3. Verify the installation by checking:
   - Installed tools in PATH
   - Credential files in C:/Agent/
   - Service configurations 