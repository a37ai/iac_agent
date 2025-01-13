packer {
  required_plugins {
    amazon = {
      version = ">= 1.3.4"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

source "amazon-ebs" "windows" {
  region         = var.aws_region
  source_ami     = var.source_ami
  instance_type  = var.instance_type
  ami_name       = "${var.ami_name_prefix}-${formatdate("YYYYMMDD-hhmmss", timestamp())}"

  communicator   = "winrm"
  winrm_use_ssl  = true
  winrm_insecure = true
  winrm_username = var.winrm_username

  tags = {
    Name        = "${var.ami_name_prefix}-base"
    Environment = var.environment_tag
  }
}

build {
  sources = ["source.amazon-ebs.windows"]

  provisioner "file" {
    source      = "./agent-config.json"
    destination = "${var.temp_path}/agent-config.json"
  }

  provisioner "powershell" {
    inline = [
      "Write-Host '=== Beginning Provision Script ==='",

      # Ensure we have a folder to store temp downloads
      "if (!(Test-Path '${var.temp_path}')) { New-Item -ItemType Directory -Path '${var.temp_path}' | Out-Null }",

      # Read JSON
      "$configPath = '${var.temp_path}/agent-config.json'",
      "if (!(Test-Path $configPath)) { Write-Host 'ERROR: agent-config.json not found.'; exit 1 }",
      "$json = Get-Content $configPath -Raw | ConvertFrom-Json",
      "New-Item -ItemType Directory -Path 'C:/Agent' -Force | Out-Null",

      # -----------------------------------------------------------------
      # 0. Common Utilities
      # -----------------------------------------------------------------
      "Write-Host 'Installing general dependencies if needed...'",

      # -----------------------------------------------------------------
      # 1. AWS (If enabled)
      # -----------------------------------------------------------------
      "if ($json.aws.enabled -eq $true) {",
      "  Write-Host '--- Installing AWS CLI version ${var.aws_cli_version} ---'",
      "  $awsVersion = \"${var.aws_cli_version}\"",
      "  # Download and install AWS CLI v2",
      "  Invoke-WebRequest -Uri 'https://awscli.amazonaws.com/AWSCLIV2.msi' -OutFile 'C:/Temp/AWSCLIV2.msi'",
      "  Start-Process msiexec.exe -ArgumentList '/i C:/Temp/AWSCLIV2.msi /quiet /norestart' -Wait",
      "  Remove-Item 'C:/Temp/AWSCLIV2.msi'",
      "",
      "  Write-Host 'Writing AWS credentials to C:/Agent/aws...'",
      "  $awsDir = 'C:/Agent/aws'",
      "  if (!(Test-Path $awsDir)) { New-Item -ItemType Directory -Path $awsDir | Out-Null }",
      "  $awsCredFile = Join-Path $awsDir 'credentials'",
      "  $awsConfigFile = Join-Path $awsDir 'config'",
      "  $awsCreds = \"[default]`r`naws_access_key_id = $($json.aws.access_key_id)`r`naws_secret_access_key = $($json.aws.secret_access_key)\"",
      "  if ($json.aws.session_token -ne '') { $awsCreds += \"`r`naws_session_token = $($json.aws.session_token)\" }",
      "  Set-Content -Path $awsCredFile -Value $awsCreds",
      "  $awsConf = \"[default]`r`nregion = $($json.aws.region)\"",
      "  Set-Content -Path $awsConfigFile -Value $awsConf",
      "}",

      # -----------------------------------------------------------------
      # 2. GCP (If enabled)
      # -----------------------------------------------------------------
      "if ($json.gcp.enabled -eq $true) {",
      "  Write-Host '--- Installing gcloud CLI (latest) ---'",
      "  $gcloudExe = 'C:/Temp/GoogleCloudSDKInstaller.exe'",
      "  Invoke-WebRequest -Uri 'https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe' -OutFile $gcloudExe",
      "  Start-Process $gcloudExe -ArgumentList '/silent' -Wait",
      "  Remove-Item $gcloudExe",
      "",
      "  Write-Host 'Writing GCP service_account.json to C:/Agent/gcp...'",
      "  $gcpDir = 'C:/Agent/gcp'",
      "  if (!(Test-Path $gcpDir)) { New-Item -ItemType Directory -Path $gcpDir | Out-Null }",
      "  Set-Content -Path (Join-Path $gcpDir 'service_account.json') -Value $($json.gcp.service_account_json)",
      "}",

      # -----------------------------------------------------------------
      # 3. Azure (If enabled)
      # -----------------------------------------------------------------
      "if ($json.azure.enabled -eq $true) {",
      "  Write-Host '--- Installing Azure CLI (latest) ---'",
      "  Invoke-WebRequest -Uri 'https://aka.ms/installazurecliwindows' -OutFile 'C:/Temp/azurecli.msi'",
      "  Start-Process msiexec.exe -ArgumentList '/i C:/Temp/azurecli.msi /quiet /norestart' -Wait",
      "  Remove-Item 'C:/Temp/azurecli.msi'",
      "",
      "  Write-Host 'Writing Azure SP credentials to C:/Agent/azure...'",
      "  $azDir = 'C:/Agent/azure'",
      "  if (!(Test-Path $azDir)) { New-Item -ItemType Directory -Path $azDir | Out-Null }",
      "  $azCreds = \"tenant_id = $($json.azure.tenant_id)`r`nclient_id = $($json.azure.client_id)`r`nclient_secret = $($json.azure.client_secret)`r`nsubscription_id = $($json.azure.subscription_id)\"",
      "  Set-Content (Join-Path $azDir 'sp_credentials.txt') $azCreds",
      "}",

      # -----------------------------------------------------------------
      # 4. GitHub / GitLab
      # -----------------------------------------------------------------
      "if ($json.gitHub.enabled -eq $true -or $json.gitLab.enabled -eq $true) {",
      "  Write-Host '--- Installing Git for Windows ---'",
      "  $gitUrl = 'https://github.com/git-for-windows/git/releases/download/v2.42.0.windows.1/Git-2.42.0-64-bit.exe'",
      "  Invoke-WebRequest -Uri $gitUrl -OutFile 'C:/Temp/GitSetup.exe'",
      "  Start-Process 'C:/Temp/GitSetup.exe' -ArgumentList '/VERYSILENT' -Wait",
      "  Remove-Item 'C:/Temp/GitSetup.exe'",
      "}",
      # GitHub
      "if ($json.gitHub.enabled -eq $true) {",
      "  Write-Host 'Storing GitHub creds...'",
      "  $ghDir = 'C:/Agent/github'",
      "  if (!(Test-Path $ghDir)) { New-Item -ItemType Directory -Path $ghDir | Out-Null }",
      "  if ($json.gitHub.use_ssh -eq $true) {",
      "    Write-Host 'Would store SSH private key here... (not in JSON example)'",
      "  } else {",
      "    Set-Content -Path (Join-Path $ghDir 'github_pat.txt') -Value $($json.gitHub.token)",
      "  }",
      "}",
      # GitLab
      "if ($json.gitLab.enabled -eq $true) {",
      "  Write-Host 'Storing GitLab creds...'",
      "  $glDir = 'C:/Agent/gitlab'",
      "  if (!(Test-Path $glDir)) { New-Item -ItemType Directory -Path $glDir | Out-Null }",
      "  if ($json.gitLab.use_ssh -eq $true) {",
      "    Write-Host 'Would store SSH private key for GitLab here...'",
      "  } else {",
      "    Set-Content -Path (Join-Path $glDir 'gitlab_pat.txt') -Value $($json.gitLab.token)",
      "  }",
      "}",

      # -----------------------------------------------------------------
      # 5. Docker (If enabled)
      # -----------------------------------------------------------------
      "if ($json.docker.enabled -eq $true) {",
      "  Write-Host '--- Installing Docker (DockerMsftProvider) on Windows ---'",
      "  Install-Module -Name DockerMsftProvider -Force",
      "  Install-Package -Name docker -ProviderName DockerMsftProvider -Force",
      "  Start-Service Docker",
      "",
      "  Write-Host 'Storing Docker credentials if provided...'",
      "  $dockerDir = 'C:/Agent/docker'",
      "  if (!(Test-Path $dockerDir)) { New-Item -ItemType Directory -Path $dockerDir | Out-Null }",
      "  $dockerCreds = \"username=$($json.docker.username)`r`npassword=$($json.docker.password)\"",
      "  Set-Content -Path (Join-Path $dockerDir 'docker_credentials.txt') -Value $dockerCreds",
      "}",

      # -----------------------------------------------------------------
      # 6. Kubernetes (If enabled)
      # -----------------------------------------------------------------
      "if ($json.kubernetes.enabled -eq $true) {",
      "  Write-Host '--- Installing kubectl (latest stable) ---'",
      "  $kubectlVersion = (Invoke-RestMethod 'https://dl.k8s.io/release/stable.txt')",
      "  $kubectlUrl = \"https://dl.k8s.io/release/$kubectlVersion/bin/windows/amd64/kubectl.exe\"",
      "  Invoke-WebRequest -UseBasicParsing $kubectlUrl -OutFile 'C:/Windows/System32/kubectl.exe'",
      "",
      "  Write-Host 'Storing kubeconfig...'",
      "  $k8sDir = 'C:/Agent/kubernetes'",
      "  if (!(Test-Path $k8sDir)) { New-Item -ItemType Directory -Path $k8sDir | Out-Null }",
      "  if ($json.kubernetes.kubeconfig -ne '') {",
      "    Set-Content -Path (Join-Path $k8sDir 'config') -Value $($json.kubernetes.kubeconfig)",
      "  }",
      "}",

      # -----------------------------------------------------------------
      # 7. Terraform (If enabled)
      # -----------------------------------------------------------------
      "if ($json.terraform.enabled -eq $true) {",
      "  Write-Host \"--- Installing Terraform version ${var.terraform_version} ---\"",
      "  $TerraformVersion = \"${var.terraform_version}\"",
      "  $TerraformUrl = \"https://releases.hashicorp.com/terraform/\" + $TerraformVersion + \"/terraform_\" + $TerraformVersion + \"_windows_amd64.zip\"",
      "",
      "  Write-Host \"Downloading Terraform from $TerraformUrl\"",
      "  Invoke-WebRequest -Uri $TerraformUrl -OutFile '${var.temp_path}/terraform.zip'",
      "  Expand-Archive -Path '${var.temp_path}/terraform.zip' -DestinationPath '${var.temp_path}/tf'",
      "  Move-Item '${var.temp_path}/tf/terraform.exe' 'C:/Windows/System32/terraform.exe'",
      "  Remove-Item '${var.temp_path}/terraform.zip'",
      "  Remove-Item '${var.temp_path}/tf' -Recurse",
      "}",

      # -----------------------------------------------------------------
      # 8. Helm (If enabled)
      # -----------------------------------------------------------------
      "if ($json.helm.enabled -eq $true) {",
      "  Write-Host \"--- Installing Helm version ${var.helm_version} ---\"",
      "  $HelmVersion = \"${var.helm_version}\"",
      "  $HelmUrl = \"https://get.helm.sh/helm-\" + $HelmVersion + \"-windows-amd64.zip\"",
      "",
      "  Write-Host \"Downloading Helm from $HelmUrl\"",
      "  Invoke-WebRequest -Uri $HelmUrl -OutFile 'C:/Temp/helm.zip'",
      "  Expand-Archive -Path 'C:/Temp/helm.zip' -DestinationPath 'C:/Temp/helm'",
      "  Move-Item 'C:/Temp/helm/windows-amd64/helm.exe' 'C:/Windows/System32/helm.exe'",
      "  Remove-Item 'C:/Temp/helm.zip'",
      "  Remove-Item 'C:/Temp/helm' -Recurse",
      "}",

      # -----------------------------------------------------------------
      # 9. Puppet (If enabled)
      # -----------------------------------------------------------------
      "if ($json.puppet.enabled -eq $true) {",
      "  Write-Host \"--- Installing Puppet Agent version ${var.puppet_agent_version} ---\"",
      "  $PuppetVersion = \"${var.puppet_agent_version}\"",
      "  if ($PuppetVersion -eq 'latest') {",
      "    $PuppetUrl = 'https://downloads.puppet.com/windows/puppet7/puppet-agent-x64-latest.msi'",
      "  } else {",
      "    $PuppetUrl = \"https://example.com/puppet-agent-\" + $PuppetVersion + \".msi\"",
      "  }",
      "",
      "  Write-Host \"Downloading Puppet from $PuppetUrl\"",
      "  Invoke-WebRequest -Uri $PuppetUrl -OutFile 'C:/Temp/puppet.msi'",
      "  Start-Process msiexec.exe -ArgumentList '/i C:/Temp/puppet.msi /quiet' -Wait",
      "  Remove-Item 'C:/Temp/puppet.msi'",
      "}",

      # -----------------------------------------------------------------
      # 9b. Ansible (If enabled)
      # -----------------------------------------------------------------
      "if ($json.ansible.enabled -eq $true) {",
      "  Write-Host '--- Installing Ansible (requires Python) ---'",
      "  if (!(Get-Command python.exe -ErrorAction SilentlyContinue)) {",
      "    $pyVer = \"${var.python_version}\"",
      "    $pyUrl = \"https://www.python.org/ftp/python/$pyVer/python-$pyVer-amd64.exe\"",
      "    Invoke-WebRequest -Uri $pyUrl -OutFile 'C:/Temp/python.exe'",
      "    Start-Process 'C:/Temp/python.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Wait",
      "    Remove-Item 'C:/Temp/python.exe'",
      "  }",
      "  pip install ansible",
      "",
      "  Write-Host 'Storing Ansible inventory / SSH key if provided...'",
      "  $ansDir = 'C:/Agent/ansible'",
      "  if (!(Test-Path $ansDir)) { New-Item -ItemType Directory -Path $ansDir | Out-Null }",
      "  if ($json.ansible.inventory_file -ne '') { Set-Content -Path (Join-Path $ansDir 'inventory.ini') -Value $($json.ansible.inventory_file) }",
      "  if ($json.ansible.ssh_private_key -ne '') { Set-Content -Path (Join-Path $ansDir 'id_rsa') -Value $($json.ansible.ssh_private_key) }",
      "}",

      # -----------------------------------------------------------------
      # 9c. Chef (If enabled)
      # -----------------------------------------------------------------
      "if ($json.chef.enabled -eq $true) {",
      "  Write-Host \"--- Installing Chef Workstation version ${var.chef_workstation_version} ---\"",
      "  $ChefVersion = \"${var.chef_workstation_version}\"",
      "  $ChefUrl = \"https://packages.chef.io/files/stable/chef-workstation/\" + $ChefVersion + \"/windows/2019/chef-workstation_\" + $ChefVersion + \"-1-x64.msi\"",
      "",
      "  Write-Host \"Downloading Chef from $ChefUrl\"",
      "  Invoke-WebRequest -Uri $ChefUrl -OutFile 'C:/Temp/chef-workstation.msi'",
      "  Start-Process msiexec.exe -ArgumentList '/i C:/Temp/chef-workstation.msi /quiet' -Wait",
      "  Remove-Item 'C:/Temp/chef-workstation.msi'",
      "",
      "  Write-Host 'Storing Chef keys if provided...'",
      "  $chefDir = 'C:/Agent/chef'",
      "  if (!(Test-Path $chefDir)) { New-Item -ItemType Directory -Path $chefDir | Out-Null }",
      "  if ($json.chef.client_key -ne '')       { Set-Content -Path (Join-Path $chefDir 'client.pem')     -Value $($json.chef.client_key) }",
      "  if ($json.chef.validation_key -ne '')   { Set-Content -Path (Join-Path $chefDir 'validation.pem') -Value $($json.chef.validation_key) }",
      "}",

      # -----------------------------------------------------------------
      # 10. Jenkins (If enabled)
      # -----------------------------------------------------------------
      "if ($json.jenkins.enabled -eq $true) {",
      "  Write-Host \"--- Installing Jenkins CLI version ${var.jenkins_version} ---\"",
      "  $JenkinsVersion = \"${var.jenkins_version}\"",
      "  $JenkinsWarUrl = \"https://get.jenkins.io/war-stable/\" + $JenkinsVersion + \"/jenkins.war\"",
      "",
      "  Write-Host \"Downloading Jenkins CLI from $JenkinsWarUrl\"",
      "  Invoke-WebRequest -Uri $JenkinsWarUrl -OutFile 'C:/Temp/jenkins.war'",
      "  New-Item -ItemType Directory -Path 'C:/Temp/jenkins-cli' | Out-Null",
      "  Add-Type -AssemblyName System.IO.Compression.FileSystem",
      "  [System.IO.Compression.ZipFile]::ExtractToDirectory('C:/Temp/jenkins.war','C:/Temp/jenkins-cli')",
      "  Move-Item 'C:/Temp/jenkins-cli/WEB-INF/jenkins-cli.jar' 'C:/Windows/System32/jenkins-cli.jar'",
      "  Remove-Item 'C:/Temp/jenkins.war'",
      "  Remove-Item 'C:/Temp/jenkins-cli' -Recurse",
      "",
      "  Write-Host 'Storing Jenkins credentials if provided...'",
      "  $jenkinsDir = 'C:/Agent/jenkins'",
      "  if (!(Test-Path $jenkinsDir)) { New-Item -ItemType Directory -Path $jenkinsDir | Out-Null }",
      "  $jenkinsCreds = \"url = $($json.jenkins.url)`r`nuser = $($json.jenkins.user)`r`napi_token = $($json.jenkins.api_token)\"",
      "  Set-Content -Path (Join-Path $jenkinsDir 'jenkins_credentials.txt') -Value $jenkinsCreds",
      "}",

      # -----------------------------------------------------------------
      # 11. Datadog (If enabled)
      # -----------------------------------------------------------------
      "if ($json.datadog.enabled -eq $true) {",
      "  Write-Host '--- Installing Datadog (Python-based CLI) ---'",
      "  if (!(Get-Command python.exe -ErrorAction SilentlyContinue)) {",
      "    $pyVer = \"${var.python_version}\"",
      "    $pyUrl = \"https://www.python.org/ftp/python/$pyVer/python-$pyVer-amd64.exe\"",
      "    Invoke-WebRequest -Uri $pyUrl -OutFile 'C:/Temp/python.exe'",
      "    Start-Process 'C:/Temp/python.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Wait",
      "    Remove-Item 'C:/Temp/python.exe'",
      "  }",
      "  pip install datadog",
      "",
      "  Write-Host 'Storing Datadog API/App keys...'",
      "  $ddDir = 'C:/Agent/datadog'",
      "  if (!(Test-Path $ddDir)) { New-Item -ItemType Directory -Path $ddDir | Out-Null }",
      "  $ddKeys = \"api_key = $($json.datadog.api_key)`r`napp_key = $($json.datadog.app_key)\"",
      "  Set-Content -Path (Join-Path $ddDir 'datadog_keys.txt') -Value $ddKeys",
      "}",

      # -----------------------------------------------------------------
      # 12. Splunk (If enabled)
      # -----------------------------------------------------------------
      "if ($json.splunk.enabled -eq $true) {",
      "  Write-Host '--- Splunk: storing credentials or optionally installing forwarder ---'",
      "  $splunkDir = 'C:/Agent/splunk'",
      "  if (!(Test-Path $splunkDir)) { New-Item -ItemType Directory -Path $splunkDir | Out-Null }",
      "  $splunkText = \"host=$($json.splunk.host)`r`nport=$($json.splunk.port)`r`nusername=$($json.splunk.username)`r`npassword=$($json.splunk.password)\"",
      "  Set-Content -Path (Join-Path $splunkDir 'splunk_credentials.txt') -Value $splunkText",
      "}",

      # -----------------------------------------------------------------
      # 13. Elasticsearch / Kibana (If enabled)
      # -----------------------------------------------------------------
      "if ($json.elasticsearchKibana.enabled -eq $true) {",
      "  Write-Host '--- Storing Elasticsearch/Kibana credentials ---'",
      "  $esDir = 'C:/Agent/elasticsearch'",
      "  if (!(Test-Path $esDir)) { New-Item -ItemType Directory -Path $esDir | Out-Null }",
      "  $esContent = \"elasticsearch_url=$($json.elasticsearchKibana.elasticsearch_url)`r`nuser=$($json.elasticsearchKibana.elasticsearch_user)`r`npassword=$($json.elasticsearchKibana.elasticsearch_password)\"",
      "  Set-Content -Path (Join-Path $esDir 'elasticsearch.txt') -Value $esContent",
      "  if ($json.elasticsearchKibana.kibana_url -ne '') {",
      "    $kbContent = \"kibana_url=$($json.elasticsearchKibana.kibana_url)`r`nuser=$($json.elasticsearchKibana.kibana_user)`r`npassword=$($json.elasticsearchKibana.kibana_password)\"",
      "    Set-Content -Path (Join-Path $esDir 'kibana.txt') -Value $kbContent",
      "  }",
      "}",

      # -----------------------------------------------------------------
      # 14. Grafana (If enabled)
      # -----------------------------------------------------------------
      "if ($json.grafana.enabled -eq $true) {",
      "  Write-Host '--- Installing Grafana & storing credentials ---'",
      "  $grafanaUrl = 'https://dl.grafana.com/enterprise/release/grafana-enterprise-9.5.2.windows-amd64.msi'",
      "  Invoke-WebRequest -Uri $grafanaUrl -OutFile '${var.temp_path}/grafana.msi'",
      "  Start-Process msiexec.exe -ArgumentList '/i ${var.temp_path}/grafana.msi /quiet' -Wait",
      "  Remove-Item '${var.temp_path}/grafana.msi'",
      "",
      "  $gfDir = 'C:/Agent/grafana'",
      "  if (!(Test-Path $gfDir)) { New-Item -ItemType Directory -Path $gfDir | Out-Null }",
      "  $gfCreds = \"url=$($json.grafana.url)`r`napi_key=$($json.grafana.api_key)\"",
      "  Set-Content -Path (Join-Path $gfDir 'grafana_credentials.txt') -Value $gfCreds",
      "}",

      # -----------------------------------------------------------------
      # 15. Prometheus (If enabled)
      # -----------------------------------------------------------------
      "if ($json.prometheus.enabled -eq $true) {",
      "  Write-Host \"--- Installing promtool & storing credentials ---\"",
      "  $PromVersion = \"${var.prometheus_version}\"",
      "  $PromUrl = \"https://github.com/prometheus/prometheus/releases/download/v\" + $PromVersion + \"/prometheus-\" + $PromVersion + \".windows-amd64.zip\"",
      "",
      "  Write-Host \"Downloading promtool from $PromUrl\"",
      "  Invoke-WebRequest -Uri $PromUrl -OutFile '${var.temp_path}/prometheus.zip'",
      "  Expand-Archive -Path '${var.temp_path}/prometheus.zip' -DestinationPath '${var.temp_path}/prometheus'",
      "  Move-Item '${var.temp_path}/prometheus/prometheus-*.windows-amd64/promtool.exe' 'C:/Windows/System32/promtool.exe'",
      "  Remove-Item '${var.temp_path}/prometheus' -Recurse",
      "  Remove-Item '${var.temp_path}/prometheus.zip'",
      "",
      "  $promDir = 'C:/Agent/prometheus'",
      "  if (!(Test-Path $promDir)) { New-Item -ItemType Directory -Path $promDir | Out-Null }",
      "  $promContent = \"endpoint=$($json.prometheus.endpoint)`r`nusername=$($json.prometheus.username)`r`npassword=$($json.prometheus.password)`r`ntoken=$($json.prometheus.token)\"",
      "  Set-Content -Path (Join-Path $promDir 'prometheus_credentials.txt') -Value $promContent",
      "}",

      # -----------------------------------------------------------------
      # 16. Vault (If enabled)
      # -----------------------------------------------------------------
      "if ($json.vault.enabled -eq $true) {",
      "  Write-Host \"--- Installing Vault version ${var.vault_version} & storing token ---\"",
      "  $VaultVersion = \"${var.vault_version}\"",
      "  $VaultUrl = \"https://releases.hashicorp.com/vault/\" + $VaultVersion + \"/vault_\" + $VaultVersion + \"_windows_amd64.zip\"",
      "",
      "  Write-Host \"Downloading Vault from $VaultUrl\"",
      "  Invoke-WebRequest -Uri $VaultUrl -OutFile '${var.temp_path}/vault.zip'",
      "  Expand-Archive -Path '${var.temp_path}/vault.zip' -DestinationPath '${var.temp_path}/vault'",
      "  Move-Item '${var.temp_path}/vault/vault.exe' 'C:/Windows/System32/vault.exe'",
      "  Remove-Item '${var.temp_path}/vault.zip'",
      "  Remove-Item '${var.temp_path}/vault' -Recurse",
      "",
      "  $vaultDir = 'C:/Agent/vault'",
      "  if (!(Test-Path $vaultDir)) { New-Item -ItemType Directory -Path $vaultDir | Out-Null }",
      "  $vaultContent = \"VAULT_ADDR=$($json.vault.address)`r`nVAULT_TOKEN=$($json.vault.token)\"",
      "  Set-Content -Path (Join-Path $vaultDir 'vault_credentials.txt') -Value $vaultContent",
      "}",

      # -----------------------------------------------------------------
      # 17. Artifactory / Nexus (If enabled)
      # -----------------------------------------------------------------
      "if ($json.artifactory.enabled -eq $true) {",
      "  Write-Host '--- Storing Artifactory credentials ---'",
      "  $artiDir = 'C:/Agent/artifactory'",
      "  if (!(Test-Path $artiDir)) { New-Item -ItemType Directory -Path $artiDir | Out-Null }",
      "  $artiContent = \"url=$($json.artifactory.url)`r`nusername=$($json.artifactory.username)`r`npassword=$($json.artifactory.password)`r`napi_token=$($json.artifactory.api_token)\"",
      "  Set-Content -Path (Join-Path $artiDir 'artifactory_creds.txt') -Value $artiContent",
      "}",
      "if ($json.nexus.enabled -eq $true) {",
      "  Write-Host '--- Storing Nexus credentials ---'",
      "  $nexusDir = 'C:/Agent/nexus'",
      "  if (!(Test-Path $nexusDir)) { New-Item -ItemType Directory -Path $nexusDir | Out-Null }",
      "  $nxContent = \"url=$($json.nexus.url)`r`nusername=$($json.nexus.username)`r`npassword=$($json.nexus.password)`r`napi_token=$($json.nexus.api_token)\"",
      "  Set-Content -Path (Join-Path $nexusDir 'nexus_creds.txt') -Value $nxContent",
      "}",

      # -----------------------------------------------------------------
      # 18. Notifications (Slack, Teams, Email)
      # -----------------------------------------------------------------
      "if ($json.notifications.slack.enabled -eq $true) {",
      "  Write-Host '--- Storing Slack Webhook ---'",
      "  $notifDir = 'C:/Agent/notifications'",
      "  if (!(Test-Path $notifDir)) { New-Item -ItemType Directory -Path $notifDir | Out-Null }",
      "  Set-Content -Path (Join-Path $notifDir 'slack_webhook.txt') -Value $($json.notifications.slack.webhook_url)",
      "}",
      "if ($json.notifications.teams.enabled -eq $true) {",
      "  Write-Host '--- Storing Teams Webhook ---'",
      "  $notifDir = 'C:/Agent/notifications'",
      "  if (!(Test-Path $notifDir)) { New-Item -ItemType Directory -Path $notifDir | Out-Null }",
      "  Set-Content -Path (Join-Path $notifDir 'teams_webhook.txt') -Value $($json.notifications.teams.webhook_url)",
      "}",
      "if ($json.notifications.email.enabled -eq $true) {",
      "  Write-Host '--- Storing Email SMTP credentials ---'",
      "  $notifDir = 'C:/Agent/notifications'",
      "  if (!(Test-Path $notifDir)) { New-Item -ItemType Directory -Path $notifDir | Out-Null }",
      "  $emailContent = \"smtp_server=$($json.notifications.email.smtp_server)`r`nsmtp_port=$($json.notifications.email.smtp_port)`r`nsmtp_username=$($json.notifications.email.smtp_username)`r`nsmtp_password=$($json.notifications.email.smtp_password)`r`nfrom=$($json.notifications.email.from)`r`nto=$($json.notifications.email.to)\"",
      "  Set-Content -Path (Join-Path $notifDir 'smtp_credentials.txt') -Value $emailContent",
      "}",

      "Write-Host '=== Provision Script Completed ==='"
    ]
  }
}
