packer {
  required_plugins {
    amazon = {
      version = ">= 1.3.4"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

source "amazon-ebs" "linux" {
  region        = var.aws_region
  source_ami    = var.source_ami
  instance_type = var.instance_type
  ami_name      = "${var.ami_name_prefix}-${formatdate("YYYYMMDD-hhmmss", timestamp())}"

  communicator = "ssh"
  ssh_username = var.ssh_username

  tags = {
    Name        = "${var.ami_name_prefix}-base"
    Environment = var.environment_tag
  }
}

build {
  sources = ["source.amazon-ebs.linux"]

  provisioner "file" {
    source      = "./agent-config.json"
    destination = "/tmp/agent-config.json"
  }

  provisioner "file" {
    source      = "install_kubectl.sh"
    destination = "/tmp/install_kubectl.sh"
  }

  provisioner "shell" {
    inline = [
      # Make it executable
      "chmod +x /tmp/install_kubectl.sh",
      # Run it
      "/tmp/install_kubectl.sh"
    ]
  }

  provisioner "shell" {
    inline = [
      "echo '=== Beginning Linux Provision Script ==='",

      # ---------------------------------------------------------
      # 0. Basic Packages & jq (to parse JSON)
      # ---------------------------------------------------------
      "sudo yum update -y",
      "sudo yum install -y jq unzip curl git",

      # Read JSON
      "if [ ! -f /tmp/agent-config.json ]; then",
      "  echo 'ERROR: /tmp/agent-config.json not found.'; exit 1",
      "fi",

      "sudo mkdir -p /opt/agent",
      "sudo chmod 777 /opt/agent",

      # -----------------------------------------------------------------
      # 1. AWS CLI (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .aws.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Installing AWS CLI version ${var.aws_cli_version} ---'",
      "  cd /tmp",
      "  curl -sSL 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o awscliv2.zip",
      "  unzip -o awscliv2.zip",
      "  sudo ./aws/install --update",
      "  rm -f awscliv2.zip",
      "  rm -rf aws",
      "",
      "  echo 'Writing AWS credentials to /opt/agent/aws...'",
      "  mkdir -p /opt/agent/aws",
      #   "  AWS_ACCESS_KEY=\"$(jq -r .aws.access_key_id /tmp/agent-config.json)\"",
      #   "  AWS_SECRET_KEY=\"$(jq -r .aws.secret_access_key /tmp/agent-config.json)\"",
      #   "  AWS_SESSION_TOKEN=\"$(jq -r .aws.session_token /tmp/agent-config.json)\"",
      #   "  cat <<EOF >/opt/agent/aws/credentials",
      #   "[default]",
      #   "aws_access_key_id = $AWS_ACCESS_KEY",
      #   "aws_secret_access_key = $AWS_SECRET_KEY",
      #   "EOF",
      #   "  if [ \"$AWS_SESSION_TOKEN\" != \"\" ] && [ \"$AWS_SESSION_TOKEN\" != \"null\" ]; then",
      #   "    echo \"aws_session_token = $AWS_SESSION_TOKEN\" >> /opt/agent/aws/credentials",
      #   "  fi",
      #   "  AWS_REGION=\"$(jq -r .aws.region /tmp/agent-config.json)\"",
      #   "  echo \"[default]\" >/opt/agent/aws/config",
      #   "  echo \"region = $AWS_REGION\" >>/opt/agent/aws/config",
      "fi",

      # -----------------------------------------------------------------
      # 2. GCP CLI (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .gcp.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Installing gcloud CLI (latest) ---'",
      "  cd /tmp",
      "  curl -sSL https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-441.0.0-linux-x86_64.tar.gz -o gcloud.tgz",
      "  tar xzf gcloud.tgz",
      "  sudo ./google-cloud-sdk/install.sh -q",
      "  sudo ln -s /tmp/google-cloud-sdk/bin/gcloud /usr/local/bin/gcloud || true",
      "  rm -f gcloud.tgz",
      "",
      "  echo 'Writing GCP service_account.json to /opt/agent/gcp...'",
      "  mkdir -p /opt/agent/gcp",
      #   "  jq -r .gcp.service_account_json /tmp/agent-config.json >/opt/agent/gcp/service_account.json",
      "fi",

      # -----------------------------------------------------------------
      # 4. GitHub / GitLab
      # -----------------------------------------------------------------
      "GH_ENABLED=$(jq -r .gitHub.enabled /tmp/agent-config.json)",
      "GL_ENABLED=$(jq -r .gitLab.enabled /tmp/agent-config.json)",
      "if [ \"$GH_ENABLED\" = \"true\" ] || [ \"$GL_ENABLED\" = \"true\" ]; then",
      "  echo '--- Git is already installed above, storing credentials... ---'",
      "fi",
      "if [ \"$GH_ENABLED\" = \"true\" ]; then",
      "  echo 'Storing GitHub creds in /opt/agent/github'",
      "  mkdir -p /opt/agent/github",
      #   "  GH_TOKEN=$(jq -r .gitHub.token /tmp/agent-config.json)",
      #   "  GH_USE_SSH=$(jq -r .gitHub.use_ssh /tmp/agent-config.json)",
      #   "  if [ \"$GH_USE_SSH\" = \"true\" ]; then",
      #   "    echo 'Would store SSH private key here... (not in JSON example)'",
      #   "  else",
      #   "    echo \"$GH_TOKEN\" >/opt/agent/github/github_pat.txt",
      #   "  fi",
      "fi",
      "if [ \"$GL_ENABLED\" = \"true\" ]; then",
      "  echo 'Storing GitLab creds in /opt/agent/gitlab'",
      "  mkdir -p /opt/agent/gitlab",
      #   "  GL_TOKEN=$(jq -r .gitLab.token /tmp/agent-config.json)",
      #   "  GL_USE_SSH=$(jq -r .gitLab.use_ssh /tmp/agent-config.json)",
      #   "  if [ \"$GL_USE_SSH\" = \"true\" ]; then",
      #   "    echo 'Would store SSH private key for GitLab here...'",
      #   "  else",
      #   "    echo \"$GL_TOKEN\" >/opt/agent/gitlab/gitlab_pat.txt",
      #   "  fi",
      "fi",

      # -----------------------------------------------------------------
      # 5. Docker (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .docker.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Installing Docker on Amazon Linux ---'",
      "  sudo yum install -y docker",
      "  sudo service docker start",
      "  sudo usermod -aG docker ec2-user || true",
      "",
      "  echo 'Storing Docker credentials if provided...'",
      "  mkdir -p /opt/agent/docker",
      #   "  DOCKER_USER=$(jq -r .docker.username /tmp/agent-config.json)",
      #   "  DOCKER_PASS=$(jq -r .docker.password /tmp/agent-config.json)",
      #   "  echo \"username=$DOCKER_USER\" >>/opt/agent/docker/docker_credentials.txt",
      #   "  echo \"password=$DOCKER_PASS\" >>/opt/agent/docker/docker_credentials.txt",
      "fi",

      # -----------------------------------------------------------------
      # 6. Kubernetes (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .kubernetes.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  chmod +x /tmp/install_kubectl.sh",
      "  /tmp/install_kubectl.sh",
      "fi",

      # -----------------------------------------------------------------
      # 7. Terraform (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .terraform.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo \"--- Installing Terraform version ${var.terraform_version} ---\"",
      "  cd /tmp",
      "  curl -sSL \"https://releases.hashicorp.com/terraform/${var.terraform_version}/terraform_${var.terraform_version}_linux_amd64.zip\" -o terraform.zip",
      "  unzip terraform.zip",
      "  sudo mv terraform /usr/local/bin/",
      "  rm -f terraform.zip",
      "fi",

      # -----------------------------------------------------------------
      # 8. Helm (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .helm.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo \"--- Installing Helm version ${var.helm_version} ---\"",
      "  cd /tmp",
      "  curl -sSL \"https://get.helm.sh/helm-${var.helm_version}-linux-amd64.tar.gz\" -o helm.tgz",
      "  tar xzf helm.tgz",
      "  sudo mv linux-amd64/helm /usr/local/bin/helm",
      "  rm -rf linux-amd64 helm.tgz",
      "fi",

      # -----------------------------------------------------------------
      # 9. Puppet (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .puppet.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo \"--- Installing Puppet Agent version ${var.puppet_agent_version} ---\"",
      "  sudo rpm -Uvh https://yum.puppet.com/puppet7-release-el-7.noarch.rpm",
      "  sudo yum install -y puppet-agent",
      "fi",

      # 9b. Ansible
      "if [ \"$(jq -r .ansible.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Installing Ansible (requires Python) ---'",
      "  sudo yum install -y python3 python3-pip",
      "  sudo pip3 install ansible",
      "",
      "  echo 'Storing Ansible inventory / SSH key if provided...'",
      "  mkdir -p /opt/agent/ansible",
      #   "  INV_FILE=$(jq -r .ansible.inventory_file /tmp/agent-config.json)",
      #   "  if [ \"$INV_FILE\" != \"null\" ]; then",
      #   "    echo \"$INV_FILE\" >/opt/agent/ansible/inventory.ini",
      #   "  fi",
      #   "  ANS_KEY=$(jq -r .ansible.ssh_private_key /tmp/agent-config.json)",
      #   "  if [ \"$ANS_KEY\" != \"null\" ]; then",
      #   "    echo \"$ANS_KEY\" >/opt/agent/ansible/id_rsa",
      #   "    chmod 600 /opt/agent/ansible/id_rsa",
      #   "  fi",
      "fi",

      # -----------------------------------------------------------------
      # 10. Jenkins (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .jenkins.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  sudo yum -y update",
      "  sudo yum -y install java-17-amazon-corretto-headless",
      "  sudo rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key || { echo 'GPG key import failed'; exit 1; }",
      "  sudo wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo || { echo 'Failed to add Jenkins repo'; exit 1; }",
      "  sudo yum -y install jenkins || { echo 'Jenkins installation failed'; exit 1; }",
      "  sudo systemctl daemon-reload",
      "  sudo systemctl enable jenkins || { echo 'Failed to enable Jenkins service'; exit 1; }",
      "  sudo systemctl start jenkins || {",
      "    echo 'Failed to start Jenkins service';",
      "    sudo systemctl status jenkins;",
      "    sudo journalctl -xe;",
      "    exit 1;",
      "  }",
      "fi",

      # -----------------------------------------------------------------
      # 11. Datadog (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .datadog.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Installing Datadog (Python-based CLI) ---'",
      "  sudo yum install -y python3 python3-pip",
      "  pip3 install datadog",
      "",
      "  echo 'Storing Datadog API/App keys...'",
      "  mkdir -p /opt/agent/datadog",
      "fi",

      # -----------------------------------------------------------------
      # 12. Splunk (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .splunk.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Splunk: storing credentials or optionally installing forwarder ---'",
      "  mkdir -p /opt/agent/splunk",
      "fi",

      # -----------------------------------------------------------------
      # 13. Elasticsearch / Kibana (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .elasticsearchKibana.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Storing Elasticsearch/Kibana credentials ---'",
      "  mkdir -p /opt/agent/elasticsearch",
      "fi",

      # -----------------------------------------------------------------
      # 14. Grafana (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .grafana.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Installing Grafana & storing credentials ---'",
      "  cd /tmp",
      "  GRAFANA_URL='https://dl.grafana.com/enterprise/release/grafana-enterprise-9.5.2-1.x86_64.rpm'",
      "  curl -sSL \"$GRAFANA_URL\" -o grafana.rpm",
      "  sudo yum install -y grafana.rpm",
      "  rm -f grafana.rpm",
      "",
      "  mkdir -p /opt/agent/grafana",
      "fi",

      # -----------------------------------------------------------------
      # 15. Prometheus (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .prometheus.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo \"--- Installing promtool & storing credentials ---\"",
      "  cd /tmp",
      "  curl -sSL \"https://github.com/prometheus/prometheus/releases/download/v${var.prometheus_version}/prometheus-${var.prometheus_version}.linux-amd64.tar.gz\" -o prometheus.tgz",
      "  tar xzf prometheus.tgz",
      "  sudo mv prometheus-${var.prometheus_version}.linux-amd64/promtool /usr/local/bin/",
      "  rm -rf prometheus-${var.prometheus_version}.linux-amd64 prometheus.tgz",
      "",
      "  mkdir -p /opt/agent/prometheus",
      #   "  PROM_ENDPOINT=$(jq -r .prometheus.endpoint /tmp/agent-config.json)",
      #   "  PROM_USER=$(jq -r .prometheus.username /tmp/agent-config.json)",
      #   "  PROM_PASS=$(jq -r .prometheus.password /tmp/agent-config.json)",
      #   "  PROM_TOKEN=$(jq -r .prometheus.token /tmp/agent-config.json)",
      #   "  cat <<EOF >/opt/agent/prometheus/prometheus_credentials.txt",
      #   "endpoint=$PROM_ENDPOINT",
      #   "username=$PROM_USER",
      #   "password=$PROM_PASS",
      #   "token=$PROM_TOKEN",
      #   "EOF",
      "fi",

      # -----------------------------------------------------------------
      # 16. Vault (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .vault.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo \"--- Installing Vault version ${var.vault_version} & storing token ---\"",
      "  cd /tmp",
      "  curl -sSL \"https://releases.hashicorp.com/vault/${var.vault_version}/vault_${var.vault_version}_linux_amd64.zip\" -o vault.zip",
      "  unzip vault.zip",
      "  sudo mv vault /usr/local/bin/",
      "  rm -f vault.zip",
      "",
      "  mkdir -p /opt/agent/vault",
      #   "  VAULT_ADDR=$(jq -r .vault.address /tmp/agent-config.json)",
      #   "  VAULT_TOKEN=$(jq -r .vault.token /tmp/agent-config.json)",
      #   "  cat <<EOF >/opt/agent/vault/vault_credentials.txt",
      #   "VAULT_ADDR=$VAULT_ADDR",
      #   "VAULT_TOKEN=$VAULT_TOKEN",
      #   "EOF",
      "fi",

      # -----------------------------------------------------------------
      # 17. Artifactory / Nexus (If enabled)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .artifactory.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Storing Artifactory credentials ---'",
      "  mkdir -p /opt/agent/artifactory",
      "  ARTI_URL=$(jq -r .artifactory.url /tmp/agent-config.json)",
      "  ARTI_USER=$(jq -r .artifactory.username /tmp/agent-config.json)",
      "  ARTI_PASS=$(jq -r .artifactory.password /tmp/agent-config.json)",
      "  ARTI_TOKEN=$(jq -r .artifactory.api_token /tmp/agent-config.json)",
      "  cat <<EOF >/opt/agent/artifactory/artifactory_creds.txt",
      "url=$ARTI_URL",
      "username=$ARTI_USER",
      "password=$ARTI_PASS",
      "api_token=$ARTI_TOKEN",
      "EOF",
      "fi",
      "if [ \"$(jq -r .nexus.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Storing Nexus credentials ---'",
      "  mkdir -p /opt/agent/nexus",
      "  NX_URL=$(jq -r .nexus.url /tmp/agent-config.json)",
      "  NX_USER=$(jq -r .nexus.username /tmp/agent-config.json)",
      "  NX_PASS=$(jq -r .nexus.password /tmp/agent-config.json)",
      "  NX_TOKEN=$(jq -r .nexus.api_token /tmp/agent-config.json)",
      "  cat <<EOF >/opt/agent/nexus/nexus_creds.txt",
      "url=$NX_URL",
      "username=$NX_USER",
      "password=$NX_PASS",
      "api_token=$NX_TOKEN",
      "EOF",
      "fi",

      # -----------------------------------------------------------------
      # 18. Notifications (Slack, Teams, Email)
      # -----------------------------------------------------------------
      "if [ \"$(jq -r .notifications.slack.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Storing Slack Webhook ---'",
      "  mkdir -p /opt/agent/notifications",
      "  SLACK_WEBHOOK=$(jq -r .notifications.slack.webhook_url /tmp/agent-config.json)",
      "  echo \"$SLACK_WEBHOOK\" >/opt/agent/notifications/slack_webhook.txt",
      "fi",
      "if [ \"$(jq -r .notifications.teams.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Storing Teams Webhook ---'",
      "  mkdir -p /opt/agent/notifications",
      "  TEAMS_WEBHOOK=$(jq -r .notifications.teams.webhook_url /tmp/agent-config.json)",
      "  echo \"$TEAMS_WEBHOOK\" >/opt/agent/notifications/teams_webhook.txt",
      "fi",
      "if [ \"$(jq -r .notifications.email.enabled /tmp/agent-config.json)\" = \"true\" ]; then",
      "  echo '--- Storing Email SMTP credentials ---'",
      "  mkdir -p /opt/agent/notifications",
      "  SMTP_SERVER=$(jq -r .notifications.email.smtp_server /tmp/agent-config.json)",
      "  SMTP_PORT=$(jq -r .notifications.email.smtp_port /tmp/agent-config.json)",
      "  SMTP_USER=$(jq -r .notifications.email.smtp_username /tmp/agent-config.json)",
      "  SMTP_PASS=$(jq -r .notifications.email.smtp_password /tmp/agent-config.json)",
      "  SMTP_FROM=$(jq -r .notifications.email.from /tmp/agent-config.json)",
      "  SMTP_TO=$(jq -r .notifications.email.to /tmp/agent-config.json)",
      "  cat <<EOF >/opt/agent/notifications/smtp_credentials.txt",
      "smtp_server=$SMTP_SERVER",
      "smtp_port=$SMTP_PORT",
      "smtp_username=$SMTP_USER",
      "smtp_password=$SMTP_PASS",
      "from=$SMTP_FROM",
      "to=$SMTP_TO",
      "EOF",
      "fi",

      "echo '=== Linux Provision Script Completed ==='"
    ]
  }
}
